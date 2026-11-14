"""Placeholder trees in UE from the PCG sample meshes, at the measured tree positions/sizes in site_params.json
(site trees + approach trees). Outliner folder Temple/Trees_Placeholder; re-runnable (removes its own actors).
Hedges and shrub balls are not placed (no fitting mesh). Swap for real foliage assets later."""
import sys, json, math, random
sys.path.insert(0, __import__("os").environ.get("AWAM_SCRIPTS") or __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(globals().get("__file__", "."))), "..", "..", "..", "scripts"))  # skill scripts/ (set AWAM_SCRIPTS when run through exec)
from ue_mcp import Ue

ue = Ue()
ST = "editor_toolset.toolsets.scene.SceneTools"; AT = "editor_toolset.toolsets.asset.AssetTools"
rv = lambda r: r["returnValue"] if isinstance(r, dict) and "returnValue" in r else r
S = json.load(open(__import__("os").path.join(__import__("os").environ.get("PROJECT_DIR", "."), r"tools\site_params.json"), encoding="utf-8"))
trees = S["trees"] + S.get("approach", {}).get("trees", [])
# native size of the PCG sample trees (cm): height above ground, crown diameter
MESH = {1: (964, 480), 2: (1246, 660), 3: (1550, 890)}
def pick(t):
    if t["kind"] in ("topiary", "round", "conifer"): return 1
    return 1 if t["h"] <= 7 else (2 if t["h"] <= 10 else 3)

FOLDER = "Temple/Trees_Placeholder"
if FOLDER in (rv(ue.call(ST, "get_folders", {})) or []):           # get_actors_in_folder raises on a missing folder
    for a in rv(ue.call(ST, "get_actors_in_folder", {"folder_path": FOLDER, "recursive": True})) or []:
        ue.call(ST, "remove_from_scene", {"actor": a})
rnd = random.Random(5); n = 0
for i, t in enumerate(trees):
    m = pick(t); H, D = MESH[m]
    sz = 100 * t["h"] / H
    sxy = 100 * 2 * t["r"] / D
    if t["kind"] == "conifer": sxy = min(sxy, sz * 0.55)          # narrow crown
    x, y = t["p"]
    act = rv(ue.call(ST, "add_to_scene_from_asset", {
        "asset_path": "/PCG/SampleContent/SimpleForest/Meshes/PCG_Tree_0%d.PCG_Tree_0%d" % (m, m), "name": "Tree_%02d_%s" % (i, t["kind"]),
        "parent": None, "snap_to_ground": False,
        "xform": {"location": {"x": 100 * x, "y": -100 * y, "z": 0}, "rotation": {"pitch": 0, "yaw": rnd.uniform(0, 360), "roll": 0},
                  "scale": {"x": sxy, "y": sxy, "z": sz}}}))
    ue.call(ST, "set_actor_folder", {"actor": act, "folder_path": FOLDER}); n += 1
lvl = rv(ue.call(ST, "get_current_level")); ue.call(AT, "save_assets", {"asset_paths": [lvl]})
print(n, "placeholder trees")
