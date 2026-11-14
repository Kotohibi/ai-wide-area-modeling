# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
"""Create the the temple master material (BaseTex * BaseColor tint, Roughness) and one MaterialInstance per Blender
material (T_* colours from temple_lib.MATS) in /Game/Temple/Materials, through the Unreal MCP server."""
import sys, json, re, ast
sys.path.insert(0, __import__("os").environ.get("AWAM_SCRIPTS") or __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(globals().get("__file__", "."))), "..", "..", "..", "scripts"))  # skill scripts/ (set AWAM_SCRIPTS when run through exec)
from ue_mcp import Ue

ue = Ue()
MT = "editor_toolset.toolsets.material.MaterialTools"; MI = "editor_toolset.toolsets.material_instance.MaterialInstanceTools"
OT = "editor_toolset.toolsets.object.ObjectTools"; AT = "editor_toolset.toolsets.asset.AssetTools"
FOLDER = "/Game/Temple/Materials"; MASTER = FOLDER + "/M_Temple_Base"
rv = lambda r: r["returnValue"] if isinstance(r, dict) and "returnValue" in r else r

def ref(p): return {"refPath": p}

if not rv(ue.call(AT, "exists", {"path": MASTER})):
    ue.call(AT, "create_folder", {"path": FOLDER})
    m = rv(ue.call(MT, "create_material", {"folder_path": FOLDER, "asset_name": "M_Temple_Base"}))
    add = lambda cls, x, y: rv(ue.call(MT, "add_expression", {"material_or_function": m, "expression_class": ref("/Script/Engine." + cls), "x": x, "y": y}))
    tex = add("MaterialExpressionTextureSampleParameter2D", -700, -100)
    col = add("MaterialExpressionVectorParameter", -700, 200)
    mul = add("MaterialExpressionMultiply", -300, 0)
    rough = add("MaterialExpressionScalarParameter", -300, 300)
    ue.call(OT, "set_properties", {"instance": tex, "values": json.dumps({"ParameterName": "BaseTex", "Texture": "/Engine/EngineResources/WhiteSquareTexture.WhiteSquareTexture"})})
    ue.call(OT, "set_properties", {"instance": col, "values": json.dumps({"ParameterName": "BaseColor", "DefaultValue": {"R": 1, "G": 1, "B": 1, "A": 1}})})
    ue.call(OT, "set_properties", {"instance": rough, "values": json.dumps({"ParameterName": "Roughness", "DefaultValue": 0.8})})
    print("tex outs", rv(ue.call(MT, "get_expression_output_names", {"expression": tex})), "mul ins", rv(ue.call(MT, "get_expression_input_names", {"expression": mul})))
    ue.call(MT, "connect_expressions", {"from_expression": tex, "from_output_name": "RGB", "to_expression": mul, "to_input_name": "A"})
    ue.call(MT, "connect_expressions", {"from_expression": col, "from_output_name": "", "to_expression": mul, "to_input_name": "B"})
    ue.call(MT, "connect_to_output", {"expression": mul, "output_name": "", "material_property": "MP_BaseColor"})
    ue.call(MT, "connect_to_output", {"expression": rough, "output_name": "", "material_property": "MP_Roughness"})
    print("recompile", ue.call(MT, "recompile", {"material_or_function": m}))
    ue.call(AT, "save_assets", {"asset_paths": [MASTER]})

# colours: parse MATS from temple_lib.py (linear values, same as Blender's Principled base colour)
src = open(__import__("os").path.join(__import__("os").environ.get("PROJECT_DIR", "."), r"tools\temple_lib.py"), encoding="utf-8").read()
mats = ast.literal_eval(re.search(r"MATS = (\{.*?\n\})", src, re.S).group(1))
made = []
for name, (r, g, b, rough) in mats.items():
    path = FOLDER + "/MI_T_" + name
    inst = ref(path + ".MI_T_" + name)
    if not rv(ue.call(AT, "exists", {"path": path})):
        inst = rv(ue.call(MI, "create", {"folder_path": FOLDER, "asset_name": "MI_T_" + name, "parent": ref(MASTER + ".M_Temple_Base")}))
    ue.call(MI, "set_vector_parameter", {"instance": inst, "name": "BaseColor", "value": {"r": r, "g": g, "b": b, "a": 1.0}})
    ue.call(MI, "set_scalar_parameter", {"instance": inst, "name": "Roughness", "value": rough})
    made.append(path)
ue.call(AT, "save_assets", {"asset_paths": made})
print(len(made), "material instances")
