# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
"""Place the imported the temple meshes in the open level (outliner folder 'Temple'), remove the template floor,
move the PlayerStart to the entrance. Blender (x, y, z) m -> UE (100x, -100y, 100z) cm (measured: Y flips)."""
import sys, json
sys.path.insert(0, __import__("os").environ.get("AWAM_SCRIPTS") or __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(globals().get("__file__", "."))), "..", "..", "..", "scripts"))  # skill scripts/ (set AWAM_SCRIPTS when run through exec)
from ue_mcp import Ue

ue = Ue()
ST = "editor_toolset.toolsets.scene.SceneTools"; AC = "editor_toolset.toolsets.actor.ActorTools"; AT = "editor_toolset.toolsets.asset.AssetTools"
rv = lambda r: r["returnValue"] if isinstance(r, dict) and "returnValue" in r else r
def ue_loc(x, y, z=0.0): return {"x": 100 * x, "y": -100 * y, "z": 100 * z}
def xf(x, y, z=0.0, yaw=0.0): return {"location": ue_loc(x, y, z), "rotation": {"pitch": 0, "yaw": yaw, "roll": 0}, "scale": {"x": 1, "y": 1, "z": 1}}
def find(name):
    return rv(ue.call(ST, "find_actors", {"root": None, "name": name, "actor_type": None, "tag": "", "bounds": None, "collision_channels": []}))

for a in find("Floor"):
    if rv(ue.call(AC, "get_label", {"actor": a})) == "Floor": print("remove floor", ue.call(ST, "remove_from_scene", {"actor": a}))
man = json.load(open(__import__("os").path.join(__import__("os").environ.get("PROJECT_DIR", "."), r"ue_export\export_manifest.json")))
placed = {}
for n, info in man.items():
    if "Planting" in n: continue
    for a in find(n): ue.call(ST, "remove_from_scene", {"actor": a})              # re-runnable
    x, y, _ = info["center_m"]
    act = rv(ue.call(ST, "add_to_scene_from_asset", {"asset_path": "/Game/Temple/Meshes/%s.%s" % (n, n), "name": n,
                                                      "xform": xf(x, y), "parent": None, "snap_to_ground": False}))
    ue.call(ST, "set_actor_folder", {"actor": act, "folder_path": "Temple"})
    placed[n] = act["refPath"] if isinstance(act, dict) else act
for a in find("PlayerStart"):
    ue.call(AC, "set_actor_transform", {"actor": a, "xform": xf(1.4, -27.0, 1.0, yaw=-90.0), "worldspace": True})
lvl = rv(ue.call(ST, "get_current_level"))
print("save level", ue.call(AT, "save_assets", {"asset_paths": [lvl]}))
print(json.dumps(placed, indent=1))
