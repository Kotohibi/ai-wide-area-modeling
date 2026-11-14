# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
"""Build the precinct around the gate: ground surfaces (slab paths, lawns, beds, parking lines, bollards), walls,
hedges, shrubs, trees, stoneworks, the main hall (hondō), the corridor, the residence (kuri), the garage, the bell
tower and the west building, from site_params.json. Run inside Blender after build_temple.py (the gate).
Rebuilds only its own collections. Measurements: see the notes in site_params.json."""
import bpy, json, math, os
TOOLS = globals().get("TEMPLE_TOOLS", __import__("os").path.join(__import__("os").environ.get("PROJECT_DIR", "."), r"tools"))
p = os.path.join(TOOLS, "temple_lib.py"); exec(compile(open(p, encoding="utf-8").read(), p, "exec"), globals())
S = json.load(open(os.path.join(TOOLS, "site_params.json"), encoding="utf-8"))

cols = reset_collections(["Temple_Ground", "Temple_Site", "Temple_Vegetation", "Temple_Hall", "Temple_Corridor",
                          "Temple_Residence", "Temple_Garage", "Temple_BellTower", "Temple_WestBldg"])
ID = Frame(0, 0)

# ================================================================ ground
gd = S["ground"]; ge = S["ground_extent"]; mb = MB(ID)
mb.add_world([(ge["x"][0], ge["y"][0], 0), (ge["x"][1], ge["y"][0], 0), (ge["x"][1], ge["y"][1], 0), (ge["x"][0], ge["y"][1], 0)], [(0, 1, 2, 3)], "asphalt")
def pad(r, z, m): mb.aabb(r["x"][0], r["y"][0], z - 0.02, r["x"][1], r["y"][1], z, m)
pad(gd["plaza"], 0.02, "brick")
for r in gd["lawns"]: pad(r, 0.03, "lawn_dry")
for r in gd["gravel"]: pad(r, 0.03, "gravel")
for sp in gd["slab_paths"]:                                           # stone slab paths in running bond, with joints
    (x0, x1), (y0, y1), (sw, sd) = sp["x"], sp["y"], sp["slab"]
    mb.aabb(x0, y0, 0.0, x1, y1, 0.03, "stone2")                      # joint colour underneath
    nrow = max(1, round((y1 - y0) / sd)); dy = (y1 - y0) / nrow
    for j in range(nrow):
        off = (j % 2) * sw / 2; x = x0 - off; k = 0
        while x < x1 - 1e-3:
            xa, xb = max(x0, x), min(x1, x + sw)
            if xb - xa > 0.08:
                mb.aabb(xa + 0.012, y0 + j * dy + 0.012, 0.03, xb - 0.012, y0 + (j + 1) * dy - 0.012, 0.05, "paving" if (j + k) % 3 else "stone")
            x += sw; k += 1
    for x in (x0, x1): mb.aabb(x - 0.09, y0, 0, x + 0.09, y1, 0.12, "granite")      # kerbs
for r in gd["lawns"]:                                                 # granite edging between lawn and plaza
    mb.aabb(r["x"][0], r["y"][0] - 0.08, 0, r["x"][1], r["y"][0] + 0.08, 0.1, "granite")
for bd_ in gd.get("beds", []):                                       # soil bed around the bell tower base
    Fb_ = Frame(*bd_["c"], bd_["rot"]); m2 = MB(Fb_); h_ = bd_["hu"]
    m2.aabb(-h_, -h_, 0.0, h_, h_, 0.06, "soil"); mb.v, mb.f, mb.m = mb.v, mb.f, mb.m
    for s in (-1, 1):
        m2.aabb(-h_, s * h_ - 0.07, 0, h_, s * h_ + 0.07, 0.15, "granite"); m2.aabb(s * h_ - 0.07, -h_, 0, s * h_ + 0.07, h_, 0.15, "granite")
    m2.build("Bed", cols["Temple_Ground"])
for L in gd["lot_lines"]:
    for y in L["ys"]: mb.aabb(L["x"][0], y - 0.06, 0.0, L["x"][1], y + 0.06, 0.012, "line")
for B in gd["lot_baselines"]: mb.aabb(B["x"] - 0.06, B["y"][0], 0.0, B["x"] + 0.06, B["y"][1], 0.012, "line")
mb.build("Ground", cols["Temple_Ground"])

# ================================================================ walls, planters, bollards, stoneworks
mb = MB(ID)
for w_ in S["walls"]:
    (x0, y0), (x1, y1) = w_["p0"], w_["p1"]; h, t = w_["h"], w_["t"]
    mb.beam((x0, y0, h / 2), (x1, y1, h / 2), t, h, "wall")
    mb.beam((x0, y0, h + 0.1), (x1, y1, h + 0.1), t + 0.35, 0.2, "tile_dk")
    mb.beam((x0, y0, 0.15), (x1, y1, 0.15), t + 0.06, 0.3, "granite")
for pl in S["planters"]:
    c, r = pl["c"], pl["r"]
    pts = [(c[0] + r * math.cos(math.pi / 8 + k * math.pi / 4), c[1] + r * math.sin(math.pi / 8 + k * math.pi / 4)) for k in range(8)]
    mb.poly_slab(pts, 0, 0.35, "granite")
    pts2 = [(c[0] + (r - 0.15) * math.cos(math.pi / 8 + k * math.pi / 4), c[1] + (r - 0.15) * math.sin(math.pi / 8 + k * math.pi / 4)) for k in range(8)]
    mb.poly_slab(pts2, 0.35, 0.38, "soil")
for bl in S.get("bollards", []):
    (x0, y0), (x1, y1) = bl["p0"], bl["p1"]; n = bl["n"]; w = bl["w"]
    for i in range(n):
        t = i / max(1, n - 1); x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        mb.aabb(x - w / 2, y - w / 2, 0, x + w / 2, y + w / 2, bl["h"], "granite")
        mb.box((x, y, bl["h"] + 0.04), (w * 0.8, w * 0.8, 0.08), "granite", math.pi / 4)
mb.build("Site_Walls", cols["Temple_Site"])
mb = MB(ID)
for pg in S.get("pagodas", []):
    x, y = pg["p"]; b = pg["base"]
    mb.aabb(x - b / 2, y - b / 2, 0, x + b / 2, y + b / 2, 0.45, "granite"); z = 0.45
    mb.aabb(x - b * 0.35, y - b * 0.35, z, x + b * 0.35, y + b * 0.35, z + 0.7, "granite"); z += 0.7
    n = pg["tiers"]; th = (pg["h"] - z - 0.6) / n
    for k in range(n):
        w = b * (0.75 - 0.3 * k / n)
        mb.aabb(x - w * 0.35, y - w * 0.35, z, x + w * 0.35, y + w * 0.35, z + th * 0.55, "granite")
        mb.aabb(x - w / 2, y - w / 2, z + th * 0.55, x + w / 2, y + w / 2, z + th, "stone"); z += th
    mb.cyl(x, y, z, z + 0.6, 0.08, "granite", 8, 0.05)
for ln in S.get("lanterns", []):                                     # kanadōrō: bronze lantern on a two-tier stone base
    x, y = ln["p"]; h = ln["h"]
    mb.aabb(x - 0.55, y - 0.55, 0, x + 0.55, y + 0.55, 0.3, "granite"); mb.aabb(x - 0.4, y - 0.4, 0.3, x + 0.4, y + 0.4, 0.75, "granite")
    mb.cyl(x, y, 0.75, 0.95, 0.38, "bronze", 16, 0.3)                 # lotus base
    mb.cyl(x, y, 0.95, h * 0.62, 0.1, "bronze", 10)                   # shaft
    mb.cyl(x, y, h * 0.62, h * 0.72, 0.42, "bronze", 16, 0.45)        # fire box (bowl)
    mb.cyl(x, y, h * 0.72, h * 0.88, 0.45, "bronze", 16, 0.42)
    mb.cyl(x, y, h * 0.88, h * 0.97, 0.55, "bronze", 16, 0.08)        # cap
    mb.blob(x, y, h, 0.07, 0.07, 0.09, "bronze", 8, 5)
for st_ in S.get("statues", []):
    x, y = st_["p"]; ph, h = st_["pedestal_h"], st_["h"]
    mb.aabb(x - 0.7, y - 0.7, 0, x + 0.7, y + 0.7, ph * 0.6, "granite"); mb.aabb(x - 0.5, y - 0.5, ph * 0.6, x + 0.5, y + 0.5, ph, "granite")
    mb.cyl(x, y, ph, ph + 0.25, 0.5, "bronze", 14, 0.35)
    mb.cyl(x, y, ph + 0.25, ph + h * 0.78, 0.26, "bronze", 12, 0.2)
    mb.blob(x, y, ph + h * 0.86, 0.15, 0.15, 0.19, "bronze", 10, 6)
    mb.blob(x, y - 0.05, ph + h * 0.86, 0.04, 0.3, 0.32, "bronze", 8, 5)
for rk in S.get("rocks", []):
    x, y = rk["p"]; mb.blob(x, y, rk["h"] * 0.4, rk["r"], rk["r"] * 0.8, rk["h"] * 0.6, "stone", 9, 5, 0.18, int(x * 10))
mb.build("Stoneworks", cols["Temple_Site"])

# ================================================================ hedges, shrubs, trees
mb = MB(ID)
for hd in S["hedges"]: hedge(mb, hd["p0"], hd["p1"], hd["h"], hd["t"])
for row in S["shrub_rows"]:
    (x0, y0), (x1, y1) = row["p0"], row["p1"]; L = math.dist(row["p0"], row["p1"]); n = int(L / row["pitch"])
    for i in range(n + 1):
        t = i / max(1, n); mb.blob(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, row["r"] * 0.9, row["r"], row["r"], row["r"] * 0.85, "foliage_dk", 10, 6, 0.06, i)
mb.build("Hedges", cols["Temple_Vegetation"], smooth=True)
mb = MB(ID)
for i, t in enumerate(S["trees"]): tree(mb, t["p"][0], t["p"][1], t["kind"], t["r"], t["h"], seed=i * 7)
mb.build("Trees", cols["Temple_Vegetation"], smooth=True)

# ================================================================ main hall
H = S["hall"]; F = Frame(*H["center"], H.get("rot", 0)); mb = MB(F); fz = H["floor_z"]
pd = H["podium"]; vr = H["veranda"]; bd = H["body"]; R = H["roof"]
hu, v0, v1 = bd["hu"], bd["v0"], bd["v1"]; zn, zk, zt = bd["nageshi_z"], bd["kashira_z"], bd["top_z"]
mb.aabb(-pd["hu"], pd["v0"], -0.02, pd["hu"], pd["v1"], pd["h"], "stone")
mb.aabb(-vr["hu"], vr["v0"], fz - 0.12, vr["hu"], vr["v1"], fz, "wood_lt")                        # veranda floor
mb.aabb(-vr["hu"] - 0.02, vr["v0"] - 0.02, fz - 0.3, vr["hu"] + 0.02, vr["v0"] + 0.06, fz - 0.12, "wood")   # edge beam
mb.aabb(-hu + 0.2, v0 + 0.2, pd["h"], hu - 0.2, v1 - 0.2, fz - 0.12, "wood")                       # dark underfloor
for u in [-vr["hu"] + 0.15 + k * 1.0 for k in range(int(2 * vr["hu"] / 1.0) + 1)]:
    mb.aabb(u - 0.07, vr["v0"] + 0.1, pd["h"], u + 0.07, vr["v0"] + 0.24, fz - 0.3, "wood")
    mb.aabb(u - 0.12, vr["v0"] + 0.05, pd["h"], u + 0.12, vr["v0"] + 0.29, pd["h"] + 0.12, "granite")
for v in [vr["v0"] + 0.15 + k * 1.0 for k in range(int((vr["v1"] - vr["v0"]) / 1.0) + 1)]:
    for su in (-1, 1): mb.aabb(su * (vr["hu"] - 0.24) - 0.07, v - 0.07, pd["h"], su * (vr["hu"] - 0.24) + 0.07, v + 0.07, fz - 0.3, "wood")
# railing (kōran): posts, three rails, giboshi finials where it stops at the steps
rh = vr["rail_h"]; ru, rv0, rv1 = vr["hu"] - 0.1, vr["v0"] + 0.1, vr["v1"]
segs = [((-ru, rv1), (-ru, rv0)), ((-ru, rv0), (vr["gap_u"][0], rv0)), ((vr["gap_u"][1], rv0), (ru, rv0)), ((ru, rv0), (ru, rv1))]
for a, b in segs:
    for zz, hh in ((fz + 0.12, 0.08), (fz + 0.42, 0.05), (fz + rh, 0.07)):
        mb.beam(F.W(a[0], a[1], zz), F.W(b[0], b[1], zz), 0.07 if zz < fz + rh else 0.09, hh, "wood")
    Ls = math.dist(a, b); n = max(1, int(Ls / 0.95))
    for i in range(n + 1):
        q = (a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n)
        mb.aabb(q[0] - 0.045, q[1] - 0.045, fz, q[0] + 0.045, q[1] + 0.045, fz + rh + 0.04, "wood")
for gu_ in vr["gap_u"]:
    mb.aabb(gu_ - 0.08, rv0 - 0.08, fz, gu_ + 0.08, rv0 + 0.08, fz + rh + 0.15, "wood")
    mb.blob(gu_, rv0, fz + rh + 0.27, 0.09, 0.09, 0.12, "bronze", 10, 6)
# body: pillars and beams
cols_f = bd["front_cols"]
nside = max(1, round((v1 - v0) / bd["side_pitch"])); side_vs = [v0 + k * (v1 - v0) / nside for k in range(nside + 1)]
for u in cols_f:
    for v in (v0, v1): mb.cyl(u, v, fz, zt, 0.17, "wood", 12)
for v in side_vs[1:-1]:
    for u in (-hu, hu): mb.cyl(u, v, fz, zt, 0.17, "wood", 12)
for zz, hh, m_ in ((fz, 0.2, "wood"), (zn, 0.13, "wood"), (zn + 0.13, zk - zn - 0.13, "plaster"), (zk, zt - zk, "wood")):
    t_ = 0.1 if m_ == "wood" else 0.06
    for v in (v0, v1): mb.aabb(-hu - (0.1 if m_ == "wood" else 0), v - t_, zz, hu + (0.1 if m_ == "wood" else 0), v + t_, zz + hh, m_)
    for u in (-hu, hu): mb.aabb(u - t_, v0, zz, u + t_, v1, zz + hh, m_)
# front: centre lattice doors, green panel doors, cusped windows on white walls in the outer bays; back plain
wn = bd["window"]
for ua, ub in zip(cols_f[:-1], cols_f[1:]):
    mid = (ua + ub) / 2; a_, b_ = ua + 0.17, ub - 0.17
    if abs(mid) < 0.5:
        lattice_door(mb, a_, b_, fz + 0.2, zn, v0, -1, leaves=4)
    elif abs(mid) < 3.5:
        panel_door(mb, a_, b_, fz + 0.2, zn, v0, -1, leaves=2)
    else:
        wall_quad(mb, a_, b_, fz + 0.2, zn, v0 - 0.02, "plaster", -1)
        mb.aabb(a_, v0 - 0.08, fz + 0.2, b_, v0 - 0.02, fz + 0.75, "wood")                       # wainscot
        mb.aabb(a_, v0 - 0.09, wn["z0"] - 0.12, b_, v0 - 0.02, wn["z0"] - 0.04, "wood")             # sill rail
        kato_window(mb, mid, v0 - 0.03, wn["z0"], wn["z1"], wn["w"], -1)
    wall_quad(mb, ua, ub, fz, zt, v1 + 0.02, "plaster", 1)
# sides (rotated frame: u' = v, v' = -u)
Fs = Frame(*H["center"], H.get("rot", 0) + 90); ms = MB(Fs)
for su, face in ((1, -1), (-1, 1)):
    vv = -su * hu
    for va, vb in zip(side_vs[:-1], side_vs[1:]):
        a_, b_ = va + 0.17, vb - 0.17
        if abs((va + vb) / 2 - v0) < 2.5:
            ms.aabb(a_, vv - 0.06, fz + 0.2, b_, vv + 0.06, zn, "plaster"); kato_window(ms, (va + vb) / 2, vv + face * 0.07, wn["z0"], wn["z1"], wn["w"] * 0.9, face)
        else:
            panel_door(ms, a_, b_, fz + 0.2, zn, vv, face, leaves=2)
# brackets (funa-hijiki / demitsudo) on every pillar, purlins, soffit
bz0, bz1 = H["brackets_z"]
for u in cols_f:
    for v, s in ((v0, -1), (v1, 1)):
        mb.box((u, v, bz0 + 0.08), (0.36, 0.36, 0.16), "wood"); mb.box((u, v + s * 0.15, bz0 + 0.24), (1.0, 0.24, 0.16), "wood")
        for du in (-0.38, 0, 0.38): mb.box((u + du, v + s * 0.15, bz1 - 0.02), (0.22, 0.24, 0.14), "wood")
for v in side_vs:
    for u, s in ((-hu, -1), (hu, 1)):
        mb.box((u, v, bz0 + 0.08), (0.36, 0.36, 0.16), "wood"); mb.box((u + s * 0.15, v, bz0 + 0.24), (0.24, 1.0, 0.16), "wood")
for (a0, b0, a1, b1) in ((-hu - 0.6, v0 - 0.6, hu + 0.6, v0 - 0.4), (-hu - 0.6, v1 + 0.4, hu + 0.6, v1 + 0.6),
                         (-hu - 0.6, v0 - 0.6, -hu - 0.4, v1 + 0.6), (hu + 0.4, v0 - 0.6, hu + 0.6, v1 + 0.6)):
    mb.aabb(a0, b0, bz1 + 0.05, a1, b1, bz1 + 0.25, "wood")
mb.aabb(-hu - 0.6, v0 - 0.6, bz1 + 0.2, hu + 0.6, v1 + 0.6, bz1 + 0.25, "wood")
# steps, landing, platform, porch
st = H["steps"]; n = st["n"]; rise = (fz - st["z0"]) / n; run = (st["v1"] - st["v0"]) / n
mb.aabb(-st["landing_hu"], st["landing_v0"], -0.02, st["landing_hu"], st["v0"], st["z0"], "granite")
for k in range(n):
    mb.aabb(-st["hu"], st["v0"] + k * run, st["z0"], st["hu"], st["platform_v1"], st["z0"] + (k + 1) * rise, "stone" if k % 2 else "stone2")
for su in (-1, 1):
    mb.aabb(su * st["hu"], st["v0"], 0, su * (st["hu"] + 0.4), st["platform_v1"], fz - 0.2, "granite")
pc = H["porch"]; pw = pc["w"]
for u in pc["cols_u"]:
    mb.aabb(u - 0.3, pc["col_v"] - 0.3, pc["col_z0"] - 0.25, u + 0.3, pc["col_v"] + 0.3, pc["col_z0"], "granite")
    mb.box((u, pc["col_v"], (pc["col_z0"] + pc["col_top"]) / 2), (pw, pw, pc["col_top"] - pc["col_z0"]), "wood", math.pi / 4 * 0)
    mb.box((u, pc["col_v"], (pc["col_z0"] + pc["col_top"]) / 2), (pw * 1.1, pw * 0.7, pc["col_top"] - pc["col_z0"]), "wood")   # chamfer hint
    mb.beam(F.W(u, pc["col_v"], pc["col_top"] - 0.5), F.W(u, v0, zk - 0.1), 0.16, 0.28, "wood")                        # ebi-kōryō
    mb.aabb(u - 0.2, pc["col_v"] - 0.2, pc["col_top"], u + 0.2, pc["col_v"] + 0.2, pc["col_top"] + 0.15, "wood")        # bearing block
z0b, z1b = pc["beam_z"]
mb.aabb(pc["cols_u"][0], pc["col_v"] - 0.11, z0b, pc["cols_u"][1], pc["col_v"] + 0.11, z1b, "wood")                    # kōryō
for su in (-1, 1):                                                                                                     # kibana (carved ends)
    mb.aabb(su * abs(pc["cols_u"][0]) - 0.3 * (su < 0) - 0.05, pc["col_v"] - 0.1, z1b - 0.05, su * abs(pc["cols_u"][0]) + 0.3 * (su > 0) + 0.05, pc["col_v"] + 0.1, z1b + 0.25, "wood_lt")
mb.aabb(pc["cols_u"][0] - 0.4, pc["col_v"] - 0.12, pc["col_top"] - 0.3, pc["cols_u"][1] + 0.4, pc["col_v"] + 0.12, pc["col_top"], "wood")
mb.box((0, pc["col_v"], (z1b + pc["col_top"] - 0.3) / 2), (0.7, 0.16, pc["col_top"] - 0.3 - z1b), "wood_lt")            # kaerumata
mb.aabb(-pc["hu"] + 0.3, pc["col_v"] - 0.5, pc["col_top"] + 0.15, pc["hu"] - 0.3, pc["col_v"] + 0.2, pc["col_top"] + 0.3, "wood")
mb.aabb(-0.65, v0 - 1.0, fz, 0.65, v0 - 0.45, fz + 0.65, "wood_lt"); mb.aabb(-0.7, v0 - 1.05, fz + 0.62, 0.7, v0 - 0.4, fz + 0.7, "wood")   # offering box
mb.build("Hall_Body", cols["Temple_Hall"]); ms.build("Hall_Sides", cols["Temple_Hall"])
def porch_z(u, v):
    """Porch (kōhai) roof: meets the main roof 4 cm ABOVE its surface at v_join, then runs flat under it to its back
    edge (hidden). The corner upturn fades out towards the join so the back corners stay under the main roof."""
    zj = irimoya_z(u, pc["v_join"], R)[0] + 0.04
    s = (v - pc["v_tip"]) / (pc["v_join"] - pc["v_tip"]); z = pc["z_tip"] + (zj - pc["z_tip"]) * g(s, 1.25)
    return z + 0.25 * (abs(u) / pc["hu"]) ** 3 * (1 - max(0.0, min(1.0, s))), True
def hall_main_z(u, v):
    """Main roof, pushed down under the porch roof: otherwise its front eave (and the eave's brown wood edge) cuts
    through the porch roof surface."""
    z, front = irimoya_z(u, v, R)
    if abs(u) < pc["hu"] - 0.1 and v < pc["v_join"] - 0.05:
        z = min(z, porch_z(u, v)[0] - 0.35)
    return z, front
gu_ = R.get("gable_u", 0.0)
roof_field("Hall_Roof", cols["Temple_Hall"], F, hall_main_z, (-R["hu"], R["hu"]), (-R["hv"], R["hv"]), R, step=0.08,
           extra_u=(gu_, -gu_, gu_ + 0.01, -gu_ - 0.01, pc["hu"] - 0.1, -pc["hu"] + 0.1, pc["hu"] - 0.02, -pc["hu"] + 0.02))
roof_field("Hall_PorchRoof", cols["Temple_Hall"], F, porch_z, (-pc["hu"], pc["hu"]), (pc["v_tip"], pc["v_join"] + 0.5), {"thick": 0.24}, step=0.08)
mb = MB(F)
irimoya_trim(mb, R)
rafters(mb, R, lambda u, v: hall_main_z(u, v)[0], hu + 0.6, v1 + 0.6, sides=(True, True, True, True), pitch=0.22)
for tier, dz, frac in ((0, 0.0, 1.0), (1, 0.14, 0.45)):              # two-tier porch rafters (jidaruki + hien-daruki)
    for i in range(int(2 * (pc["hu"] - 0.1) / 0.22) + 1):
        u = -pc["hu"] + 0.1 + i * 0.22; vt = pc["v_tip"] + 0.02 + (1 - frac) * 0.0
        va = vt if tier else vt + 0.5; vb = pc["col_v"] + 0.1 if tier == 0 else vt + 1.2
        mb.beam(F.W(u, va, porch_z(u, va)[0] - 0.3 - dz), F.W(u, vb, porch_z(u, vb)[0] - 0.3 - dz), 0.07, 0.09, "wood_lt")
mb.build("Hall_RoofParts", cols["Temple_Hall"])

# ================================================================ corridor hall -> residence
C = S["corridor"]; mb = MB(ID)
x0, x1 = C["x"]; y0, y1 = C["y"]; fzc = C["floor_z"]
mb.aabb(x0, y0, 0, x1, y1, fzc, "wood"); mb.aabb(x0, y0 + 0.3, fzc, x1, y1 - 0.3, C["z_eave"] - 0.3, "plaster")
for x in [x0 + k * (x1 - x0) / 3 for k in range(4)]:
    for y in (y0 + 0.3, y1 - 0.3): mb.cyl(x, y, fzc, C["z_eave"] - 0.2, 0.12, "wood", 10)
mb.build("Corridor_Body", cols["Temple_Corridor"])
Fc = Frame((x0 + x1) / 2, (y0 + y1) / 2)
Rc = {"hv": (y1 - y0) / 2 + 0.6, "z_eave": C["z_eave"], "z_ridge": C["z_ridge"], "p": 1.0, "thick": 0.18}
roof_field("Corridor_Roof", cols["Temple_Corridor"], Fc, lambda u, v: gable_z(u, v, Rc), (-(x1 - x0) / 2, (x1 - x0) / 2), (-Rc["hv"], Rc["hv"]), Rc, step=0.1, mats=("tile_gray", "wood"))

# ================================================================ bell tower (splayed pillars, river-stone base)
B = S["bell_tower"]; Fb = Frame(*B["center"], B["rot"]); mb = MB(Fb); bh, bu = B["base_h"], B["base_hu"]
mb.aabb(-bu, -bu, 0, bu, bu, bh - 0.01, "granite"); mb.aabb(-bu - 0.1, -bu - 0.1, bh - 0.18, bu + 0.1, bu + 0.1, bh, "granite")   # base top 1 cm below the cap: no coplanar tops
import random as _r; rnd = _r.Random(3)
for s in (-1, 1):                                                     # river stones set into the base faces
    for k in range(9):
        for row in range(2):
            t = -bu + 0.25 + k * (2 * bu - 0.5) / 8 + (row * 0.22); z = 0.25 + row * 0.38
            mb.blob(t, s * bu, z, 0.22, 0.08, 0.17, "riverstone", 8, 5, 0.1, k + row * 10 + (s > 0) * 50)
            mb.blob(s * bu, t, z, 0.08, 0.22, 0.17, "riverstone", 8, 5, 0.1, k + row * 10 + (s > 0) * 70)
cu = B["col_u"]; ct = B["col_top"]; spl = 0.12                         # pillars lean inward (uchikorobi)
for su in (-1, 1):
    for sv in (-1, 1):
        mb.aabb(su * cu - 0.25, sv * cu - 0.25, bh, su * cu + 0.25, sv * cu + 0.25, bh + 0.2, "granite")
        mb.beam(Fb.W(su * cu, sv * cu, bh + 0.2), Fb.W(su * (cu - spl), sv * (cu - spl), ct), 0.28, 0.28, "wood")
for zz in (bh + 0.8, ct - 0.3):
    c_ = cu - spl * (zz - bh) / (ct - bh)
    for s in (-1, 1):
        mb.aabb(-c_ - 0.25, s * c_ - 0.08, zz, c_ + 0.25, s * c_ + 0.08, zz + 0.2, "wood")
        mb.aabb(s * c_ - 0.08, -c_ - 0.25, zz, s * c_ + 0.08, c_ + 0.25, zz + 0.2, "wood")
mb.aabb(-cu - 0.6, -cu - 0.6, ct, cu + 0.6, cu + 0.6, ct + 0.25, "wood")
for su in (-1, 1):
    for sv in (-1, 1): mb.box((su * (cu - spl), sv * (cu - spl), ct + 0.35), (0.7, 0.7, 0.2), "wood")
mb.cyl(0, 0, ct - 1.7, ct - 0.35, 0.45, "bronze", 20, 0.36)
mb.cyl(0, 0, ct - 1.75, ct - 1.65, 0.48, "bronze", 20)
mb.cyl(0, 0, ct - 0.35, ct - 0.1, 0.12, "bronze", 10)
Rb = B["roof"]; irimoya_trim(mb, Rb)
mb.build("BellTower_Body", cols["Temple_BellTower"])
irimoya_roof("BellTower_Roof", cols["Temple_BellTower"], Fb, Rb, step=0.06, amp=0.025)

# ================================================================ houses (residence, west building): ground floor boxes + optional upper floor
def face_frames(cx, cy):
    """Local frames for the four faces of a box centred at (cx, cy): returns (frame, u-range sign) per face."""
    return {"south": Frame(cx, cy, 0), "north": Frame(cx, cy, 180), "east": Frame(cx, cy, 90), "west": Frame(cx, cy, -90)}

def house_facades(coll, name, box, z0, z1, kind, entrance=None, set_back=0.0):
    """Timber posts, beams, window bands (and an entrance) on all four faces of an axis-aligned box."""
    x0, x1 = box["x"]; y0, y1 = box["y"]; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    halfs = {"south": ((x1 - x0) / 2, (y1 - y0) / 2), "north": ((x1 - x0) / 2, (y1 - y0) / 2),
             "east": ((y1 - y0) / 2, (x1 - x0) / 2), "west": ((y1 - y0) / 2, (x1 - x0) / 2)}
    for fname, Fr in face_frames(cx, cy).items():
        a, b = halfs[fname]; mbf = MB(Fr); v = -b                     # in each face frame the face is at v = -b, facing -v
        mbf.aabb(-a, v - 0.05, z0, a, v + 0.05, z1, "house")
        vo = v - 0.06                                                # opening plane: 1 cm proud of the wall face (v - 0.05), else z-fighting
        n = max(1, round(2 * a / 1.82))
        us = [-a + 2 * a * k / n for k in range(n + 1)]
        for u in us: mbf.aabb(u - 0.06, v - 0.09, z0, u + 0.06, v - 0.03, z1, "wood")
        for zz in (z0, z1 - 0.18): mbf.aabb(-a, v - 0.1, zz, a, v - 0.03, zz + 0.18, "wood")
        ent = None
        if entrance and entrance["face"] == fname:
            ent = (entrance["y"] - cy) if fname in ("east", "west") else (entrance["x"] - cx)
            if fname in ("west",): ent = -ent
            if fname in ("north",): ent = -ent
        for ua, ub in zip(us[:-1], us[1:]):
            mid = (ua + ub) / 2
            if ent is not None and abs(mid - ent) < (entrance["w"] / 2 + 0.2):
                lattice_door(mbf, ua + 0.08, ub - 0.08, z0 + 0.05, z0 + entrance["h"], vo, -1, leaves=2, pitch=0.12)
                continue
            if kind == "ground":
                sash_window(mbf, ua + 0.1, ub - 0.1, z0 + 0.75, z1 - 0.55, vo, -1)
            else:
                sash_window(mbf, ua + 0.1, ub - 0.1, z0 + 0.65, z1 - 0.45, vo, -1)
                mbf.aabb(ua + 0.08, v - 0.14, z0 + 0.55, ub - 0.08, v - 0.03, z0 + 0.62, "wood")       # balustrade rail
        mbf.build("%s_%s_%s" % (name, kind, fname), coll)

def house(spec, coll):
    nm = spec["name"]; mbb = MB(ID); z1 = spec["z1"]
    for gb in spec["ground"]:
        (x0, x1), (y0, y1) = gb["x"], gb["y"]
        mbb.aabb(x0 - 0.15, y0 - 0.15, 0, x1 + 0.15, y1 + 0.15, 0.45, "granite")
        mbb.aabb(x0 + 0.06, y0 + 0.06, 0.45, x1 - 0.06, y1 - 0.06, z1, "house")
        house_facades(coll, nm, {"x": [x0, x1], "y": [y0, y1]}, 0.45, z1, "ground", spec.get("entrance"))
    mbb.build(nm + "_Core", coll)
    e = spec["eave"]
    if spec["upper"]:
        se = spec["skirt_eave"]
        for i, gb in enumerate(spec["ground"]):                       # first-floor roof skirt (hisashi) around each block
            (x0, x1), (y0, y1) = gb["x"], gb["y"]; Fh = Frame((x0 + x1) / 2, (y0 + y1) / 2); a, b = (x1 - x0) / 2, (y1 - y0) / 2
            Rp = {"hu": a + se, "hv": b + se, "thick": 0.15}
            def pz(u, v, a=a, b=b):
                d = min(a + se - abs(u), b + se - abs(v)); return z1 + (spec["skirt_top"] - z1) * min(1, d / (se + 1.2)), (b + se - abs(v)) <= (a + se - abs(u))
            roof_field("%s_Skirt%d" % (nm, i), coll, Fh, pz, (-Rp["hu"], Rp["hu"]), (-Rp["hv"], Rp["hv"]), Rp,
                       keep=lambda u, v, a=a, b=b: min(a + se - abs(u), b + se - abs(v)) <= se + 1.25, step=0.12, amp=0.02, mats=("tile_gray", "wood"))
        mbu = MB(ID); zu0, z2 = spec["z_up0"], spec["z2"]
        for ub in spec["upper"]:
            (x0, x1), (y0, y1) = ub["x"], ub["y"]
            mbu.aabb(x0 + 0.06, y0 + 0.06, zu0, x1 - 0.06, y1 - 0.06, z2, "house")
            house_facades(coll, nm + "_U", {"x": [x0, x1], "y": [y0, y1]}, zu0, z2, "upper")
        mbu.build(nm + "_UpperCore", coll)
        top, blocks = z2, spec["upper"]
    else:
        top, blocks = z1, spec["ground"]
    for i, ub in enumerate(blocks):                                   # hip (or irimoya) roof per block (overlapping blocks make an L)
        (x0, x1), (y0, y1) = ub["x"], ub["y"]; long_x = (x1 - x0) >= (y1 - y0)
        Fh = Frame((x0 + x1) / 2, (y0 + y1) / 2, 0 if long_x else 90); a, b = ((x1 - x0) / 2, (y1 - y0) / 2) if long_x else ((y1 - y0) / 2, (x1 - x0) / 2)
        iri = spec.get("irimoya", False)
        Rh = {"hu": a + e, "hv": b + e, "z_eave": top, "z_ridge": top + spec["ridge_add"], "gable_u": (a + e - spec.get("gable_in", 2.0)) if iri else 0.0,
              "p": 1.2 if iri else 1.0, "rise": 0.25 if iri else 0.15, "thick": 0.2, "ridge_u": a + e - spec.get("gable_in", 2.0) + 0.3, "ridge_h": 0.35, "oni_h": 0.45}
        if iri: Rh["run_side"] = spec.get("gable_in", 2.0) * 1.6
        if iri: irimoya_roof("%s_Roof%d" % (nm, i), coll, Fh, Rh, step=0.12, amp=0.025, mats=("tile_gray", "wood"))
        else: roof_field("%s_Roof%d" % (nm, i), coll, Fh, lambda u, v, Rh=Rh: irimoya_z(u, v, Rh), (-Rh["hu"], Rh["hu"]), (-Rh["hv"], Rh["hv"]), Rh,
                         step=0.12, amp=0.02, mats=("tile_gray", "wood"))
        mt = MB(Fh)
        if iri: irimoya_trim(mt, Rh, ridge_mat="tile_gray")
        else: hip_trim(mt, Rh)
        mt.build("%s_RoofTrim%d" % (nm, i), coll)
    pch = spec.get("porch")
    if pch:                                                           # entrance porch (genkan): gable facing out, pillars, step
        (x0, x1), (y0, y1) = pch["x"], pch["y"]; east = x1 > spec["ground"][0]["x"][1] - 0.01
        Fp = Frame((x0 + x1) / 2, (y0 + y1) / 2, 90 if east else -90)   # u along y, ridge along local v (outward = -v)
        a, b = (y1 - y0) / 2, (x1 - x0) / 2; mp = MB(Fp); zf = 0.45
        mp.aabb(-a - 0.5, -b - 1.1, 0, a + 0.5, -b + 0.2, pch["step_h"], "granite")            # stone step in front
        mp.aabb(-a - 0.2, -b, 0, a + 0.2, b, zf, "granite")
        for su in (-1, 1):
            for vv in (-b + 0.15, b - 0.1):
                mp.cyl(su * (a - 0.1), vv, zf, pch["z_eave"] - 0.15, 0.13, "wood", 12)
            mp.aabb(su * (a - 0.1) - 0.08, -b + 0.15, pch["z_eave"] - 0.55, su * (a - 0.1) + 0.08, b, pch["z_eave"] - 0.3, "wood")
        mp.aabb(-a, -b + 0.05, pch["z_eave"] - 0.55, a, -b + 0.25, pch["z_eave"] - 0.15, "wood")   # front tie beam
        lattice_door(mp, -a + 0.25, a - 0.25, zf, zf + spec["entrance"]["h"], b - 0.12, -1, leaves=4, pitch=0.11)
        Rg = {"hv": a + pch["eave"], "z_eave": pch["z_eave"], "z_ridge": pch["z_ridge"], "p": 1.3, "thick": 0.18}
        Fg = Frame((x0 + x1) / 2, (y0 + y1) / 2 - 0.0, 0)          # gable roof: ridge along x (outward)
        ext = (x0 - 0.0, x1 + pch["eave"]) if east else (x0 - pch["eave"], x1)
        roof_field(nm + "_PorchRoof", coll, Frame(sum(ext) / 2, (y0 + y1) / 2, 0), lambda u, v: gable_z(u, v, Rg),
                   (-(ext[1] - ext[0]) / 2, (ext[1] - ext[0]) / 2), (-Rg["hv"], Rg["hv"]), Rg, step=0.08, amp=0.03, mats=("tile_gray", "wood"))
        xg = ext[1] - 0.15 if east else ext[0] + 0.15; mg = MB(ID)
        vs_ = [-(a + 0.05) + 2 * (a + 0.05) * k / 20 for k in range(21)]
        for va, vb in zip(vs_[:-1], vs_[1:]):                         # gable infill, bargeboards, gegyo
            za_, zb_ = gable_z(0, va, Rg)[0], gable_z(0, vb, Rg)[0]
            mg.add_world([(xg - 0.6, (y0 + y1) / 2 + va, pch["z_eave"] - 0.1), (xg - 0.6, (y0 + y1) / 2 + vb, pch["z_eave"] - 0.1),
                          (xg - 0.6, (y0 + y1) / 2 + vb, zb_ - 0.12), (xg - 0.6, (y0 + y1) / 2 + va, za_ - 0.12)], [(0, 1, 2, 3)], "wood")   # dark carved gable (photo 00209)
        for va, vb in zip([-Rg["hv"] + 2 * Rg["hv"] * k / 24 for k in range(24)], [-Rg["hv"] + 2 * Rg["hv"] * (k + 1) / 24 for k in range(24)]):
            mg.beam((xg, (y0 + y1) / 2 + va, gable_z(0, va, Rg)[0] + 0.02), (xg, (y0 + y1) / 2 + vb, gable_z(0, vb, Rg)[0] + 0.02), 0.08, 0.32, "wood")
        mg.box((xg + 0.03, (y0 + y1) / 2, pch["z_ridge"] - 0.55), (0.06, 0.7, 0.55), "wood")
        mg.box((sum(ext) / 2, (y0 + y1) / 2, pch["z_ridge"] + 0.1), (ext[1] - ext[0], 0.3, 0.25), "tile_gray")
        mg.box((xg, (y0 + y1) / 2, pch["z_ridge"] + 0.35), (0.3, 0.45, 0.5), "tile_gray")       # onigawara
        mp.build(nm + "_Porch", coll); mg.build(nm + "_PorchGable", coll)
for spec in S["residence"]: house(spec, cols["Temple_Residence"])
for spec in S["west_bldg"]: house(spec, cols["Temple_WestBldg"])

# ================================================================ garage (three shutters, mono-pitch roof)
Gp = S["garage"]; (x0, x1), (y0, y1) = Gp["x"], Gp["y"]; mb = MB(ID)
mb.aabb(x0, y0, 0, x1, y1, Gp["h_back"], "frame_white")
for k in range(Gp["doors"]):                                          # shutters on the west face, ribbed
    ya = y0 + (y1 - y0) * k / Gp["doors"] + 0.12; yb = y0 + (y1 - y0) * (k + 1) / Gp["doors"] - 0.12
    mb.aabb(x0 - 0.05, ya, 0, x0 + 0.01, yb, Gp["h_front"] - 0.45, "shutter")
    for z in [0.15 + j * 0.12 for j in range(int((Gp["h_front"] - 0.6) / 0.12))]:
        mb.aabb(x0 - 0.07, ya, z, x0 - 0.04, yb, z + 0.03, "frame_white")
    mb.aabb(x0 - 0.12, ya - 0.05, Gp["h_front"] - 0.45, x0, yb + 0.05, Gp["h_front"] - 0.25, "frame_white")   # shutter box
mb.add_world([(x0 - 0.3, y0 - 0.2, Gp["h_front"]), (x1 + 0.2, y0 - 0.2, Gp["h_back"]), (x1 + 0.2, y1 + 0.2, Gp["h_back"]), (x0 - 0.3, y1 + 0.2, Gp["h_front"])],
             [(0, 1, 2, 3)], "fascia")
mb.beam((x0 - 0.3, y0 - 0.2, Gp["h_front"] - 0.1), (x0 - 0.3, y1 + 0.2, Gp["h_front"] - 0.1), 0.06, 0.25, "fascia")
mb.add_world([(x0, y0, Gp["h_back"]), (x1, y0, Gp["h_back"]), (x1, y0, Gp["h_back"]), (x0, y0, Gp["h_front"])], [(0, 1, 2, 3)], "frame_white")
mb.aabb(x0 + 1.0, y0 - 0.06, 1.2, x0 + 2.6, y0 - 0.02, 2.2, "sign")   # parking sign on the south face
mb.build("Garage", cols["Temple_Garage"])

# ================================================================ approach: entrance gateposts -> romon
A = S.get("approach")
if A:
    ca = reset_collections(["Temple_Approach"])["Temple_Approach"]
    mb = MB(ID)
    pr = A["public_road"]                                             # public road with edge line and a gutter grating
    mb.aabb(pr["x"][0], pr["y_far"], 0.0, pr["x"][1], pr["y_edge"], 0.02, "asphalt")
    mb.aabb(pr["x"][0], pr["y_edge"] - 0.15, 0.02, pr["x"][1], pr["y_edge"] - 0.03, 0.03, "line")
    mb.aabb(pr["x"][0], pr["y_far"] + 0.05, 0.02, pr["x"][1], pr["y_far"] + 0.17, 0.03, "line")
    mb.aabb(-3.6, pr["gutter_y"] - 0.2, 0.0, -1.0, pr["gutter_y"] + 0.2, 0.025, "grating")
    mb.poly_slab([tuple(q) for q in A["road"]], 0.0, 0.03, "asphalt")                 # approach road (asphalt)
    mb.poly_slab([tuple(q) for q in A["east_lawn"]], 0.0, 0.12, "lawn_dry")           # east garden, slightly raised
    ek = A["east_kerb"]
    for a_, b_ in zip(ek[:-1], ek[1:]):                                               # white concrete kerb along the road
        mb.beam((a_[0], a_[1], 0.15), (b_[0], b_[1], 0.15), 0.16, 0.3, "concrete")
    sp = A["statue_platform"]; x0, x1 = sp["x"]; y0, y1 = sp["y"]                     # statue platform with steps
    mb.aabb(x0, y0, 0, x1, y1, sp["h"], "concrete"); mb.aabb(x0 + 0.15, y0 + 0.15, sp["h"], x1 - 0.15, y1 - 0.15, sp["h"] + 0.03, "soil")
    for k in range(2):
        mb.aabb(x0 + 0.5, sp["steps_y0"] + k * 0.35, 0, x1 - 0.5, y0, sp["h"] * (k + 1) / 2, "concrete")
    st_ = A["statue"]; x, y = st_["p"]; ph, h = st_["pedestal_h"], st_["h"]; ms_ = st_.get("mat", "stone_dk")
    mb.aabb(x - 0.6, y - 0.6, sp["h"], x + 0.6, y + 0.6, sp["h"] + ph * 0.5, "granite"); mb.aabb(x - 0.42, y - 0.42, sp["h"] + ph * 0.5, x + 0.42, y + 0.42, sp["h"] + ph, "granite")
    zb = sp["h"] + ph
    mb.cyl(x, y, zb, zb + 0.3, 0.48, ms_, 14, 0.36)                                 # lotus base
    mb.cyl(x, y, zb + 0.3, zb + h * 0.8, 0.27, ms_, 12, 0.2)                         # robed figure
    mb.blob(x, y, zb + h * 0.88, 0.15, 0.15, 0.19, ms_, 10, 6)
    mb.blob(x, y + 0.08, zb + h * 0.85, 0.04 + 0.3, 0.04, 0.36, ms_, 8, 5)           # halo (faces south)
    wc = A["west_cemetery"]; (x0, x1), (y0, y1) = wc["x"], wc["y"]                  # cemetery terrace: white wall + grave rows
    mb.aabb(x0, y0, 0, x1, y1, wc["h"], "concrete"); mb.aabb(x0 + 0.12, y0 + 0.12, wc["h"], x1 - 0.12, y1 - 0.12, wc["h"] + 0.02, "soil")
    import random as _r; rg = _r.Random(11)
    for xr in wc["rows_x"]:
        yy = y0 + 0.8
        while yy < y1 - 0.6:
            hh = rg.uniform(0.9, 1.35); w = rg.uniform(0.32, 0.42); z = wc["h"]
            mb.aabb(xr - 0.45, yy - 0.45, z, xr + 0.45, yy + 0.45, z + 0.18, "granite")          # plot kerb / base
            mb.aabb(xr - 0.3, yy - 0.3, z + 0.18, xr + 0.3, yy + 0.3, z + 0.38, "granite_dk")
            mb.aabb(xr - w / 2, yy - w / 2, z + 0.38, xr + w / 2, yy + w / 2, z + 0.38 + hh, "granite_dk")
            yy += wc["pitch"]
    mb.poly_slab([tuple(q) for q in A["west_bed_south"]], 0, A["west_bed_h"], "concrete")
    inner = [tuple(q) for q in A["west_bed_south"]]
    cx_ = sum(q[0] for q in inner) / len(inner); cy_ = sum(q[1] for q in inner) / len(inner)
    mb.poly_slab([(cx_ + (q[0] - cx_) * 0.93, cy_ + (q[1] - cy_) * 0.95) for q in inner], A["west_bed_h"], A["west_bed_h"] + 0.03, "soil")
    for gp in A["gateposts"]:                                          # granite gateposts with a recessed name plate
        x, y = gp["p"]; w = gp["w"]; h = gp["h"]
        mb.aabb(x - w * 0.7, y - w * 0.7, 0, x + w * 0.7, y + w * 0.7, 0.45, "granite")
        mb.aabb(x - w / 2, y - w / 2, 0.45, x + w / 2, y + w / 2, h, "stone")
        mb.aabb(x - w / 2 - 0.05, y - w / 2 - 0.05, h, x + w / 2 + 0.05, y + w / 2 + 0.05, h + 0.12, "stone")
        mb.aabb(x - w * 0.3, y - w / 2 - 0.02, 1.0, x + w * 0.3, y - w / 2 + 0.01, h - 0.25, "stone_dk")
    mo = A["monument"]; x, y = mo["p"]                                 # temple-name monument on a two-tier pedestal
    mb.aabb(x - mo["base"][0] / 2, y - mo["base"][0] / 2, 0, x + mo["base"][0] / 2, y + mo["base"][0] / 2, mo["base"][1], "granite")
    z = mo["base"][1]; mb.aabb(x - mo["base2"][0] / 2, y - mo["base2"][0] / 2, z, x + mo["base2"][0] / 2, y + mo["base2"][0] / 2, z + mo["base2"][1], "granite")
    z += mo["base2"][1]; w = mo["w"]
    mb.aabb(x - w / 2, y - w / 2, z, x + w / 2, y + w / 2, z + mo["h"], "stone")
    mb.box((x, y, z + mo["h"] + 0.08), (w * 0.7, w * 0.7, 0.16), "stone", math.pi / 4)
    for sl in A.get("stone_lanterns", []):                             # stone lantern (ishidōrō)
        x, y = sl["p"]; h = sl["h"]
        mb.aabb(x - 0.35, y - 0.35, 0, x + 0.35, y + 0.35, 0.25, "stone"); mb.cyl(x, y, 0.25, h * 0.5, 0.12, "stone", 8)
        mb.aabb(x - 0.3, y - 0.3, h * 0.5, x + 0.3, y + 0.3, h * 0.56, "stone"); mb.aabb(x - 0.22, y - 0.22, h * 0.56, x + 0.22, y + 0.22, h * 0.74, "stone")
        mb.cyl(x, y, h * 0.74, h * 0.86, 0.5, "stone", 6, 0.08); mb.blob(x, y, h * 0.92, 0.1, 0.1, 0.12, "stone", 8, 5)
    mb.build("Approach_Hardscape", ca)
    mb = MB(ID)
    for hd in A["hedges"]: hedge(mb, hd["p0"], hd["p1"], hd["h"], hd["t"], hd.get("mat", "hedge"))
    for x, y, r in A["shrubs"]: mb.blob(x, y, r * 0.95, r, r, r * 0.9, "foliage_dk", 10, 6, 0.08, int(x * 7 + y * 3))
    for i, t in enumerate(A["trees"]): tree(mb, t["p"][0], t["p"][1], t["kind"], t["r"], t["h"], seed=100 + i * 5)
    mb.build("Approach_Planting", ca, smooth=True)

result = {c: len(col.objects) for c, col in cols.items()}
