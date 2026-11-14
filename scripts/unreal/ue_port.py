r"""Port groups exported by blender/bl_export_groups.py into the open Unreal Editor through its MCP server.

usage: python ue_port.py <config.json> <step> [...]
  steps (run in this order the first time; each is re-runnable):
    materials [--force]   master M_<Name>_Base (BaseTex x BaseColor, Roughness) + MI_<material> per Blender material,
                          colours from export_manifest.json "_materials". Existing instances are kept unless --force
                          (they may have been re-parented to a textured/procedural master since).
    import [groups...]    import each FBX (removes placed actors of that mesh first), assign MI_<slot>, Nanite on
                          every mesh (non-Nanite meshes overflow the virtual shadow map), complex-as-simple collision.
    level                 open config "level"; create it from the template level if missing; remove the template floor.
    place                 place every imported group at its centre, outliner folder <Name>, save the level.
    walkable              GameMode override + PlayerStart (config "game_mode", "player_start"), collision check.
    all                   materials, import, level, place
config.json:
  {"name": "Temple", "export_dir": "F:/.../ue_export",
   "level": "/Game/Temple/Maps/L_Temple",            (optional, this is the default)
   "skip_groups": ["SM_Temple_Planting"], "no_shadow": ["SM_Temple_Ground"],
   "game_mode": "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode.BP_ThirdPersonGameMode_C",
   "player_start": [x_m, y_m, z_m, yaw_deg]}                (model frame; yaw -90 faces model +Y)
Axes/units: model (x, y, z) m -> UE (100x, -100y, 100z) cm (meshes are baked x100 by bl_export_groups.py).
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ue_mcp import Ue

TS = {"MT": "editor_toolset.toolsets.material.MaterialTools", "MI": "editor_toolset.toolsets.material_instance.MaterialInstanceTools",
      "OT": "editor_toolset.toolsets.object.ObjectTools", "AT": "editor_toolset.toolsets.asset.AssetTools",
      "SM": "editor_toolset.toolsets.static_mesh.StaticMeshTools", "ST": "editor_toolset.toolsets.scene.SceneTools",
      "AC": "editor_toolset.toolsets.actor.ActorTools"}
rv = lambda r: r["returnValue"] if isinstance(r, dict) and "returnValue" in r else r
ref = lambda p: {"refPath": p}
def full(p): return p if "." in p.rsplit("/", 1)[1] else p + "." + p.rsplit("/", 1)[1]
def ue_xf(x, y, z=0.0, yaw=0.0):
    return {"location": {"x": 100 * x, "y": -100 * y, "z": 100 * z}, "rotation": {"pitch": 0, "yaw": yaw, "roll": 0}, "scale": {"x": 1, "y": 1, "z": 1}}

class Port:
    def __init__(self, cfg_path):
        self.cfg = json.load(open(cfg_path, encoding="utf-8")); c = self.cfg
        self.name = c["name"]; self.root = "/Game/" + self.name
        self.level = c.get("level", "%s/Maps/L_%s" % (self.root, self.name))
        self.man = json.load(open(os.path.join(c["export_dir"], "export_manifest.json")))
        self.groups = [g for g in self.man if not g.startswith("_") and g not in c.get("skip_groups", [])]
        self._ue = None
    @property
    def ue(self):                                  # connect on first use (Poly Haven steps need no editor)
        if self._ue is None: self._ue = Ue()
        return self._ue
    def call(self, ts, tool, args=None): return rv(self.ue.call(TS[ts], tool, args or {}))
    def getp(self, obj, props):
        v = self.call("OT", "get_properties", {"instance": obj, "properties": props}); return json.loads(v) if isinstance(v, str) else v
    def find(self, name):
        return self.call("ST", "find_actors", {"root": None, "name": name, "actor_type": None, "tag": "", "bounds": None, "collision_channels": []}) or []
    def save(self, paths, tries=20):
        for i in range(tries):                     # right after a Nanite/mesh rebuild the asset reports "does not exist"
            try: return self.call("AT", "save_assets", {"asset_paths": paths})
            except RuntimeError as e:
                if "does not exist" not in str(e) or i == tries - 1: raise
                time.sleep(5)

    # ------------------------------------------------------------ materials
    def materials(self, force=False):
        F = self.root + "/Materials"; M = "%s/M_%s_Base" % (F, self.name)
        if not self.call("AT", "exists", {"path": M}):
            self.call("AT", "create_folder", {"path": F})
            m = self.call("MT", "create_material", {"folder_path": F, "asset_name": "M_%s_Base" % self.name})
            add = lambda cls, x, y: self.call("MT", "add_expression", {"material_or_function": m, "expression_class": ref("/Script/Engine." + cls), "x": x, "y": y})
            tex = add("MaterialExpressionTextureSampleParameter2D", -700, -100); col = add("MaterialExpressionVectorParameter", -700, 200)
            mul = add("MaterialExpressionMultiply", -300, 0); rough = add("MaterialExpressionScalarParameter", -300, 300)
            for e, v in ((tex, {"ParameterName": "BaseTex", "Texture": "/Engine/EngineResources/WhiteSquareTexture.WhiteSquareTexture"}),
                         (col, {"ParameterName": "BaseColor", "DefaultValue": {"R": 1, "G": 1, "B": 1, "A": 1}}),
                         (rough, {"ParameterName": "Roughness", "DefaultValue": 0.8})):
                self.call("OT", "set_properties", {"instance": e, "values": json.dumps(v)})
            self.call("MT", "connect_expressions", {"from_expression": tex, "from_output_name": "RGB", "to_expression": mul, "to_input_name": "A"})
            self.call("MT", "connect_expressions", {"from_expression": col, "from_output_name": "", "to_expression": mul, "to_input_name": "B"})
            self.call("MT", "connect_to_output", {"expression": mul, "output_name": "", "material_property": "MP_BaseColor"})
            self.call("MT", "connect_to_output", {"expression": rough, "output_name": "", "material_property": "MP_Roughness"})
            self.call("MT", "recompile", {"material_or_function": m}); self.save([M])
        made = []
        for mat, (r, g, b, ro) in self.man.get("_materials", {}).items():
            p = "%s/MI_%s" % (F, mat)
            if self.call("AT", "exists", {"path": p}):
                if not force: continue
                inst = ref(full(p))
            else:
                inst = self.call("MI", "create", {"folder_path": F, "asset_name": "MI_" + mat, "parent": ref(full(M))})
            self.call("MI", "set_vector_parameter", {"instance": inst, "name": "BaseColor", "value": {"r": r, "g": g, "b": b, "a": 1}})
            self.call("MI", "set_scalar_parameter", {"instance": inst, "name": "Roughness", "value": ro})
            made.append(p)
        if made: self.save(made)
        print("materials: %d instances created/updated" % len(made))

    # ------------------------------------------------------------ import
    def import_(self, only=None):
        F = self.root + "/Meshes"; self.call("AT", "create_folder", {"path": F})
        for g in (only or self.groups):
            for a in self.find(g): self.call("ST", "remove_from_scene", {"actor": a})     # free the asset first
            p = "%s/%s" % (F, g)
            if self.call("AT", "exists", {"path": p}): self.call("AT", "delete", {"path": p})
            mesh = self.call("SM", "import_file", {"folder_path": F, "asset_name": g, "source_file": self.man[g]["file"],
                                                   "import_materials": False, "combine_meshes": True})[0]
            missing = []
            for s in self.call("SM", "get_material_slots", {"mesh": mesh}):
                mi = "%s/Materials/MI_%s" % (self.root, s)
                if self.call("AT", "exists", {"path": mi}): self.call("SM", "set_material", {"mesh": mesh, "slot_name": s, "material": ref(full(mi))})
                else: missing.append(s)
            self.call("SM", "set_nanite_enabled", {"mesh": mesh, "enabled": True})
            bs = self.getp(mesh, ["BodySetup"])["BodySetup"]
            self.call("OT", "set_properties", {"instance": bs, "values": json.dumps({"CollisionTraceFlag": "CTF_UseComplexAsSimple"})})
            self.save([p])
            b = self.call("SM", "get_bounds", {"mesh": mesh})
            size = [round((b["max"][k] - b["min"][k]) / 100, 2) for k in "xyz"]
            print("import %-30s size %s m (Blender %s)%s" % (g, size, self.man[g].get("size_m"), "  MISSING MI: %s" % missing if missing else ""), flush=True)

    # ------------------------------------------------------------ level
    def open_level(self):
        cur = self.call("ST", "get_current_level")
        if cur != self.level:
            if not self.call("AT", "exists", {"path": self.level}):
                self.call("AT", "duplicate", {"path": self.cfg.get("template", "/Engine/Maps/Templates/Template_Default"), "new_path": self.level})
                self.save([self.level])
            self.call("ST", "load_level", {"level_path": self.level})     # refused while an unsaved Untitled level is open
        for a in self.find("Floor"):
            if self.call("AC", "get_label", {"actor": a}) == "Floor": self.call("ST", "remove_from_scene", {"actor": a})
        print("level:", self.call("ST", "get_current_level"))

    # ------------------------------------------------------------ place
    def place(self):
        for g in self.groups:
            for a in self.find(g): self.call("ST", "remove_from_scene", {"actor": a})
            x, y, _ = self.man[g]["center_m"]
            act = self.call("ST", "add_to_scene_from_asset", {"asset_path": full("%s/Meshes/%s" % (self.root, g)), "name": g,
                                                              "xform": ue_xf(x, y), "parent": None, "snap_to_ground": False})
            self.call("ST", "set_actor_folder", {"actor": act, "folder_path": self.name})
            if g in self.cfg.get("no_shadow", []):
                for c in self.call("AC", "get_components", {"actor": act}):
                    if "StaticMeshComponent" in c["refPath"]:
                        self.call("OT", "set_properties", {"instance": c, "values": json.dumps({"CastShadow": False})})
        self.save([self.call("ST", "get_current_level")]); print("placed", len(self.groups), "groups")

    # ------------------------------------------------------------ walkable
    def walkable(self):
        if self.cfg.get("game_mode"):
            ws = self.find("WorldSettings")[0]
            self.call("OT", "set_properties", {"instance": ws, "values": json.dumps({"DefaultGameMode": self.cfg["game_mode"]})})
        if self.cfg.get("player_start"):
            x, y, z, yaw = self.cfg["player_start"]
            for a in self.find("PlayerStart"):
                self.call("AC", "set_actor_transform", {"actor": a, "xform": ue_xf(x, y, z, yaw), "worldspace": True})
            d = self.call("ST", "trace_world", {"start": {"x": 100 * x, "y": -100 * y, "z": 100 * z + 200}, "end": {"x": 100 * x, "y": -100 * y, "z": -1000}})
            print("ground under PlayerStart: %.2f m below the start" % ((d - 200) / 100) if d else "NO collision under PlayerStart")
        self.save([self.call("ST", "get_current_level")])

if __name__ == "__main__":
    P = Port(sys.argv[1]); step = sys.argv[2]; rest = sys.argv[3:]
    if step in ("materials", "all"): P.materials(force="--force" in rest)
    if step in ("import", "all"): P.import_([g for g in rest if not g.startswith("--")] or None)
    if step in ("level", "all"): P.open_level()
    if step in ("place", "all"): P.place()
    if step == "walkable": P.walkable()
