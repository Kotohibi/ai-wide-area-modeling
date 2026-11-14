r"""Materials for meshes WITHOUT UVs (models generated from 3DGS/SfM measurements), through the Unreal MCP server.
Two world-space masters, then per-material instances from a mapping JSON. (Do not bake the training photos onto the
meshes: users found it ugly - see references/unreal.md.)

usage: python ue_surfaces.py <config.json> <step> [...]
  proc                      build M_<Name>_Proc: one Custom HLSL node -> base colour from world position
                            (Pattern 0 value-noise fbm, 1 wood streaks along Z, 2 running-bond pavers/slabs with mortar,
                             3 roof-tile courses = shadow line every Size.y cm of height)
  tri                       build M_<Name>_Tri: triplanar BaseTex/RoughTex/NormTex (world normal, whiteout blend)
  polyhaven-list <words>    Poly Haven texture ids matching words (API, no download)
  polyhaven-get <ids...>    download 2K diff/nor_dx/rough jpg to <config "polyhaven_dir">  (ASK THE USER FIRST:
                            show ids and total MB - polyhaven-list prints sizes with --sizes)
  import-tex                import every downloaded set to /Game/<Name>/Textures/PolyHaven (normal/rough linear)
  apply <mapping.json>      re-parent MI_<material> to a master and set its parameters:
      {"T_wood":  {"master": "tri",  "set": "dark_wood", "tile_cm": 120, "tint": [0.42, 0.36, 0.33], "rough": 1.0},
       "T_brick": {"master": "proc", "pattern": 2, "a": [0.24,0.21,0.18], "b": [0.15,0.13,0.11], "c": [0.22,0.21,0.19],
                   "size_cm": [20, 10], "mortar_cm": 0.6, "scale_cm": 15, "contrast": 1.2, "rough": 0.9}}
      proc: "a" defaults to the Blender colour from export_manifest.json, "b" to a * "b_factor" (0.8).
config.json: the same file as ue_port.py ("name", "export_dir") + "polyhaven_dir".
Notes: in Custom HLSL use Texture2DSample(), not Tex.Sample() - Sample() does not compile in the path-tracing hit
shader and the whole material fails. Real ground albedos are dark (asphalt ~0.07 linear); Blender preview colours
are too bright for UE - add an unbound PostProcessVolume with exposure bias if the scene looks washed out.
"""
import sys, os, json, glob, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ue_port import Port, ref, full, rv

PROC_HLSL = r"""
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
float f = k.fbm(WP / max(Scale, 0.01));
float t = saturate((f - 0.5) * Contrast + 0.5);
float3 col = lerp(ColorA, ColorB, t);
int pat = (int)round(Pattern);
if (pat == 1) {
  float s = k.n(float3(WP.x / 0.6, WP.y / 0.6, WP.z / 25.0)) * 0.6 + k.n(float3(WP.x / 2.5, WP.y / 2.5, WP.z / 60.0)) * 0.4;
  float tw = saturate((0.55 * s + 0.45 * f - 0.5) * Contrast + 0.5);
  col = lerp(ColorA, ColorB, tw * tw);
} else if (pat == 2) {
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
} else if (pat == 3) {
  float course = frac(WP.z / max(Size.y, 1.0));
  col = lerp(ColorA, ColorB, t) * (1.0 - 0.35 * (1.0 - smoothstep(0.0, 0.18, course)));
}
return col;
"""
TRI = r"""
float3 n = normalize(N); float3 w = pow(abs(n), 4.0); w /= (w.x + w.y + w.z);
float3 p = WP / max(TileCm, 1.0);
float2 uvx = p.zy, uvy = p.xz, uvz = p.xy;
"""
TRI_BASE = TRI + "float3 c = Texture2DSample(Base, BaseSampler, uvx).rgb * w.x + Texture2DSample(Base, BaseSampler, uvy).rgb * w.y + Texture2DSample(Base, BaseSampler, uvz).rgb * w.z;\nreturn c * Tint;\n"
TRI_ROUGH = TRI + "float r = Texture2DSample(Rough, RoughSampler, uvx).r * w.x + Texture2DSample(Rough, RoughSampler, uvy).r * w.y + Texture2DSample(Rough, RoughSampler, uvz).r * w.z;\nreturn saturate(r * RoughMul);\n"
TRI_NORM = TRI + r"""
float3 tx = Texture2DSample(Norm, NormSampler, uvx).rgb * 2.0 - 1.0; tx.g = -tx.g;   // Poly Haven nor_dx -> GL
float3 ty = Texture2DSample(Norm, NormSampler, uvy).rgb * 2.0 - 1.0; ty.g = -ty.g;
float3 tz = Texture2DSample(Norm, NormSampler, uvz).rgb * 2.0 - 1.0; tz.g = -tz.g;
tx = float3(tx.xy + n.zy, abs(tx.z) * n.x); ty = float3(ty.xy + n.xz, abs(ty.z) * n.y); tz = float3(tz.xy + n.xy, abs(tz.z) * n.z);
float3 o = normalize(tx.zyx * w.x + ty.xzy * w.y + tz.xyz * w.z);
return normalize(lerp(n, o, Strength));
"""

class Surfaces(Port):
    def master_path(self, kind): return "%s/Materials/M_%s_%s" % (self.root, self.name, {"proc": "Proc", "tri": "Tri"}[kind])

    def custom(self, m, x, y, code, inputs, out_type):
        e = self.call("MT", "add_expression", {"material_or_function": m, "expression_class": ref("/Script/Engine.MaterialExpressionCustom"), "x": x, "y": y})
        self.call("OT", "set_properties", {"instance": e, "values": json.dumps({"Code": code, "OutputType": out_type})})
        # set_properties cannot resize an array and change its elements in one call: grow with copies, then rename
        cur = self.getp(e, ["Inputs"])["Inputs"]; cur = cur + [json.loads(json.dumps(cur[0])) for _ in range(len(inputs) - len(cur))]
        self.call("OT", "set_properties", {"instance": e, "values": json.dumps({"Inputs": cur})})
        cur = self.getp(e, ["Inputs"])["Inputs"]
        for el, nm in zip(cur, inputs): el["inputName"] = nm
        self.call("OT", "set_properties", {"instance": e, "values": json.dumps({"Inputs": cur})})
        return e

    def build(self, kind):
        M = self.master_path(kind)
        if self.call("AT", "exists", {"path": M}): print(M, "exists"); return
        m = self.call("MT", "create_material", {"folder_path": self.root + "/Materials", "asset_name": M.rsplit("/", 1)[1]})
        add = lambda cls, x, y: self.call("MT", "add_expression", {"material_or_function": m, "expression_class": ref("/Script/Engine." + cls), "x": x, "y": y})
        con = lambda a, ao, b, bi: self.call("MT", "connect_expressions", {"from_expression": a, "from_output_name": ao, "to_expression": b, "to_input_name": bi})
        def param(cls, name, val, y):
            e = add(cls, -1200, y); key = "Texture" if "Texture" in cls else "DefaultValue"
            self.call("OT", "set_properties", {"instance": e, "values": json.dumps({"ParameterName": name, key: val})}); return e
        wp = add("MaterialExpressionWorldPosition", -1200, -300); nrm = add("MaterialExpressionVertexNormalWS", -1200, -200)
        out = lambda e, prop: self.call("MT", "connect_to_output", {"expression": e, "output_name": "", "material_property": prop})
        if kind == "proc":
            ins = ["WP", "N", "ColorA", "ColorB", "ColorC", "Size", "Scale", "Contrast", "Pattern", "Mortar"]
            cus = self.custom(m, -400, 0, PROC_HLSL, ins, "CMOT_Float3")
            con(wp, "", cus, "WP"); con(nrm, "", cus, "N"); y = -100
            for nm, v in (("ColorA", .5), ("ColorB", .4), ("ColorC", .3)):
                con(param("MaterialExpressionVectorParameter", nm, {"R": v, "G": v, "B": v, "A": 1}, y), "RGB", cus, nm); y += 110
            con(param("MaterialExpressionVectorParameter", "Size", {"R": 100, "G": 50, "B": 0, "A": 1}, y), "RGB", cus, "Size"); y += 110
            for nm, v in (("Scale", 30.0), ("Contrast", 1.0), ("Pattern", 0.0), ("Mortar", 1.0)):
                con(param("MaterialExpressionScalarParameter", nm, v, y), "", cus, nm); y += 90
            out(cus, "MP_BaseColor"); out(param("MaterialExpressionScalarParameter", "Roughness", 0.8, y), "MP_Roughness")
        else:
            self.call("OT", "set_properties", {"instance": m, "values": json.dumps({"bTangentSpaceNormal": False})})
            white = "/Engine/EngineResources/WhiteSquareTexture.WhiteSquareTexture"
            base = param("MaterialExpressionTextureObjectParameter", "BaseTex", white, 0)
            rough = param("MaterialExpressionTextureObjectParameter", "RoughTex", white, 150)
            norm = param("MaterialExpressionTextureObjectParameter", "NormTex", white, 300)
            tile = param("MaterialExpressionScalarParameter", "TileCm", 200.0, 450); rmul = param("MaterialExpressionScalarParameter", "RoughMul", 1.0, 540)
            stren = param("MaterialExpressionScalarParameter", "NormalStrength", 1.0, 630)
            tint = param("MaterialExpressionVectorParameter", "Tint", {"R": 1, "G": 1, "B": 1, "A": 1}, 720)
            cb = self.custom(m, -500, -100, TRI_BASE, ["WP", "N", "TileCm", "Base", "Tint"], "CMOT_Float3")
            cr = self.custom(m, -500, 200, TRI_ROUGH, ["WP", "N", "TileCm", "Rough", "RoughMul"], "CMOT_Float1")
            cn = self.custom(m, -500, 500, TRI_NORM, ["WP", "N", "TileCm", "Norm", "Strength"], "CMOT_Float3")
            for c in (cb, cr, cn): con(wp, "", c, "WP"); con(nrm, "", c, "N"); con(tile, "", c, "TileCm")
            con(base, "", cb, "Base"); con(tint, "RGB", cb, "Tint"); con(rough, "", cr, "Rough"); con(rmul, "", cr, "RoughMul")
            con(norm, "", cn, "Norm"); con(stren, "", cn, "Strength")
            out(cb, "MP_BaseColor"); out(cr, "MP_Roughness"); out(cn, "MP_Normal")
        self.call("MT", "recompile", {"material_or_function": m}); self.save([M]); print("built", M)

    # ------------------------------------------------------------ Poly Haven
    def ph(self, url): return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "ai-wide-area-modeling"}), timeout=60))
    def ph_list(self, words, sizes=False):
        allt = self.ph("https://api.polyhaven.com/assets?t=textures")
        hit = sorted(i for i, a in allt.items() if any(w in i or any(w in t for t in a.get("tags", [])) for w in words))
        for i in hit:
            if sizes:
                f = self.ph("https://api.polyhaven.com/files/" + i)
                mb = sum(f[m]["2k"]["jpg"]["size"] for m in ("Diffuse", "nor_dx", "Rough") if m in f) / 1e6
                print("%-28s %5.1f MB" % (i, mb))
            else: print(i)
    def ph_get(self, ids):
        d = self.cfg["polyhaven_dir"]; tot = 0
        for i in ids:
            f = self.ph("https://api.polyhaven.com/files/" + i); os.makedirs(os.path.join(d, i), exist_ok=True)
            for m in ("Diffuse", "nor_dx", "Rough"):
                e = f[m]["2k"]["jpg"]; out = os.path.join(d, i, e["url"].rsplit("/", 1)[1])
                if not (os.path.exists(out) and os.path.getsize(out) == e["size"]):
                    open(out, "wb").write(urllib.request.urlopen(urllib.request.Request(e["url"], headers={"User-Agent": "ai-wide-area-modeling"}), timeout=300).read())
                tot += os.path.getsize(out)
        print("%d sets, %.1f MB in %s" % (len(ids), tot / 1e6, d))
    def tex_path(self, s, kind): return "%s/Textures/PolyHaven/T_%s_%s" % (self.root, s, kind)
    def import_tex(self):
        TF = self.root + "/Textures/PolyHaven"; self.call("AT", "create_folder", {"path": TF})
        for d in sorted(glob.glob(os.path.join(self.cfg["polyhaven_dir"], "*"))):
            s = os.path.basename(d)
            for f in glob.glob(os.path.join(d, "*_2k.jpg")):
                kind = "D" if "_diff_" in f else ("N" if "_nor_dx_" in f else "R"); p = self.tex_path(s, kind)
                if self.call("AT", "exists", {"path": p}): continue
                t = self.call("TX", "import_file", {"folder_path": TF, "asset_name": p.rsplit("/", 1)[1], "source_file": f})
                t = t[0] if isinstance(t, list) else t
                if kind != "D": self.call("OT", "set_properties", {"instance": t, "values": json.dumps({"SRGB": False, "CompressionSettings": "TC_Default"})})
                self.save([p])
            print("imported", s, flush=True)

    # ------------------------------------------------------------ apply
    def apply(self, mapping):
        mats = self.man.get("_materials", {}); done = []
        for mat, s in mapping.items():
            inst = ref(full("%s/Materials/MI_%s" % (self.root, mat)))
            self.call("MI", "set_parent", {"instance": inst, "parent": ref(full(self.master_path(s["master"])))})
            vec = lambda nm, v: self.call("MI", "set_vector_parameter", {"instance": inst, "name": nm, "value": {"r": v[0], "g": v[1], "b": v[2], "a": 1}})
            sca = lambda nm, v: self.call("MI", "set_scalar_parameter", {"instance": inst, "name": nm, "value": float(v)})
            if s["master"] == "tri":
                for nm, kind in (("BaseTex", "D"), ("RoughTex", "R"), ("NormTex", "N")):
                    self.call("MI", "set_texture_parameter", {"instance": inst, "name": nm, "value": ref(full(self.tex_path(s["set"], kind)))})
                sca("TileCm", s.get("tile_cm", 200)); sca("RoughMul", s.get("rough", 1.0)); vec("Tint", s.get("tint", [1, 1, 1]))
            else:
                a = s.get("a") or mats.get(mat, [0.5, 0.5, 0.5])[:3]; bf = s.get("b_factor", 0.8)
                vec("ColorA", a); vec("ColorB", s.get("b") or [v * bf for v in a]); vec("ColorC", s.get("c") or [v * 0.6 for v in a])
                sz = s.get("size_cm", [100, 50]); vec("Size", [sz[0], sz[1], 0])
                sca("Pattern", s.get("pattern", 0)); sca("Scale", s.get("scale_cm", 30)); sca("Contrast", s.get("contrast", 1.0))
                sca("Mortar", s.get("mortar_cm", 1.0)); sca("Roughness", s.get("rough", mats.get(mat, [0, 0, 0, 0.8])[3]))
            done.append("%s/Materials/MI_%s" % (self.root, mat))
        self.save(done); print("applied", len(done))

if __name__ == "__main__":
    from ue_port import TS
    TS["TX"] = "editor_toolset.toolsets.texture.TextureTools"
    S = Surfaces(sys.argv[1]); step = sys.argv[2]; rest = sys.argv[3:]
    if step in ("proc", "tri"): S.build(step)
    elif step == "polyhaven-list": S.ph_list([w for w in rest if not w.startswith("--")], "--sizes" in rest)
    elif step == "polyhaven-get": S.ph_get(rest)
    elif step == "import-tex": S.import_tex()
    elif step == "apply": S.apply(json.load(open(rest[0], encoding="utf-8")))
    else: sys.exit(__doc__)
