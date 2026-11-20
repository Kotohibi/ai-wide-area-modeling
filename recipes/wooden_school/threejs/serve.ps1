# Open the Three.js viewer: serves the public folder on http://127.0.0.1:8771 and opens the page in the default browser.
# (Browsers block loading the .glb / .json files from file://, so the page needs a local server.) Stop with Ctrl+C.
# Regenerate the data after changing the Blender model (from the model folder):
#   python web\make_materials.py
#   & "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b ruin_school.blend -P web\export_web.py -- ruin
#   & "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b ruin_school_restored.blend -P web\export_web.py -- restored
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Start-Process "http://127.0.0.1:8771/index.html"
python -m http.server 8771 --bind 127.0.0.1 --directory (Join-Path $here "public")
