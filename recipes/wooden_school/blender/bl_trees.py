"""Procedural trees: recursive branching skeleton -> tube mesh; leaves instanced on scattered points by Geometry Nodes;
trees placed as collection instances (trees.json from the scan + a random forest fill outside the scanned area).
Adapted from an earlier project's bl_veg.py.   build_proc_trees(T, mode) rebuilds TreeProtos / Trees / Forest."""
import bpy, json, os, math
import numpy as np

def _wipe(name, parent=None):
    """Collection `name`, emptied recursively (objects, child collections)."""
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name); (parent or bpy.context.scene.collection).children.link(c); return c
    def rec(cc):
        for ch in list(cc.children): rec(ch); bpy.data.collections.remove(ch)
        for o in list(cc.objects):
            me = o.data; bpy.data.objects.remove(o, do_unlink=True)
            if isinstance(me, bpy.types.Mesh) and me.users == 0: bpy.data.meshes.remove(me)
    rec(c); return c

def _leaf_mesh(name, kind):
    me = bpy.data.meshes.get(name)
    if me: return me
    if kind == "spray":      # cedar frond: tapered axis with alternating branchlets, two crossed planes
        vs = []; fs = []
        def strip(a, b, w0, w1, nrm):
            a = np.array(a, float); b = np.array(b, float); d = b - a; p = np.cross(d, nrm); p /= np.linalg.norm(p) + 1e-9; o = len(vs)
            vs.extend([tuple(a - p * w0), tuple(a + p * w0), tuple(b + p * w1), tuple(b - p * w1)]); fs.append((o, o + 1, o + 2, o + 3))
        for w_, n_ in (((1.0, 0, 0), (0, 1.0, 0)), ((0, 1.0, 0), (1.0, 0, 0))):
            w_ = np.array(w_); n_ = np.array(n_)
            pts = [w_ * 0.06 * (t * t) - np.array([0, 0, t]) for t in np.linspace(0, 1, 5)]
            for k in range(4): strip(pts[k], pts[k + 1], 0.05 - 0.009 * k, 0.05 - 0.009 * (k + 1), n_)
            for j, t in enumerate((0.12, 0.27, 0.42, 0.57, 0.72, 0.85)):
                side = 1 if j % 2 == 0 else -1; L_ = 0.36 * (1 - 0.55 * t); a = np.array([0, 0, -t]) + w_ * 0.06 * t * t
                b = a + w_ * side * L_ * 0.85 + np.array([0, 0, -L_ * 0.5]); strip(a, b, 0.045, 0.01, n_)
    elif kind == "petal":    # blossom cluster: three five-petal flowers at different tilts
        vs = []; fs = []
        for k, (cx, cy, cz, tx, ty) in enumerate(((0, 0, 0, 0.0, 0.0), (0.9, 0.3, 0.2, 0.9, 0.2), (-0.5, 0.8, -0.2, -0.4, 0.9))):
            o = len(vs); ring = []
            for j in range(10):
                a = 6.283 * j / 10; r = 1.0 if j % 2 == 0 else 0.5; x, y = r * math.cos(a), r * math.sin(a)
                ring.append((cx + x, cy + y * math.cos(tx) , cz + y * math.sin(tx) + x * math.sin(ty) * 0.6))
            vs += ring; fs.append(tuple(range(o, o + 10)))
    else:                    # ovate leaf cluster: two folded leaves
        vs = [(0, -0.9, 0), (0.5, 0, 0.12), (0, 1.0, 0), (-0.5, 0, 0.12), (0, 0, -0.2), (0.75, 0.45, 0.1), (0.1, 0.9, 0.35), (-0.6, 0.5, 0.2)]
        fs = [(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7)]
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update(); return me

def _gn_leaves():
    ng = bpy.data.node_groups.get("GN_LeavesRS")
    if ng: return ng
    ng = bpy.data.node_groups.new("GN_LeavesRS", "GeometryNodeTree"); I = ng.interface
    I.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"); I.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    I.new_socket("Leaf", in_out="INPUT", socket_type="NodeSocketObject")
    s = I.new_socket("Scale", in_out="INPUT", socket_type="NodeSocketFloat"); s.default_value = 0.02
    s = I.new_socket("Seed", in_out="INPUT", socket_type="NodeSocketInt"); s.default_value = 0
    N = ng.nodes; L = ng.links
    gi = N.new("NodeGroupInput"); go = N.new("NodeGroupOutput")
    m2p = N.new("GeometryNodeMeshToPoints"); oi = N.new("GeometryNodeObjectInfo"); iop = N.new("GeometryNodeInstanceOnPoints")
    rrot = N.new("FunctionNodeRandomValue"); rrot.data_type = "FLOAT_VECTOR"
    rsc = N.new("FunctionNodeRandomValue"); rsc.data_type = "FLOAT"
    rat = N.new("FunctionNodeRandomValue"); rat.data_type = "FLOAT"
    sto = N.new("GeometryNodeStoreNamedAttribute"); sto.data_type = "FLOAT"; sto.domain = "INSTANCE"
    rea = N.new("GeometryNodeRealizeInstances"); mul = N.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
    def en(node, name, out=False):
        for s_ in (node.outputs if out else node.inputs):
            if s_.name == name and s_.enabled: return s_
        raise KeyError(name)
    L.new(gi.outputs["Geometry"], m2p.inputs["Mesh"]); L.new(gi.outputs["Leaf"], oi.inputs["Object"])
    L.new(m2p.outputs[0], iop.inputs["Points"]); L.new(en(oi, "Geometry", True), iop.inputs["Instance"])
    en(rrot, "Min").default_value = (-0.9, -0.9, 0.0); en(rrot, "Max").default_value = (0.9, 0.9, 6.283)
    L.new(gi.outputs["Seed"], en(rrot, "Seed")); L.new(en(rrot, "Value", True), iop.inputs["Rotation"])
    en(rsc, "Min").default_value = 0.6; en(rsc, "Max").default_value = 1.3
    L.new(en(rsc, "Value", True), mul.inputs[0]); L.new(gi.outputs["Scale"], mul.inputs[1]); L.new(mul.outputs[0], iop.inputs["Scale"])
    L.new(iop.outputs[0], sto.inputs["Geometry"]); en(sto, "Name").default_value = "lrand"; rat.inputs["Seed"].default_value = 7
    L.new(en(rat, "Value", True), en(sto, "Value")); L.new(sto.outputs[0], rea.inputs[0]); L.new(rea.outputs[0], go.inputs[0])
    return ng

class _Tree:
    def __init__(self, rng): self.rng = rng; self.seg = []; self.leaves = []
    def branch(self, p, d, length, r, level, P):
        rng = self.rng; nseg = 3 if level < P["levels"] - 1 else 2; q = np.array(p, float); d = np.array(d, float)
        for k in range(nseg):
            d = d + rng.normal(0, P["wiggle"], 3) + np.array([0, 0, P["up"] * (0.5 if level else 0.0)]); d /= np.linalg.norm(d)
            q2 = q + d * length / nseg; r2 = r * (1 - 0.28 / nseg * (1 if level else 0.6))
            self.seg.append((q.copy(), r, q2.copy(), r2)); q, r = q2, r2
            if level >= P["leaf_from"]:
                n = rng.poisson(P["leaves"] * (0.5 if level < P["levels"] - 1 else 1.0))
                if n: self.leaves.append(q + rng.normal(0, P["spread"], (n, 3)) * np.array([1, 1, 0.7]))
        if level >= P["levels"] - 1 or r < 0.0012: return
        nch = rng.integers(P["split"][0], P["split"][1] + 1)
        ref = np.cross(d, [0, 0, 1.0]) if abs(d[2]) < 0.95 else np.array([1.0, 0, 0]); ref /= np.linalg.norm(ref); w = np.cross(d, ref)
        a0 = rng.uniform(0, 6.283)
        for c in range(nch):
            ang = math.radians(rng.uniform(*P["angle"])) * (0.45 if (c == 0 and P.get("leader")) else 1.0); az = a0 + 6.283 * c / nch + rng.normal(0, 0.3)
            nd = d * math.cos(ang) + (ref * math.cos(az) + w * math.sin(az)) * math.sin(ang)
            self.branch(q, nd, length * P["ratio"] * rng.uniform(0.8, 1.15), r * P["rratio"] * (1.15 if c == 0 else 1.0), level + 1, P)
    def conifer(self, P):
        rng = self.rng; q = np.zeros(3); r = P["r0"]; n = 24
        for k in range(n):
            q2 = np.array([rng.normal(0, 0.002), rng.normal(0, 0.002), (k + 1) / n]); r2 = P["r0"] * (1 - (k + 1) / n) ** 0.8 + 0.002
            self.seg.append((q.copy(), r, q2, r2)); q, r = q2, r2
        z = P["crown_from"]
        while z < 0.985:
            t = (z - P["crown_from"]) / (1 - P["crown_from"]); ln = P["blen"] * (1 - t) ** 0.75 * (0.55 + 0.45 * min(1, t * 4)) + 0.02
            nb = rng.integers(*P.get("nb", (4, 7))); a0 = rng.uniform(0, 6.283)
            for b in range(nb):
                az = a0 + 6.283 * b / nb + rng.normal(0, 0.25); el = math.radians(rng.uniform(-18, 12))
                d = np.array([math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)]); p0 = np.array([0, 0, z]); l2 = ln * rng.uniform(0.7, 1.15)
                p1 = p0 + d * l2 * 0.5 + (0, 0, -0.01); p2 = p0 + d * l2 + (0, 0, -0.02 - 0.1 * l2)
                self.seg.append((p0, 0.006 * (1 - t) + 0.002, p1, 0.004 * (1 - t) + 0.0015)); self.seg.append((p1, 0.004 * (1 - t) + 0.0015, p2, 0.001))
                m = max(2, int(P["leaves"] * l2 / P["blen"])); nc = max(1, int(round(P["clumps"] * l2 / P["blen"])))
                for c_ in range(nc):
                    tc = 1.0 if c_ == 0 else rng.uniform(0.3, 0.95); cc = p0 + (p2 - p0) * tc + rng.normal(0, P["spread"], 3) * np.array([1, 1, 0.5])
                    k_ = max(2, m // nc); self.leaves.append(cc + rng.normal(0, P["clump_r"], (k_, 3)) * np.array([1, 1, 0.65]))
            z += P["whorl"] * rng.uniform(0.8, 1.2)
    def mesh(self):
        """Trunk and branches as CONTINUOUS TUBES: consecutive segments of one branch share the ring at their joint (the ring lies in the
        plane that bisects the bend; its frame is carried along without twist), a side branch starts inside its parent, every end is closed.
        One cylinder per segment (the first version) left a wedge-shaped gap on the outside of every bend - seen as notches in the trunk."""
        chains = []
        for (p0, r0, p1, r1) in self.seg:
            p0 = np.asarray(p0, float); p1 = np.asarray(p1, float)
            if chains and np.allclose(chains[-1][0][-1], p0, atol=1e-9) and abs(chains[-1][1][-1] - r0) < 1e-9: chains[-1][0].append(p1); chains[-1][1].append(r1)
            else: chains.append(([p0, p1], [r0, r1]))
        vs = []; fs = []
        for ci, (P, R) in enumerate(chains):
            n = 8 if R[0] > 0.012 else (5 if R[0] > 0.004 else 3); m = len(P)
            d = [P[i + 1] - P[i] for i in range(m - 1)]; d = [x / (np.linalg.norm(x) + 1e-12) for x in d]; P = list(P)
            if ci > 0: P[0] = P[0] - d[0] * R[0] * 0.8
            u = None; rings = []
            for i in range(m):
                t = d[0] if i == 0 else (d[-1] if i == m - 1 else d[i - 1] + d[i]); nt = np.linalg.norm(t); t = t / nt if nt > 1e-9 else d[min(i, m - 2)]
                if u is not None: u = u - t * float(np.dot(u, t))
                if u is None or np.linalg.norm(u) < 1e-6: u = np.cross(t, np.array([0, 0, 1.0]) if abs(t[2]) < 0.9 else np.array([1.0, 0, 0]))
                u = u / np.linalg.norm(u); w = np.cross(t, u); k_ = 1.0
                if 0 < i < m - 1: k_ = min(1.25, 1.0 / max(0.5, math.sqrt(max(0.0, (1.0 + float(np.dot(d[i - 1], d[i]))) / 2.0))))   # mitre: the tube keeps its thickness round the bend
                r = R[i] * k_ * (1.03 if i == 0 else 1.0); rings.append(len(vs))
                for k in range(n):
                    a = 6.283185 * k / n; vs.append(P[i] + r * (math.cos(a) * u + math.sin(a) * w))
            for i in range(m - 1):
                a, b = rings[i], rings[i + 1]
                for k in range(n): fs.append((a + k, a + (k + 1) % n, b + (k + 1) % n, b + k))
            tip = len(vs); vs.append(P[-1] + d[-1] * R[-1] * 0.6); b = rings[-1]
            for k in range(n): fs.append((b + k, b + (k + 1) % n, tip))
        return vs, fs

# kinds for this site (spring, warm-temperate): big evergreen broadleaf trees on the hill, fresh green deciduous, cedar, cherry
TREE_KINDS = {
    "evergreen": dict(gen="broad", leaf="ovate", mat="leafc_dark", bark="bark", lscale=0.013, P=dict(levels=6, split=(2, 3), angle=(30, 62), ratio=0.76, rratio=0.66, wiggle=0.10, up=0.04, leaves=90, leaf_from=2, spread=0.045, trunk=0.22, len0=0.30, r0=0.028)),
    "mid": dict(gen="broad", leaf="ovate", mat="leafc_mid", bark="bark", lscale=0.012, P=dict(levels=6, split=(2, 3), angle=(26, 55), ratio=0.75, rratio=0.66, wiggle=0.10, up=0.10, leaves=75, leaf_from=2, spread=0.04, trunk=0.25, len0=0.28, r0=0.025)),
    "fresh": dict(gen="broad", leaf="ovate", mat="leafc_fresh", bark="bark", lscale=0.011, P=dict(levels=6, split=(2, 3), angle=(24, 50), ratio=0.74, rratio=0.65, wiggle=0.09, up=0.16, leaves=50, leaf_from=3, spread=0.035, trunk=0.30, len0=0.26, r0=0.022, leader=1)),
    "cherry": dict(gen="broad", leaf="petal", mat="leafc_cherry", bark="bark_dark", lscale=0.0042, P=dict(levels=6, split=(2, 3), angle=(30, 60), ratio=0.76, rratio=0.66, wiggle=0.10, up=0.03, leaves=190, leaf_from=3, spread=0.035, trunk=0.18, len0=0.30, r0=0.026)),
    "cedar": dict(gen="conifer", leaf="spray", mat="leafc_cedar", bark="bark_cedar", lscale=0.024, P=dict(r0=0.020, crown_from=0.34, blen=0.17, whorl=0.020, leaves=270, spread=0.014, clumps=4, clump_r=0.028, nb=(6, 9))),
    "bush": dict(gen="broad", leaf="ovate", mat="leafc_mid", bark="bark", lscale=0.035, P=dict(levels=4, split=(3, 4), angle=(30, 65), ratio=0.75, rratio=0.6, wiggle=0.12, up=0.05, leaves=110, leaf_from=1, spread=0.07, trunk=0.10, len0=0.32, r0=0.03)),
}
NVAR = 3

def _leaf_mat(name, c1, c2, trans=0.3):
    """Leaf cards: colour varies per leaf (attribute lrand), some light passes through, half-transparent to shadow rays."""
    t = NT(name, view=tuple((a + b) / 2 for a, b in zip(c1, c2)))
    at = t.t.nodes.new("ShaderNodeAttribute"); at.attribute_name = "lrand"
    t.set(t.mix(at.outputs["Fac"], c1, c2), 0.6)
    tl = t.t.nodes.new("ShaderNodeBsdfTranslucent"); t.L(t.b.inputs["Base Color"].links[0].from_socket, tl.inputs["Color"])
    m1 = t.t.nodes.new("ShaderNodeMixShader"); m1.inputs[0].default_value = trans; t.L(t.b.outputs[0], m1.inputs[1]); t.L(tl.outputs[0], m1.inputs[2])
    tr = t.t.nodes.new("ShaderNodeBsdfTransparent"); m2 = t.t.nodes.new("ShaderNodeMixShader"); lp = t.t.nodes.new("ShaderNodeLightPath")
    t.L(t.math("MULTIPLY", lp.outputs["Is Shadow Ray"], 0.45), m2.inputs[0]); t.L(m1.outputs[0], m2.inputs[1]); t.L(tr.outputs[0], m2.inputs[2])
    t.L(m2.outputs[0], t.out.inputs[0]); return t.m

def grow_proto(kind, v):
    """Prototype <kind>_<v> (the same random numbers every time): trunk mesh (vertices, faces) and leaf points, scaled to 1 m height."""
    K = TREE_KINDS[kind]
    rng = np.random.default_rng(sum(map(ord, kind)) * 31 + v); T = _Tree(rng); P = K["P"]
    if K["gen"] == "conifer": T.conifer(P)
    else:
        q = np.zeros(3); r = P["r0"]; nt = 4; d = np.array([rng.normal(0, 0.05), rng.normal(0, 0.05), 1.0])
        for k in range(nt):
            d = d + rng.normal(0, 0.04, 3); d[2] = abs(d[2]); d /= np.linalg.norm(d); q2 = q + d * P["trunk"] / nt; r2 = r * 0.94
            T.seg.append((q.copy(), r * (1.35 if k == 0 else 1.0), q2.copy(), r2)); q, r = q2, r2
        nch = 3; a0 = rng.uniform(0, 6.283)
        for c in range(nch + (1 if P.get("leader") else 0)):
            lead = P.get("leader") and c == nch
            ang = math.radians(8 if lead else rng.uniform(*P["angle"]) * 0.8); az = a0 + 6.283 * c / nch
            nd = np.array([math.cos(az) * math.sin(ang), math.sin(az) * math.sin(ang), math.cos(ang)])
            T.branch(q, nd, P["len0"] * (1.25 if lead else 1.0), r * (0.9 if lead else 0.72), 1, P)
    vs, fs = T.mesh(); vs = np.array(vs); zmax = max(vs[:, 2].max(), 1e-3)
    lv = np.concatenate(T.leaves) if T.leaves else np.zeros((0, 3))
    zmax = max(zmax, lv[:, 2].max() if len(lv) else 0); vs = vs / zmax; lv = lv / zmax
    return T, vs, fs, lv

def build_tree_protos():
    root = _wipe("TreeProtos"); ng = _gn_leaves(); out = {}
    # albedo from the photo patches (hill trees: photo 96,98,92 against 35,47,28 with the first, darker set)
    _leaf_mat("leafc_dark", (0.05, 0.085, 0.035), (0.14, 0.20, 0.09)); _leaf_mat("leafc_mid", (0.08, 0.14, 0.045), (0.21, 0.30, 0.10))
    _leaf_mat("leafc_fresh", (0.15, 0.26, 0.05), (0.33, 0.45, 0.11), 0.45); _leaf_mat("leafc_cherry", (0.75, 0.52, 0.56), (0.92, 0.78, 0.80), 0.4)
    _leaf_mat("leafc_cedar", (0.045, 0.08, 0.035), (0.12, 0.18, 0.08), 0.15)
    m_plain("bark", (0.10, 0.075, 0.055), (0.22, 0.17, 0.13), 4.0, (8, 8, 0.6), bump=0.5)
    m_plain("bark_dark", (0.045, 0.035, 0.03), (0.12, 0.09, 0.075), 4.0, (8, 8, 0.6), bump=0.5)
    m_plain("bark_cedar", (0.13, 0.075, 0.05), (0.26, 0.16, 0.11), 3.0, (10, 10, 0.4), bump=0.6)
    for kind, K in TREE_KINDS.items():
        lm_name = "LeafMesh_" + K["leaf"] + "_" + kind
        old = bpy.data.meshes.get(lm_name)
        leaf_ob = bpy.data.objects.new("Leaf_" + kind, _leaf_mesh(lm_name, K["leaf"]))
        leaf_ob.data.materials.clear(); leaf_ob.data.materials.append(mat(K["mat"]))
        root.objects.link(leaf_ob); leaf_ob.hide_render = True; leaf_ob.hide_viewport = True
        for v in range(NVAR):
            T, vs, fs, lv = grow_proto(kind, v)
            pc = bpy.data.collections.new("TP_%s_%d" % (kind, v)); root.children.link(pc)
            wm = bpy.data.meshes.new("TW_%s_%d" % (kind, v)); wm.from_pydata([tuple(p) for p in vs], [], fs); wm.update()
            for p_ in wm.polygons: p_.use_smooth = True
            wm.materials.append(mat(K["bark"])); pc.objects.link(bpy.data.objects.new(wm.name, wm))
            lm = bpy.data.meshes.new("TLp_%s_%d" % (kind, v)); lm.from_pydata([tuple(p) for p in lv], [], []); lo_ = bpy.data.objects.new("TL_%s_%d" % (kind, v), lm); pc.objects.link(lo_)
            for o_ in pc.objects:
                o_.visible_shadow = False; o_.visible_diffuse = False
            md = lo_.modifiers.new("Leaves", "NODES"); md.node_group = ng
            for item in ng.interface.items_tree:
                if item.item_type == "SOCKET" and item.in_out == "INPUT":
                    val = {"Leaf": leaf_ob, "Scale": K["lscale"], "Seed": v}.get(item.name)
                    if val is None: continue
                    try: getattr(md.properties.inputs, item.identifier).value = val      # Blender 5.x
                    except Exception: md[item.identifier] = val                           # Blender 4.x
            rad = float(np.percentile(np.hypot(lv[:, 0], lv[:, 1]), 90)) if len(lv) else 0.3
            out["%s_%d" % (kind, v)] = dict(coll=pc.name, r=rad, nleaf=int(len(lv)), nseg=len(T.seg))
    def find(lc, name):
        if lc.collection.name == name: return lc
        for ch in lc.children:
            f = find(ch, name)
            if f: return f
    lc = find(bpy.context.view_layer.layer_collection, "TreeProtos")
    if lc: lc.exclude = True                       # prototypes are not shown themselves; their instances render
    return out

def _inst(name, cname, c, loc, scale, rotz, hide_view=False):
    e = bpy.data.objects.new(name, None); e.instance_type = "COLLECTION"; e.instance_collection = bpy.data.collections[cname]
    e.location = loc; e.scale = scale; e.rotation_euler = (0, 0, rotz); e.empty_display_size = 0.5; e.hide_viewport = hide_view; c.objects.link(e)
    # trees do not shade the site (visible to the camera and reflections only): with their shadows the hill-side walls went
    # black against 110-125 in the photos (set1 round 6) - real canopies let far more sky light through than leaf cards do
    for k in ("visible_shadow", "visible_diffuse"):
        try: setattr(e, k, False)
        except Exception: pass
    return e

def _kind_of(rgb, h, y, rng, mode):
    r, g, b = [v / 255 for v in rgb]; lum = (r + g + b) / 3
    if mode == "restored" and y > 12.0: return "cherry"                    # yard edge: cherry trees in bloom (imagined)
    if r > g * 1.02 and lum > 0.38: return "cherry"                           # pinkish crowns in the scan (frames 21 / 145)
    if r > g * 0.93 and lum > 0.33: return "fresh"
    if lum > 0.40: return "fresh"
    if h < 4.5: return "bush" if h < 3.2 else "mid"
    return "mid" if lum > 0.27 else "evergreen"

def build_proc_trees(T, mode="ruin"):
    protos = build_tree_protos(); c = _wipe("Trees"); cf = _wipe("Forest"); rng = np.random.default_rng(7)
    trees = json.load(open(os.path.join(ROOT, "trees.json")))
    fr = json.load(open(os.path.join(ROOT, "frames.json"))); CA = np.array([v["c"] for v in fr.values()])
    if len(cam_path()): CA = np.vstack([CA, np.array(cam_path())[::3]])           # the fly-through camera
    def blocked(x, y, z0, h, r):
        d = np.hypot(CA[:, 0] - x, CA[:, 1] - y)
        if (d[CA[:, 2] < z0 + 4.0] < 1.9).any(): return True                  # the drone / the fly-through camera passes here at trunk height
        return bool(((d < 1.1 * r) & (CA[:, 2] > z0 + 0.2 * h) & (CA[:, 2] < z0 + h)).any())   # or through where the crown would be
    def zat(x, y):
        i = int(np.clip(round((x - T["xs"][0]) / 0.5), 0, len(T["xs"]) - 1)); j = int(np.clip(round((y - T["ys"][0]) / 0.5), 0, len(T["ys"]) - 1)); return float(T["Z"][j, i])
    PP = json.load(open(os.path.join(ROOT, "params.json"), encoding="utf-8"))
    rects = [f["r"] for B in (PP["west"], PP["east"]) for f in B["floors"]] + [[21.6, -2.1, 26.7, 0.0], PP["shed"]["r"]]
    def dbuild(x, y):                                                         # distance to the nearest building footprint
        return min(math.hypot(max(r_[0] - x, 0, x - r_[2]), max(r_[1] - y, 0, y - r_[3])) for r_ in rects)
    n1 = n2 = 0
    for i, t in enumerate(trees):
        x, y, z0 = t["p"]; h, r = t["h"], t["r"]
        if h > 10:                                                            # the cloud is cut off 13.6 m above the floor: real crowns go a little higher
            h = 16.5 + 4 * rng.random(); r = max(r, 3.8)                       # 12.5-16.5 m left the skyline too low against frames 175 / 522
        db = dbuild(x, y)
        if db < 1.0 or blocked(x, y, z0, h, r): continue
        # crowns stay out of the rooms (leaves came in through the walls, set1 rounds 7-8): r is the 90 % radius of the
        # crown, so it is held to 0.6 x the distance to the wall; tall trees may still spread above the roof
        r = min(r, max(0.6 * db, 0.5) if h < 10 else max(0.8 * db, 1.0))
        kind = _kind_of(t["rgb"], h, y, rng, mode)
        if y < -1.0 and h > 10 and kind != "cherry": kind = "evergreen" if rng.random() < 0.75 else "mid"
        v = int(rng.integers(0, NVAR)); pr = protos["%s_%d" % (kind, v)]
        sxy = h * float(np.clip(r / max(pr["r"] * h, 0.1), 0.25, 1.7))
        _inst("T_%03d_%s" % (i, kind), pr["coll"], c, (x, y, z0 - 0.15), (sxy, sxy, h), float(rng.uniform(0, 6.283))); n1 += 1
    # forest fill outside the scanned area (positions are random: nothing was measured there); hidden in the viewport, rendered
    x0, x1, y0, y1 = -75.0, 100.0, -62.0, 78.0; yy = y0
    while yy < y1:
        xx = x0
        while xx < x1:
            x, y = xx + (rng.random() - 0.5) * 4, yy + (rng.random() - 0.5) * 4
            scanned = (-22 < x < 48 and -7 < y < 30); dyard = max(0.0, max(-22 - x, x - 48, -7 - y, y - 30))
            if not scanned and rng.random() < min(1.0, 0.35 + dyard / 12):
                south = y < -6
                kind = str(rng.choice(["evergreen", "cedar", "mid"], p=[0.55, 0.25, 0.20])) if south else str(rng.choice(["mid", "evergreen", "fresh", "cedar", "cherry"], p=[0.38, 0.22, 0.28, 0.08, 0.04]))
                h = float(rng.uniform(10, 15)) if south else float(rng.uniform(6, 13))   # the skyline in frame 175 'front' is about 40 deg up
                if kind == "cedar": h = float(rng.uniform(13, 18))
                z0 = zat(x, y)
                if dbuild(x, y) > 5.0 and not blocked(x, y, z0, h, 3.5):
                    v = int(rng.integers(0, NVAR)); pr = protos["%s_%d" % (kind, v)]
                    sxy = h * (1.0 if kind == "cedar" else float(rng.uniform(0.9, 1.3)))
                    _inst("F_%04d_%s" % (n2, kind), pr["coll"], cf, (x, y, z0 - 0.3), (sxy, sxy, h), float(rng.uniform(0, 6.283)), hide_view=True); n2 += 1
            xx += 5.5
        yy += 5.5
    return {"scan_trees": n1, "forest": n2, "protos": {k: v["nleaf"] for k, v in protos.items()}}
