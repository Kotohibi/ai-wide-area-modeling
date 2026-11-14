# Render the 3DGS from training cameras (exactly the photo's pose) via LichtFeld MCP.
#   powershell -File lfs_capture_dataset.ps1 -Cams <cams.csv> -Out <dir> -Names name1.png,name2.png [-Width 480]
# cams.csv: uid,x,y,z,image_name (from camera_list). Writes <dir>\lfs_<image_name>.png for each name.
# Together with the training photo and a Blender render from the same COLMAP pose (cmp_render.py) this gives a
# pixel-aligned photo | 3DGS | model triple: the 3DGS shows what the reconstruction "knows", the photo is ground truth.
param([string]$Cams, [string]$Out, [string[]]$Names, [int]$Width = 480)
. (Join-Path $PSScriptRoot "lfs_mcp.ps1")
$map = @{}
Get-Content $Cams | ForEach-Object { $f = $_.Split(","); if ($f.Count -ge 5) { $map[$f[4]] = [int]$f[0] } }
foreach ($n in $Names) {
    if (-not $map.ContainsKey($n)) { Write-Output "unknown image $n"; continue }
    $r = LfsRaw "render_capture" @{ camera_index = $map[$n]; width = $Width }
    LfsSaveImage $r (Join-Path $Out ("lfs_" + $n))
    Write-Output "rendered $n (uid $($map[$n]))"
}
