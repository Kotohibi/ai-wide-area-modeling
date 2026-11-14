# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
r"""Turn photo-review decisions about poles into $BLENDER_SHARED\street_furniture.json for build_furniture.py.

usage: python make_furniture_spec.py <scratch_dir> <review.json>
review.json: {"default": "light"|"drop", "default_light_h": 3.8,
              "items": {"<pole id>": {"type": ..., "face": deg, ...}, ...}}   (ids from sign_views.py / pole_index.json)
Every pole in pole_index.json gets the default unless reviewed; "type": "drop" removes false poles
(utility poles already in extras, parking-structure columns, sky-only crops).
"""
import sys, os, json
SP = sys.argv[1]; rv = json.load(open(sys.argv[2])); SH = os.environ.get("BLENDER_SHARED", "")
idx = json.load(open(SP + r"\pole_index.json"))
out = []
for p in idx:
    r = rv["items"].get(str(p["id"]), {})
    typ = r.get("type", rv.get("default", "light"))
    if typ == "drop": continue
    it = dict(x=p["x"], y=p["y"], type=typ, s=round(p["s"], 1), lat=round(p["lat"], 2), id=p["id"])
    if typ == "light":
        it["h"] = r.get("h", rv.get("default_light_h", 3.8))
        it["face"] = r.get("face", 90 if p["lat"] < 7 else -90)      # lamp arm reaches over the carriageway
    it.update({k: v for k, v in r.items() if k != "type"})
    out.append(it)
# posts the point clouds missed, located with ground_pick.py: review["add"] = [{"x","y","type",...}, ...]
for a in rv.get("add", []):
    out.append(dict(a, id=a.get("id", "added")))
json.dump({"items": out}, open(SH + r"\street_furniture.json", "w"), indent=1)
print({t: sum(1 for o in out if o["type"] == t) for t in ("light", "signal", "sign")})
