r"""Gently falling things (petals, leaves, snow, dust) as a Niagara system built through the editor's MCP tools.  UE 5.9+.

  python ue_niagara_fall.py <config.json> [material] [system] [place]        (no step = all three; level open, not in PIE)

config.json (every key but "system" optional; positions in model metres, model (x, y, z) -> UE (100 x, -100 y, 100 z)):
  {"system": "/Game/FX/NS_Fall", "material": "/Game/FX/M_Fall",
   "shape": "petal" | "disc" | "leaf", "tint": [0.95, 0.72, 0.78], "emissive": 0.45,
   "spawn_rate": 11, "lifetime_s": [10, 16], "size_cm": [3.2, 5.0], "color": [1, 0.93, 0.95, 1],
   "wind_cm_s": [3, 1, -40],        # the velocity the particles settle to (drag): z < 0 is the fall speed
   "turbulence": 2.0, "frequency": 2.0, "lift": 0.3,
   "emitters": [{"x": 1, "y": 2, "z": 5, "size": [6, 6, 3]}, ...],   # centre and size (m) of each spawn box, e.g. one per tree crown
   "label": "NS_Fall_", "folder": "FX/Fall"}
How it is built: CreateNiagaraSystem (any system template) -> AddEmitter HangingParticulates (spawns in a box, WindForce +
AerodynamicDrag) -> the template's own emitters removed -> inputs set with SetStackInputData.  The spawn box is 1 m and
follows the owner's scale, so one system serves boxes of any size.
Tuning by feel:  wind_cm_s = direction and speed;  turbulence = WindForce 'Scale', the CURL-NOISE strength, not a force
multiplier (6 throws petals about like gusts, 0 = dead straight, 0.5-2 = a quiet sway);  lift = sideways gliding.
The particles do not collide: they vanish at the end of their lifetime (choose it so they reach the ground)."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ue_py import run, call
NS = "NiagaraToolsets.NiagaraToolset_System"; F32 = "/Script/Niagara.NiagaraFloat"; V3 = "/Script/CoreUObject.Vector3f"; COL = "/Script/CoreUObject.LinearColor"
SHAPES = {   # opacity mask from the sprite UVs (p in -1..1)
 "petal": "float w = 0.62 * sqrt(saturate(1.0 - p.y * p.y)) * (0.75 + 0.25 * p.y);\nfloat notch = (p.y > 0.62 && abs(p.x) < 0.22 * (p.y - 0.62) / 0.38) ? 0.0 : 1.0;\nreturn (abs(p.x) < w && abs(p.y) < 0.97) ? notch : 0.0;",
 "leaf": "float w = 0.5 * sqrt(saturate(1.0 - p.y * p.y)) * (1.0 - 0.45 * p.y);\nreturn (abs(p.x) < w && abs(p.y) < 0.97) ? 1.0 : 0.0;",
 "disc": "return dot(p, p) < 0.9 ? 1.0 : 0.0;"}
UE_MAT = r'''
import json
C = json.loads(@DATA@); at = unreal.AssetToolsHelpers.get_asset_tools(); mel = unreal.MaterialEditingLibrary; eal = unreal.EditorAssetLibrary
F, name = C["material"].rsplit("/", 1); eal.make_directory(F)
m = eal.load_asset(C["material"]) if eal.does_asset_exist(C["material"]) else at.create_asset(name, F, unreal.Material, unreal.MaterialFactoryNew())
mel.delete_all_material_expressions(m)          # (a material in use cannot be deleted and re-created: empty it instead)
m.set_editor_property("two_sided", True); m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
uv = mel.create_material_expression(m, unreal.MaterialExpressionTextureCoordinate, -900, 0)
pc = mel.create_material_expression(m, unreal.MaterialExpressionParticleColor, -900, -300)
c = mel.create_material_expression(m, unreal.MaterialExpressionCustom, -500, 0); c.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT1)
ci = unreal.CustomInput(); ci.set_editor_property("input_name", "UV"); c.set_editor_property("inputs", [ci])
c.set_editor_property("code", "float2 p = (UV - 0.5) * 2.0;\n" + C["code"]); mel.connect_material_expressions(uv, "", c, "UV")
k = mel.create_material_expression(m, unreal.MaterialExpressionConstant3Vector, -900, -500); k.set_editor_property("constant", unreal.LinearColor(C["tint"][0], C["tint"][1], C["tint"][2], 1))
mu = mel.create_material_expression(m, unreal.MaterialExpressionMultiply, -500, -400)
mel.connect_material_expressions(pc, "", mu, "A"); mel.connect_material_expressions(k, "", mu, "B")
mel.connect_material_property(mu, "", unreal.MaterialProperty.MP_BASE_COLOR); mel.connect_material_property(c, "", unreal.MaterialProperty.MP_OPACITY_MASK)
ro = mel.create_material_expression(m, unreal.MaterialExpressionConstant, -500, 300); ro.set_editor_property("r", 0.6); mel.connect_material_property(ro, "", unreal.MaterialProperty.MP_ROUGHNESS)
em = mel.create_material_expression(m, unreal.MaterialExpressionMultiply, -300, -200); ek = mel.create_material_expression(m, unreal.MaterialExpressionConstant, -500, -150); ek.set_editor_property("r", C["emissive"])
mel.connect_material_expressions(mu, "", em, "A"); mel.connect_material_expressions(ek, "", em, "B"); mel.connect_material_property(em, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)   # sprites facing away from the sun come out nearly black without it
mel.set_material_usage(m, unreal.MaterialUsage.MATUSAGE_NIAGARA_SPRITES); mel.recompile_material(m); eal.save_loaded_asset(m, False)
C["material"]
'''
UE_PLACE = r'''
import json
C = json.loads(@DATA@); eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for a in eas.get_all_level_actors():
    if a.get_actor_label().startswith(C["label"]): eas.destroy_actor(a)
sysa = unreal.EditorAssetLibrary.load_asset(C["system"]); n = 0
for i, t in enumerate(C["emitters"]):
    act = eas.spawn_actor_from_object(sysa, unreal.Vector(100 * t["x"], -100 * t["y"], 100 * t["z"]), unreal.Rotator(0, 0, 0))
    act.set_actor_label("%s%03d" % (C["label"], i)); act.set_folder_path(C["folder"]); s = t.get("size", [3, 3, 2])
    act.set_actor_scale3d(unreal.Vector(max(s[0], 0.5), max(s[1], 0.5), max(s[2], 0.5))); n += 1
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
n
'''
def system(C):
    path = C["system"]; folder, name = path.rsplit("/", 1); S = {"refPath": path + "." + name}; E = "Fall"
    def setin(script, module, inp, struct, value):
        return call(NS, "SetStackInputData", {"stackInputRef": {"system": S, "emitterName": E, "scriptName": script, "moduleName": module, "inputNameStack": [inp]},
                                              "inputData": {"struct": {"refPath": struct}, "value": value}})
    if not run('unreal.EditorAssetLibrary.does_asset_exist("%s")' % path):
        call(NS, "CreateNiagaraSystem", {"assetName": name, "assetPath": folder, "templateSystem": {"refPath": "/Niagara/DefaultAssets/Templates/Systems/DirectionalBurst.DirectionalBurst"}})
        call(NS, "AddEmitter", {"system": S, "templateEmitter": {"refPath": "/Niagara/DefaultAssets/Templates/Emitters/HangingParticulates.HangingParticulates"}, "emitterName": E})
        for e in call(NS, "GetSystemSummary", {"system": S})["emitters"]:
            if e["emitterName"] != E: call(NS, "RemoveEmitter", {"emitterRef": {"system": S, "emitterName": e["emitterName"]}})
    U, PS, PU = "EmitterUpdateScript", "ParticleSpawnScript", "ParticleUpdateScript"; lt = C.get("lifetime_s", [10, 16]); sz = C.get("size_cm", [3.2, 5.0]); col = C.get("color", [1, 1, 1, 1]); w = C.get("wind_cm_s", [3, 1, -40])
    setin(U, "SpawnRate", "SpawnRate", F32, {"value": float(C.get("spawn_rate", 11))})
    setin(PS, "InitializeParticle", "Lifetime Min", F32, {"value": float(lt[0])}); setin(PS, "InitializeParticle", "Lifetime Max", F32, {"value": float(lt[1])})
    setin(PS, "InitializeParticle", "Uniform Sprite Size Min", F32, {"value": float(sz[0])}); setin(PS, "InitializeParticle", "Uniform Sprite Size Max", F32, {"value": float(sz[1])})
    setin(PS, "InitializeParticle", "Color", COL, {"r": col[0], "g": col[1], "b": col[2], "a": col[3]})
    setin(PS, "ShapeLocation", "Box Size", V3, {"x": 100.0, "y": 100.0, "z": 100.0})
    setin(PU, "WindForce", "Wind Speed", V3, {"x": float(w[0]), "y": float(-w[1]), "z": float(w[2])})          # model y -> UE -y
    setin(PU, "WindForce", "Scale", F32, {"value": float(C.get("turbulence", 2.0))}); setin(PU, "WindForce", "Frequency", F32, {"value": float(C.get("frequency", 2.0))})
    setin(PU, "AerodynamicDrag", "Lift Contribution", F32, {"value": float(C.get("lift", 0.3))})
    if C.get("material"):
        call(NS, "SetRendererData", {"rendererRef": {"system": S, "emitterName": E, "rendererIndex": 0},
             "rendererData": {"propertyValues": json.dumps({"Material": {"refPath": C["material"] + "." + C["material"].rsplit("/", 1)[1]}, "bCastShadows": False})}})
    iss = call(NS, "GetStackIssues", {"system": S}); st = call(NS, "GetSystemCompileState", {"system": S})
    run('unreal.EditorAssetLibrary.save_asset("%s", False)' % path)
    return {"errors": iss.get("numErrors"), "warnings": iss.get("numWarnings"), "compile": st.get("aggregateStatus")}
if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    C = json.load(open(a[0], encoding="utf-8")); steps = a[1:] or ["material", "system", "place"]
    C.setdefault("label", "NS_Fall_"); C.setdefault("folder", "FX/Fall")
    if "material" in steps and C.get("material"):
        d = {"material": C["material"], "tint": C.get("tint", [1, 1, 1]), "emissive": float(C.get("emissive", 0.45)), "code": SHAPES[C.get("shape", "petal")]}
        print("material:", run(UE_MAT.replace("@DATA@", repr(json.dumps(d)))))
    if "system" in steps: print("system:", system(C))
    if "place" in steps and C.get("emitters"):
        d = {"system": C["system"], "label": C["label"], "folder": C["folder"], "emitters": C["emitters"]}
        print("placed:", run(UE_PLACE.replace("@DATA@", repr(json.dumps(d)))))
