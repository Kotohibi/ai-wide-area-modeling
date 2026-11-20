r"""Export one variant of the school for the Three.js viewer (web\public). Background Blender, nothing is saved:
    blender -b ruin_school.blend          -P web\export_web.py -- ruin
    blender -b ruin_school_restored.blend -P web\export_web.py -- restored
    ... -- ruin veg / -- restored veg     only the trees again (about 2 min; the restored school is not rebuilt)
Out (web\public):
    <variant>.glb       S_build (buildings, fittings, damage: one mesh, one primitive per material), S_grass (blade height in the
                        vertex colour, red), S_terrain (vertex colour: red = green cover, green = dry litter).  No UVs, no textures.
    <variant>_veg.glb   tree prototypes: trunks TW_<proto>, leaf cards LC0_<proto> (near) / LC1_<proto> (far), 1 m tall
    <variant>.json      instance matrices per prototype (three.js axes), cherry trees (petal sources), counts for checking
    scene.json          sun, camera path, footprints / floors of the buildings, holes of the ruin (same from both variants)
The restored school is rebuilt in memory with every sliding door open (as for Unreal): the viewer can go inside.
Materials are NOT baked: the viewer draws them with the formulas of bl_mats.py (proc.js, materials.json from make_materials.py).
Leaf cards: the Geometry Nodes leaves of a prototype (up to 1.6 M faces) are binned in a voxel grid sized for a target count,
one card per voxel at the area-weighted centre, sized to the leaf area; colour = the two colours of the leaf material."""
import bpy, bmesh, json, os, sys, math, time, numpy as np
from mathutils import Matrix, Vector
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); WEB = os.path.join(ROOT, "web", "public")      # <model>\web\export_web.py -> <model>; os.makedirs(WEB, exist_ok=True)
VAR = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "ruin"
VEG_ONLY = "veg" in sys.argv          # "-- ruin veg": only the trees (<variant>_veg.glb, <variant>.json); the buildings are left as they are
T0 = time.time()
def log(*a): print("[web %s %5.0fs]" % (VAR, time.time() - T0), *a, flush=True)
if VAR == "restored" and not VEG_ONLY:
    OPEN_ALL_DOORS = True
    _p = ROOT + r"\blender\boot.py"; exec(compile(open(_p, encoding="utf-8").read(), _p, "exec"), globals()); build_all("restored"); log("rebuilt with open doors")
sc = bpy.context.scene; vl = bpy.context.view_layer; sc.frame_set(1)

C = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1))); Ci = C.inverted()      # Blender Z-up -> three.js Y-up: (x, y, z) -> (x, z, -y)
def yup(v): return [round(v[0], 4), round(v[2], 4), round(-v[1], 4)]
def mat12(M):
    R = C @ M @ Ci; return [round(R[i][j], 5) for j in range(4) for i in range(3)]             # column-major 3x4
def coll(name):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in sc.collection.children: sc.collection.children.link(c)
    return c
OUT_S = coll("WEB_STATIC"); OUT_V = coll("WEB_VEG")

# ---------- static: every mesh of the collections as one mesh in world coordinates, materials kept
def gather(name, colls, skip=()):
    dg = bpy.context.evaluated_depsgraph_get(); bm = bmesh.new(); mats = []; nobj = 0
    for cn in colls:
        for o in (list(bpy.data.collections[cn].objects) if cn in bpy.data.collections else []):
            if o.type != "MESH": continue
            me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
            if len(me.polygons) == 0: bpy.data.meshes.remove(me); continue
            me.transform(o.matrix_world)
            names = [m.name if m else "none" for m in me.materials] or ["none"]
            for n_ in names:
                if n_ not in mats: mats.append(n_)
            mi = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get("material_index", mi)
            lut = np.array([mats.index(n_) for n_ in names], np.int32); me.polygons.foreach_set("material_index", lut[np.clip(mi, 0, len(names) - 1)])
            for uv in list(me.uv_layers): me.uv_layers.remove(uv)
            bm.from_mesh(me); bpy.data.meshes.remove(me); nobj += 1
    if skip:
        dead = [f for f in bm.faces if mats[f.material_index] in skip]
        if dead: bmesh.ops.delete(bm, geom=dead, context="FACES")
    out = bpy.data.meshes.new(name); bm.to_mesh(out); bm.free()
    for n_ in mats: out.materials.append(bpy.data.materials.get(n_) or bpy.data.materials.new(n_))
    ob = bpy.data.objects.new(name, out); OUT_S.objects.link(ob)
    cnt = {}; mi = np.empty(len(out.polygons), np.int32); out.polygons.foreach_get("material_index", mi)
    for k, n_ in enumerate(mats):
        c = int((mi == k).sum())
        if c: cnt[n_] = c
    log(name, nobj, "objects", len(out.polygons), "faces", len(cnt), "materials"); return ob, cnt

cnt_build = cnt_terr = cnt_grass = None
if not VEG_ONLY:
    build, cnt_build = gather("S_build", ["School_West", "School_East", "Shed", "Ruin_damage", "Restored_fittings", "Restored_yard"], skip=("petal_pink",))
    terrain, cnt_terr = gather("S_terrain", ["Terrain"])
    ca = terrain.data.color_attributes.get("cover")
    if ca is not None: terrain.data.color_attributes.active_color = ca; terrain.data.color_attributes.render_color_index = terrain.data.color_attributes.active_color_index
    grass, cnt_grass = gather("S_grass", ["Grass"])
    # grass blades are a quad (root .. 60 % of the length) and a triangle (.. tip): blade height 0 / 0.6 / 1 into the vertex colour
    gm = grass.data
    if len(gm.polygons):
        nl = len(gm.loops); co = np.empty(len(gm.vertices) * 3, np.float32); gm.vertices.foreach_get("co", co); z = co.reshape(-1, 3)[:, 2]
        lv = np.empty(nl, np.int32); gm.loops.foreach_get("vertex_index", lv); ls = np.empty(len(gm.polygons), np.int32); lt = np.empty(len(gm.polygons), np.int32)
        gm.polygons.foreach_get("loop_start", ls); gm.polygons.foreach_get("loop_total", lt); col = np.zeros((nl, 4), np.float32); col[:, 3] = 1
        zl = z[lv]; pid = np.repeat(np.arange(len(ls)), lt); zmin = np.full(len(ls), 1e9); zmax = np.full(len(ls), -1e9)
        np.minimum.at(zmin, pid, zl); np.maximum.at(zmax, pid, zl); hi = zl > (zmin[pid] + zmax[pid]) / 2; quad = lt[pid] == 4
        col[:, 0] = np.where(quad, np.where(hi, 0.6, 0.0), np.where(hi, 1.0, 0.6))
        a = gm.color_attributes.new("cover", "FLOAT_COLOR", "CORNER"); a.data.foreach_set("color", col.ravel())
        gm.color_attributes.active_color = a; gm.color_attributes.render_color_index = gm.color_attributes.active_color_index

# ---------- vegetation prototypes: trunk + leaf cards
LEAFMAT = {"evergreen": "ovate", "mid": "ovate", "bush": "ovate", "fresh": "ovate", "cherry": "blossom", "cedar": "spray"}
LEAFCOL = json.load(open(os.path.join(WEB, "materials.json")))["leaf"] if os.path.exists(os.path.join(WEB, "materials.json")) else {}
def vkey(cen, cs, off):
    q = np.floor(cen / cs + off).astype(np.int64) + (1 << 19); return (q[:, 0] << 40) | (q[:, 1] << 20) | q[:, 2]
def cards(cen, nrm, ar, target, rng):
    """One card per occupied voxel.  The card stands on ONE FACE OF THE VOXEL PICKED AT RANDOM (weighted by area), not on the voxel's
    centre of area: in a dense crown the centres of area sit on the voxel lattice, and from the side the crown showed as horizontal
    stripes (rows of cards 0.4 - 0.9 m apart, worst in the far LOD)."""
    off = rng.random(3); lo, hi = 0.0005, 2.0
    for _ in range(20):
        cs = math.sqrt(lo * hi); n = len(np.unique(vkey(cen, cs, off)))
        if n > target: lo = cs
        else: hi = cs
    cs = hi; key, inv = np.unique(vkey(cen, cs, off), return_inverse=True); inv = inv.ravel(); k = len(key)
    A = np.bincount(inv, ar, k)
    N = np.stack([np.bincount(inv, ar * nrm[:, i], k) for i in range(3)], 1); nl = np.linalg.norm(N, axis=1)
    w = rng.random(len(ar)) ** (1.0 / np.maximum(ar / ar.mean(), 1e-6))        # weighted pick: the largest u^(1/w) of each voxel wins
    order = np.lexsort((w, inv)); last = np.r_[inv[order][1:] != inv[order][:-1], True]; P = cen[order[last]]
    return P, N, nl, A, cs
def card_mesh(name, P, N, nl, A, cs, kind, rng):
    k = len(P); rnd = rng.normal(size=(k, 3)); rnd /= np.linalg.norm(rnd, axis=1, keepdims=True)
    N = np.where(nl[:, None] > 0.25 * A[:, None], N / np.maximum(nl[:, None], 1e-9), rnd)
    S = np.clip(np.sqrt(A / 0.30), 0.8 * cs, 2.4 * cs) * rng.uniform(0.85, 1.2, k)                         # a sprig texture covers about a third of its card
    centre = P.mean(0); centre[2] -= 0.15 * (P[:, 2].max() - P[:, 2].min())
    c1, c2 = [np.array(c) for c in LEAFCOL.get(kind, [(0.1, 0.16, 0.05), (0.2, 0.3, 0.1)])]
    verts, faces, cols, nors, uvs = [], [], [], [], []
    for i in range(k):
        n = Vector(N[i])
        if kind == "cedar": n = (n + Vector((0, 0, 0.8))).normalized()          # sprays hang: cards tilt towards the vertical
        t = n.orthogonal().normalized(); b = n.cross(t).normalized(); ang = rng.random() * math.tau
        t, b = t * math.cos(ang) + b * math.sin(ang), -t * math.sin(ang) + b * math.cos(ang)
        h = S[i] / 2; c = Vector(P[i]); b0 = len(verts)
        verts += [c - t * h - b * h, c + t * h - b * h, c + t * h + b * h, c - t * h + b * h]; faces.append((b0, b0 + 1, b0 + 2, b0 + 3))
        rad = c - Vector(centre); rad = rad.normalized() if rad.length > 1e-6 else Vector((0, 0, 1))
        nors += [(n * 0.35 + rad * 0.65).normalized()] * 4                       # shaded like a crown, not like single cards
        col = list(c1 + (c2 - c1) * rng.random()) + [1.0]; cols += [col] * 4
        tx, ty = int(rng.random() * 2) * 0.5, int(rng.random() * 2) * 0.5; q = [(tx, ty), (tx + 0.5, ty), (tx + 0.5, ty + 0.5), (tx, ty + 0.5)]
        uvs += [q[1], q[0], q[3], q[2]] if rng.random() < 0.5 else q             # one tile of a 2 x 2 atlas, randomly mirrored
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(v) for v in verts], [], faces)
    uv = me.uv_layers.new(name="UVMap"); uv.data.foreach_set("uv", np.array(uvs, np.float32).ravel())
    a = me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER"); a.data.foreach_set("color", np.array(cols, np.float32).ravel()); me.color_attributes.active_color = a
    me.normals_split_custom_set([tuple(v) for v in nors])
    m = bpy.data.materials.get("LEAF_" + kind) or bpy.data.materials.new("LEAF_" + kind); me.materials.append(m)
    ob = bpy.data.objects.new(name, me); OUT_V.objects.link(ob); return ob

def find(lc, name):
    if lc.collection.name == name: return lc
    for ch in lc.children:
        f = find(ch, name)
        if f: return f
lc = find(vl.layer_collection, "TreeProtos")
if lc:                                           # prototypes are excluded from the view layer: include them so that every one evaluates
    lc.exclude = False
    for ch in lc.children: ch.exclude = False
vl.update(); dg = bpy.context.evaluated_depsgraph_get(); pinfo = {}
# trunks: grown again here with the current generator (blender\bl_trees.py grow_proto), so that a fix to the trunk mesh reaches the web without
# rebuilding the .blend files; the leaves come from the .blend (same skeleton, same random numbers)
TR = {}
for _f in ("bl_lib.py", "bl_trees.py"):
    _p = os.path.join(ROOT, "blender", _f); exec(compile(open(_p, encoding="utf-8").read(), _p, "exec"), TR)
for pc in bpy.data.collections["TreeProtos"].children:
    p = pc.name[3:]; kind = p.rsplit("_", 1)[0]
    tw = [o for o in pc.objects if o.name.startswith("TW_")][0]; tl = [o for o in pc.objects if o.name.startswith("TL_")][0]
    _T, _vs, _fs, _lv = TR["grow_proto"](kind, int(p.rsplit("_", 1)[1]))
    wm = bpy.data.meshes.new("TWm_" + p); wm.from_pydata([tuple(float(c) for c in v_) for v_ in _vs], [], [tuple(int(i) for i in f_) for f_ in _fs]); wm.update()
    for p_ in wm.polygons: p_.use_smooth = True
    for ms_ in tw.material_slots: wm.materials.append(ms_.material)
    w = bpy.data.objects.new("TW_" + p, wm); OUT_V.objects.link(w)
    lm = bpy.data.meshes.new_from_object(tl.evaluated_get(dg), depsgraph=dg); n = len(lm.polygons); out = {}
    if n:
        cen = np.empty(n * 3, np.float32); nrm = np.empty(n * 3, np.float32); ar = np.empty(n, np.float32)
        lm.polygons.foreach_get("center", cen); lm.polygons.foreach_get("normal", nrm); lm.polygons.foreach_get("area", ar)
        cen = cen.reshape(-1, 3).astype(np.float64); nrm = nrm.reshape(-1, 3).astype(np.float64); ar = ar.astype(np.float64)
        rng = np.random.default_rng(sum(map(ord, p)) * 7 + 3)
        for lod, tgt in (("LC0", 5200), ("LC1", 900)):
            P, N, nl, A, cs = cards(cen, nrm, ar, tgt, rng); card_mesh("%s_%s" % (lod, p), P, N, nl, A, cs, kind, rng); out[lod] = [len(P), round(cs, 4)]
        rad = float(np.percentile(np.hypot(cen[:, 0], cen[:, 1]), 90)); zc = [float(np.percentile(cen[:, 2], 8)), float(cen[:, 2].max())]
    else: rad, zc = 0.3, [0.4, 1.0]
    bpy.data.meshes.remove(lm)
    pinfo[p] = dict(kind=kind, leaf=LEAFMAT.get(kind, "ovate"), leaves=n, cards=out, r=round(rad, 3), crown=[round(v, 3) for v in zc], trunk_faces=len(wm.polygons))
    log("proto", p, pinfo[p])

# ---------- instances
trees = {}; cherry = []
for cn, layer in (("Trees", "trees"), ("Forest", "forest")):
    for e in bpy.data.collections[cn].objects:
        if e.type != "EMPTY" or e.instance_collection is None: continue
        # matrix_basis (location / rotation / scale), NOT matrix_world: the forest empties are hidden in the viewport, and in background Blender the
        # world matrix of a hidden object is never evaluated - it stays the identity.  All 728 forest trees were exported at the origin, 1 m tall:
        # a bush with cherry blossom in it at the corner of the building, and no forest on the hills.
        p = e.instance_collection.name[3:]; M = e.matrix_basis @ Matrix.Translation(-e.instance_collection.instance_offset)
        trees.setdefault(layer, {}).setdefault(p, []).append(mat12(M))
        if p.startswith("cherry"):
            pi = pinfo[p]; s = e.scale
            cherry.append(dict(p=yup(e.location), h=round(s.z, 2), r=round(pi["r"] * s.x, 2), crown=[round(pi["crown"][0] * s.z, 2), round(pi["crown"][1] * s.z, 2)], layer=layer))
    _xy = np.array([[a[9], -a[11], a[4]] for v in trees.get(layer, {}).values() for a in v]) if trees.get(layer) else np.zeros((1, 3))
    log("instances", layer, len(_xy), "x %.0f..%.0f y %.0f..%.0f height %.1f..%.1f" % (_xy[:, 0].min(), _xy[:, 0].max(), _xy[:, 1].min(), _xy[:, 1].max(), _xy[:, 2].min(), _xy[:, 2].max()))
    assert len(_xy) < 3 or np.ptp(_xy[:, :2], axis=0).max() > 5.0, "all instances of layer %s sit at one place - stale matrices?" % layer
_jp = os.path.join(WEB, VAR + ".json")
faces = json.load(open(_jp)).get("faces") if VEG_ONLY and os.path.exists(_jp) else dict(build=cnt_build, terrain=cnt_terr, grass=cnt_grass)
json.dump(dict(variant=VAR, protos=pinfo, trees=trees, cherry=cherry, faces=faces),
          open(os.path.join(WEB, VAR + ".json"), "w"), separators=(",", ":"))

# ---------- scene: sun, camera path, footprints
PP = json.load(open(os.path.join(ROOT, "params.json"), encoding="utf-8")); cam = json.load(open(os.path.join(ROOT, "anim", "cam_frames.json")))
sun = bpy.data.objects.get("Sun"); d = (sun.matrix_world.to_3x3() @ Vector((0, 0, 1))) if sun else Vector((0.79, -0.21, 0.58))      # toward the sun
def rect_of(B):
    fl = [f["r"] for f in B["floors"]]; return [min(r[0] for r in fl), min(r[1] for r in fl), max(r[2] for r in fl), max(r[3] for r in fl)]
boxes = [rect_of(PP["west"]) + [PP["west"]["ceilings"][0]["z"]], rect_of(PP["east"]) + [max(c["z"] for c in PP["east"]["ceilings"])], list(PP["shed"]["r"]) + [PP["shed"].get("wall_top", 2.0)]]
floors = [dict(r=f["r"], z=f["z"]) for b in ("west", "east") for f in PP[b]["floors"]] + [dict(r=PP["shed"]["r"], z=PP["shed"]["z0"])]
roofs = [[PP[b]["roof"][k] for k in ("x0", "y0", "x1", "y1")] for b in ("west", "east")]
holes = [h for b in ("west", "east") for h in PP[b].get("damage", {}).get("roof_holes", [])]
frames = [dict(p=yup(f["loc"]), t=yup(f["look"]), part=f.get("part", "")) for f in cam["frames"]]
json.dump(dict(sun_to=yup(d.normalized()), sun_color=list(sun.data.color) if sun else [1, 0.96, 0.9], fps=cam.get("fps", 24), hfov=90.0, boxes=boxes, floors=floors, roofs=roofs,
               holes=holes, frames=frames, model_axes="three (x, y, z) = model (x, z, -y), metres"), open(os.path.join(WEB, "scene.json"), "w"), separators=(",", ":"))

# ---------- glTF
def export(collection, path, uv):
    bpy.ops.object.select_all(action="DESELECT")
    for o in collection.objects: o.hide_set(False); o.select_set(True)
    vl.objects.active = collection.objects[0]
    props = bpy.ops.export_scene.gltf.get_rna_type().properties.keys()
    kw = dict(filepath=path, export_format="GLB", use_selection=True, export_apply=True, export_yup=True,
              export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6,
              export_draco_position_quantization=16, export_draco_normal_quantization=10, export_draco_texcoord_quantization=10,
              export_draco_color_quantization=8, export_normals=True, export_texcoords=uv, export_materials="EXPORT",
              export_vertex_color="ACTIVE", export_all_vertex_colors=False, export_active_vertex_color_when_no_material=True,
              export_cameras=False, export_lights=False, export_animations=False, export_extras=False, export_skins=False, export_morph=False)
    miss = [k for k in kw if k not in props]; kw = {k: v for k, v in kw.items() if k in props}
    bpy.ops.export_scene.gltf(**kw); log("exported", os.path.basename(path), round(os.path.getsize(path) / 1e6, 2), "MB; unknown exporter args:", miss)
if not VEG_ONLY: export(OUT_S, os.path.join(WEB, VAR + ".glb"), False)
export(OUT_V, os.path.join(WEB, VAR + "_veg.glb"), True)
log("WEB_EXPORT_DONE")
