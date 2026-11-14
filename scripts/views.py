r"""Choose training views, render them from the 3DGS in LichtFeld, and sync the LichtFeld viewport with the model frame.

usage: python views.py <project.json> <command> ...

  select <set> (--names a.png,b.png | --near x,y,z [--n 6] [--maxdist 40] | --every K) [--width 640]
      Writes <project_dir>\views\<set>.json (and a copy in the Blender shared folder): pose + intrinsics of each photo
      in the model frame. --near picks photos that SEE the model point (in front, inside the image, nearest first,
      spread over viewing directions) - the usual way to check one object from several sides.
  lfs <set>            Render the 3DGS from exactly those training cameras (render_capture camera_index=uid)
                       -> views\<set>\lfs_<stem>.png, same pose and FOV as the photo.
  viewport [<set>]     Current LichtFeld viewport (camera_get) -> model-frame camera "LFS_view" (+ a capture of the
                       viewport) appended to the set (default set "lfs_view"). Use when the user shows a view in LFS.
  look ex,ey,ez tx,ty,tz [--fov 60]   Point the LichtFeld viewport from model-frame eye to target (metres, Z up).
  goto <image name>    Move the LichtFeld viewport to a training camera.
  restore              Put the LichtFeld viewport back where it was at setup (do this after look/goto: it is the user's view).
  find x,y,z [--n 12] [--crop 360] [--out sheet.png]   Photos that see a model point, cropped around it with a marker.
"""
import sys, os, json, argparse, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from project import Project

def vec(s): return np.array([float(v) for v in s.split(",")])

def seeing(P, X, maxdist=None):
    """Photos whose frustum contains model point X: list of (dist, name, u, v, view dir)."""
    import colmap_io
    out = []
    Xr = P.to_raw(X[None])[0]
    for n, im in P.imgs.items():
        cam = P.cams[im["camera_id"]]
        (u, v), z = (lambda r: (r[0][0], r[1][0]))(colmap_io.project(cam, im, Xr[None]))
        if z <= 0 or not (0 <= u < cam["width"] and 0 <= v < cam["height"]): continue
        d = P.S * np.linalg.norm(colmap_io.cam_center(im) - Xr)
        if maxdist and d > maxdist: continue
        out.append((d, n, u, v, P.dir_to_model(colmap_io.cam_center(im) - Xr) / (d / P.S)))
    return sorted(out)

def spread(cands, n):
    """Nearest views first, but prefer new viewing directions (azimuth bins of 45 deg)."""
    pick, used = [], set()
    for c in cands:
        b = int(((np.degrees(np.arctan2(c[4][1], c[4][0])) + 360) % 360) // 45)
        if b not in used: pick.append(c); used.add(b)
        if len(pick) >= n: return pick
    for c in cands:
        if c not in pick: pick.append(c)
        if len(pick) >= n: break
    return pick

def write_set(P, name, cams):
    os.makedirs(os.path.join(P.dir, "views"), exist_ok=True)
    p = os.path.join(P.dir, "views", name + ".json"); json.dump(cams, open(p, "w", encoding="utf-8"), indent=1)
    sh = P.cfg.get("shared_dir")
    if sh and os.path.isdir(sh):
        os.makedirs(os.path.join(sh, "views"), exist_ok=True)
        json.dump(cams, open(os.path.join(sh, "views", name + ".json"), "w", encoding="utf-8"), indent=1)
    return p

def coords_first(rest):
    """Let model-frame points with negative values ("-5,68,2.5") through argparse: options first, then '--', then points."""
    if "--" in rest: return rest
    opts, pos, i = [], [], 0
    while i < len(rest):
        if rest[i].startswith("--"): opts += rest[i:i + 2]; i += 2
        else: pos.append(rest[i]); i += 1
    return opts + ["--"] + pos

def main():
    P = Project(sys.argv[1]); cmd = sys.argv[2]; ap = argparse.ArgumentParser(); rest = sys.argv[3:]
    if cmd in ("look", "find"): rest = coords_first(rest)
    if cmd == "select":
        ap.add_argument("set"); ap.add_argument("--names"); ap.add_argument("--near"); ap.add_argument("--n", type=int, default=6)
        ap.add_argument("--maxdist", type=float); ap.add_argument("--every", type=int)
        a = ap.parse_args(rest)
        if a.names: names = a.names.split(",")
        elif a.near: names = [c[1] for c in spread(seeing(P, vec(a.near), a.maxdist), a.n)]
        elif a.every: names = P.names()[:: a.every]
        else: sys.exit("give --names, --near or --every")
        cams = [P.camera(n) for n in names if n in P.imgs]
        sh = P.cfg.get("shared_dir")
        if sh and os.path.isdir(sh):                      # Blender may not see the dataset folder (Store sandbox)
            from PIL import Image
            od = os.path.join(sh, "views", a.set); os.makedirs(od, exist_ok=True)
            for c in cams:
                q = os.path.join(od, "photo_" + os.path.splitext(c["name"])[0] + ".jpg")
                im = Image.open(c["photo"]).convert("RGB"); im.thumbnail((1280, 1280)); im.save(q, quality=90); c["photo_shared"] = q
        print(write_set(P, a.set, cams)); [print(" ", c["name"], np.round(c["loc"], 2).tolist()) for c in cams]
    elif cmd == "lfs":
        ap.add_argument("set"); ap.add_argument("--width", type=int, default=640); a = ap.parse_args(rest)
        from lfs_mcp import Lfs
        lfs = Lfs(); cams = json.load(open(os.path.join(P.dir, "views", a.set + ".json"), encoding="utf-8"))
        od = os.path.join(P.dir, "views", a.set); os.makedirs(od, exist_ok=True)
        for c in cams:
            if c.get("uid") is None: print("no LichtFeld uid for", c["name"]); continue
            lfs.save_image(lfs.call("render_capture", camera_index=c["uid"], width=a.width), os.path.join(od, "lfs_" + os.path.splitext(c["name"])[0] + ".png"))
            print("rendered", c["name"])
    elif cmd == "viewport":
        ap.add_argument("set", nargs="?", default="lfs_view"); ap.add_argument("--width", type=int, default=1280); a = ap.parse_args(rest)
        from lfs_mcp import Lfs
        lfs = Lfs(); cg = lfs.json("camera_get"); vc = P.viewport_camera(cg)
        if min(cg["camera"].get("width", 0) or 0, cg["camera"].get("height", 0) or 0) < 50:
            print("WARNING: LichtFeld reports a %sx%s viewport - the window is probably minimised or hidden. The capture is then the LAST "
                  "frame it drew and may not match camera_get. Ask the user to bring the LichtFeld window up and retry."
                  % (cg["camera"].get("width"), cg["camera"].get("height")))
        od = os.path.join(P.dir, "views", a.set); os.makedirs(od, exist_ok=True)
        cams = []
        sp = os.path.join(P.dir, "views", a.set + ".json")
        if os.path.exists(sp): cams = json.load(open(sp, encoding="utf-8"))
        vc["name"] = "LFS_view_%02d.png" % len(cams)
        img = os.path.join(od, "lfs_" + vc["name"]); lfs.save_image(lfs.call("render_capture", width=a.width), img)
        from PIL import Image
        w, h = Image.open(img).size; vc.update(w=w, h=h, photo=img)        # the viewport capture plays the "photo" role
        cams.append(vc); print(write_set(P, a.set, cams), vc["name"], "eye(m)", np.round(vc["loc"], 2).tolist(), "fov_v", vc["fov_v_deg"])
    elif cmd == "look":
        ap.add_argument("eye"); ap.add_argument("target"); ap.add_argument("--fov", type=float); a = ap.parse_args(rest)
        from lfs_mcp import Lfs
        e = P.raw_to_world(P.to_raw(vec(a.eye)[None]))[0]; t = P.raw_to_world(P.to_raw(vec(a.target)[None]))[0]
        up = P.raw_dir_to_world(np.array(P.cfg["frame"]["up_raw"]))
        kw = dict(eye=e.tolist(), target=t.tolist(), up=(up / np.linalg.norm(up)).tolist())
        if a.fov: kw["fov_degrees"] = a.fov
        print(Lfs().text(Lfs().call("camera_set_view", **kw))[:300])
    elif cmd == "restore":
        from lfs_mcp import Lfs
        v = P.cfg.get("viewport_at_setup") or sys.exit("no viewport saved in project.json")
        Lfs().call("camera_set_view", eye=v["eye"], target=v["target"], up=v["up"], fov_degrees=v["fov_degrees"]); print("viewport restored")
    elif cmd == "goto":
        from lfs_mcp import Lfs
        print(Lfs().text(Lfs().call("camera_go_to_dataset_camera", uid=P.uid(rest[0])))[:300])
    elif cmd == "find":
        ap.add_argument("point"); ap.add_argument("--n", type=int, default=12); ap.add_argument("--crop", type=int, default=360)
        ap.add_argument("--maxdist", type=float); ap.add_argument("--out"); a = ap.parse_args(rest)
        X = vec(a.point); picks = spread(seeing(P, X, a.maxdist), a.n)
        for d, n, u, v, vd in picks: print("%-50s dist %6.1f m  px (%4.0f,%4.0f)  view from az %4.0f deg" % (n, d, u, v, np.degrees(np.arctan2(vd[1], vd[0]))))
        if a.out:
            from PIL import Image, ImageDraw
            T = 240; cols = 4; rows = (len(picks) + cols - 1) // cols; sheet = Image.new("RGB", (cols * T, rows * T), (30, 30, 30))
            for i, (d, n, u, v, vd) in enumerate(picks):
                im = Image.open(P.photo_path(n)).convert("RGB"); r = a.crop // 2
                cr = im.crop((int(u) - r, int(v) - r, int(u) + r, int(v) + r)).resize((T, T)); dr = ImageDraw.Draw(cr)
                dr.ellipse((T / 2 - 6, T / 2 - 6, T / 2 + 6, T / 2 + 6), outline=(255, 0, 0), width=2); dr.text((4, 4), "%s %.0fm" % (n[-24:], d), fill=(255, 255, 0))
                sheet.paste(cr, ((i % cols) * T, (i // cols) * T))
            sheet.save(a.out); print(a.out)
    else:
        print(__doc__)

if __name__ == "__main__": main()
