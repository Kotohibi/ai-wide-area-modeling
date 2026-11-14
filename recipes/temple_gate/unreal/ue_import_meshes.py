"""Import the exported FBX groups into /Game/Temple/Meshes, assign MI_T_<name> by slot name, enable Nanite on
heavy meshes. Usage: python ue_import_meshes.py [names...]  (default: every group in export_manifest.json except Planting)"""
import sys, json, os
sys.path.insert(0, __import__("os").environ.get("AWAM_SCRIPTS") or __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(globals().get("__file__", "."))), "..", "..", "..", "scripts"))  # skill scripts/ (set AWAM_SCRIPTS when run through exec)
from ue_mcp import Ue

ue = Ue()
SM = "editor_toolset.toolsets.static_mesh.StaticMeshTools"; AT = "editor_toolset.toolsets.asset.AssetTools"
rv = lambda r: r["returnValue"] if isinstance(r, dict) and "returnValue" in r else r
man = json.load(open(__import__("os").path.join(__import__("os").environ.get("PROJECT_DIR", "."), r"ue_export\export_manifest.json")))
names = sys.argv[1:] or [n for n in man if "Planting" not in n]
out = {}
for n in names:
    path = "/Game/Temple/Meshes/" + n
    if rv(ue.call(AT, "exists", {"path": path})): ue.call(AT, "delete", {"path": path})
    src = os.path.join(__import__("os").path.join(__import__("os").environ.get("PROJECT_DIR", "."), r"ue_export"), n + ".fbx")
    mesh = rv(ue.call(SM, "import_file", {"folder_path": "/Game/Temple/Meshes", "asset_name": n, "source_file": src,
                                           "import_materials": False, "combine_meshes": True}))[0]
    slots = rv(ue.call(SM, "get_material_slots", {"mesh": mesh}))
    bad = []
    for s in slots:
        mi = "/Game/Temple/Materials/MI_" + s
        if rv(ue.call(AT, "exists", {"path": mi})):
            ue.call(SM, "set_material", {"mesh": mesh, "slot_name": s, "material": {"refPath": mi + ".MI_" + s}})
        else: bad.append(s)
    tris = rv(ue.call(SM, "get_triangle_count", {"mesh": mesh}))
    if tris > 20000: ue.call(SM, "set_nanite_enabled", {"mesh": mesh, "enabled": True})
    ue.call(AT, "save_assets", {"asset_paths": [path]})
    b = rv(ue.call(SM, "get_bounds", {"mesh": mesh}))
    out[n] = {"tris": tris, "nanite": tris > 20000, "missing_mat": bad, "size_cm": [round(b["max"][a] - b["min"][a]) for a in "xyz"]}
    print(n, out[n], flush=True)
json.dump(out, open(__import__("os").path.join(__import__("os").environ.get("PROJECT_DIR", "."), r"ue_export\import_log.json"), "w"), indent=1)
