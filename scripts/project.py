r"""Project file (project.json) and coordinate frames shared by every tool in this skill.

Frames
  world : LichtFeld viewport coordinates (camera_get eye/forward/up, camera_set_view)
  raw   : dataset / COLMAP coordinates (images.txt, points3D, camera_list position, scene_export_ply)
          raw = M @ world_h          (M = world matrix of the splat node, transform_get)
  model : the frame everything is built in: metres, Z up, origin on the ground under the reference camera,
          +Y = horizontal viewing direction of the reference view, +X = right.  Blender uses this frame 1:1.
          model = S * R @ (raw - origin)

    from project import Project
    P = Project(r"C:\work\scene\project.json")
    Xm = P.to_model(points_raw)              # (N,3) metres
    c = P.camera("frame_0012.png")           # pose + intrinsics in the model frame, ready for Blender
    P.photo_path("frame_0012.png")
"""
import os, json, numpy as np

class Project:
    def __init__(self, path):
        self.path = os.path.abspath(path); self.dir = os.path.dirname(self.path)
        self.cfg = json.load(open(self.path, encoding="utf-8"))
        f = self.cfg["frame"]
        self.R = np.array(f["R"], float); self.o = np.array(f["origin_raw"], float)
        self.S = float(self.cfg["scale"]["m_per_unit"])
        self.M = np.array(self.cfg.get("lfs", {}).get("M", np.eye(4).tolist()), float)
        self._colmap = None; self._uid = None

    # ---- frames -------------------------------------------------------------------------------------------
    def to_model(self, X):  return self.S * (np.asarray(X, float) - self.o) @ self.R.T
    def to_raw(self, Xm):   return np.asarray(Xm, float) / self.S @ self.R + self.o
    def dir_to_model(self, d): return np.asarray(d, float) @ self.R.T
    def world_to_raw(self, Xw):
        Xw = np.asarray(Xw, float); return Xw @ self.M[:3, :3].T + self.M[:3, 3]
    def raw_to_world(self, X):
        A = self.M[:3, :3]; return (np.asarray(X, float) - self.M[:3, 3]) @ np.linalg.inv(A).T
    def world_dir_to_raw(self, d): return np.asarray(d, float) @ self.M[:3, :3].T
    def raw_dir_to_world(self, d): return np.asarray(d, float) @ np.linalg.inv(self.M[:3, :3]).T
    def save(self):
        json.dump(self.cfg, open(self.path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    def set_scale(self, S, source):
        self.cfg["scale"] = dict(m_per_unit=float(S), source=source); self.S = float(S); self.save()

    # ---- data ---------------------------------------------------------------------------------------------
    @property
    def colmap(self):
        if self._colmap is None:
            import colmap_io
            self._colmap = colmap_io.read_model(self.cfg["sparse_dir"], with_points=False)[:2]
        return self._colmap
    @property
    def cams(self): return self.colmap[0]
    @property
    def imgs(self): return self.colmap[1]
    def points_raw(self):
        import colmap_io
        return colmap_io.read_points(self.cfg["sparse_dir"])
    def photo_path(self, name): return os.path.join(self.cfg["images_dir"], name)
    def uid(self, name):
        """LichtFeld camera UID for an image name (for render_capture camera_index)."""
        if self._uid is None:
            p = os.path.join(self.dir, "lfs_cameras.json")
            self._uid = {c["name"]: c["uid"] for c in json.load(open(p, encoding="utf-8"))} if os.path.exists(p) else {}
        return self._uid.get(name)
    def names(self): return sorted(self.imgs)

    def camera(self, name):
        """Pose and intrinsics of a training photo in the model frame. rot = Blender camera rotation (columns
        = camera x right, y up, z back), loc in metres."""
        import colmap_io
        im = self.imgs[name]; cam = self.cams[im["camera_id"]]
        r, d, f = colmap_io.cam_axes(im)
        rot = np.stack([self.dir_to_model(r), -self.dir_to_model(d), -self.dir_to_model(f)], axis=1)
        fx, fy, cx, cy = colmap_io.intrinsics(cam)
        return dict(name=name, uid=self.uid(name), loc=self.to_model(colmap_io.cam_center(im)).tolist(), rot=rot.tolist(),
                    fx=fx, fy=fy, cx=cx, cy=cy, w=cam["width"], h=cam["height"], photo=self.photo_path(name))

    def all_centers(self):
        """(names, (N,3) model-frame camera centres, (N,3) model-frame forward vectors)."""
        import colmap_io
        ns = self.names(); C, F = [], []
        for n in ns:
            im = self.imgs[n]; C.append(colmap_io.cam_center(im)); F.append(colmap_io.cam_axes(im)[2])
        return ns, self.to_model(np.array(C)), self.dir_to_model(np.array(F))

    def project_model(self, name, Xm):
        """Model-frame points -> pixel coords + depth in photo `name`."""
        import colmap_io
        im = self.imgs[name]; return colmap_io.project(self.cams[im["camera_id"]], im, self.to_raw(Xm))

    def pixel_ray_model(self, name, u, v):
        import colmap_io
        im = self.imgs[name]; C, d = colmap_io.pixel_ray(self.cams[im["camera_id"]], im, u, v)
        return self.to_model(C), self.dir_to_model(d)

    def viewport_camera(self, cam_get):
        """LichtFeld camera_get result -> Blender-ready camera in the model frame (vertical FOV)."""
        c = cam_get.get("camera", cam_get)
        eye = self.to_model(self.world_to_raw(c["eye"]))
        fwd = self.dir_to_model(self.world_dir_to_raw(c["forward"])); up = self.dir_to_model(self.world_dir_to_raw(c["up"]))
        fwd /= np.linalg.norm(fwd); up -= fwd * (up @ fwd); up /= np.linalg.norm(up); right = np.cross(fwd, up)
        return dict(name="LFS_view", loc=eye.tolist(), rot=np.stack([right, up, -fwd], axis=1).tolist(),
                    fov_v_deg=c.get("fov_degrees"), w=c.get("width"), h=c.get("height"))
