r"""Find z-fighting candidates: faces of visible meshes that face the SAME way, lie in the same plane (within tol)
and overlap. Opposite-facing coincident faces (a box sitting on another) are not reported.

Run inside Blender:
    COPLANAR = {"skip": ["Trees", "Hedges"], "tol": 0.004, "min_overlap": 0.02, "examples": 4}
    p = SH + r"\bl_coplanar.py"; exec(compile(open(p, encoding="utf-8").read(), p, "exec"), globals())
result: {"faces_checked", "pairs": [{"a", "b", "area", "examples": [[area, normal, centre], ...]}, ...]}
Each example is the overlap rectangle's area (m^2), the shared normal and the overlap centre (world). Many hits are
hidden (inside walls, under roofs); judge from the centre/normal whether the face can be seen, then fix those by
moving one surface off the other (1 cm is enough at building scale) or by not generating the hidden duplicate.
"""
import bpy, numpy as np
from collections import defaultdict

cfg = globals().get("COPLANAR", {})
skip = set(cfg.get("skip", [])); tol = cfg.get("tol", 0.004); mino = cfg.get("min_overlap", 0.02); nex = cfg.get("examples", 4)
dg = bpy.context.evaluated_depsgraph_get(); recs = []
for o in bpy.data.objects:
    if o.type != 'MESH' or o.name in skip or not o.visible_get(): continue
    oe = o.evaluated_get(dg); me = oe.to_mesh(); M = o.matrix_world; R = M.to_3x3()
    co = np.array([tuple(M @ v.co) for v in me.vertices])
    for f in me.polygons:
        if f.area < 0.01: continue
        n = (R @ f.normal).normalized(); vs = co[list(f.vertices)]
        recs.append((o.name, tuple(round(c, 3) for c in n), float(np.dot(tuple(n), vs[0])), vs.min(0), vs.max(0)))
    oe.to_mesh_clear()
buck = defaultdict(list)
for i, r in enumerate(recs): buck[(r[1], round(r[2] / (tol * 1.25)))].append(i)
pairs = defaultdict(list)
for ids in buck.values():
    for a in range(len(ids)):
        ra = recs[ids[a]]; ax = int(np.argmax(np.abs(ra[1])))
        for b in range(a + 1, len(ids)):
            rb = recs[ids[b]]
            if abs(ra[2] - rb[2]) > tol: continue
            lo = np.maximum(ra[3], rb[3]); hi = np.minimum(ra[4], rb[4]); ov = np.delete(hi - lo, ax)
            if ov.min() > mino:
                pairs[tuple(sorted((ra[0], rb[0])))].append((round(float(ov[0] * ov[1]), 3), ra[1], [round(float(c), 2) for c in (lo + hi) / 2]))
out = []
for k, v in sorted(pairs.items(), key=lambda t: -sum(e[0] for e in t[1])):
    out.append({"a": k[0], "b": k[1], "area": round(sum(e[0] for e in v), 2), "examples": sorted(v, key=lambda e: -e[0])[:nex]})
result = {"faces_checked": len(recs), "pairs": out[:cfg.get("max_pairs", 30)]}
