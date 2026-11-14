r"""Create project.json for the 3DGS currently open in LichtFeld (or for a COLMAP folder alone).

usage: python setup_project.py <project_dir> [--sfm DIR] [--up auto|cameras|ground|x,y,z] [--ref viewport|<image name>]
                               [--scale M_PER_UNIT | --cam-height-m 1.6] [--shared BLENDER_SHARED_DIR] [--no-lfs]

What it does
  1. LichtFeld: camera_list (-> lfs_cameras.json: name, uid, position), the splat node's world matrix M (raw = M @ world),
     camera_get (the user's current view = reference view). The COLMAP folder is taken from camera_list image_path.
  2. Checks that LichtFeld's camera positions equal the COLMAP camera centres (if not, the dataset was transformed
     on load and M alone does not explain it -> stop and investigate).
  3. Up direction: mean "up" (-y) of all training cameras as a prior, refined by a RANSAC plane through sparse points
     BELOW the cameras (floor / ground / table). SfM frames are usually tilted (20 deg was seen), so never assume raw z is up.
  4. Model frame: origin on that plane under the reference camera (nearest training camera to the viewport eye),
     +Y = horizontal viewport direction, Z up, metres.
  5. Scale: --scale if known, otherwise camera height above the plane = --cam-height-m (default 1.6 m, handheld /
     head height). This is a guess: confirm it with known dimensions (pick3d.py measures distances) and
     update with `python setup_project.py <dir> --rescale <m_per_unit> "<reason>"`.
"""
import sys, os, json, argparse, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import colmap_io

ap = argparse.ArgumentParser()
ap.add_argument("project_dir"); ap.add_argument("--sfm"); ap.add_argument("--up", default="auto"); ap.add_argument("--ref", default="viewport")
ap.add_argument("--scale", type=float); ap.add_argument("--cam-height-m", type=float, default=1.6); ap.add_argument("--shared", default="")
ap.add_argument("--no-lfs", action="store_true"); ap.add_argument("--rescale", nargs=2, metavar=("M_PER_UNIT", "REASON"))
a = ap.parse_args()
os.makedirs(a.project_dir, exist_ok=True); PJ = os.path.join(a.project_dir, "project.json")

if a.rescale:
    from project import Project
    P = Project(PJ); P.set_scale(float(a.rescale[0]), a.rescale[1]); print("scale ->", P.S, "m/unit"); sys.exit()

def unit(v): v = np.asarray(v, float); return v / np.linalg.norm(v)

# ---- 1. LichtFeld ---------------------------------------------------------------------------------------------
M = np.eye(4); view = None; lfs_cams = []; splat = None
if not a.no_lfs:
    from lfs_mcp import Lfs
    lfs = Lfs()
    lfs_cams = lfs.json("camera_list")["cameras"]
    json.dump([dict(name=c["name"], uid=c["uid"], position=c["position"], image_path=c.get("image_path")) for c in lfs_cams],
              open(os.path.join(a.project_dir, "lfs_cameras.json"), "w", encoding="utf-8"))
    nodes = lfs.json("scene_list_nodes")["nodes"]
    splats = [n for n in nodes if n.get("type") == "splat"]
    if splats:
        splat = max(splats, key=lambda n: n.get("gaussian_count", 0))["name"]
        tr = lfs.json("transform_get", node=splat)
        t = tr["nodes"][0] if "nodes" in tr else tr
        M = np.array(t["world"]["matrix"], float)
        if not np.allclose(M[3, :3], 0):          # translation in the last row = column-major -> make row-major
            M = M.T
    view = lfs.json("camera_get")
    print("LichtFeld: %d cameras, splat node %s, view eye %s" % (len(lfs_cams), splat, view["camera"]["eye"]))

sfm = a.sfm or (os.path.dirname(os.path.dirname(lfs_cams[0]["image_path"])) if lfs_cams else None)
if not sfm: sys.exit("give --sfm (no LichtFeld camera list)")
sparse = colmap_io.find_sparse(sfm)
cams, imgs, _ = colmap_io.read_model(sparse, with_points=False)
images_dir = os.path.dirname(lfs_cams[0]["image_path"]) if lfs_cams and lfs_cams[0].get("image_path") else os.path.join(sfm, "images")
names = sorted(imgs); C = np.array([colmap_io.cam_center(imgs[n]) for n in names])
D = np.array([colmap_io.cam_axes(imgs[n])[1] for n in names])          # camera "down"
print("COLMAP: %s  %d images, %d camera models" % (sparse, len(imgs), len(cams)))

# ---- 2. consistency LFS <-> COLMAP --------------------------------------------------------------------------
if lfs_cams:
    pos = {c["name"]: np.array(c["position"]) for c in lfs_cams}
    err = [np.linalg.norm(pos[n] - colmap_io.cam_center(imgs[n])) for n in names[:: max(1, len(names) // 200)] if n in pos]
    ext = np.linalg.norm(C.max(0) - C.min(0))
    print("LFS camera_list position vs COLMAP centre: max err %.4g (scene extent %.4g)" % (max(err), ext))
    if max(err) > 1e-3 * ext: print("  WARNING: LichtFeld cameras are not the COLMAP centres -> dataset transformed on load; check before use")

# ---- 3. up direction ------------------------------------------------------------------------------------------
prior = unit(-D.mean(0)); strength = np.linalg.norm(D.mean(0))
print("camera-up prior", prior.round(4), "consistency %.2f (1 = all cameras level)" % strength)
pts = colmap_io.read_points(sparse)["xyz"]
rng = np.random.default_rng(0)
P = pts[rng.choice(len(pts), min(len(pts), 200000), replace=False)]
up, plane_d, cam_h = prior, None, None
if a.up not in ("auto", "cameras", "ground"):
    up = unit([float(v) for v in a.up.split(",")])
elif a.up != "cameras":
    Cs = C[:: max(1, len(C) // 400)]
    # horizontal nearest camera (w.r.t. prior) for each point, in chunks
    e1 = unit(np.cross(prior, [1, 0, 0] if abs(prior[0]) < 0.9 else [0, 1, 0])); e2 = np.cross(prior, e1)
    Ph, Ch = np.c_[P @ e1, P @ e2], np.c_[Cs @ e1, Cs @ e2]
    near = np.empty(len(P), int); dist = np.empty(len(P))
    for i in range(0, len(P), 20000):
        dd = ((Ph[i:i + 20000, None, :] - Ch[None, :, :]) ** 2).sum(-1); near[i:i + 20000] = dd.argmin(1); dist[i:i + 20000] = np.sqrt(dd.min(1))
    dh = (Cs[near] - P) @ prior                                           # >0: point below its nearest camera
    step = np.median(np.linalg.norm(np.diff(C[:: max(1, len(C) // 400)], axis=0), axis=1)) + 1e-9
    ext = np.linalg.norm(C.max(0) - C.min(0)); rad = max(0.05 * ext, 5 * step)
    cand = P[(dh > 0) & (dist < rad)]
    best = (0, None)
    tau = 0.004 * ext
    if len(cand) > 300:
        for _ in range(600):
            s = cand[rng.choice(len(cand), 3, replace=False)]
            n = np.cross(s[1] - s[0], s[2] - s[0])
            if np.linalg.norm(n) < 1e-12: continue
            n = unit(n); n = n if n @ prior > 0 else -n
            if n @ prior < np.cos(np.radians(30)): continue
            k = int((np.abs((cand - s[0]) @ n) < tau).sum())
            if k > best[0]: best = (k, (n, s[0] @ n))
    if best[1] is not None and best[0] > 500:
        n, d0 = best[1]; inl = cand[np.abs(cand @ n - d0) < tau]
        for it in range(3):                    # refit, tightening the band to ~15 % of the camera height
            c0 = inl.mean(0); w, V = np.linalg.eigh(np.cov((inl - c0).T)); n = unit(V[:, 0]); n = n if n @ prior > 0 else -n
            d0 = float(c0 @ n); tau = 0.15 * float(np.median(C @ n - d0))
            inl = cand[np.abs(cand @ n - d0) < tau]
        up, plane_d = n, d0
        print("ground plane: %d inliers of %d below-camera points, tilt vs camera prior %.1f deg" % (len(inl), len(cand), np.degrees(np.arccos(min(1, n @ prior)))))
    elif a.up == "ground":
        sys.exit("no ground plane found; use --up cameras or --up x,y,z")
    else:
        print("no reliable ground plane -> using the camera prior")
if plane_d is None:                                                         # ground height from the lowest points below cameras
    hp = P @ up; plane_d = float(np.percentile(hp[hp < np.median(C @ up)], 5)) if (hp < np.median(C @ up)).any() else float(hp.min())
cam_h_all = C @ up - plane_d; cam_h = float(np.median(cam_h_all))
print("camera height above ground: median %.4g units (10-90%% %.4g .. %.4g)" % (cam_h, *np.percentile(cam_h_all, [10, 90])))

# ---- 4. reference view & model frame -------------------------------------------------------------------------
if a.ref == "viewport" and view:
    eye = M[:3, :3] @ np.array(view["camera"]["eye"]) + M[:3, 3]; fwd = M[:3, :3] @ np.array(view["camera"]["forward"])
    ref = names[int(np.argmin(np.linalg.norm(C - eye, axis=1)))]
else:
    ref = a.ref if a.ref in imgs else names[0]; eye = colmap_io.cam_center(imgs[ref]); fwd = colmap_io.cam_axes(imgs[ref])[2]
Cref = colmap_io.cam_center(imgs[ref])
y = fwd - (fwd @ up) * up
if np.linalg.norm(y) < 1e-3: y = np.cross(up, colmap_io.cam_axes(imgs[ref])[0])     # looking straight up/down
y = unit(y - (y @ up) * up); x = np.cross(y, up); R = np.stack([x, y, up])
origin = Cref - (Cref @ up - plane_d) * up

# ---- 5. scale -------------------------------------------------------------------------------------------------
if a.scale: S, src = a.scale, "given (--scale)"
else: S, src = a.cam_height_m / cam_h, "ASSUMED camera height %.2f m above ground (verify with known dimensions)" % a.cam_height_m

cfg = dict(sfm_dir=sfm, sparse_dir=sparse, images_dir=images_dir, shared_dir=a.shared,
           lfs=dict(url=os.environ.get("LFS_URL", "http://127.0.0.1:45677/mcp"), splat_node=splat, M=M.tolist()),
           frame=dict(R=R.tolist(), origin_raw=origin.tolist(), up_raw=up.tolist(), up_method=a.up, ref_camera=ref,
                      ground_d=plane_d, note="model = S * R @ (raw - origin_raw); Z up, metres"),
           scale=dict(m_per_unit=S, source=src), camera_height_units=cam_h,
           viewport_at_setup=view["camera"] if view else None)
json.dump(cfg, open(PJ, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
Cm = S * (C - origin) @ R.T
print("reference camera", ref, "| scale %.4g m/unit (%s)" % (S, src))
print("cameras in model frame (m): x %.1f..%.1f  y %.1f..%.1f  z %.2f..%.2f" % (Cm[:, 0].min(), Cm[:, 0].max(), Cm[:, 1].min(), Cm[:, 1].max(), *np.percentile(Cm[:, 2], [5, 95])))
print("wrote", PJ)
