"""Make L_Temple walkable in PIE: complex-as-simple collision on every Temple mesh, the level's GameMode override
set to BP_ThirdPersonGameMode, PlayerStart at the entrance facing the gate."""
import sys, json
sys.path.insert(0, __import__("os").environ.get("AWAM_SCRIPTS") or __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(globals().get("__file__", "."))), "..", "..", "..", "scripts"))  # skill scripts/ (set AWAM_SCRIPTS when run through exec)
from ue_mcp import Ue

ue = Ue()
OT = "editor_toolset.toolsets.object.ObjectTools"; AT = "editor_toolset.toolsets.asset.AssetTools"
ST = "editor_toolset.toolsets.scene.SceneTools"; AC = "editor_toolset.toolsets.actor.ActorTools"
rv = lambda r: r["returnValue"] if isinstance(r, dict) and "returnValue" in r else r
def getp(obj, props): v = rv(ue.call(OT, "get_properties", {"instance": obj, "properties": props})); return json.loads(v) if isinstance(v, str) else v
def find(name):
    return rv(ue.call(ST, "find_actors", {"root": None, "name": name, "actor_type": None, "tag": "", "bounds": None, "collision_channels": []}))

meshes = rv(ue.call(AT, "find_assets", {"folder_path": "/Game/Temple/Meshes", "name": "", "asset_type": "/Script/Engine.StaticMesh", "recursive": True}))
paths = []
for a in meshes:
    p = a if isinstance(a, str) else a["refPath"]
    if "." not in p.rsplit("/", 1)[1]: p += "." + p.rsplit("/", 1)[1]
    bs = getp({"refPath": p}, ["BodySetup"])["BodySetup"]
    ok = rv(ue.call(OT, "set_properties", {"instance": bs, "values": json.dumps({"CollisionTraceFlag": "CTF_UseComplexAsSimple"})}))
    print("collision", p.rsplit("/", 1)[1].split(".")[0], ok, getp(bs, ["CollisionTraceFlag"]))
    paths.append(p.split(".")[0])
ue.call(AT, "save_assets", {"asset_paths": paths})

ws = find("WorldSettings")[0]
gm = "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode.BP_ThirdPersonGameMode_C"
print("gamemode", ue.call(OT, "set_properties", {"instance": ws, "values": json.dumps({"DefaultGameMode": gm})}), getp(ws, ["DefaultGameMode"]))
for a in find("PlayerStart"):
    ue.call(AC, "set_actor_transform", {"actor": a, "xform": {"location": {"x": 140, "y": 2600, "z": 120},
        "rotation": {"pitch": 0, "yaw": -90, "roll": 0}, "scale": {"x": 1, "y": 1, "z": 1}}, "worldspace": True})
lvl = rv(ue.call(ST, "get_current_level")); print("save level", ue.call(AT, "save_assets", {"asset_paths": [lvl]}))
