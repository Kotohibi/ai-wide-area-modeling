# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
"""Poly Haven textures in UE, world-aligned (triplanar) because the meshes have no UVs.
1) import the 2K jpgs (diffuse sRGB; normal and roughness linear) into /Game/Temple/Textures/PolyHaven
2) master M_Temple_Tex: three Custom HLSL nodes (base colour, roughness, world-space normal with whiteout blend),
   TextureObjectParameters BaseTex/NormTex/RoughTex, TileCm, Tint, RoughMul; tangent-space normal off
3) re-parent the matching MI_T_* instances to it (others stay on the procedural master)
usage: python ue_tex_materials.py [--skip-import]"""
import sys, json, os, glob
sys.path.insert(0, __import__("os").environ.get("AWAM_SCRIPTS") or __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(globals().get("__file__", "."))), "..", "..", "..", "scripts"))  # skill scripts/ (set AWAM_SCRIPTS when run through exec)
from ue_mcp import Ue

ue = Ue()
MT = "editor_toolset.toolsets.material.MaterialTools"; MI = "editor_toolset.toolsets.material_instance.MaterialInstanceTools"
OT = "editor_toolset.toolsets.object.ObjectTools"; AT = "editor_toolset.toolsets.asset.AssetTools"; TX = "editor_toolset.toolsets.texture.TextureTools"
rv = lambda r: r["returnValue"] if isinstance(r, dict) and "returnValue" in r else r
ref = lambda p: {"refPath": p}
PH = __import__("os").path.join(__import__("os").environ.get("PROJECT_DIR", "."), r"polyhaven"); TF = "/Game/Temple/Textures/PolyHaven"
FOLDER = "/Game/Temple/Materials"; NAME = "M_Temple_Tex"; MASTER = FOLDER + "/" + NAME

# ---------------------------------------------------------------- 1) textures
def tex_path(setname, kind): return "%s/T_%s_%s" % (TF, setname, kind)
if "--skip-import" not in sys.argv:
    ue.call(AT, "create_folder", {"path": TF})
    for d in sorted(glob.glob(os.path.join(PH, "*"))):
        if not os.path.isdir(d): continue
        s = os.path.basename(d)
        for f in glob.glob(os.path.join(d, "*_2k.jpg")):
            kind = "D" if "_diff_" in f else ("N" if "_nor_dx_" in f else "R")
            p = tex_path(s, kind)
            if rv(ue.call(AT, "exists", {"path": p})): ue.call(AT, "delete", {"path": p})
            t = rv(ue.call(TX, "import_file", {"folder_path": TF, "asset_name": "T_%s_%s" % (s, kind), "source_file": f}))
            t = t[0] if isinstance(t, list) else t
            if kind != "D":                      # linear data, sampled raw in HLSL (no normal-map unpacking)
                ue.call(OT, "set_properties", {"instance": t, "values": json.dumps({"SRGB": False, "CompressionSettings": "TC_Default"})})
            ue.call(AT, "save_assets", {"asset_paths": [p]})
        print("imported", s, flush=True)

# ---------------------------------------------------------------- 2) master material
# Texture2DSample (not Tex.Sample): UE maps it to SampleLevel in ray-tracing/path-tracing hit shaders,
# where Sample() does not compile.
TRI = r"""
float3 n = normalize(N); float3 w = pow(abs(n), 4.0); w /= (w.x + w.y + w.z);
float3 p = WP / max(TileCm, 1.0);
float2 uvx = p.zy, uvy = p.xz, uvz = p.xy;
"""
CODE_BASE = TRI + r"""
float3 c = Texture2DSample(Base, BaseSampler, uvx).rgb * w.x + Texture2DSample(Base, BaseSampler, uvy).rgb * w.y + Texture2DSample(Base, BaseSampler, uvz).rgb * w.z;
return c * Tint;
"""
CODE_ROUGH = TRI + r"""
float r = Texture2DSample(Rough, RoughSampler, uvx).r * w.x + Texture2DSample(Rough, RoughSampler, uvy).r * w.y + Texture2DSample(Rough, RoughSampler, uvz).r * w.z;
return saturate(r * RoughMul);
"""
CODE_NORM = TRI + r"""
float3 tx = Texture2DSample(Norm, NormSampler, uvx).rgb * 2.0 - 1.0; tx.g = -tx.g;   // DirectX -> OpenGL convention
float3 ty = Texture2DSample(Norm, NormSampler, uvy).rgb * 2.0 - 1.0; ty.g = -ty.g;
float3 tz = Texture2DSample(Norm, NormSampler, uvz).rgb * 2.0 - 1.0; tz.g = -tz.g;
tx = float3(tx.xy + n.zy, abs(tx.z) * n.x);                                // whiteout blend (world space)
ty = float3(ty.xy + n.xz, abs(ty.z) * n.y);
tz = float3(tz.xy + n.xy, abs(tz.z) * n.z);
float3 o = normalize(tx.zyx * w.x + ty.xzy * w.y + tz.xyz * w.z);
return normalize(lerp(n, o, Strength));
"""

def custom(m, x, y, code, inputs, out_type, desc):
    e = rv(ue.call(MT, "add_expression", {"material_or_function": m, "expression_class": ref("/Script/Engine.MaterialExpressionCustom"), "x": x, "y": y}))
    ue.call(OT, "set_properties", {"instance": e, "values": json.dumps({"Code": code, "OutputType": out_type, "Description": desc})})
    getp = lambda: json.loads(rv(ue.call(OT, "get_properties", {"instance": e, "properties": ["Inputs"]})))["Inputs"]
    cur = getp(); cur = cur + [json.loads(json.dumps(cur[0])) for _ in range(len(inputs) - len(cur))]
    ue.call(OT, "set_properties", {"instance": e, "values": json.dumps({"Inputs": cur})})
    cur = getp()
    for el, nme in zip(cur, inputs): el["inputName"] = nme
    ue.call(OT, "set_properties", {"instance": e, "values": json.dumps({"Inputs": cur})})
    return e

def build_master():
    m = rv(ue.call(MT, "create_material", {"folder_path": FOLDER, "asset_name": NAME}))
    ue.call(OT, "set_properties", {"instance": m, "values": json.dumps({"bTangentSpaceNormal": False})})
    add = lambda cls, x, y: rv(ue.call(MT, "add_expression", {"material_or_function": m, "expression_class": ref("/Script/Engine." + cls), "x": x, "y": y}))
    con = lambda a, ao, b, bi: ue.call(MT, "connect_expressions", {"from_expression": a, "from_output_name": ao, "to_expression": b, "to_input_name": bi})
    wp = add("MaterialExpressionWorldPosition", -1200, -200); nrm = add("MaterialExpressionVertexNormalWS", -1200, -100)
    def tparam(name, tex, y):
        e = add("MaterialExpressionTextureObjectParameter", -1200, y)
        ue.call(OT, "set_properties", {"instance": e, "values": json.dumps({"ParameterName": name, "Texture": tex})}); return e
    base = tparam("BaseTex", "/Engine/EngineResources/WhiteSquareTexture.WhiteSquareTexture", 0)
    rough = tparam("RoughTex", "/Engine/EngineResources/WhiteSquareTexture.WhiteSquareTexture", 150)
    norm = tparam("NormTex", "/Engine/EngineResources/WhiteSquareTexture.WhiteSquareTexture", 300)
    def sparam(name, val, y):
        e = add("MaterialExpressionScalarParameter", -1200, y)
        ue.call(OT, "set_properties", {"instance": e, "values": json.dumps({"ParameterName": name, "DefaultValue": val})}); return e
    tile = sparam("TileCm", 200.0, 450); rmul = sparam("RoughMul", 1.0, 540); strength = sparam("NormalStrength", 1.0, 630)
    tint = add("MaterialExpressionVectorParameter", -1200, 720)
    ue.call(OT, "set_properties", {"instance": tint, "values": json.dumps({"ParameterName": "Tint", "DefaultValue": {"R": 1, "G": 1, "B": 1, "A": 1}})})
    cb = custom(m, -500, -100, CODE_BASE, ["WP", "N", "TileCm", "Base", "Tint"], "CMOT_Float3", "triplanar base colour")
    cr = custom(m, -500, 200, CODE_ROUGH, ["WP", "N", "TileCm", "Rough", "RoughMul"], "CMOT_Float1", "triplanar roughness")
    cn = custom(m, -500, 500, CODE_NORM, ["WP", "N", "TileCm", "Norm", "Strength"], "CMOT_Float3", "triplanar world normal")
    for c in (cb, cr, cn):
        con(wp, "", c, "WP"); con(nrm, "", c, "N"); con(tile, "", c, "TileCm")
    con(base, "", cb, "Base"); con(tint, "RGB", cb, "Tint")
    con(rough, "", cr, "Rough"); con(rmul, "", cr, "RoughMul")
    con(norm, "", cn, "Norm"); con(strength, "", cn, "Strength")
    ue.call(MT, "connect_to_output", {"expression": cb, "output_name": "", "material_property": "MP_BaseColor"})
    ue.call(MT, "connect_to_output", {"expression": cr, "output_name": "", "material_property": "MP_Roughness"})
    ue.call(MT, "connect_to_output", {"expression": cn, "output_name": "", "material_property": "MP_Normal"})
    print("recompile:", ue.call(MT, "recompile", {"material_or_function": m}))
    ue.call(AT, "save_assets", {"asset_paths": [MASTER]})
if not rv(ue.call(AT, "exists", {"path": MASTER})): build_master()

# ---------------------------------------------------------------- 3) instances
# name: (texture set, tile cm, tint, roughness multiplier)
MAP = {"tile_gray": ("grey_roof_tiles", 160, (1, 1, 1), 1.0), "tile": ("grey_roof_tiles", 160, (0.62, 0.95, 0.82), 0.9),
       "tile_dk": ("grey_roof_tiles", 160, (0.5, 0.78, 0.68), 0.9),
       "wood": ("dark_wood", 120, (0.75, 0.62, 0.55), 1.0), "bark": ("dark_wood", 120, (0.8, 0.7, 0.6), 1.0),
       "wood_lt": ("japanese_cedar_planks", 160, (0.85, 0.75, 0.65), 1.0), "fascia": ("japanese_cedar_planks", 160, (0.7, 0.6, 0.5), 1.0),
       "plaster": ("white_stucco", 220, (1, 1, 1), 1.0), "house": ("white_stucco", 220, (1.0, 0.9, 0.72), 1.0),
       "wall": ("clay_plaster", 220, (1, 1, 1), 1.0), "asphalt": ("asphalt_02", 300, (0.8, 0.8, 0.8), 1.0),
       "gravel": ("gravel_floor_02", 150, (1, 1, 1), 1.0), "paving": ("stone_tiles", 240, (1, 1, 1), 1.0),
       "stone2": ("stone_tiles", 240, (0.9, 0.9, 0.9), 1.0), "brick": ("brick_pavement_02", 160, (1, 1, 1), 1.0),
       "lawn_dry": ("withered_grass", 220, (1, 1, 1), 1.0), "soil": ("withered_grass", 220, (0.45, 0.4, 0.35), 1.0),
       "concrete": ("concrete", 200, (1, 1, 1), 1.0), "granite": ("concrete", 160, (0.85, 0.85, 0.83), 1.0),
       "stone": ("concrete", 160, (0.9, 0.88, 0.84), 1.0), "granite_dk": ("concrete", 160, (0.25, 0.25, 0.27), 0.7),
       "stone_dk": ("concrete", 160, (0.5, 0.49, 0.47), 1.0), "riverstone": ("concrete", 120, (0.7, 0.68, 0.62), 1.0)}
done = []
for name, (s, tile, tint, rmul) in MAP.items():
    inst = ref("%s/MI_T_%s.MI_T_%s" % (FOLDER, name, name))
    ue.call(MI, "set_parent", {"instance": inst, "parent": ref(MASTER + "." + NAME)})
    for k, kind in (("BaseTex", "D"), ("RoughTex", "R"), ("NormTex", "N")):
        p = tex_path(s, kind); ue.call(MI, "set_texture_parameter", {"instance": inst, "name": k, "value": ref(p + "." + p.rsplit("/", 1)[1])})
    ue.call(MI, "set_scalar_parameter", {"instance": inst, "name": "TileCm", "value": float(tile)})
    ue.call(MI, "set_scalar_parameter", {"instance": inst, "name": "RoughMul", "value": float(rmul)})
    ue.call(MI, "set_vector_parameter", {"instance": inst, "name": "Tint", "value": {"r": tint[0], "g": tint[1], "b": tint[2], "a": 1}})
    done.append("%s/MI_T_%s" % (FOLDER, name))
ue.call(AT, "save_assets", {"asset_paths": done})
print(len(done), "instances now textured")
