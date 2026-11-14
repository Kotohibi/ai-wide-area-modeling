r"""Trees, shrubs and hedges in UE at measured positions/sizes, from real plant assets (Megaplants skeletal meshes
from Bridge/Fab, or any static meshes). Blender-made vegetation looks poor in UE: keep only positions and sizes.

usage: python ue_vegetation.py <config.json> measure [<root folder>]     -> <export_dir>/plants_measured.json
       python ue_vegetation.py <config.json> place <plants.json> [--folder <Name>/Vegetation]
plants.json (model frame, metres):
  {"trees":  [{"x": 5.2, "y": 51.0, "h": 9.0, "w": 6.0, "kind": "bare"}, ...],
   "rows":   [{"p0": [5.6, 29.0], "p1": [5.6, 42.5], "h": 1.8, "w": 1.1, "kind": "hedge", "pitch": 0.9}, ...]}
config.json (same as ue_port.py) + "veg_kinds": {"bare": ["Hornbeam_A", "European_Beech_B"], "conifer": [...],
  "hedge": ["Greasewood_A", ...]}  (keys of plants_measured.json; pick a variant whose native shape fits, the
  script scales it to h and to the crown width w within 0.6-1.6x of the uniform scale - 0.4-2.5x for rows)
Megaplants (UE 5.8): one ProceduralVegetation + four SkeletalMesh variants _A.._D per species; SkeletalMeshTools.
get_bounds returns origin/boxExtent (not min/max). Leaves are Nanite Assembly parts: they only render after
Project Settings > Rendering > Nanite Foliage (bEnableNaniteFoliage) is on and the editor restarted. The crown is
often off the pivot (cx, cy) - the script recentres it. Plants get no collision.
"""
import sys, os, json, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ue_port import Port, TS, rv

TS["SK"] = "editor_toolset.toolsets.skeletal_mesh.SkeletalMeshTools"

class Veg(Port):
    def measure(self, root="/Game/Megaplant_Library"):
        out = {}
        for tp, key in (("/Script/Engine.SkeletalMesh", "SK"), ("/Script/Engine.StaticMesh", "SM")):
            for a in self.call("AT", "find_assets", {"folder_path": root, "name": "", "asset_type": tp, "recursive": True}) or []:
                p = a if isinstance(a, str) else a["refPath"]
                if "/Instances/" in p: continue                      # Megaplant parts (branches, leaves)
                if "." not in p.rsplit("/", 1)[1]: p += "." + p.rsplit("/", 1)[1]
                b = self.call(key, "get_bounds", {"mesh": {"refPath": p}})
                if "origin" in b: o, e = b["origin"], b["boxExtent"]; mn = {k: o[k] - e[k] for k in "xyz"}; mx = {k: o[k] + e[k] for k in "xyz"}
                else: mn, mx = b["min"], b["max"]
                name = p.rsplit("/", 1)[1].split(".")[0]
                for pre in ("Tree_", "Shrub_", "SM_", "SK_"):
                    if name.startswith(pre): name = name[len(pre):]
                name = name.replace("_01_", "_").replace("_Forest", "")
                out[name] = {"path": p, "h": round(mx["z"] - max(mn["z"], 0)), "dx": round(mx["x"] - mn["x"]), "dy": round(mx["y"] - mn["y"]),
                             "cx": round((mx["x"] + mn["x"]) / 2), "cy": round((mx["y"] + mn["y"]) / 2)}
        f = os.path.join(self.cfg["export_dir"], "plants_measured.json"); json.dump(out, open(f, "w"), indent=1)
        for k, v in sorted(out.items()): print("%-26s h %5d cm  crown %4d x %4d" % (k, v["h"], v["dx"], v["dy"]))
        print(len(out), "->", f)

    def place(self, plants, folder):
        MP = json.load(open(os.path.join(self.cfg["export_dir"], "plants_measured.json"))); kinds = self.cfg["veg_kinds"]
        rnd = random.Random(11); n = 0
        if folder in (self.call("ST", "get_folders", {}) or []):            # get_actors_in_folder raises on a missing folder
            for a in self.call("ST", "get_actors_in_folder", {"folder_path": folder, "recursive": True}) or []:
                self.call("ST", "remove_from_scene", {"actor": a})
        def put(name, kind, x, y, h, w, squash):
            nonlocal n
            m = MP[rnd.choice(kinds[kind])]; s = 100.0 * h / max(m["h"], 1); sxy = s
            if w: sxy = min(max(100.0 * w / max((m["dx"] + m["dy"]) / 2, 1), s * squash[0]), s * squash[1])
            yaw = rnd.uniform(0, 360); a = math.radians(yaw)
            ox = (m["cx"] * math.cos(a) - m["cy"] * math.sin(a)) * sxy; oy = (m["cx"] * math.sin(a) + m["cy"] * math.cos(a)) * sxy
            act = self.call("ST", "add_to_scene_from_asset", {"asset_path": m["path"], "name": name, "parent": None, "snap_to_ground": False,
                "xform": {"location": {"x": 100 * x - ox, "y": -100 * y - oy, "z": 0}, "rotation": {"pitch": 0, "yaw": yaw, "roll": 0},
                          "scale": {"x": sxy, "y": sxy, "z": s}}})
            self.call("ST", "set_actor_folder", {"actor": act, "folder_path": folder}); n += 1
        for i, t in enumerate(plants.get("trees", [])):
            put(t.get("name", "Plant_%03d_%s" % (i, t["kind"])), t["kind"], t["x"], t["y"], t["h"], t.get("w"), (0.6, 1.6))
        for i, r in enumerate(plants.get("rows", [])):                      # hedges: a row of shrubs with a little jitter
            (x0, y0), (x1, y1) = r["p0"], r["p1"]; L = math.dist(r["p0"], r["p1"]); k = max(1, int(L / r.get("pitch", 0.9)))
            for j in range(k + 1):
                f = j / k
                put("Row_%02d_%03d" % (i, j), r["kind"], x0 + (x1 - x0) * f + rnd.uniform(-.08, .08), y0 + (y1 - y0) * f + rnd.uniform(-.08, .08),
                    r["h"] * rnd.uniform(0.92, 1.05), r.get("w"), (0.4, 2.5))
        self.save([self.call("ST", "get_current_level")]); print(n, "plants placed in", folder)

if __name__ == "__main__":
    V = Veg(sys.argv[1]); step = sys.argv[2]; rest = sys.argv[3:]
    if step == "measure": V.measure(*(rest[:1] or []))
    elif step == "place":
        fo = rest[rest.index("--folder") + 1] if "--folder" in rest else V.name + "/Vegetation"
        V.place(json.load(open(rest[0], encoding="utf-8")), fo)
    else: sys.exit(__doc__)
