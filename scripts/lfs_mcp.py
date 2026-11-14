r"""Minimal LichtFeld Studio MCP client (JSON-RPC over HTTP, standard library only).

As a module:
    from lfs_mcp import Lfs
    lfs = Lfs()                                  # http://127.0.0.1:45677/mcp (env LFS_URL overrides)
    cams = lfs.json("camera_list")               # text content parsed as JSON
    lfs.save_image(lfs.call("render_capture", camera_index=12, width=640), "out.png")
From the shell:
    python lfs_mcp.py tools                      # list tool names
    python lfs_mcp.py call camera_get            # print the text result
    python lfs_mcp.py call transform_get node=Model
    python lfs_mcp.py image out.png render_capture camera_index=12 width=640
Arguments are key=value; values are parsed as JSON when possible (numbers, lists, true/false).
After LichtFeld restarts the server answers "not initialized" until `initialize` is sent; this client does that
automatically and keeps the mcp-session-id header if the server issues one.
"""
import json, os, sys, base64, random, urllib.request

class Lfs:
    def __init__(self, url=None, timeout=600):
        self.url = url or os.environ.get("LFS_URL", "http://127.0.0.1:45677/mcp")
        self.timeout = timeout
        self.headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}

    def _post(self, obj):
        req = urllib.request.Request(self.url, json.dumps(obj).encode(), self.headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            sid = r.headers.get("mcp-session-id")
            if sid: self.headers["mcp-session-id"] = sid
            body = r.read().decode("utf-8")
        if not body.strip(): return {}
        if body.lstrip().startswith("{"): return json.loads(body)
        data = [l[5:].strip() for l in body.splitlines() if l.startswith("data:")]     # SSE framing
        return json.loads(data[-1]) if data else {}

    def initialize(self):
        self._post({"jsonrpc": "2.0", "id": 0, "method": "initialize",
                    "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "lfs-py", "version": "1.0"}}})
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def rpc(self, method, params=None):
        req = {"jsonrpc": "2.0", "id": random.randint(1, 1 << 30), "method": method, "params": params or {}}
        res = self._post(req)
        if "error" in res and "not initialized" in str(res["error"].get("message", "")).lower():
            self.initialize(); res = self._post(req)
        if "error" in res: raise RuntimeError("LFS error: %s" % res["error"].get("message"))
        return res.get("result", {})

    def call(self, name, **arguments):
        r = self.rpc("tools/call", {"name": name, "arguments": arguments})
        if r.get("isError"): raise RuntimeError("LFS tool error: %s" % self.text(r))
        return r

    @staticmethod
    def text(result):
        return "".join(c.get("text", "") for c in result.get("content", []) if c.get("type") == "text")

    def json(self, name, **arguments):
        t = self.text(self.call(name, **arguments))
        try: return json.loads(t)
        except ValueError: return t

    @staticmethod
    def save_image(result, path):
        for c in result.get("content", []):
            if c.get("type") == "image":
                open(path, "wb").write(base64.b64decode(c["data"])); return path
        raise RuntimeError("no image in result: %s" % Lfs.text(result)[:200])

    def tools(self):
        return self.rpc("tools/list").get("tools", [])

def _args(kv):
    out = {}
    for a in kv:
        k, v = a.split("=", 1)
        try: out[k] = json.loads(v)
        except ValueError: out[k] = v
    return out

if __name__ == "__main__":
    lfs = Lfs(); cmd = sys.argv[1] if len(sys.argv) > 1 else "tools"
    if cmd == "tools":
        for t in lfs.tools(): print(t["name"], "::", " ".join(t.get("description", "").split())[:100])
    elif cmd == "schema":
        for t in lfs.tools():
            if t["name"] == sys.argv[2]: print(json.dumps(t, indent=1, ensure_ascii=False))
    elif cmd == "call":
        print(lfs.text(lfs.call(sys.argv[2], **_args(sys.argv[3:]))))
    elif cmd == "image":
        print(lfs.save_image(lfs.call(sys.argv[3], **_args(sys.argv[4:])), sys.argv[2]))
    else:
        print(__doc__)
