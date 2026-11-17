r"""Call the Unreal Editor MCP server directly over HTTP (JSON-RPC), like lfs_mcp.py does for LichtFeld.
Use when the editor runs its MCP server (ModelContextProtocol plugin, default http://127.0.0.1:8000/mcp) but the
client session has no unreal-mcp tools registered.

usage: python ue_mcp.py toolsets                        list toolsets (meta-tool list_toolsets)
       python ue_mcp.py describe <Toolset>              tool schemas of one toolset (UE 5.8 and 5.9 forms)
       python ue_mcp.py tools <Toolset.Tool> ...        UE 5.9: full schemas of single tools
       python ue_mcp.py call <Toolset> <tool> '<json args>'   dispatch through call_tool
       python ue_mcp.py raw <method> '<json params>'    any JSON-RPC method (tools/list, ...)
Environment: UE_MCP_URL overrides the endpoint. Python import: from ue_mcp import Ue; Ue().call(ts, tool, {...})
"""
import sys, os, json, urllib.request

URL = os.environ.get("UE_MCP_URL", "http://127.0.0.1:8000/mcp")

class Ue:
    def __init__(self, url=URL, timeout=600):
        self.url, self.timeout, self.sid, self.n = url, timeout, None, 0
        self.rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "claude-code-ue", "version": "1"}})
        self.notify("notifications/initialized")

    def _post(self, body):
        h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.sid: h["Mcp-Session-Id"] = self.sid
        req = urllib.request.Request(self.url, data=json.dumps(body).encode(), headers=h, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            self.sid = r.headers.get("Mcp-Session-Id") or self.sid
            txt = r.read().decode("utf-8", "replace")
        if not txt.strip(): return None
        if txt.lstrip().startswith("event:") or txt.lstrip().startswith("data:"):      # SSE framing
            txt = "\n".join(l[5:].strip() for l in txt.splitlines() if l.startswith("data:"))
        return json.loads(txt)

    def notify(self, method, params=None):
        self._post({"jsonrpc": "2.0", "method": method, **({"params": params} if params else {})})

    def rpc(self, method, params=None):
        self.n += 1
        r = self._post({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params or {}})
        if r is None: return None
        if "error" in r: raise RuntimeError(json.dumps(r["error"], ensure_ascii=False))
        return r["result"]

    def tool(self, name, args=None):
        return self.rpc("tools/call", {"name": name, "arguments": args or {}})

    def call(self, toolset, tool, args=None):
        """Dispatch a toolset tool via call_tool; returns parsed JSON of the text content when possible."""
        res = self.tool("call_tool", {"toolset_name": toolset, "tool_name": tool, "arguments": args or {}})
        return unwrap(res)

def unwrap(res):
    if not isinstance(res, dict): return res
    out = []
    for c in res.get("content", []):
        if c.get("type") == "text":
            t = c["text"]
            try: out.append(json.loads(t))
            except Exception: out.append(t)
    if res.get("structuredContent") is not None: return res["structuredContent"]
    v = out[0] if len(out) == 1 else out
    if res.get("isError"): raise RuntimeError(json.dumps(v, ensure_ascii=False)[:2000])
    return v

if __name__ == "__main__":
    a = sys.argv[1:]; ue = Ue()
    if a[0] == "toolsets": r = unwrap(ue.tool("list_toolsets"))
    elif a[0] == "describe":
        try: r = unwrap(ue.tool("describe_toolset", {"toolset_name": a[1]}))                       # UE 5.8
        except Exception: r = unwrap(ue.tool("describe_toolsets", {"toolset_names": a[1:], "include_schemas": True}))   # UE 5.9
    elif a[0] == "tools": r = unwrap(ue.tool("describe_tools", {"tool_names": a[1:]}))             # UE 5.9: full schemas of Toolset.Tool names
    elif a[0] == "call": r = ue.call(a[1], a[2], json.loads(a[3]) if len(a) > 3 else {})
    elif a[0] == "raw": r = ue.rpc(a[1], json.loads(a[2]) if len(a) > 2 else {})
    else: sys.exit(__doc__)
    sys.stdout.reconfigure(encoding="utf-8")                                                       # cp932 consoles choke on the tool descriptions
    print(json.dumps(r, ensure_ascii=False, indent=1) if not isinstance(r, str) else r)

def capture(ue, path, loc, rot, width=None):
    """EditorAppToolset.CaptureViewport from a pose (UE cm / degrees) -> PNG file. Returns the path."""
    import base64
    res = ue.tool("call_tool", {"toolset_name": "EditorToolset.EditorAppToolset", "tool_name": "CaptureViewport",
                                "arguments": {"captureTransform": {"location": loc, "rotation": rot, "scale": {"x": 1, "y": 1, "z": 1}}, "annotations": None}})
    for c in res.get("content", []):
        if c.get("type") == "image": data = c["data"]; break
        if c.get("type") == "text":
            j = json.loads(c["text"]); data = j["returnValue"]["image"]["data"]; break
    open(path, "wb").write(base64.b64decode(data)); return path
