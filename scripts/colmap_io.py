r"""Read COLMAP sparse models (text or binary) and project points into the photos. numpy only.

    from colmap_io import read_model, cam_center, project
    cams, imgs, pts = read_model(r"F:\data\scene")          # finds cameras/images/points3D in <dir>, <dir>\sparse\0, ...
    im = imgs["frame_0001.png"]                              # dict keyed by image name
    C = cam_center(im)                                       # camera centre (COLMAP world)
    uv, z = project(cams[im["camera_id"]], im, pts["xyz"])   # pixel coords + depth (z > 0 = in front)

Conventions: COLMAP camera axes are x right, y DOWN, z forward. R = qvec2rotmat(q) maps world -> camera,
C = -R^T t, and the camera axes in world coordinates are the columns of R^T.
Distortion parameters are read but ignored by project() (fine for PINHOLE / undistorted 3DGS datasets).
"""
import os, struct, numpy as np

CAMERA_MODELS = {0: ("SIMPLE_PINHOLE", 3), 1: ("PINHOLE", 4), 2: ("SIMPLE_RADIAL", 4), 3: ("RADIAL", 5), 4: ("OPENCV", 8),
                 5: ("OPENCV_FISHEYE", 8), 6: ("FULL_OPENCV", 12), 7: ("FOV", 5), 8: ("SIMPLE_RADIAL_FISHEYE", 4),
                 9: ("RADIAL_FISHEYE", 5), 10: ("THIN_PRISM_FISHEYE", 12)}

def qvec2rotmat(q):
    w, x, y, z = np.asarray(q, float) / np.linalg.norm(q)
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])

def intrinsics(cam):
    """(fx, fy, cx, cy) for any COLMAP model."""
    m, p = cam["model"], cam["params"]
    if m in ("SIMPLE_PINHOLE", "SIMPLE_RADIAL", "RADIAL", "SIMPLE_RADIAL_FISHEYE", "RADIAL_FISHEYE", "FOV"):
        return p[0], p[0], p[1], p[2]
    return p[0], p[1], p[2], p[3]

def find_sparse(root):
    for d in (root, os.path.join(root, "sparse", "0"), os.path.join(root, "sparse"), os.path.join(root, "colmap", "sparse", "0")):
        if any(os.path.exists(os.path.join(d, "images" + e)) for e in (".txt", ".bin")): return d
    raise FileNotFoundError("no COLMAP images.txt/.bin under " + root)

def _read_cameras_txt(p):
    out = {}
    for l in open(p, encoding="utf-8"):
        if l.startswith("#") or not l.strip(): continue
        t = l.split()
        out[int(t[0])] = dict(model=t[1], width=int(t[2]), height=int(t[3]), params=[float(v) for v in t[4:]])
    return out

def _read_cameras_bin(p):
    out = {}
    with open(p, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        for _ in range(n):
            cid, mid, w, h = struct.unpack("<iiQQ", f.read(24))
            name, k = CAMERA_MODELS[mid]
            out[cid] = dict(model=name, width=w, height=h, params=list(struct.unpack("<%dd" % k, f.read(8 * k))))
    return out

def _read_images_txt(p, with_points2d=False):
    out = {}
    lines = [l for l in open(p, encoding="utf-8") if not l.startswith("#")]
    for i in range(0, len(lines) - 1, 2):
        t = lines[i].split()
        if len(t) < 10: continue
        im = dict(id=int(t[0]), q=[float(v) for v in t[1:5]], t=[float(v) for v in t[5:8]], camera_id=int(t[8]), name=" ".join(t[9:]))
        if with_points2d:
            v = lines[i + 1].split(); im["xys"] = np.array(v, float).reshape(-1, 3) if v else np.zeros((0, 3))
        out[im["name"]] = im
    return out

def _read_images_bin(p, with_points2d=False):
    out = {}
    with open(p, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        for _ in range(n):
            iid, *rest = struct.unpack("<idddddddi", f.read(64))
            name = b""
            while True:
                c = f.read(1)
                if c == b"\0": break
                name += c
            n2 = struct.unpack("<Q", f.read(8))[0]; raw = f.read(24 * n2)
            im = dict(id=iid, q=list(rest[0:4]), t=list(rest[4:7]), camera_id=rest[7], name=name.decode())
            if with_points2d:
                a = np.frombuffer(raw, dtype=[("x", "<f8"), ("y", "<f8"), ("id", "<i8")])
                im["xys"] = np.c_[a["x"], a["y"], a["id"]]
            out[im["name"]] = im
    return out

def read_points(d):
    """{'xyz': (N,3) float, 'rgb': (N,3) uint8} from points3D.bin / .txt / .ply in d."""
    pb, pt, pp = (os.path.join(d, "points3D" + e) for e in (".bin", ".txt", ".ply"))
    if os.path.exists(pb):
        xyz, rgb = [], []
        with open(pb, "rb") as f:
            n = struct.unpack("<Q", f.read(8))[0]
            for _ in range(n):
                v = struct.unpack("<QdddBBBd", f.read(43)); xyz.append(v[1:4]); rgb.append(v[4:7])
                k = struct.unpack("<Q", f.read(8))[0]; f.read(8 * k)
        return dict(xyz=np.array(xyz), rgb=np.array(rgb, np.uint8))
    if os.path.exists(pt):
        a = np.loadtxt(pt, comments="#", usecols=range(7))
        return dict(xyz=a[:, 1:4], rgb=a[:, 4:7].astype(np.uint8))
    if os.path.exists(pp): return read_ply(pp)
    raise FileNotFoundError("no points3D in " + d)

def read_ply(p, fields=None):
    """Binary little-endian / ASCII PLY vertices -> dict with 'xyz', 'rgb' (if present) and every raw field."""
    with open(p, "rb") as f:
        hdr = []
        while True:
            l = f.readline().decode("ascii", "ignore").strip(); hdr.append(l)
            if l == "end_header": break
        fmt = [h.split()[1] for h in hdr if h.startswith("format")][0]
        n = int([h.split()[2] for h in hdr if h.startswith("element vertex")][0])
        props, inv = [], False
        for h in hdr:
            if h.startswith("element"): inv = h.split()[1] == "vertex"
            elif h.startswith("property") and inv: props.append((h.split()[-1], h.split()[1]))
        tm = {"float": "<f4", "float32": "<f4", "double": "<f8", "uchar": "u1", "uint8": "u1", "int": "<i4", "int32": "<i4",
              "uint": "<u4", "short": "<i2", "ushort": "<u2", "char": "i1"}
        if fmt == "ascii":
            a = np.loadtxt(f, max_rows=n); arr = {nm: a[:, i] for i, (nm, _) in enumerate(props)}
        else:
            dt = np.dtype([(nm, tm[t]) for nm, t in props]); a = np.frombuffer(f.read(n * dt.itemsize), dtype=dt, count=n)
            arr = {nm: a[nm] for nm, _ in props}
    out = {k: v for k, v in arr.items() if fields is None or k in fields}
    out["xyz"] = np.c_[arr["x"], arr["y"], arr["z"]].astype(float)
    if "red" in arr: out["rgb"] = np.c_[arr["red"], arr["green"], arr["blue"]].astype(np.uint8)
    elif "f_dc_0" in arr:                                          # 3DGS: SH degree-0 colour
        out["rgb"] = np.clip((0.5 + 0.2820948 * np.c_[arr["f_dc_0"], arr["f_dc_1"], arr["f_dc_2"]]) * 255, 0, 255).astype(np.uint8)
    return out

def read_model(root, with_points=True, with_points2d=False):
    d = find_sparse(root)
    cp = os.path.join(d, "cameras.bin"); ip = os.path.join(d, "images.bin")
    cams = _read_cameras_bin(cp) if os.path.exists(cp) else _read_cameras_txt(os.path.join(d, "cameras.txt"))
    imgs = _read_images_bin(ip, with_points2d) if os.path.exists(ip) else _read_images_txt(os.path.join(d, "images.txt"), with_points2d)
    pts = read_points(d) if with_points else None
    return cams, imgs, pts

def rotation(im): return qvec2rotmat(im["q"])
def cam_center(im): return -rotation(im).T @ np.asarray(im["t"], float)
def cam_axes(im):
    """(right, down, forward) unit vectors in COLMAP world coordinates."""
    Rt = rotation(im).T; return Rt[:, 0], Rt[:, 1], Rt[:, 2]

def project(cam, im, X):
    """World points (N,3) -> pixel (N,2) and depth (N,). Only z > 0 points are in front of the camera."""
    fx, fy, cx, cy = intrinsics(cam)
    Xc = (np.asarray(X, float) @ rotation(im).T) + np.asarray(im["t"], float)
    z = Xc[:, 2]; zs = np.where(np.abs(z) < 1e-9, 1e-9, z)
    return np.c_[fx * Xc[:, 0] / zs + cx, fy * Xc[:, 1] / zs + cy], z

def pixel_ray(cam, im, u, v):
    """Unit ray (COLMAP world) through pixel (u, v) and the camera centre."""
    fx, fy, cx, cy = intrinsics(cam)
    d = rotation(im).T @ np.array([(u - cx) / fx, (v - cy) / fy, 1.0])
    return cam_center(im), d / np.linalg.norm(d)
