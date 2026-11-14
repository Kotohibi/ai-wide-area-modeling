r"""Point clouds in the model frame (metres, Z up) for analysis and for Blender (diff checks, reference display).

usage: python export_points.py <project.json> sfm  [--box x0,y0,z0,x1,y1,z1] [--max N] [--name sfm]
       python export_points.py <project.json> 3dgs [--ply model_sh0.ply | --export] [--min-opacity 0.5] [--max-scale 0.3]
                               [--box ...] [--max N] [--name gs]
Writes <project_dir>\points_<name>.npz (xyz float32 metres, rgb uint8) and, if the Blender shared folder is set,
points_<name>.npy (N x 6 float32: xyz, rgb/255) there for bl_point_diff.py / bl_points.py.

sfm  : COLMAP points3D - triangulated, no floaters, but sparse and empty on smooth / textureless surfaces.
3dgs : Gaussian centres from LichtFeld (scene_export_ply with --export, or an existing PLY). Dense, but full of
       floaters: filter by opacity and size (--min-opacity, --max-scale in metres), and still distrust anything
       not seen from the ground-level cameras (above, behind objects).
"""
import sys, os, json, argparse, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from project import Project
import colmap_io

ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("src", choices=["sfm", "3dgs"])
ap.add_argument("--box"); ap.add_argument("--max", type=int, default=2000000); ap.add_argument("--name")
ap.add_argument("--ply"); ap.add_argument("--export", action="store_true")
ap.add_argument("--min-opacity", type=float, default=0.5); ap.add_argument("--max-scale", type=float, default=0.3)
a = ap.parse_args(); P = Project(a.project); name = a.name or ("sfm" if a.src == "sfm" else "gs")

if a.src == "sfm":
    d = P.points_raw(); X, C = P.to_model(d["xyz"]), d["rgb"]
else:
    ply = a.ply or os.path.join(P.dir, "model_sh0.ply")
    if a.export or not os.path.exists(ply):
        from lfs_mcp import Lfs
        node = P.cfg["lfs"].get("splat_node") or "Model"
        print(Lfs().text(Lfs().call("scene_export_ply", nodes=[node], path=ply, sh_degree=0, include_provenance=False))[:300])
    g = colmap_io.read_ply(ply)
    X, C = P.to_model(g["xyz"]), g["rgb"]
    keep = np.ones(len(X), bool)
    if "opacity" in g: keep &= 1 / (1 + np.exp(-g["opacity"])) >= a.min_opacity
    if "scale_0" in g:
        smax = np.exp(np.max(np.c_[g["scale_0"], g["scale_1"], g["scale_2"]], axis=1)) * P.S
        keep &= smax <= a.max_scale
    print("3DGS: %d gaussians, %d after opacity >= %.2f and size <= %.2f m" % (len(X), keep.sum(), a.min_opacity, a.max_scale))
    X, C = X[keep], C[keep]
if a.box:
    b = [float(v) for v in a.box.split(",")]; m = np.all((X >= b[:3]) & (X <= b[3:]), axis=1); X, C = X[m], C[m]
if len(X) > a.max:
    i = np.random.default_rng(0).choice(len(X), a.max, replace=False); X, C = X[i], C[i]
np.savez_compressed(os.path.join(P.dir, "points_%s.npz" % name), xyz=X.astype(np.float32), rgb=C)
sh = P.cfg.get("shared_dir")
if sh and os.path.isdir(sh):
    np.save(os.path.join(sh, "points_%s.npy" % name), np.c_[X, C / 255.0].astype(np.float32))
print("%d points -> points_%s  bbox (m) %s .. %s" % (len(X), name, X.min(0).round(1).tolist(), X.max(0).round(1).tolist()))
