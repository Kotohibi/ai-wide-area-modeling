# LichtFeld Studio MCP helper (JSON-RPC over HTTP).
#   . .\lfs_mcp.ps1
#   $t = Lfs "camera_list" @{}              # -> text of the first content block (JSON string for most tools)
#   $r = LfsRaw "render_capture" @{ width = 1400 }   # -> full result (image blocks are base64 in $r.content[i].data)
# LichtFeld must be running; default endpoint http://127.0.0.1:45677/mcp.
# After LichtFeld restarts the server answers "Server not initialized" until `initialize` is called;
# LfsRaw does that automatically (and keeps the mcp-session-id header if the server issues one).
$script:LfsUrl = "http://127.0.0.1:45677/mcp"
$script:LfsHeaders = @{ Accept = "application/json, text/event-stream" }
function LfsPost($obj) {
    $b = $obj | ConvertTo-Json -Depth 8 -Compress
    Invoke-WebRequest -Uri $script:LfsUrl -Method Post -ContentType "application/json" -Headers $script:LfsHeaders -Body $b -UseBasicParsing -TimeoutSec 300
}
function LfsInit {
    $r = LfsPost @{ jsonrpc = "2.0"; id = 0; method = "initialize"; params = @{ protocolVersion = "2025-06-18"; capabilities = @{}; clientInfo = @{ name = "lfs-helper"; version = "1.0" } } }
    $sid = $r.Headers["mcp-session-id"]
    if ($sid) { $script:LfsHeaders["mcp-session-id"] = $sid }
    $null = LfsPost @{ jsonrpc = "2.0"; method = "notifications/initialized" }
}
function LfsRaw($name, $arguments) {
    $req = @{ jsonrpc = "2.0"; id = (Get-Random); method = "tools/call"; params = @{ name = $name; arguments = $arguments } }
    $res = (LfsPost $req).Content | ConvertFrom-Json
    if ($res.error -and $res.error.message -match "not initialized") { LfsInit; $res = (LfsPost $req).Content | ConvertFrom-Json }
    if ($res.error) { throw "LFS error: $($res.error.message)" }
    $res.result
}
function Lfs($name, $arguments) { (LfsRaw $name $arguments).content[0].text }
function LfsSaveImage($result, $path) {
    $img = $result.content | Where-Object { $_.type -eq "image" } | Select-Object -First 1
    [IO.File]::WriteAllBytes($path, [Convert]::FromBase64String($img.data))
}
