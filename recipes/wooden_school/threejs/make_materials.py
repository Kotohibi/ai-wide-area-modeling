r"""materials.json for the Three.js viewer: the material tables of ue\ue_mats.py (the same numbers as blender\bl_mats.py)
for both variants, plus bark / grass (bl_trees.py, bl_mats.py) and the wet zones under the holes of the ruin.
    python make_materials.py        -> public\materials.json
No numpy needed.  Run again after changing a material number in ue_mats.py / bl_mats.py."""
import os, sys, json, importlib.util
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); UE = os.path.join(ROOT, "ue"); sys.path.insert(0, UE)

def table(var):
    os.environ["RS_VARIANT"] = var
    spec = importlib.util.spec_from_file_location("ue_mats_" + var, os.path.join(UE, "ue_mats.py")); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    out = {}
    for name, r in m.M.items():
        e = {k: [round(float(x), 5) for x in (list(r[k]) + [0.0] * 4)[:(3 if k.startswith("C") else 4)]] for k in ("CA", "CB", "CC", "P0", "P1", "P2", "P3", "P4", "P5")}
        e["rough"] = r["Roughness"]; e["metal"] = r["Metallic"]; out[name] = e
    return out, m

def plain(c1, c2, scale, stretch=(1, 1, 1), rough=0.9, kind=0):
    return dict(CA=list(c1), CB=list(c2), CC=[0, 0, 0], P0=[kind, 1, 0, 0], P1=[0.5, 0.45, 1.0, 0], P2=[scale, *stretch], P3=[0, 0, 0, 0], P4=[0, 0, 0, 0], P5=[0, 0, 0, 0], rough=rough, metal=0.0)

EXTRA = {   # bl_trees.py / bl_mats.py (not in the UE table: UE uses plant assets)
    "bark": plain((0.10, 0.075, 0.055), (0.22, 0.17, 0.13), 4.0, (8, 8, 0.6)), "bark_dark": plain((0.045, 0.035, 0.03), (0.12, 0.09, 0.075), 4.0, (8, 8, 0.6)),
    "bark_cedar": plain((0.13, 0.075, 0.05), (0.26, 0.16, 0.11), 3.0, (10, 10, 0.4)),
    "grass_dry": plain((0.36, 0.28, 0.17), (0.62, 0.52, 0.36), 3.0, kind=8), "grass_green": plain((0.12, 0.19, 0.04), (0.27, 0.34, 0.09), 3.0, kind=8),
}
LEAF = {"evergreen": [(0.05, 0.085, 0.035), (0.14, 0.20, 0.09)], "mid": [(0.08, 0.14, 0.045), (0.21, 0.30, 0.10)], "bush": [(0.08, 0.14, 0.045), (0.21, 0.30, 0.10)],
        "fresh": [(0.15, 0.26, 0.05), (0.33, 0.45, 0.11)], "cherry": [(0.75, 0.52, 0.56), (0.92, 0.78, 0.80)], "cedar": [(0.045, 0.08, 0.035), (0.12, 0.18, 0.08)]}
ruin, m = table("ruin"); restored, _ = table("restored")
for t in (ruin, restored): t.update(json.loads(json.dumps(EXTRA)))
restored["lamp_glow"]["emit"] = 2.2                                           # lamp shades glow in the web version
out = dict(ruin=ruin, restored=restored, glass={"glass": 0.0, "glass_frost": 1.0}, leaf=LEAF,
           wet=[[round(v, 3) for v in p] for p in m.WET], wetf=[[round(v, 3) for v in p] for p in m.WETF])
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public"); os.makedirs(p, exist_ok=True)
json.dump(out, open(os.path.join(p, "materials.json"), "w"), separators=(",", ":"))
print("materials.json: ruin", len(ruin), "restored", len(restored), "wet", len(out["wet"]), "wetf", len(out["wetf"]))
