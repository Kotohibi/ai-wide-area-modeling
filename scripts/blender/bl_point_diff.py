r"""3D difference between the Blender model and a reference point cloud (SfM or filtered 3DGS, model frame).

Run inside Blender after `export_points.py` wrote <shared>\points_<name>.npy:
    import os; os.environ["BLENDER_SHARED"] = SH = r"<shared folder>"
    PDIFF = {"points": "points_sfm.npy", "collections": ["Building"], "tol": 0.15, "max_dist": 2.0}
    p = SH + r"\bl_point_diff.py"; exec(compile(open(p, encoding="utf-8").read(), p, "exec"), globals())

Two directions, both matter:
  points -> model   For every point near the modelled region: distance to the nearest model surface.
                    "fit"  = share within tol. Per object: mean SIGNED distance of its nearby points
                    (+ = points in front of the surface, along its normal) -> a systematic offset means the
                    object is shifted/too thin/too thick. Points farther than max_dist from any surface are
                    clustered (voxel `cluster` m) -> "unmodelled" candidates: things the model is missing.
  model -> points   Surfaces sampled every ~1/sqrt(density) m; share of samples with a point within `support`
                    m = "supported". Low support = geometry the data does not show (invented, or a smooth /
                    dark / glass surface that SfM cannot see - check the photos before deleting anything).
Options: box [x0,y0,z0,x1,y1,z1] limits the points, max_points (default 400k), density samples per m^2 (default 4),
support (default 2*tol), cluster (default 1.0), show (default True: coloured point objects in collection "Diff":
green = fit, yellow = within max_dist, red = unmodelled; hide them before rendering comparisons).
Writes <shared>\diff_<points stem>.json and returns a summary in `result`.
"""
import bpy, bmesh, os, json, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

SH = os.environ.get("BLENDER_SHARED", ""); cfg = globals().get("PDIFF", {})
tol = float(cfg.get("tol", 0.15)); maxd = float(cfg.get("max_dist", 2.0)); support = float(cfg.get("support", 2 * tol))
dens = float(cfg.get("density", 4.0)); cl = float(cfg.get("cluster", 1.0))
pts = np.load(os.path.join(SH, cfg.get("points", "points_sfm.npy")))
XYZ = pts[:, :3].astype(np.float64)
if cfg.get("box"):
    b = np.array(cfg["box"], float); XYZ = XYZ[np.all((XYZ >= b[:3]) & (XYZ <= b[3:]), axis=1)]

def objs_in(names):
    out = []
    def walk(c):
        out.extend(o for o in c.objects if o.type == 'MESH' and o.visible_get()); [walk(ch) for ch in c.children]
    if not names: return [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.visible_get() and not o.name.startswith("Diff_")]
    for n in names:
        c = bpy.data.collections.get(n)
        if c: walk(c)
    return [o for o in dict.fromkeys(out) if not o.name.startswith("Diff_")]

obs = objs_in(cfg.get("collections"))
dg = bpy.context.evaluated_depsgraph_get()
verts, polys, owner, areas = [], [], [], []
for oi, o in enumerate(obs):
    me = o.evaluated_get(dg).to_mesh(); mw = o.matrix_world; base = len(verts)
    verts.extend(mw @ v.co for v in me.vertices)
    for p in me.polygons:
        polys.append([base + i for i in p.vertices]); owner.append(oi); areas.append(p.area * abs(mw.determinant()) ** (2 / 3))
    o.evaluated_get(dg).to_mesh_clear()
if not polys: raise RuntimeError("no mesh faces in the given collections")
bvh = BVHTree.FromPolygons(verts, polys)
V = np.array([tuple(v) for v in verts])
lo, hi = V.min(0) - maxd, V.max(0) + maxd
X = XYZ[np.all((XYZ >= lo) & (XYZ <= hi), axis=1)]
mp = int(cfg.get("max_points", 400000))
if len(X) > mp: X = X[np.random.default_rng(0).choice(len(X), mp, replace=False)]

# ---- points -> model
dist = np.full(len(X), np.inf); sdist = np.zeros(len(X)); own = np.full(len(X), -1)
for i, p in enumerate(X):
    loc, nrm, fi, d = bvh.find_nearest(Vector(p), maxd)
    if loc is not None:
        dist[i] = d; own[i] = owner[fi]; sdist[i] = (Vector(p) - loc).dot(nrm)
fit = dist <= tol; near = np.isfinite(dist); far = ~near
per_obj = []
for oi, o in enumerate(obs):
    m = own == oi
    if m.sum() == 0: per_obj.append(dict(object=o.name, points=0)); continue
    per_obj.append(dict(object=o.name, points=int(m.sum()), fit=round(float((dist[m] <= tol).mean()), 3),
                        mean_signed=round(float(np.median(sdist[m])), 3), mean_abs=round(float(np.mean(dist[m])), 3)))

# unmodelled clusters
clusters = []
if far.any():
    F = X[far]; key = np.floor(F / cl).astype(np.int64)
    uk, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    order = np.argsort(-cnt)[:15]
    for k in order:
        if cnt[k] < 20: break
        Q = F[inv.ravel() == k]
        clusters.append(dict(center=np.round(Q.mean(0), 2).tolist(), points=int(cnt[k]), zmin=round(float(Q[:, 2].min()), 2), zmax=round(float(Q[:, 2].max()), 2)))

# ---- model -> points
kd = KDTree(len(X))
for i, p in enumerate(X): kd.insert(Vector(p), i)
kd.balance()
# only judge surfaces inside the region the points cover (a 500 m deck checked against a 60 m box is not "unsupported")
plo, phi = X.min(0) - support, X.max(0) + support
inbox = np.array([np.all(V[pv].max(0) >= plo) and np.all(V[pv].min(0) <= phi) for pv in polys])
A = np.array(areas) * inbox; tot = A.sum(); ns = min(200000, int(tot * dens) + 1)
rng = np.random.default_rng(1); fsel = rng.choice(len(polys), ns, p=A / tot)
sup_obj = np.zeros(len(obs)); cnt_obj = np.zeros(len(obs))
for fi in fsel:
    pv = polys[fi]; w = rng.dirichlet(np.ones(len(pv)))
    qa = (V[pv] * w[:, None]).sum(0)
    if np.any(qa < plo) or np.any(qa > phi): continue
    _, _, d = kd.find(Vector(tuple(qa)))
    cnt_obj[owner[fi]] += 1; sup_obj[owner[fi]] += d is not None and d <= support
for oi, r in enumerate(per_obj):
    if cnt_obj[oi]: r["supported"] = round(float(sup_obj[oi] / cnt_obj[oi]), 3)

# ---- display
if cfg.get("show", True):
    col = bpy.data.collections.get("Diff") or bpy.data.collections.new("Diff")
    if col.name not in bpy.context.scene.collection.children: bpy.context.scene.collection.children.link(col)
    for nm, m, rgb in (("Diff_fit", fit, (0.1, 0.8, 0.2, 1)), ("Diff_near", near & ~fit, (1, 0.8, 0.1, 1)), ("Diff_unmodelled", far, (1, 0.1, 0.1, 1))):
        old = bpy.data.objects.get(nm)
        if old: bpy.data.objects.remove(old)
        me = bpy.data.meshes.new(nm); me.from_pydata([tuple(p) for p in X[m][:150000]], [], []); ob = bpy.data.objects.new(nm, me); col.objects.link(ob)
        mat = bpy.data.materials.get(nm) or bpy.data.materials.new(nm); mat.diffuse_color = rgb; ob.color = rgb
        ng = bpy.data.node_groups.get(nm + "_gn")                      # vertices -> small spheres that render, with material
        if ng is None:
            ng = bpy.data.node_groups.new(nm + "_gn", 'GeometryNodeTree')
            ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
            ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
            gi = ng.nodes.new("NodeGroupInput"); go = ng.nodes.new("NodeGroupOutput")
            mtp = ng.nodes.new("GeometryNodeMeshToPoints"); mtp.inputs["Radius"].default_value = float(cfg.get("radius", 0.04))
            sm_ = ng.nodes.new("GeometryNodeSetMaterial"); sm_.inputs["Material"].default_value = mat
            ng.links.new(gi.outputs[0], mtp.inputs["Mesh"]); ng.links.new(mtp.outputs["Points"], sm_.inputs["Geometry"])
            ng.links.new(sm_.outputs["Geometry"], go.inputs[0])
        ob.modifiers.new("points", 'NODES').node_group = ng

summary = dict(points_checked=int(len(X)), fit=round(float(fit.mean()), 3), within_max_dist=round(float(near.mean()), 3),
               unmodelled=round(float(far.mean()), 3), tol=tol, max_dist=maxd, support=support,
               objects=sorted(per_obj, key=lambda r: -r.get("points", 0)), unmodelled_clusters=clusters)
json.dump(summary, open(os.path.join(SH, "diff_" + os.path.splitext(cfg.get("points", "points_sfm.npy"))[0] + ".json"), "w"), indent=1)
result = dict(summary, objects=summary["objects"][:12])
