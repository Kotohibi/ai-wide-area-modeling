r"""A camera path made outside Unreal (Blender fly-through, a script) -> Level Sequence -> frames by Movie Render Queue.  UE 5.9+.

  python ue_camera_seq.py seq <camera.json> </Game/.../LS_Name>
  python ue_camera_seq.py render </Game/.../LS_Name> </Game/.../Map> <out dir> [--size 1280 720] [--range S E]
                                 [--warm 480 96] [--blur] [--name f_{frame_number}]
  python ue_camera_seq.py status

camera.json (model metres, z up; model (x, y, z) -> UE (100 x, -100 y, 100 z) cm):
  {"fps": 24, "lens_mm": 18, "sensor_mm": [36, 20.25],
   "frames": [{"f": 1, "loc": [x, y, z], "look": [x, y, z]}, ...],      # one entry per frame: position and look-at point
   "cuts": [[1, 400], [400, 900]]}                                       # optional shots, [start, end)
Write it from Blender with the camera evaluated on every frame (look = loc + forward); nothing of Blender is needed afterwards.

seq:    spawnable CineCameraActor (so the same sequence plays in every level that shares the coordinates: variants,
        seasons), one linear key per frame (the last key of a shot is constant), camera cut section per shot,
        depth of field off, filmback = the source camera's sensor so the horizontal field of view is the same.
render: PIE executor, deferred pass, jpg sequence (files <name>.jpeg, frame numbers = sequence frames), the pawn of the
        level's game mode is replaced (MoviePipelineGameOverrideSetting), motion blur off unless --blur (frames meant
        to be compared or wiped against an offline render have none).  --warm: engine frames (particles fill the air)
        and rendered frames (Lumen, exposure) before the first frame of every shot.  Returns when the queue is done.
The level must not be in PIE.  Check free disk space first: 1080p jpg is 1-1.5 MB per frame."""
import sys, os, json, math, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ue_py import run

UE_SEQ = r'''
import json
C = json.loads(@DATA@); K = C["keys"]; N0, N1 = K[0][0], K[-1][0]; at = unreal.AssetToolsHelpers.get_asset_tools(); eal = unreal.EditorAssetLibrary
P, name = "@SEQ@".rsplit("/", 1); eal.make_directory(P)
if eal.does_asset_exist("@SEQ@"): eal.delete_asset("@SEQ@")
seq = at.create_asset(name, P, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
seq.set_display_rate(unreal.FrameRate(C["fps"], 1)); seq.set_playback_start(N0); seq.set_playback_end(N1 + 1)
cam = seq.add_spawnable_from_class(unreal.CineCameraActor); cam.set_display_name("PathCam")
c = cam.get_object_template().get_editor_property("camera_component")      # (get_cine_camera_component() is None on a spawnable template)
fb = c.get_editor_property("filmback"); fb.set_editor_property("sensor_width", C["sensor"][0]); fb.set_editor_property("sensor_height", C["sensor"][1]); c.set_editor_property("filmback", fb)
ls = c.get_editor_property("lens_settings"); ls.set_editor_property("min_focal_length", 2.0); ls.set_editor_property("max_focal_length", 1000.0); c.set_editor_property("lens_settings", ls)
c.set_editor_property("current_focal_length", C["lens"])
fs = c.get_editor_property("focus_settings"); fs.set_editor_property("focus_method", unreal.CameraFocusMethod.DISABLE); c.set_editor_property("focus_settings", fs)
tr = cam.add_track(unreal.MovieScene3DTransformTrack); sec = tr.add_section(); sec.set_range(N0, N1 + 1)
ch = sec.get_all_channels()                                   # location x y z, rotation x(roll) y(pitch) z(yaw), scale
LIN = unreal.MovieSceneKeyInterpolation.LINEAR; CON = unreal.MovieSceneKeyInterpolation.CONSTANT; DR = unreal.MovieSceneTimeUnit.DISPLAY_RATE
last = set(e - 1 for s, e in C["cuts"])
for k in K:
    f = unreal.FrameNumber(k[0]); ip = CON if k[0] in last else LIN
    for j, v in ((0, k[1]), (1, k[2]), (2, k[3]), (3, 0.0), (4, k[4]), (5, k[5])): ch[j].add_key(f, v, 0.0, DR, ip)
ct = seq.add_track(unreal.MovieSceneCameraCutTrack); bid = seq.get_binding_id(cam)
for s, e in C["cuts"]:
    cs = ct.add_section(); cs.set_range(s, e); cs.set_camera_binding_id(bid)
eal.save_loaded_asset(seq, False)
{"frames": len(K), "range": [N0, N1], "shots": len(C["cuts"]), "hfov": c.get_horizontal_field_of_view()}
'''
UE_RENDER = r'''
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem); ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if ues.get_editor_world().get_path_name().split(".")[0] != "@MAP@": les.load_level("@MAP@")
sub = unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem); q = sub.get_queue(); q.delete_all_jobs()
job = q.allocate_new_job(unreal.MoviePipelineExecutorJob); job.job_name = "@SEQ@".rsplit("/", 1)[1]
job.sequence = unreal.SoftObjectPath("@SEQ@." + "@SEQ@".rsplit("/", 1)[1]); job.map = unreal.SoftObjectPath("@MAP@." + "@MAP@".rsplit("/", 1)[1])
cfg = job.get_configuration()
cfg.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase); cfg.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_JPG)
cfg.find_or_add_setting_by_class(unreal.MoviePipelineGameOverrideSetting)
o = cfg.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
o.output_directory = unreal.DirectoryPath(r"@OUT@"); o.file_name_format = "@NAME@"; o.zero_pad_frame_numbers = 4
o.output_resolution = unreal.IntPoint(@W@, @H@); o.override_existing_output = True
if @S@ >= 0: o.use_custom_playback_range = True; o.custom_start_frame = @S@; o.custom_end_frame = @E@ + 1
aa = cfg.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
aa.spatial_sample_count = 1; aa.temporal_sample_count = 1; aa.engine_warm_up_count = @WE@; aa.render_warm_up_count = @WR@; aa.render_warm_up_frames = True
if not @BLUR@:
    cv = cfg.find_or_add_setting_by_class(unreal.MoviePipelineConsoleVariableSetting); cv.add_or_update_console_variable("r.MotionBlurQuality", 0.0)
sub.render_queue_with_executor(unreal.MoviePipelinePIEExecutor)
True
'''
def keys(C):
    K = []; prev = None
    for f in C["frames"]:
        p, l = f["loc"], f["look"]; d = (l[0] - p[0], -(l[1] - p[1]), l[2] - p[2]); n = math.sqrt(sum(v * v for v in d)) or 1.0
        pitch = math.degrees(math.asin(max(-1.0, min(1.0, d[2] / n)))); yaw = math.degrees(math.atan2(d[1], d[0]))
        if prev is not None: yaw += 360.0 * round((prev - yaw) / 360.0)             # continuous: no 360 deg jump between neighbouring keys
        prev = yaw; K.append([int(f["f"]), round(100 * p[0], 2), round(-100 * p[1], 2), round(100 * p[2], 2), round(pitch, 4), round(yaw, 4)])
    return K
def sub(code, **kw):
    for k, v in kw.items(): code = code.replace("@%s@" % k, str(v))
    return code
def opt(a, name, n, default):
    if name in a:
        i = a.index(name); v = a[i + 1:i + 1 + n]; del a[i:i + 1 + n]; return v
    return default
if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    if a[0] == "seq":
        C = json.load(open(a[1], encoding="utf-8")); K = keys(C); sm = C.get("sensor_mm", [36.0, 20.25])
        data = {"fps": int(C.get("fps", 24)), "lens": float(C.get("lens_mm", 18.0)), "sensor": sm, "keys": K, "cuts": C.get("cuts") or [[K[0][0], K[-1][0] + 1]]}
        print(run(sub(UE_SEQ, DATA=repr(json.dumps(data)), SEQ=a[2])))
    elif a[0] == "status":
        print(run("unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem).is_rendering()"))
    elif a[0] == "render":
        size = opt(a, "--size", 2, ["1280", "720"]); rng = opt(a, "--range", 2, ["-1", "-1"]); warm = opt(a, "--warm", 2, ["480", "96"])
        name = opt(a, "--name", 1, ["f_{frame_number}"])[0]; blur = "--blur" in a
        if blur: a.remove("--blur")
        seq, mp, out = a[1], a[2], os.path.abspath(a[3]); os.makedirs(out, exist_ok=True)
        print(run(sub(UE_RENDER, MAP=mp, SEQ=seq, OUT=out, NAME=name, W=size[0], H=size[1], S=rng[0], E=rng[1], WE=warm[0], WR=warm[1], BLUR=blur)), flush=True)
        t0 = time.time(); time.sleep(20)
        while True:
            try: busy = run("unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem).is_rendering()")
            except Exception as ex: busy = True; print("  (editor busy: %s)" % str(ex)[:80], flush=True)
            got = len([f for f in os.listdir(out) if f.lower().endswith((".jpg", ".jpeg"))])
            print("  %4.0f s  %d frames" % (time.time() - t0, got), flush=True)
            if not busy: break
            time.sleep(30)
        print("RENDER_DONE", got, "frames in", out)
