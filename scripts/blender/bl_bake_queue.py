r"""Run bl_photo_bake.py jobs one after another from a Blender timer, so the MCP call returns at once (long bakes exceed
the MCP request timeout). Progress goes to <out_dir>/bake_queue_status.json; poll that file from outside.

    BAKE_QUEUE = {"jobs": [BAKE dict, ...], "script": SH + r"\bl_photo_bake.py", "status": r"...\bake_queue_status.json"}
    p = SH + r"\bl_bake_queue.py"; exec(compile(open(p, encoding="utf-8").read(), p, "exec"), globals())
"""
import bpy, json, time, traceback

_q = dict(globals()["BAKE_QUEUE"]); _q["jobs"] = list(_q["jobs"]); _q["done"] = []

def _write(state):
    json.dump(dict(state=state, done=_q["done"], left=[j["group"] for j in _q["jobs"]], t=time.strftime("%H:%M:%S")),
              open(_q["status"], "w"), indent=1)

def _step():
    if not _q["jobs"]: _write("finished"); return None
    job = _q["jobs"].pop(0); _write("running " + job["group"])
    ns = {"BAKE": job}
    try:
        exec(compile(open(_q["script"], encoding="utf-8").read(), _q["script"], "exec"), ns)
        _q["done"].append(ns.get("result"))
    except Exception:
        _q["done"].append({"group": job["group"], "error": traceback.format_exc()[-1500:]})
    _write("running")
    return 0.5                                   # next job after the UI had a moment

_write("queued")
bpy.app.timers.register(_step, first_interval=0.5)
result = {"queued": [j["group"] for j in _q["jobs"]]}
