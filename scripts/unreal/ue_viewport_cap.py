r"""Capture the open Unreal level through the LIVE level viewport (UE 5.9+), from poses given in model metres.

  python ue_viewport_cap.py set <cmp dir> [stems...] --out <dir> [--size 960]      cameras.json of cmp_set.py: the same poses as the
                                                                                    comparison photos -> <out>/<stem>_ue.png
  python ue_viewport_cap.py pose <out.png> x y z  tx ty tz [fov] [--size W H]      camera position and look-at target
Why the viewport and not SceneCaptureToolset.Capture: the offscreen capture has no temporal history, so Lumen and the
sky light are missing and every shadow is black.  Here the viewport is put in game view + realtime, moved, left to
settle (--wait seconds, default 10) and captured; its FOV is set wide enough to contain the wanted frame and the
centre is cropped.  The editor window must be visible (not minimised or covered).  Model (x, y, z) -> UE (100 x, -100 y, 100 z)."""
import sys, os, json, math, base64, time, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ue_py import ue, call, run, _retry
SC = "SceneCaptureToolset.SceneCaptureToolset"

def rot_from(fwd):
    f = (fwd[0], -fwd[1], fwd[2]); n = math.sqrt(sum(v * v for v in f)); f = [v / n for v in f]
    return {"pitch": math.degrees(math.asin(max(-1, min(1, f[2])))), "yaw": math.degrees(math.atan2(f[1], f[0])), "roll": 0.0}

def capture(path, loc, fwd, fov=90.0, size=(960, 960), wait=10.0):
    from PIL import Image
    vp = [v for v in call(SC, "ListEditorViewports", {}) if v["kind"] == "LevelEditor"][0]
    if not vp.get("bIsVisible", True): print("  warning: the level viewport is not visible - the image may be stale or refused")
    vw, vh = vp["size"]["x"], vp["size"]["y"]; asp = size[0] / size[1]
    th = math.tan(math.radians(fov) / 2); hv = max(th, th / asp * vw / vh); vfov = min(170.0, math.degrees(2 * math.atan(hv)))
    run("les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem); k = les.get_active_viewport_config_key()\n"
        "les.editor_set_game_view(True, k); les.editor_set_viewport_realtime(True, k); les.set_level_viewport_fov(%f, k)\n" % vfov)
    call("EditorToolset.EditorAppToolset", "SetCameraTransform", {"translation": {"x": 100 * loc[0], "y": -100 * loc[1], "z": 100 * loc[2]}, "rotation": rot_from(fwd)})
    time.sleep(wait)
    res = _retry(lambda: ue().tool("call_tool", {"toolset_name": SC, "tool_name": "CaptureEditorViewport", "arguments": {}}))
    data = next((c["data"] for c in res.get("content", []) if c.get("type") == "image"), None)
    if data is None: raise RuntimeError("no image: " + json.dumps(res)[:800])
    im = Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB"); W_, H_ = im.size
    hv = math.tan(math.radians(vfov) / 2); cw = W_ * th / hv; ch = cw / asp
    im = im.crop((int((W_ - cw) / 2), int((H_ - ch) / 2), int((W_ + cw) / 2), int((H_ + ch) / 2))).resize(size, Image.LANCZOS)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True); im.save(path); return path

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    def opt(name, n=1, default=None):
        if name in a:
            i = a.index(name); v = a[i + 1:i + 1 + n]; del a[i:i + 1 + n]; return v
        return default
    wait = float((opt("--wait") or [10])[0])
    if a[0] == "set":
        size = int((opt("--size") or [960])[0]); out = opt("--out")[0]; cams = json.load(open(os.path.join(a[1], "cameras.json")))
        for c in cams:
            if a[2:] and c["stem"] not in a[2:]: continue
            R = c["rot"]; fwd = [-R[0][2], -R[1][2], -R[2][2]]; fov = math.degrees(2 * math.atan(c["w"] / 2 / c["fx"]))
            print(capture(os.path.join(out, c["stem"] + "_ue.png"), c["loc"], fwd, fov, (size, int(size * c["h"] / c["w"])), wait), flush=True)
    elif a[0] == "pose":
        size = [int(v) for v in (opt("--size", 2) or [1280, 720])]; v = [float(x) for x in a[2:8]]; fov = float(a[8]) if len(a) > 8 else 90.0
        print(capture(a[1], v[:3], [v[3] - v[0], v[4] - v[1], v[5] - v[2]], fov, size, wait))
