import bpy, bmesh, json, math, os
import numpy as np

import os; SH = os.environ.get("BLENDER_SHARED", "")
S = PARAMS.get("S", 1.6)                           # metres per 3DGS unit (estimated)

# ------------------------------------------------------------------ route (leveled frame, 3DGS units)
P = np.array(json.load(open(SH + r"\path_level.json"))["path"])
s_, x_, y_, g_ = P[:, 0], P[:, 1], P[:, 2], P[:, 3]
u = (s_ - 266.0) / 180.0
x_ = np.polyval(np.polyfit(u, x_, 4), u); y_ = np.polyval(np.polyfit(u, y_, 4), u)
g_ = np.polyval(np.polyfit(u, g_, 2), u)
n_st = len(P)
tan = np.zeros((n_st, 2))
for i in range(n_st):
    a, b = max(i - 1, 0), min(i + 1, n_st - 1)
    t = np.array([x_[b] - x_[a], y_[b] - y_[a]]); tan[i] = t / np.linalg.norm(t)
nrm = np.stack([tan[:, 1], -tan[:, 0]], 1)                 # right of travel (+lat)

def at(s):
    i = float(np.interp(s, s_, np.arange(n_st)))
    i0 = int(math.floor(i)); i1 = min(i0 + 1, n_st - 1); f = i - i0
    p = np.array([x_[i0] * (1 - f) + x_[i1] * f, y_[i0] * (1 - f) + y_[i1] * f])
    t = tan[i0] * (1 - f) + tan[i1] * f; t /= np.linalg.norm(t)
    return p, t, np.array([t[1], -t[0]]), g_[i0] * (1 - f) + g_[i1] * f

# ------------------------------------------------------------------ parameters
# Decks: PARAMS["decks"] = [dict(name="A", cp=[(s, L, R), ...], ngird=4, soffit_s=240), ...]  (twin / multiple decks)
#        or the older single-deck form PARAMS["deck"] = [(s, L, R), ...] with "ngird" and "soffit_s".
# Pier columns: PARAMS["cols"] = [(s, c1, c2), ...] lateral column positions interpolated along s
#        (repeat an s with new values for a step change); a pier dict(s=..., c1=..., c2=..., skew=deg) overrides.
DECKS = PARAMS.get("decks") or [dict(name="", cp=PARAMS["deck"], ngird=PARAMS["ngird"], soffit_s=PARAMS.get("soffit_s"))]
def deck_lr(s, D=None):
    cp = (D or DECKS[0])["cp"]; ss = [d[0] for d in cp]
    return float(np.interp(s, ss, [d[1] for d in cp])), float(np.interp(s, ss, [d[2] for d in cp]))
def all_lr(s):
    lr = [deck_lr(s, D) for D in DECKS]
    return min(a for a, _ in lr), max(b for _, b in lr)
CAP_B, CAP_D, BEAR = PARAMS["cap_b"], PARAMS["cap_d"], PARAMS["bear"]
ZG, WEB, SLAB, BARR = PARAMS["zg"], PARAMS["web"], PARAMS["slab"], PARAMS["barr"]
PIERS = PARAMS["piers"]          # list of dict(s=..., [c1], [c2], [skew=deg])
COLS = PARAMS.get("cols")
S0, S1 = PARAMS["s0"], PARAMS["s1"]
def col_pos(s):
    if COLS:
        ss = [c[0] for c in COLS]
        return float(np.interp(s, ss, [c[1] for c in COLS])), float(np.interp(s, ss, [c[2] for c in COLS]))
    L, R = all_lr(s)                 # legacy rule: keep columns off the surveyed walking path (lat ~ 0)
    return (max(L + 2.2, 2.0) if s >= 245 else min(L + 2.2, -2.6)), R - 2.2

# ------------------------------------------------------------------ scene helpers
for c in list(bpy.data.collections):
    if c.name in ("Viaduct_Full", "Viaduct_V3"):
        for o in list(c.objects): bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(c)
col = bpy.data.collections.new("Viaduct_V3")
bpy.context.scene.collection.children.link(col)
for nm in ("Overpass",):
    lc = bpy.context.view_layer.layer_collection.children.get(nm)
    if lc: lc.exclude = True

def mat(name, rgb, rough=0.9, metal=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1); b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal; m.diffuse_color = (*rgb, 1)
    return m
CONC = mat("Concrete", (0.80, 0.78, 0.74)); STEEL = mat("PaintedSteel", (0.82, 0.83, 0.82), 0.6, 0.2)
ASPH = mat("Asphalt", (0.06, 0.06, 0.07)); SOFFIT = mat("SoffitPanel", (0.45, 0.40, 0.34))
BLD = mat("Building", (0.70, 0.72, 0.74)); GROUND = mat("Ground", (0.22, 0.24, 0.21))

def make(name, verts, faces, material):
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces); me.update()
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); ob.data.materials.append(material); col.objects.link(ob)
    return ob

def sweep(name, prof_fn, s0, s1, material):
    """prof_fn(s) -> list of (lat, h); swept along the route between s0 and s1"""
    idx = [i for i in range(n_st) if s0 <= s_[i] <= s1]
    V, F = [], []; k = len(prof_fn(s_[idx[0]]))
    for i in idx:
        for (l, h) in prof_fn(s_[i]):
            V.append(((x_[i] + nrm[i, 0] * l) * S, (y_[i] + nrm[i, 1] * l) * S, (g_[i] + h) * S))
    for a in range(len(idx) - 1):
        for j in range(k):
            j2 = (j + 1) % k
            F.append((a * k + j, a * k + j2, (a + 1) * k + j2, (a + 1) * k + j))
    F.append(tuple(range(k - 1, -1, -1))); F.append(tuple((len(idx) - 1) * k + j for j in range(k)))
    return make(name, V, F, material)

def prism(name, p, t, n, g, profile, a0, a1, material):
    V, F = [], []; k = len(profile)
    for a in (a0, a1):
        for (l, h) in profile:
            q = p + n * l + t * a
            V.append((q[0] * S, q[1] * S, (g + h) * S))
    for j in range(k):
        j2 = (j + 1) % k; F.append((j, j2, k + j2, k + j))
    F.append(tuple(range(k - 1, -1, -1))); F.append(tuple(k + j for j in range(k)))
    return make(name, V, F, material)

def rect(l0, l1, h0, h1): return [(l0, h0), (l1, h0), (l1, h1), (l0, h1)]

# ------------------------------------------------------------------ decks (one sweep set per deck)
# A deck may sit at its own height: D["zg"] = [[s, girder_underside], ...] (interpolated; default PARAMS["zg"]).
# Twin decks at different levels (upper / lower viaducts, ramps) are common - measure each with band_heights.py.
def zg_of(s, D):
    if D.get("zg"):
        return float(np.interp(s, [z[0] for z in D["zg"]], [z[1] for z in D["zg"]]))
    return ZG
def girder_lat(s, j, D):
    L, R = deck_lr(s, D); m = 1.2 if R - L < 11 else 1.8; ng = D.get("ngird", 4)
    return L + m + (R - L - 2 * m) * j / max(ng - 1, 1)
def igirder(s, j, D):
    lat = girder_lat(s, j, D); w = 0.06; Z = zg_of(s, D)
    return [(lat - 0.5, Z), (lat + 0.5, Z), (lat + 0.5, Z + 0.22), (lat + w, Z + 0.22), (lat + w, Z + WEB - 0.2),
            (lat + 0.45, Z + WEB - 0.2), (lat + 0.45, Z + WEB), (lat - 0.45, Z + WEB), (lat - 0.45, Z + WEB - 0.2),
            (lat - w, Z + WEB - 0.2), (lat - w, Z + 0.22), (lat - 0.5, Z + 0.22)]
for D in DECKS:
    pre = (D.get("name") or "") + ("_" if D.get("name") else "")
    ds0, ds1 = max(S0, D["cp"][0][0]), min(S1, D["cp"][-1][0])
    for j in range(D.get("ngird", 4)):
        sweep(f"{pre}Girder_{j+1}", (lambda s, j=j, D=D: igirder(s, j, D)), ds0, ds1, STEEL)
    sweep(f"{pre}DeckSlab", lambda s, D=D: rect(deck_lr(s, D)[0], deck_lr(s, D)[1], zg_of(s, D) + WEB, zg_of(s, D) + WEB + SLAB), ds0, ds1, CONC)
    sweep(f"{pre}Barrier_L", lambda s, D=D: rect(deck_lr(s, D)[0], deck_lr(s, D)[0] + 0.5, zg_of(s, D) + WEB + SLAB, zg_of(s, D) + WEB + SLAB + BARR), ds0, ds1, CONC)
    sweep(f"{pre}Barrier_R", lambda s, D=D: rect(deck_lr(s, D)[1] - 0.5, deck_lr(s, D)[1], zg_of(s, D) + WEB + SLAB, zg_of(s, D) + WEB + SLAB + BARR), ds0, ds1, CONC)
    if D.get("soffit_s") is not None and D["soffit_s"] < ds1:
        sweep(f"{pre}SoffitPanel", lambda s, D=D: rect(deck_lr(s, D)[0] + 0.3, deck_lr(s, D)[1] - 0.3, zg_of(s, D) - 0.12, zg_of(s, D) - 0.02), max(ds0, D["soffit_s"]), ds1, SOFFIT)
    for k_, s in enumerate(np.arange(ds0 + 3, ds1 - 2, 6.0)):
        p, t, n, g = at(s); Z = zg_of(s, D)
        for j in range(D.get("ngird", 4) - 1):
            l0, l1 = girder_lat(s, j, D) + 0.6, girder_lat(s, j + 1, D) - 0.6
            if l1 > l0: prism(f"{pre}Diaph_{k_}_{j}", p, t, n, g, rect(l0, l1, Z + 0.3, Z + WEB - 0.35), -0.08, 0.08, STEEL)
if PARAMS.get("road_strip", True):
    sweep("RoadStrip", lambda s: rect(-14.0, 28.0, -0.06, -0.02), S0, S1, ASPH)

# ------------------------------------------------------------------ portal piers
# Decks at the same height share one frame (global "cols"). A deck with its own "zg" gets its own frame at its
# height, with its own columns D["cols"] = [[s, c1, c2], ...] (e.g. a tall frame for an upper deck beside a low one).
def frame_profile(c1, c2, colw, L, R, cap_b):
    i1, i2 = c1 + colw / 2, c2 - colw / 2; ch = min(1.0, max(0.0, (i2 - i1) / 2 - 0.2), cap_b / 3)
    eL = min(L - 0.8, c1 - colw / 2); eR = max(R + 0.8, c2 + colw / 2)
    return [(c1 - colw / 2, 0), (i1, 0), (i1, cap_b - ch), (i1 + ch, cap_b), (i2 - ch, cap_b), (i2, cap_b - ch), (i2, 0),
            (c2 + colw / 2, 0), (c2 + colw / 2, cap_b), (eR, cap_b), (eR, cap_b + CAP_D), (eL, cap_b + CAP_D),
            (eL, cap_b), (c1 - colw / 2, cap_b)]
def deck_cols(s, D):
    c = D.get("cols")
    if not c: return None
    ss = [v[0] for v in c]
    return float(np.interp(s, ss, [v[1] for v in c])), float(np.interp(s, ss, [v[2] for v in c]))
for i, pr in enumerate(PIERS, 1):
    s = pr["s"]; p, t, n, g = at(s)
    sk = math.radians(pr.get("skew", 0.0))
    t2 = np.array([t[0] * math.cos(sk) - t[1] * math.sin(sk), t[0] * math.sin(sk) + t[1] * math.cos(sk)]); n2 = np.array([t2[1], -t2[0]])
    colw = pr.get("colw", 2.4)
    here = [D for D in DECKS if D["cp"][0][0] <= s <= D["cp"][-1][0]]
    if pr.get("decks"): here = [D for D in here if D.get("name") in pr["decks"]]   # e.g. {"s":196,"decks":["A"]}: this pier carries deck A only
    shared = [D for D in here if not D.get("zg") and not D.get("cols")]
    groups = ([shared] if shared else []) + [[D] for D in here if D.get("zg") or D.get("cols")]
    for gi, grp in enumerate(groups):
        lr = [deck_lr(s, D) for D in grp]; L, R = min(a for a, _ in lr), max(b for _, b in lr)
        own = deck_cols(s, grp[0]) if len(grp) == 1 else None
        c1, c2 = own if own else col_pos(s)
        if gi == 0: c1 = pr.get("c1", c1); c2 = pr.get("c2", c2)
        Z = min(zg_of(s, D) for D in grp); cap_b = Z - BEAR - CAP_D
        tag = "" if gi == 0 else "_" + (grp[0].get("name") or str(gi))
        prism(f"PortalPier_{i}{tag}", p, t2, n2, g, frame_profile(c1, c2, colw, L, R, cap_b), -1.4, 1.4, CONC)
        for D in grp:
            for j in range(D.get("ngird", 4)):
                lat = girder_lat(s, j, D)
                prism(f"Bearing_{i}_{D.get('name','')}{j}", p, t2, n2, g, rect(lat - 0.4, lat + 0.4, cap_b + CAP_D, zg_of(s, D)), -0.4, 0.4, CONC)
        for sd, lc in (("L", c1), ("R", c2)):
            prism(f"Footing_{i}{tag}{sd}", p, t2, n2, g, rect(lc - 1.7, lc + 1.7, -0.5, 0.15), -2.0, 2.0, CONC)

# ------------------------------------------------------------------ surrounding buildings (rough boxes) + ground
blds = json.load(open(SH + r"\buildings_final2.json"))
def lat_of_point(X, Y):
    d2 = (x_ - X) ** 2 + (y_ - Y) ** 2; i = int(np.argmin(d2))
    return float((X - x_[i]) * nrm[i, 0] + (Y - y_[i]) * nrm[i, 1]), float(math.sqrt(d2[i])), float(s_[i])
kept = []
for b in blds:
    ca, sa = math.cos(b["ang"]), math.sin(b["ang"]); bad = False
    for (dx, dy) in ((-1, -1), (1, -1), (1, 1), (-1, 1), (0, 0), (0, -1), (0, 1), (-1, 0), (1, 0)):
        lx, ly = dx * b["w"] / 2, dy * b["d"] / 2
        X = b["cx"] + lx * ca - ly * sa; Y = b["cy"] + lx * sa + ly * ca
        lt, dist, ss = lat_of_point(X, Y)
        if S0 - 10 <= ss <= S1 + 10 and -5.0 <= lt <= 17.5 and dist < 40: bad = True
    if not bad: kept.append(b)
blds = kept
# hand-picked outlines (manual_buildings.py) win over overlapping auto boxes
man = json.load(open(SH + r"\buildings_manual.json")) if os.path.exists(SH + r"\buildings_manual.json") else []
def in_manual(X, Y, pad=4.0):
    for mb in man:
        if mb["kind"] == "cyl":
            if (X - mb["cx"]) ** 2 + (Y - mb["cy"]) ** 2 < (mb["r"] + pad) ** 2: return True
        else:
            ca, sa = math.cos(mb["ang"]), math.sin(mb["ang"]); dx, dy = X - mb["cx"], Y - mb["cy"]
            if abs(dx * ca + dy * sa) < mb["w"] / 2 + pad and abs(-dx * sa + dy * ca) < mb["d"] / 2 + pad: return True
    return False
blds = [b for b in blds if not in_manual(b["cx"], b["cy"])] + [mb for mb in man if mb["kind"] == "box"]
for k_, mb in enumerate([mb for mb in man if mb["kind"] == "cyl"]):
    n = 32; V = [(mb["cx"] * S + mb["r"] * S * math.cos(2 * math.pi * i / n), mb["cy"] * S + mb["r"] * S * math.sin(2 * math.pi * i / n), z)
                 for z in (0.0, mb["h"] * S) for i in range(n)]
    F = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    make(f"RoundBuilding_{mb.get('name', k_)}", V, F, BLD)
for k_, b in enumerate(blds):
    ca, sa = math.cos(b["ang"]), math.sin(b["ang"])
    V, F = [], []
    for (dx, dy) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        lx, ly = dx * b["w"] / 2, dy * b["d"] / 2
        X = b["cx"] + lx * ca - ly * sa; Y = b["cy"] + lx * sa + ly * ca
        V.append((X * S, Y * S, 0.0))
    for q in list(V): V.append((q[0], q[1], b["h"] * S))
    F = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    make(f"Building_{k_+1}", V, F, BLD)
xs, ys = P[:, 1] * S, P[:, 2] * S
gx0, gx1, gy0, gy1 = xs.min() - 200, xs.max() + 200, ys.min() - 200, ys.max() + 200
make("Ground", [(gx0, gy0, -0.12), (gx1, gy0, -0.12), (gx1, gy1, -0.12), (gx0, gy1, -0.12)], [(0, 1, 2, 3)], GROUND)

result = {"objects": len(col.objects), "S": S, "buildings": len(blds), "piers": len(PIERS)}
