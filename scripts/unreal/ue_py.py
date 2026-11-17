r"""Run Python inside the open Unreal Editor (UE 5.9+: PythonScriptingTools.execute_python over the editor's MCP server).
The `unreal` module is preimported; the script's final expression is the result (strings as they are, anything else
as JSON); top-level `await` works, and `await call_tool("Toolset.Tool", **args)` reaches the other tools.
Rejected outright: imports inside functions, time.sleep, urllib.request.urlopen, subprocess.run (see the tool's read_me).

usage: python ue_py.py <script.py> [KEY=VALUE ...]      (KEY=VALUE become string variables in front of the script)
       python ue_py.py -c "<code>"
Python: from ue_py import run, call;  run(code) -> parsed result;  call("EditorToolset.LevelToolset", "GetCurrentLevel")
The editor refuses tools while a slow task runs (imports, shader jobs): both wait and retry.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ue_mcp import Ue

PT = "editor_toolset.toolsets.python_scripting.PythonScriptingTools"
_ue = None
def ue():
    global _ue
    if _ue is None: _ue = Ue(timeout=1800)
    return _ue

def _retry(fn, tries=200):
    for i in range(tries):
        try: return fn()
        except RuntimeError as e:
            if "slow task" not in str(e) or i == tries - 1: raise
            time.sleep(3)

def run(code):
    r = _retry(lambda: ue().call(PT, "execute_python", {"script": {"content": code, "language": "Python"}}))
    v = r.get("returnValue") if isinstance(r, dict) else r
    if isinstance(v, str):
        try: return json.loads(v)
        except Exception: return v
    return v

def call(toolset, tool, args=None):
    r = _retry(lambda: ue().call(toolset, tool, args or {}))
    return r.get("returnValue", r) if isinstance(r, dict) else r

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    if a[0] == "-c": code = a[1]
    else: code = "".join("%s = %r\n" % tuple(kv.split("=", 1)) for kv in a[1:]) + open(a[0], encoding="utf-8").read()
    r = run(code); sys.stdout.reconfigure(encoding="utf-8")
    print(r if isinstance(r, str) else json.dumps(r, ensure_ascii=False, indent=1))
