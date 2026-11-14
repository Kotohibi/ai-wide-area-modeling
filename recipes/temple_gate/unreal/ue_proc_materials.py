"""Procedural (texture-node) materials for the temple in UE: master M_Temple_Proc computes the base colour from
world position in a Custom HLSL node (value-noise fbm, wood grain, running-bond pavers/slabs, roof-tile courses) and
the existing MI_T_* instances are re-parented to it with per-material parameters. No UVs or textures needed.
usage: python ue_proc_materials.py"""
import sys, json, re, ast
sys.path.insert(0, __import__("os").environ.get("AWAM_SCRIPTS") or __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(globals().get("__file__", "."))), "..", "..", "..", "scripts"))  # skill scripts/ (set AWAM_SCRIPTS when run through exec)
from ue_mcp import Ue

ue = Ue()
MT = "editor_toolset.toolsets.material.MaterialTools"; MI = "editor_toolset.toolsets.material_instance.MaterialInstanceTools"
OT = "editor_toolset.toolsets.object.ObjectTools"; AT = "editor_toolset.toolsets.asset.AssetTools"
rv = lambda r: r["returnValue"] if isinstance(r, dict) and "returnValue" in r else r
FOLDER = "/Game/Temple/Materials"; NAME = "M_Temple_Proc"; MASTER = FOLDER + "/" + NAME
ref = lambda p: {"refPath": p}

HLSL = r"""
struct FK {
  float h(float3 v) { return frac(sin(dot(v, float3(127.1, 311.7, 74.7))) * 43758.5453); }
  float n(float3 x) {
    float3 i = floor(x); float3 f = frac(x); f = f * f * (3.0 - 2.0 * f);
    return lerp(lerp(lerp(h(i), h(i + float3(1,0,0)), f.x), lerp(h(i + float3(0,1,0)), h(i + float3(1,1,0)), f.x), f.y),
                lerp(lerp(h(i + float3(0,0,1)), h(i + float3(1,0,1)), f.x), lerp(h(i + float3(0,1,1)), h(i + float3(1,1,1)), f.x), f.y), f.z);
  }
  float fbm(float3 p) { return (0.5 * n(p) + 0.25 * n(p * 2.03 + 17.0) + 0.125 * n(p * 4.01 + 31.0) + 0.0625 * n(p * 8.07 + 53.0)) / 0.9375; }
};
FK k;
float3 p = WP / max(Scale, 0.01);
float f = k.fbm(p);
float t = saturate((f - 0.5) * Contrast + 0.5);
float3 col = lerp(ColorA, ColorB, t);
int pat = (int)round(Pattern);
if (pat == 1) {                      // wood: long streaks along world Z (posts) + broad patches
  float s = k.n(float3(WP.x / 0.6, WP.y / 0.6, WP.z / 25.0)) * 0.6 + k.n(float3(WP.x / 2.5, WP.y / 2.5, WP.z / 60.0)) * 0.4;
  float tw = saturate((0.55 * s + 0.45 * f - 0.5) * Contrast + 0.5);
  col = lerp(ColorA, ColorB, tw * tw);
}
else if (pat == 2) {                 // running-bond pavers / slabs on the plane facing the normal
  float3 an = abs(N);
  float2 uv = (an.z > 0.6) ? WP.xy : ((an.x > an.y) ? WP.yz : WP.xz);
  uv /= max(Size.xy, float2(0.1, 0.1));
  float row = floor(uv.y); uv.x += 0.5 * fmod(abs(row), 2.0);
  float2 id = floor(uv); float2 g = frac(uv);
  float edge = min(min(g.x, 1.0 - g.x) * Size.x, min(g.y, 1.0 - g.y) * Size.y);
  float mortar = 1.0 - smoothstep(Mortar * 0.5, Mortar, edge);
  float v = k.h(float3(id, 7.0));
  float3 stone = lerp(ColorA, ColorB, saturate(0.65 * v + 0.35 * (f - 0.5) * Contrast + 0.35 * f));
  col = lerp(stone, ColorC, mortar);
}
else if (pat == 3) {                 // roof tiles: colour patches + a shadow line at every tile course (world height bands)
  float course = frac(WP.z / max(Size.y, 1.0));
  float shade = 1.0 - 0.35 * (1.0 - smoothstep(0.0, 0.18, course));
  col = lerp(ColorA, ColorB, t) * shade;
}
return col;
"""

PARAMS_V = {"ColorA": (0.5, 0.5, 0.5), "ColorB": (0.4, 0.4, 0.4), "ColorC": (0.3, 0.3, 0.3), "Size": (100.0, 50.0, 0.0)}
PARAMS_S = {"Scale": 30.0, "Contrast": 1.0, "Pattern": 0.0, "Mortar": 1.0, "Roughness": 0.8}

def build_master():
    ue.call(AT, "create_folder", {"path": FOLDER})
    m = rv(ue.call(MT, "create_material", {"folder_path": FOLDER, "asset_name": NAME}))
    add = lambda cls, x, y: rv(ue.call(MT, "add_expression", {"material_or_function": m, "expression_class": ref("/Script/Engine." + cls), "x": x, "y": y}))
    cus = add("MaterialExpressionCustom", -400, 0)
    inputs = ["WP", "N", "ColorA", "ColorB", "ColorC", "Size", "Scale", "Contrast", "Pattern", "Mortar"]
    ue.call(OT, "set_properties", {"instance": cus, "values": json.dumps({
        "Code": HLSL, "OutputType": "CMOT_Float3", "Description": "Temple procedural base colour"})})
    # ObjectTools refuses to resize an array and change its elements in one call: grow first (copies of the
    # default element), then rename. get_properties returns a JSON string with camelCase keys.
    getp = lambda: json.loads(rv(ue.call(OT, "get_properties", {"instance": cus, "properties": ["Inputs"]})))["Inputs"]
    cur = getp(); cur = cur + [json.loads(json.dumps(cur[0])) for _ in range(len(inputs) - len(cur))]
    ue.call(OT, "set_properties", {"instance": cus, "values": json.dumps({"Inputs": cur})})
    cur = getp()
    for e, n in zip(cur, inputs): e["inputName"] = n
    ue.call(OT, "set_properties", {"instance": cus, "values": json.dumps({"Inputs": cur})})
    print("custom inputs:", rv(ue.call(MT, "get_expression_input_names", {"expression": cus})))
    wp = add("MaterialExpressionWorldPosition", -900, -300)
    nrm = add("MaterialExpressionVertexNormalWS", -900, -200)
    ue.call(MT, "connect_expressions", {"from_expression": wp, "from_output_name": "", "to_expression": cus, "to_input_name": "WP"})
    ue.call(MT, "connect_expressions", {"from_expression": nrm, "from_output_name": "", "to_expression": cus, "to_input_name": "N"})
    y = -100
    for name, val in PARAMS_V.items():
        e = add("MaterialExpressionVectorParameter", -900, y); y += 120
        ue.call(OT, "set_properties", {"instance": e, "values": json.dumps({"ParameterName": name, "DefaultValue": {"R": val[0], "G": val[1], "B": val[2], "A": 1}})})
        ue.call(MT, "connect_expressions", {"from_expression": e, "from_output_name": "RGB", "to_expression": cus, "to_input_name": name})
    rough = None
    for name, val in PARAMS_S.items():
        e = add("MaterialExpressionScalarParameter", -900, y); y += 90
        ue.call(OT, "set_properties", {"instance": e, "values": json.dumps({"ParameterName": name, "DefaultValue": val})})
        if name == "Roughness": rough = e
        else: ue.call(MT, "connect_expressions", {"from_expression": e, "from_output_name": "", "to_expression": cus, "to_input_name": name})
    ue.call(MT, "connect_to_output", {"expression": cus, "output_name": "", "material_property": "MP_BaseColor"})
    ue.call(MT, "connect_to_output", {"expression": rough, "output_name": "", "material_property": "MP_Roughness"})
    print("recompile:", ue.call(MT, "recompile", {"material_or_function": m}))
    ue.call(AT, "save_assets", {"asset_paths": [MASTER]})

if not rv(ue.call(AT, "exists", {"path": MASTER})): build_master()

# ---------------------------------------------------------------- per-material parameters (linear colours, cm)
src = open(__import__("os").path.join(__import__("os").environ.get("PROJECT_DIR", "."), r"tools\temple_lib.py"), encoding="utf-8").read()
MATS = ast.literal_eval(re.search(r"MATS = (\{.*?\n\})", src, re.S).group(1))
def dk(c, k): return tuple(round(v * k, 4) for v in c)
SPEC = {   # name: (pattern, colorB or factor, scale cm, contrast, extra)
    "wood": (1, 0.55, 40, 1.6, {}), "wood_lt": (1, 0.6, 40, 1.6, {}), "fascia": (1, 0.6, 40, 1.4, {}), "bark": (1, 0.6, 30, 1.8, {}),
    "plaster": (0, 0.86, 60, 0.9, {}), "house": (0, 0.88, 60, 0.9, {}), "wall": (0, 0.82, 45, 1.1, {}), "concrete": (0, 0.85, 20, 1.1, {}),
    "tile": (3, 0.62, 70, 1.3, {"Size": (0, 12, 0)}), "tile_dk": (3, 0.62, 70, 1.3, {"Size": (0, 12, 0)}), "tile_gray": (3, 0.6, 70, 1.2, {"Size": (0, 11, 0)}),
    "copper": (0, 0.65, 30, 1.4, {}), "bronze": (0, 0.6, 18, 1.6, {}),
    "stone": (0, 0.72, 14, 1.4, {}), "stone2": (0, 0.75, 10, 1.2, {}), "stone_dk": (0, 0.7, 10, 1.4, {}), "riverstone": (0, 0.7, 8, 1.6, {}),
    "granite": (0, 0.68, 3.5, 2.2, {}), "granite_dk": (0, 0.6, 3.5, 2.0, {}),
    "asphalt": (0, 0.5, 2.5, 1.9, {}), "gravel": (0, 0.6, 1.4, 2.6, {}), "soil": (0, 0.6, 9, 1.6, {}), "lawn_dry": (0, 0.62, 22, 1.6, {}),
    "brick": (2, 0.7, 15, 1.2, {"Size": (20, 10, 0), "Mortar": 0.6, "ColorC": (0.22, 0.21, 0.19)}),
    "paving": (2, 0.8, 25, 1.0, {"Size": (90, 60, 0), "Mortar": 1.2, "ColorC": (0.33, 0.32, 0.30)}),
}
made = []
for name, (r, g, b, rough) in MATS.items():
    path = FOLDER + "/MI_T_" + name; inst = ref(path + ".MI_T_" + name)
    if not rv(ue.call(AT, "exists", {"path": path})):
        inst = rv(ue.call(MI, "create", {"folder_path": FOLDER, "asset_name": "MI_T_" + name, "parent": ref(MASTER + "." + NAME)}))
    else:
        ue.call(MI, "set_parent", {"instance": inst, "parent": ref(MASTER + "." + NAME)})
    pat, kb, scale, con, extra = SPEC.get(name, (0, 0.85, 25, 0.6, {}))
    A = (r, g, b); B = dk(A, kb)
    vals_v = {"ColorA": A, "ColorB": B, "ColorC": extra.get("ColorC", dk(A, 0.6)), "Size": extra.get("Size", (100, 50, 0))}
    vals_s = {"Scale": scale, "Contrast": con, "Pattern": pat, "Mortar": extra.get("Mortar", 1.0), "Roughness": rough}
    for k_, v in vals_v.items():
        ue.call(MI, "set_vector_parameter", {"instance": inst, "name": k_, "value": {"r": v[0], "g": v[1], "b": v[2], "a": 1.0}})
    for k_, v in vals_s.items():
        ue.call(MI, "set_scalar_parameter", {"instance": inst, "name": k_, "value": float(v)})
    made.append(path)
ue.call(AT, "save_assets", {"asset_paths": made})
print(len(made), "instances re-parented to", NAME)
