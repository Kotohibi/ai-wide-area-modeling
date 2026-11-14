r"""Photo-projection texture bake, stage 1 (inside Blender): UV-unwrap a group of objects, find for every texel the
training photos that see it (frustum + facing + BVH occlusion, best two by angle/distance) and write the texel ->
photo-pixel table; also export the UV-mapped group as FBX (one material slot "T_baked_<group>").
Stage 2 (photo_bake_sample.py, outside Blender) reads the photos and writes the texture.

Run inside Blender:
    BAKE = {"group": "SM_Gate", "collections": [...], "objects": [...], "center": [x, y], "res": [W, H],
            "uv": "smart" | ["planar", x0, y0, x1, y1], "cameras": r"...\cameras_model.npz",
            "occluders": ["Temple_Hall", ...], "out_dir": r"...\bake", "exclude_views": ["top"],
            "max_dist": 35.0, "unit_scale": 100.0, "fbx_dir": r"...\ue_export"}
    p = SH + r"\bl_photo_bake.py"; exec(compile(open(p, encoding="utf-8").read(), p, "exec"), globals())
Outputs: <out_dir>/<group>_texels.npz  (pix, cam1, cam2, uv1, uv2 [x16 uint16], w1, w2, fallback sRGB) and the FBX.
Notes: camera R = Blender camera rotation (columns x right, y up, z back); photo pixel u = cx + fx*x/(-z),
v = cy - fy*y/(-z) from the top. Large triangles get a per-texel occlusion test, small ones per centroid.
"""
import bpy, bmesh, os, math, time, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

cfg = globals()["BAKE"]; t0 = time.time(); log = []
dg = bpy.context.evaluated_depsgraph_get()

def objs(spec_cols, spec_obs):
    out = []
    for cn in spec_cols or []:
        c = bpy.data.collections.get(cn)
        if c: out += [o for o in c.all_objects if o.type == 'MESH']
    for on in spec_obs or []:
        o = bpy.data.objects.get(on)
        if o and o.type == 'MESH': out.append(o)
    seen = set(); return [o for o in out if not (o.name in seen or seen.add(o.name))]

# ---------------------------------------------------------------- group mesh with per-face fallback colour layer
# (an int face layer "fb" = object number * 1000 + material slot survives joining and triangulation)
obs = objs(cfg.get("collections"), cfg.get("objects"))
bm = bmesh.new(); colL = None
for o in obs:
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), depsgraph=dg); me.transform(o.matrix_world)
    cols = [tuple(m.diffuse_color[:3]) if m else (0.5, 0.5, 0.5) for m in me.materials] or [(0.5, 0.5, 0.5)]
    tmp = bmesh.new(); tmp.from_mesh(me)
    lay = tmp.faces.layers.int.new("fb")
    for f in tmp.faces: f[lay] = min(f.material_index, len(cols) - 1) + 1000 * len(log)
    log.append(cols)
    tmp.to_mesh(me); tmp.free(); bm.from_mesh(me); bpy.data.meshes.remove(me)
bmesh.ops.triangulate(bm, faces=bm.faces)
fbl = bm.faces.layers.int.get("fb")
me = bpy.data.meshes.new("BAKE_" + cfg["group"]); bm.to_mesh(me); bm.free()
ob = bpy.data.objects.new("BAKE_" + cfg["group"], me); bpy.context.scene.collection.objects.link(ob)
fb_attr = me.attributes.get("fb")
fbv = np.zeros(len(me.polygons), np.int64); fb_attr.data.foreach_get("value", fbv)
fallback_lin = np.array([log[v // 1000][v % 1000] for v in fbv], np.float32)

# ---------------------------------------------------------------- UVs
uvmode = cfg.get("uv", "smart")
if not me.uv_layers: me.uv_layers.new(name="UVMap")
if uvmode == "smart":
    for o in bpy.context.selected_objects: o.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=cfg.get("margin", 0.002), area_weight=0.0, scale_to_bounds=True)
    bpy.ops.object.mode_set(mode='OBJECT')
else:
    _, x0, y0, x1, y1 = uvmode
    co = np.zeros(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    li = np.zeros(len(me.loops), np.int64); me.loops.foreach_get("vertex_index", li)
    uv = np.stack([(co[li, 0] - x0) / (x1 - x0), (co[li, 1] - y0) / (y1 - y0)], 1).astype(np.float32)
    me.uv_layers[0].data.foreach_set("uv", uv.ravel())
log_t = {"uv_s": round(time.time() - t0, 1)}

# ---------------------------------------------------------------- triangle arrays
nT = len(me.polygons)
co = np.zeros(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
li = np.zeros(len(me.loops), np.int64); me.loops.foreach_get("vertex_index", li)
uv = np.zeros(len(me.loops) * 2, np.float32); me.uv_layers[0].data.foreach_get("uv", uv); uv = uv.reshape(-1, 2)
ls = np.zeros(nT, np.int64); me.polygons.foreach_get("loop_start", ls)
L = ls[:, None] + np.arange(3)[None]
TP = co[li[L]]                        # (T,3,3) world positions
TU = uv[L]                            # (T,3,2) uv
TN = np.cross(TP[:, 1] - TP[:, 0], TP[:, 2] - TP[:, 0]); area = 0.5 * np.linalg.norm(TN, axis=1)
TN = TN / np.maximum(np.linalg.norm(TN, axis=1, keepdims=True), 1e-12)
W, H = cfg["res"]

# ---------------------------------------------------------------- rasterise UV triangles -> texels
P = TU * np.array([W, H], np.float32) - 0.5           # pixel-centre coordinates
pix_l, tri_l, bary_l = [], [], []
mn = np.floor(P.min(1)).astype(np.int64); mx = np.ceil(P.max(1)).astype(np.int64)
mn = np.clip(mn, 0, [W - 1, H - 1]); mx = np.clip(mx, 0, [W - 1, H - 1])
for t in range(nT):
    xs = np.arange(mn[t, 0], mx[t, 0] + 1); ys = np.arange(mn[t, 1], mx[t, 1] + 1)
    if xs.size == 0 or ys.size == 0: continue
    gx, gy = np.meshgrid(xs, ys); gx = gx.ravel(); gy = gy.ravel()
    a, b, c = P[t]
    d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    if abs(d) < 1e-12: continue
    l1 = ((b[1] - c[1]) * (gx - c[0]) + (c[0] - b[0]) * (gy - c[1])) / d
    l2 = ((c[1] - a[1]) * (gx - c[0]) + (a[0] - c[0]) * (gy - c[1])) / d
    l3 = 1 - l1 - l2
    m = (l1 >= -0.05) & (l2 >= -0.05) & (l3 >= -0.05)
    if not m.any():                                     # sub-pixel triangle: take its nearest texel
        gx = np.array([int(round((a[0] + b[0] + c[0]) / 3))]); gy = np.array([int(round((a[1] + b[1] + c[1]) / 3))])
        l1 = l2 = l3 = np.array([1 / 3]); m = np.array([True])
    pix_l.append((gy[m] * W + gx[m]).astype(np.int64)); tri_l.append(np.full(m.sum(), t, np.int64))
    bary_l.append(np.stack([np.clip(l1[m], 0, 1), np.clip(l2[m], 0, 1), np.clip(l3[m], 0, 1)], 1))
pix = np.concatenate(pix_l); tri = np.concatenate(tri_l); bary = np.concatenate(bary_l).astype(np.float32)
bary /= bary.sum(1, keepdims=True)
_, first = np.unique(pix, return_index=True)           # one triangle per texel
pix, tri, bary = pix[first], tri[first], bary[first]
X = (TP[tri] * bary[:, :, None]).sum(1)               # texel world positions
log_t["texels"] = int(pix.size); log_t["raster_s"] = round(time.time() - t0, 1)

# ---------------------------------------------------------------- cameras
cz = np.load(cfg["cameras"]); names = cz["names"]; CC = cz["C"].astype(np.float32); RR = cz["R"].astype(np.float32); KK = cz["K"].astype(np.float32)
keep = np.array([not any(n.endswith("_" + v + ".png") for v in cfg.get("exclude_views", ["top"])) for n in names])
cam_ids = np.where(keep)[0]; CC, RR, KK = CC[keep], RR[keep], KK[keep]

def project(Xs, ci):
    """Xs (N,3), ci (N,) camera indices (into the kept arrays) -> u, v, depth."""
    d = Xs - CC[ci]; R = RR[ci]
    x = (d * R[:, :, 0]).sum(1); y = (d * R[:, :, 1]).sum(1); z = -(d * R[:, :, 2]).sum(1)
    k = KK[ci]; zz = np.maximum(z, 1e-6)
    return k[:, 2] + k[:, 0] * x / zz, k[:, 3] - k[:, 1] * y / zz, z

# occluder BVH (world space)
obv = objs(cfg.get("occluders"), []) + obs
bmo = bmesh.new()
for o in obv:
    m2 = bpy.data.meshes.new_from_object(o.evaluated_get(dg), depsgraph=dg); m2.transform(o.matrix_world); bmo.from_mesh(m2); bpy.data.meshes.remove(m2)
bvh = BVHTree.FromBMesh(bmo); bmo.free()

def visible(p, n, cpos):
    o = Vector(p) + Vector(n) * 0.03; dv = Vector(cpos) - o; dist = dv.length
    hit = bvh.ray_cast(o, dv / dist, dist - 0.05)
    return hit[0] is None

# per-triangle candidate cameras (top K by score), chunked
K_CAND = 8; maxd = cfg.get("max_dist", 35.0)
cent = TP.mean(1); cand = np.full((nT, K_CAND), -1, np.int64); cscore = np.zeros((nT, K_CAND), np.float32)
used_tris = np.unique(tri)
for s in range(0, used_tris.size, 3000):
    tt = used_tris[s:s + 3000]; c0 = cent[tt]; n0 = TN[tt]
    V = CC[None, :, :] - c0[:, None, :]; dist = np.linalg.norm(V, axis=2)
    cosv = (V * n0[:, None, :]).sum(2) / np.maximum(dist, 1e-6)
    d = -V; x = np.einsum("tmk,mk->tm", d, RR[:, :, 0]); y = np.einsum("tmk,mk->tm", d, RR[:, :, 1]); z = -np.einsum("tmk,mk->tm", d, RR[:, :, 2])
    zz = np.maximum(z, 1e-6); u = KK[None, :, 2] + KK[None, :, 0] * x / zz; v = KK[None, :, 3] - KK[None, :, 1] * y / zz
    ok = (z > 0.3) & (dist < maxd) & (cosv > 0.15) & (u > 0.02 * KK[None, :, 4]) & (u < 0.98 * KK[None, :, 4]) & (v > 0.02 * KK[None, :, 5]) & (v < 0.98 * KK[None, :, 5])
    # prefer frontal and close views; also prefer the photo centre (less distortion at cube-face edges)
    cen = 1 - 0.5 * (np.abs(u / KK[None, :, 4] - 0.5) + np.abs(v / KK[None, :, 5] - 0.5))
    sc = np.where(ok, cosv ** 2 * cen / (dist + 2.0), 0)
    k = min(K_CAND, sc.shape[1]); idx = np.argpartition(-sc, k - 1, axis=1)[:, :k]
    ss = np.take_along_axis(sc, idx, 1); o2 = np.argsort(-ss, 1); idx = np.take_along_axis(idx, o2, 1); ss = np.take_along_axis(ss, o2, 1)
    idx[ss <= 0] = -1; cand[tt] = idx; cscore[tt] = ss
log_t["cand_s"] = round(time.time() - t0, 1)

# visibility: small triangles per centroid, large triangles per texel
big = area > cfg.get("big_area", 0.04)
tri_best = np.full((nT, 2), -1, np.int64); tri_w = np.zeros((nT, 2), np.float32)
for t in used_tris:
    if big[t]: continue
    got = 0
    for j in range(K_CAND):
        ci = cand[t, j]
        if ci < 0: break
        if visible(cent[t], TN[t], CC[ci]):
            tri_best[t, got] = ci; tri_w[t, got] = cscore[t, j]; got += 1
            if got == 2: break
cam1 = tri_best[tri, 0].copy(); cam2 = tri_best[tri, 1].copy(); w1 = tri_w[tri, 0].copy(); w2 = tri_w[tri, 1].copy()
bigtex = np.where(big[tri])[0]
# large triangles (walls, ground slabs, the ground plane): candidates per texel, not per triangle centroid - a
# triangle centroid can be tens of metres from the texel. Texels are grouped in 2 m cells so each chunk only scores
# the cameras near it.
order = bigtex[np.lexsort((np.floor(X[bigtex, 1] / 2), np.floor(X[bigtex, 0] / 2)))]
for s in range(0, order.size, 4000):
    ii = order[s:s + 4000]; P0 = X[ii]; N0 = TN[tri[ii]]
    lo = P0.min(0) - maxd; hi = P0.max(0) + maxd
    sub = np.where(np.all((CC >= lo) & (CC <= hi), axis=1))[0]
    if sub.size == 0: continue
    V = CC[sub][None] - P0[:, None]; dist = np.linalg.norm(V, axis=2)
    cosv = (V * N0[:, None]).sum(2) / np.maximum(dist, 1e-6)
    Rs = RR[sub]; Ks = KK[sub]; d = -V
    x = np.einsum("tmk,mk->tm", d, Rs[:, :, 0]); y = np.einsum("tmk,mk->tm", d, Rs[:, :, 1]); z = -np.einsum("tmk,mk->tm", d, Rs[:, :, 2])
    zz = np.maximum(z, 1e-6); u = Ks[None, :, 2] + Ks[None, :, 0] * x / zz; v = Ks[None, :, 3] - Ks[None, :, 1] * y / zz
    ok = (z > 0.3) & (dist < maxd) & (cosv > 0.15) & (u > 0.02 * Ks[None, :, 4]) & (u < 0.98 * Ks[None, :, 4]) & (v > 0.02 * Ks[None, :, 5]) & (v < 0.98 * Ks[None, :, 5])
    cen = 1 - 0.5 * (np.abs(u / Ks[None, :, 4] - 0.5) + np.abs(v / Ks[None, :, 5] - 0.5))
    sc = np.where(ok, cosv ** 2 * cen / (dist + 2.0), 0)
    k = min(K_CAND, sc.shape[1]); idx = np.argpartition(-sc, k - 1, axis=1)[:, :k]
    ss = np.take_along_axis(sc, idx, 1); o2 = np.argsort(-ss, 1); idx = np.take_along_axis(idx, o2, 1); ss = np.take_along_axis(ss, o2, 1)
    for r, i in enumerate(ii):
        got = 0
        for j in range(k):
            if ss[r, j] <= 0: break
            ci = sub[idx[r, j]]
            if visible(X[i], N0[r], CC[ci]):
                if got == 0: cam1[i] = ci; w1[i] = ss[r, j]
                else: cam2[i] = ci; w2[i] = ss[r, j]
                got += 1
                if got == 2: break
log_t["vis_s"] = round(time.time() - t0, 1); log_t["big_texels"] = int(bigtex.size)

def uv16(ci):
    u = np.zeros(pix.size, np.float32); v = np.zeros(pix.size, np.float32); m = ci >= 0
    if m.any():
        uu, vv, _ = project(X[m], ci[m]); u[m] = uu; v[m] = vv
    return np.clip(np.stack([u, v], 1) * 16, 0, 65535).astype(np.uint16)
fb_srgb = np.where(fallback_lin <= 0.0031308, fallback_lin * 12.92, 1.055 * np.power(np.maximum(fallback_lin, 0), 1 / 2.4) - 0.055)
os.makedirs(cfg["out_dir"], exist_ok=True)
np.savez(os.path.join(cfg["out_dir"], cfg["group"] + "_texels.npz"), res=np.array([W, H]), pix=pix.astype(np.int32),
         cam1=np.where(cam1 >= 0, cam_ids[np.maximum(cam1, 0)], -1).astype(np.int32), cam2=np.where(cam2 >= 0, cam_ids[np.maximum(cam2, 0)], -1).astype(np.int32),
         uv1=uv16(cam1), uv2=uv16(cam2), w1=w1.astype(np.float32), w2=w2.astype(np.float32),
         fallback=(np.clip(fb_srgb[tri], 0, 1) * 255).astype(np.uint8))

# ---------------------------------------------------------------- FBX with UVs, one baked material slot
mat = bpy.data.materials.get("T_baked_" + cfg["group"]) or bpy.data.materials.new("T_baked_" + cfg["group"])
me.materials.clear(); me.materials.append(mat)
for p in me.polygons: p.material_index = 0
c = cfg.get("center", [0, 0]); k = cfg.get("unit_scale", 100.0)
me.transform(__import__("mathutils").Matrix.Translation((-c[0], -c[1], 0)))
me.transform(__import__("mathutils").Matrix.Diagonal((k, k, k, 1)))
for o in bpy.context.selected_objects: o.select_set(False)
ob.select_set(True); bpy.context.view_layer.objects.active = ob
f = os.path.join(cfg["fbx_dir"], cfg["group"] + ".fbx")
bpy.ops.export_scene.fbx(filepath=f, use_selection=True, object_types={'MESH'}, mesh_smooth_type='FACE', apply_scale_options='FBX_SCALE_UNITS',
                         add_leaf_bones=False, path_mode='STRIP')
bpy.data.objects.remove(ob); bpy.data.meshes.remove(me)
seen1 = float((cam1 >= 0).mean())
result = dict(log_t, group=cfg["group"], tris=nT, seen_by_photo=round(seen1, 3), total_s=round(time.time() - t0, 1), fbx=f)
