# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
"""Place Megaplants (skeletal-mesh trees/shrubs from Bridge, /Game/Megaplant_Library) at the measured vegetation of
site_params.json: trees by kind and size, hedges as rows of shrubs, shrub balls as small shrubs. Removes the PCG
placeholders. Outliner folder Temple/Vegetation; re-runnable. Sizes from megaplants.json (bounds in cm)."""
import sys, json, math, random
sys.path.insert(0, __import__("os").environ.get("AWAM_SCRIPTS") or __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(globals().get("__file__", "."))), "..", "..", "..", "scripts"))  # skill scripts/ (set AWAM_SCRIPTS when run through exec)
from ue_mcp import Ue

ue = Ue()
ST = "editor_toolset.toolsets.scene.SceneTools"; AT = "editor_toolset.toolsets.asset.AssetTools"
rv = lambda r: r["returnValue"] if isinstance(r, dict) and "returnValue" in r else r
S = json.load(open(__import__("os").path.join(__import__("os").environ.get("PROJECT_DIR", "."), r"tools\site_params.json"), encoding="utf-8"))
MP = json.load(open(__import__("os").path.join(__import__("os").environ.get("PROJECT_DIR", "."), r"megaplants.json")))
rnd = random.Random(11)

def clear(folder):
    if folder in (rv(ue.call(ST, "get_folders", {})) or []):
        for a in rv(ue.call(ST, "get_actors_in_folder", {"folder_path": folder, "recursive": True})) or []:
            ue.call(ST, "remove_from_scene", {"actor": a})
clear("Temple/Trees_Placeholder"); clear("Temple/Vegetation")

# candidate meshes per kind (names in megaplants.json)
KINDS = {"bare_big": ["Hornbeam_A", "Hornbeam_B"], "bare": ["European_Beech_B", "English_Oak_C", "Norway_Maple_B", "Hornbeam_C", "English_Oak_B"],
         "conifer": ["Norway_Spruce_C", "Norway_Spruce_B"], "topiary": ["Baltic_Pine_D", "Baltic_Pine_C"],
         "round": ["Common_Hazel_A", "Common_Hazel_B"], "shrub": ["Greasewood_A", "Greasewood_B", "Greasewood_C"]}

placed = 0
def put(name, mesh, x, y, h_m, w_m=None, folder="Temple/Vegetation", squash=(0.6, 1.6)):
    """Place mesh at model (x, y) m scaled to height h_m (and crown width w_m, limited to +-60 % of uniform)."""
    global placed
    m = MP[mesh]; s = 100.0 * h_m / max(m["h"], 1)
    sxy = s
    if w_m:
        sw = 100.0 * w_m / max((m["dx"] + m["dy"]) / 2, 1)
        sxy = min(max(sw, s * squash[0]), s * squash[1])
    yaw = rnd.uniform(0, 360); a = math.radians(yaw)
    ox = (m["cx"] * math.cos(a) - m["cy"] * math.sin(a)) * sxy; oy = (m["cx"] * math.sin(a) + m["cy"] * math.cos(a)) * sxy  # recentre crown
    act = rv(ue.call(ST, "add_to_scene_from_asset", {"asset_path": m["path"], "name": name, "parent": None, "snap_to_ground": False,
        "xform": {"location": {"x": 100 * x - ox, "y": -100 * y - oy, "z": 0}, "rotation": {"pitch": 0, "yaw": yaw, "roll": 0},
                  "scale": {"x": sxy, "y": sxy, "z": s}}}))
    ue.call(ST, "set_actor_folder", {"actor": act, "folder_path": folder}); placed += 1

trees = S["trees"] + S.get("approach", {}).get("trees", [])
for i, t in enumerate(trees):
    k = t["kind"]
    if k == "bare": k = "bare_big" if t["r"] >= 4 else "bare"
    put("Tree_%02d_%s" % (i, t["kind"]), rnd.choice(KINDS[k]), t["p"][0], t["p"][1], t["h"], 2 * t["r"])

def hedge_row(tag, p0, p1, h, t, pitch=None):
    L = math.dist(p0, p1); pitch = pitch or max(0.6, 0.8 * t); n = max(1, int(L / pitch))
    for j in range(n + 1):
        f = j / n; x = p0[0] + (p1[0] - p0[0]) * f + rnd.uniform(-0.08, 0.08); y = p0[1] + (p1[1] - p0[1]) * f + rnd.uniform(-0.08, 0.08)
        put("%s_%03d" % (tag, j), rnd.choice(KINDS["shrub"]), x, y, h * rnd.uniform(0.92, 1.05), t * 1.15, squash=(0.4, 2.5))
for i, hd in enumerate(S["hedges"]): hedge_row("Hedge_%d" % i, hd["p0"], hd["p1"], hd["h"], hd["t"])
for i, hd in enumerate(S.get("approach", {}).get("hedges", [])): hedge_row("AHedge_%d" % i, hd["p0"], hd["p1"], hd["h"], hd["t"])
for i, row in enumerate(S["shrub_rows"]):                      # clipped shrub balls along the hall front and paths
    (x0, y0), (x1, y1) = row["p0"], row["p1"]; n = int(math.dist(row["p0"], row["p1"]) / row["pitch"])
    for j in range(n + 1):
        f = j / max(1, n); put("Shrub_%d_%02d" % (i, j), rnd.choice(KINDS["shrub"]), x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, 1.7 * row["r"], 2.2 * row["r"], squash=(0.5, 2.0))
for j, (x, y, r) in enumerate(S.get("approach", {}).get("shrubs", [])):
    put("AShrub_%02d" % j, rnd.choice(KINDS["shrub"]), x, y, 1.7 * r, 2.2 * r, squash=(0.5, 2.0))
lvl = rv(ue.call(ST, "get_current_level")); ue.call(AT, "save_assets", {"asset_paths": [lvl]})
print(placed, "vegetation actors placed")
