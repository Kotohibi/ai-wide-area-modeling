# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
"""Shared Blender helpers for the the temple model: materials, a multi-material mesh builder in a local (rotated)
frame, roof height fields (irimoya / hip / pent / lean-to) and small parametric parts (trees, shrubs, hedges).
Load inside Blender with exec(...) before build_site.py."""
import bpy, bmesh, math
from mathutils import Vector

MATS = {
    "wood":    (0.10, 0.060, 0.035, 0.8), "wood_lt": (0.20, 0.120, 0.070, 0.8),
    "plaster": (0.85, 0.84, 0.80, 0.9),   "tile":    (0.22, 0.32, 0.29, 0.5),
    "tile_dk": (0.15, 0.22, 0.20, 0.5),   "tile_gray": (0.20, 0.21, 0.22, 0.6),
    "copper":  (0.28, 0.40, 0.33, 0.4),   "stone":   (0.62, 0.60, 0.56, 0.9),
    "granite": (0.55, 0.55, 0.53, 0.8),   "asphalt": (0.20, 0.20, 0.20, 0.95),
    "water":   (0.03, 0.05, 0.06, 0.1),   "wall":    (0.72, 0.62, 0.47, 0.9),
    "hedge":   (0.10, 0.22, 0.07, 0.9),   "gold":    (0.75, 0.55, 0.20, 0.3),
    "back":    (0.80, 0.10, 0.10, 0.8),   "door_green": (0.08, 0.28, 0.24, 0.6),
    "glass":   (0.05, 0.06, 0.07, 0.2),   "brick":   (0.42, 0.38, 0.34, 0.9),
    "paving":  (0.60, 0.58, 0.54, 0.9),   "lawn_dry": (0.62, 0.50, 0.32, 1.0),
    "gravel":  (0.72, 0.71, 0.68, 1.0),   "line":    (0.92, 0.92, 0.90, 0.6),
    "house":   (0.80, 0.68, 0.48, 0.9),   "foliage": (0.12, 0.25, 0.08, 0.9),
    "foliage_dk": (0.07, 0.16, 0.06, 0.9), "conifer_br": (0.35, 0.27, 0.12, 0.9),
    "bare":    (0.36, 0.30, 0.25, 1.0),   "bark":    (0.22, 0.17, 0.13, 0.9),
    "bronze":  (0.20, 0.30, 0.25, 0.4),   "soil":    (0.30, 0.24, 0.18, 1.0),
    "frame_white": (0.82, 0.82, 0.80, 0.5), "shutter": (0.78, 0.78, 0.76, 0.6), "stone2": (0.56, 0.55, 0.52, 0.9),
    "riverstone": (0.50, 0.49, 0.45, 0.9), "sign": (0.08, 0.08, 0.09, 0.6), "fascia": (0.35, 0.25, 0.15, 0.7),
    "hedge_red": (0.30, 0.17, 0.11, 0.9), "stone_dk": (0.30, 0.29, 0.28, 0.7), "granite_dk": (0.14, 0.14, 0.15, 0.4),
    "concrete": (0.80, 0.79, 0.76, 0.9), "grating": (0.12, 0.12, 0.12, 0.6),
}
def mat(name):
    m = bpy.data.materials.get("T_" + name)
    if m is None:
        m = bpy.data.materials.new("T_" + name); m.use_nodes = True
    c = MATS[name]; bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*c[:3], 1); bsdf.inputs["Roughness"].default_value = c[3]
    m.diffuse_color = (*c[:3], 1)
    return m

def reset_collections(names, root_name="Temple"):
    root = bpy.data.collections.get(root_name)
    if root is None:
        root = bpy.data.collections.new(root_name); bpy.context.scene.collection.children.link(root)
    out = {}
    for n in names:
        c = bpy.data.collections.get(n)
        if c is not None:
            for o in list(c.objects): bpy.data.objects.remove(o, do_unlink=True)
        else:
            c = bpy.data.collections.new(n); root.children.link(c)
        out[n] = c
    return out

class Frame:
    """Local frame: u along the building's width, v along its depth (v<0 = front), rotated by rot_deg about Z."""
    def __init__(self, cx, cy, rot_deg=0.0):
        self.cx, self.cy = cx, cy; a = math.radians(rot_deg); self.c, self.s = math.cos(a), math.sin(a); self.rot = a
    def W(self, u, v, z=0.0):
        return (self.cx + u * self.c - v * self.s, self.cy + u * self.s + v * self.c, z)

class MB:
    """Multi-material mesh builder. Coordinates passed to box/aabb/cyl/beam are LOCAL (u, v, z) of its frame."""
    def __init__(self, F=None): self.F = F or Frame(0, 0); self.v = []; self.f = []; self.m = []; self.mats = []
    def mi(self, name):
        if name not in self.mats: self.mats.append(name)
        return self.mats.index(name)
    def add_world(self, verts, faces, m):
        o = len(self.v); k = self.mi(m); self.v += [tuple(p) for p in verts]
        for f in faces: self.f.append([o + i for i in f]); self.m.append(k)
    def add(self, verts_local, faces, m):
        self.add_world([self.F.W(*p) for p in verts_local], faces, m)
    def box(self, c, s, m, rz=0.0):
        hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2; cr, sr = math.cos(rz), math.sin(rz); vs = []
        for z in (-hz, hz):
            for x, y in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)):
                vs.append((c[0] + x * cr - y * sr, c[1] + x * sr + y * cr, c[2] + z))
        self.add(vs, [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)], m)
    def aabb(self, u0, v0, z0, u1, v1, z1, m):
        self.box(((u0 + u1) / 2, (v0 + v1) / 2, (z0 + z1) / 2), (abs(u1 - u0), abs(v1 - v0), abs(z1 - z0)), m)
    def beam(self, p0, p1, w, h, m):
        a, b = Vector(p0), Vector(p1); d = b - a; L = d.length
        if L < 1e-6: return
        t = d / L; side = t.cross(Vector((0, 0, 1)))
        if side.length < 1e-6: side = Vector((1, 0, 0))
        side.normalize(); up = side.cross(t).normalized(); vs = []
        for e in (a, b):
            for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                vs.append(tuple(e + side * (sx * w / 2) + up * (sz * h / 2)))
        # beam endpoints are WORLD coordinates (callers pass F.W(...)), so no second local->world transform
        self.add_world(vs, [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)], m)
    def cyl(self, u, v, z0, z1, r, m, n=16, r1=None):
        r1 = r if r1 is None else r1
        vs = [(u + rr * math.cos(2 * math.pi * i / n), v + rr * math.sin(2 * math.pi * i / n), z) for z, rr in ((z0, r), (z1, r1)) for i in range(n)]
        fs = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        self.add(vs, fs, m)
    def blob(self, u, v, z, rx, ry, rz, m, nu=12, nv=8, jitter=0.0, seed=0):
        """Ellipsoid (foliage, shrubs). jitter roughens the surface a little (deterministic)."""
        import random; rnd = random.Random(seed); vs = []
        for j in range(nv + 1):
            th = math.pi * j / nv
            for i in range(nu):
                ph = 2 * math.pi * i / nu; k = 1 + (rnd.uniform(-jitter, jitter) if 0 < j < nv else 0)
                vs.append((u + rx * k * math.sin(th) * math.cos(ph), v + ry * k * math.sin(th) * math.sin(ph), z + rz * k * math.cos(th)))
        fs = []
        for j in range(nv):                       # rows run top -> bottom, so (a, a+nu, b+nu, b) faces outward
            for i in range(nu):
                a, b = j * nu + i, j * nu + (i + 1) % nu; fs.append((a, a + nu, b + nu, b))
        self.add(vs, fs, m)
    def poly_slab(self, pts, z0, z1, m):
        """Vertical prism over a convex/concave polygon (local coords). Clockwise outlines are reversed first: the
        faces below assume counter-clockwise order, and a clockwise outline gives a top facing down (culled in UE,
        whose visible bottom then z-fights with the ground)."""
        pts = list(pts)
        if sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1])) < 0: pts.reverse()
        n = len(pts); vs = [(p[0], p[1], z0) for p in pts] + [(p[0], p[1], z1) for p in pts]
        fs = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        self.add(vs, fs, m)
    def build(self, name, coll, smooth=False):
        me = bpy.data.meshes.new(name); me.from_pydata(self.v, [], self.f); me.update()
        for n in self.mats: me.materials.append(mat(n))
        for p, k in zip(me.polygons, self.m): p.material_index = k; p.use_smooth = smooth
        ob = bpy.data.objects.new(name, me); coll.objects.link(ob); return ob

# ------------------------------------------------------------------ roofs (local frame, height fields)
def g(s, p): return max(0.0, min(1.0, s)) ** p

def irimoya_z(u, v, R):
    """Irimoya (gable_u > 0) or hip roof (gable_u = 0). Same concave profile on all slopes, corner upturn."""
    hu, hv, ze, zr, gu, p = R["hu"], R["hv"], R["z_eave"], R["z_ridge"], R.get("gable_u", 0.0), R["p"]
    D = zr - ze; run = R.get("run", hv); run_s = R.get("run_side", run)
    zf = ze + D * g((hv - abs(v)) / run, p)
    zs = ze + D * g((hu - abs(u)) / run_s, p)     # run_side < run: steeper hips, higher gable base
    z = zf if (gu > 0 and abs(u) <= gu) else min(zf, zs)
    front = (gu > 0 and abs(u) <= gu) or zf <= zs
    z += R.get("rise", 0.0) * (abs(u) / hu) ** 3 * (abs(v) / hv) ** 3
    return z, front

def gable_z(u, v, R):
    """Kirizuma (gable) roof, ridge along u."""
    hv, ze, zr, p = R["hv"], R["z_eave"], R["z_ridge"], R.get("p", 1.0)
    return ze + (zr - ze) * g((hv - abs(v)) / hv, p), True

def ribs(u, v, front, amp=0.035, pitch=0.30):
    if amp <= 0: return 0.0
    t = (u if front else v) / pitch
    return amp * abs(math.sin(math.pi * t)) ** 0.6

def samples(a, b, step, extra=()):
    n = max(1, int(round((b - a) / step)))
    return sorted(set([round(a + (b - a) * i / n, 4) for i in range(n + 1)] + [round(e, 4) for e in extra if a <= e <= b]))

def roof_field(name, coll, F, zfun, urange, vrange, R, keep=None, step=0.1, extra_u=(), amp=0.035, mats=("tile", "wood")):
    """Height-field roof over a local rectangle; zfun(u,v)->(z, front). keep(u,v)->bool trims faces. Solidified."""
    us = samples(*urange, step, extra_u); vs = samples(*vrange, step)
    bm = bmesh.new(); grid = {}
    for j, v in enumerate(vs):
        for i, u in enumerate(us):
            z, front = zfun(u, v)
            grid[i, j] = (bm.verts.new(F.W(u, v, z + ribs(u, v, front, amp))), keep(u, v) if keep else True)
    for j in range(len(vs) - 1):
        for i in range(len(us) - 1):
            q = [grid[i, j], grid[i + 1, j], grid[i + 1, j + 1], grid[i, j + 1]]
            if not all(k for _, k in q): continue
            bm.faces.new([a for a, _ in q])
    loose = [vv for vv in bm.verts if not vv.link_faces]; bmesh.ops.delete(bm, geom=loose, context="VERTS")
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for mm in mats: me.materials.append(mat(mm))
    for pg in me.polygons: pg.use_smooth = True
    ob = bpy.data.objects.new(name, me); coll.objects.link(ob)
    sd = ob.modifiers.new("thick", "SOLIDIFY"); sd.thickness = R.get("thick", 0.25); sd.offset = -1.0
    sd.material_offset = 1; sd.material_offset_rim = 1; sd.use_even_offset = True
    return ob

def irimoya_roof(name, coll, F, R, step=0.08, amp=0.035, mats=("tile", "wood")):
    gu = R.get("gable_u", 0.0); ex = (gu, -gu, gu + 0.01, -gu - 0.01) if gu > 0 else ()
    return roof_field(name, coll, F, lambda u, v: irimoya_z(u, v, R), (-R["hu"], R["hu"]), (-R["hv"], R["hv"]), R,
                      step=step, extra_u=ex, amp=amp, mats=mats)

def irimoya_trim(mb, R, ridge_mat="tile_dk", oni=True):
    """Gable walls, bargeboards, ridges for an irimoya roof built with irimoya_roof (same frame as mb)."""
    gu, hv, hu, zr = R["gable_u"], R["hv"], R["hu"], R["z_ridge"]
    zg = irimoya_z(gu + 0.011, 0, R)[0]
    def zf(v): return irimoya_z(0, v, R)[0]
    vg = 0.0
    while zf(vg) > zg and vg < hv: vg += 0.01
    for su in (-1, 1):
        u = su * gu; vs_ = [-vg + 2 * vg * i / 30 for i in range(31)]
        for a, b in zip(vs_[:-1], vs_[1:]):
            mb.add([(u, a, zg), (u, b, zg), (u, b, zf(b) - 0.05), (u, a, zf(a) - 0.05)], [(0, 1, 2, 3) if su > 0 else (3, 2, 1, 0)], "plaster")
            mb.beam(mb.F.W(u + su * 0.06, a, zf(a) + 0.02), mb.F.W(u + su * 0.06, b, zf(b) + 0.02), 0.08, 0.3, "wood")
            mb.beam(mb.F.W(u, a, zf(a) + 0.18), mb.F.W(u, b, zf(b) + 0.18), 0.28, 0.2, ridge_mat)
        for sv in (-1, 1):                       # hip ridge, segmented so it follows the concave roof surface
            a = (su * (gu + 0.02), sv * vg); b = (su * (hu - 0.15), sv * (hv - 0.15)); N = 10
            pts = [(a[0] + (b[0] - a[0]) * k / N, a[1] + (b[1] - a[1]) * k / N) for k in range(N + 1)]
            for p0, p1 in zip(pts[:-1], pts[1:]):
                mb.beam(mb.F.W(p0[0], p0[1], irimoya_z(*p0, R)[0] + 0.13), mb.F.W(p1[0], p1[1], irimoya_z(*p1, R)[0] + 0.13), 0.26, 0.22, ridge_mat)
    ru = R.get("ridge_u", gu + 0.3); rh = R.get("ridge_h", 0.35)
    mb.aabb(-ru, -0.2, zr - 0.05, ru, 0.2, zr + rh, ridge_mat)
    if oni:
        oh = R.get("oni_h", 0.5)
        for su in (-1, 1):
            mb.aabb(su * ru - 0.22, -0.28, zr, su * ru + 0.14, 0.28, zr + oh, ridge_mat)
    return zg, vg

def hip_trim(mb, R, ridge_mat="tile_gray"):
    hu, hv = R["hu"], R["hv"]; zr = R["z_ridge"]; run = R.get("run", hv)
    ru = max(0.0, hu - hv * run / hv) if hu > hv else 0.0
    ru = max(0.0, hu - run) if hu > run else 0.0
    mb.aabb(-ru - 0.1, -0.15, zr - 0.05, ru + 0.1, 0.15, zr + 0.22, ridge_mat)
    for su in (-1, 1):
        for sv in (-1, 1):
            a = (su * ru, 0.0); b = (su * (hu - 0.1), sv * (hv - 0.1))
            mb.beam(mb.F.W(a[0], a[1], zr + 0.08), mb.F.W(b[0], b[1], irimoya_z(*b, R)[0] + 0.1), 0.2, 0.16, ridge_mat)

def rafters(mb, R, zfun, inner_u, inner_v, pitch=0.24, sides=(True, True, True, True), mat_="wood_lt"):
    hu, hv, t = R["hu"], R["hv"], R.get("thick", 0.25)
    def under(u, v): return zfun(u, v) - t - 0.06
    W = mb.F.W
    if sides[0] or sides[1]:
        n = int(2 * (inner_u + 0.3) / pitch)
        for sgn, on in ((-1, sides[0]), (1, sides[1])):
            if not on: continue
            for i in range(n + 1):
                u = -(inner_u + 0.3) + i * pitch
                mb.beam(W(u, sgn * (hv - 0.02), under(u, sgn * (hv - 0.02))), W(u, sgn * inner_v, under(u, sgn * inner_v)), 0.08, 0.1, mat_)
    m = int(2 * (inner_v + 0.3) / pitch)
    for sgn, on in ((-1, sides[2]), (1, sides[3])):
        if not on: continue
        for i in range(m + 1):
            v = -(inner_v + 0.3) + i * pitch
            mb.beam(W(sgn * (hu - 0.02), v, under(sgn * (hu - 0.02), v)), W(sgn * inner_u, v, under(sgn * inner_u, v)), 0.08, 0.1, mat_)

# ------------------------------------------------------------------ openings (in a wall plane v = const, facing -v if face<0)
def wall_quad(mb, u0, u1, z0, z1, v, m, face=-1):
    q = [(u0, v, z0), (u1, v, z0), (u1, v, z1), (u0, v, z1)]
    mb.add(q, [(0, 1, 2, 3) if face < 0 else (3, 2, 1, 0)], m)

def kato_window(mb, uc, v, z0, z1, w, face=-1, frame="wood", glass="glass", bars=True):
    """Cusped (katō) window: rectangle with an ogee/cusped arch top, dark grille bars, wooden frame. In plane v."""
    hw = w / 2; za = z1 - w * 0.45                  # arch springs at za
    pts = [(uc - hw, z0), (uc + hw, z0), (uc + hw, za)]
    N = 14
    for k in range(1, N):
        t = k / N; a = math.pi * t
        r = hw * (1 + 0.12 * math.sin(3 * a) ** 2)   # small cusps
        x = uc + math.cos(a) * r * (1 - 0.15 * math.sin(a)); z = za + math.sin(a) * (z1 - za) * (1 + 0.15 * (1 - abs(math.cos(a))) ** 3)
        pts.append((x, min(z, z1)))
    pts.append((uc - hw, za))
    off = face * 0.02
    c = (uc, v + off, (z0 + za) / 2)
    vs = [c] + [(x, v + off, z) for x, z in pts]; n = len(pts)
    fs = [(0, 1 + i, 1 + (i + 1) % n) if face < 0 else (0, 1 + (i + 1) % n, 1 + i) for i in range(n)]
    mb.add(vs, fs, glass)
    for (x0, z0_), (x1, z1_) in zip(pts, pts[1:] + pts[:1]):     # frame along the outline
        mb.beam(mb.F.W(x0, v + face * 0.05, z0_), mb.F.W(x1, v + face * 0.05, z1_), 0.07, 0.09, frame)
    if bars:
        nb = max(3, int(w / 0.14))
        for i in range(1, nb):
            x = uc - hw + w * i / nb
            mb.aabb(x - 0.015, v + face * 0.07, z0, x + 0.015, v + face * 0.03, za + (z1 - za) * 0.8 * (1 - (2 * (x - uc) / w) ** 2) ** 0.5, frame)

def lattice_door(mb, u0, u1, z0, z1, v, face=-1, leaves=2, frame="wood", panel="glass", pitch=0.15):
    """Sliding lattice doors: frame per leaf and a grid of thin bars over a dark panel."""
    wall_quad(mb, u0, u1, z0, z1, v + face * 0.03, panel, face)
    lw = (u1 - u0) / leaves
    for k in range(leaves + 1):
        x = u0 + k * lw; mb.aabb(x - 0.04, v + face * 0.09, z0, x + 0.04, v + face * 0.03, z1, frame)
    for zz in (z0, z1 - 0.06, z0 + 0.7):
        mb.aabb(u0, v + face * 0.09, zz, u1, v + face * 0.03, zz + 0.06, frame)
    nx = int((u1 - u0) / pitch); nz = int((z1 - z0 - 0.8) / pitch)
    for i in range(1, nx):
        x = u0 + (u1 - u0) * i / nx; mb.aabb(x - 0.012, v + face * 0.07, z0 + 0.76, x + 0.012, v + face * 0.05, z1, frame)
    for j in range(1, nz):
        z = z0 + 0.76 + (z1 - z0 - 0.76) * j / nz; mb.aabb(u0, v + face * 0.07, z - 0.012, u1, v + face * 0.05, z + 0.012, frame)

def panel_door(mb, u0, u1, z0, z1, v, face=-1, leaves=2, m="door_green", frame="wood"):
    wall_quad(mb, u0, u1, z0, z1, v + face * 0.04, m, face)
    lw = (u1 - u0) / leaves
    for k in range(leaves + 1):
        x = u0 + k * lw; mb.aabb(x - 0.035, v + face * 0.08, z0, x + 0.035, v + face * 0.03, z1, frame)
    for zz in (z0, (z0 + z1) / 2, z1 - 0.05):
        mb.aabb(u0, v + face * 0.08, zz, u1, v + face * 0.03, zz + 0.05, frame)

def sash_window(mb, u0, u1, z0, z1, v, face=-1, frame="frame_white", mull=0.9):
    """Modern sliding window: dark glass, light frame and mullions (houses)."""
    wall_quad(mb, u0, u1, z0, z1, v + face * 0.02, "glass", face)
    n = max(2, round((u1 - u0) / mull))
    for k in range(n + 1):
        x = u0 + (u1 - u0) * k / n; mb.aabb(x - 0.025, v + face * 0.05, z0, x + 0.025, v + face * 0.02, z1, frame)
    for zz in (z0, z1 - 0.05): mb.aabb(u0, v + face * 0.05, zz, u1, v + face * 0.02, zz + 0.05, frame)

# ------------------------------------------------------------------ vegetation
def tree(mb, x, y, kind, r, h, seed=0):
    """kind: 'bare' (winter deciduous), 'conifer', 'topiary' (cloud-pruned pine), 'round' (evergreen ball)."""
    import random; rnd = random.Random(seed)
    if kind == "topiary":
        mb.cyl(x, y, 0, h * 0.6, 0.12, "bark", 8, 0.08)
        tiers = 3 if h > 2.5 else 2
        for k in range(tiers):
            t = (k + 1) / tiers; zc = h * (0.35 + 0.55 * t); rr = r * (1.0 - 0.45 * t)
            dx, dy = rnd.uniform(-0.3, 0.3) * r, rnd.uniform(-0.3, 0.3) * r
            mb.blob(x + dx, y + dy, zc, rr, rr * 0.9, rr * 0.45, "foliage", 12, 6, 0.08, seed + k)
        return
    if kind == "round":
        mb.blob(x, y, h * 0.5, r, r, h * 0.5, "foliage_dk", 12, 7, 0.06, seed); return
    if kind == "conifer":
        mb.cyl(x, y, 0, h * 0.35, r * 0.12, "bark", 8)
        for k in range(4):
            t = k / 4; zc = h * (0.4 + 0.5 * t); rr = r * (1 - 0.6 * t)
            mb.blob(x, y, zc, rr, rr, h * 0.16, "conifer_br" if k % 2 else "foliage_dk", 10, 6, 0.1, seed + k)
        return
    # bare deciduous (winter): trunk and a branching crown of limbs and twigs, no foliage mass
    t0 = max(0.12, r * 0.06); zt = h * 0.4
    mb.cyl(x, y, 0, zt, t0, "bark", 8, t0 * 0.8)
    def branch(p, ang, elev, L, w, depth):
        q = (p[0] + math.cos(ang) * math.cos(elev) * L, p[1] + math.sin(ang) * math.cos(elev) * L, p[2] + math.sin(elev) * L)
        mb.beam(p, q, w, w, "bark" if depth < 2 else "bare")
        if depth >= 3: return
        for k in range(3 if depth < 2 else 2):
            branch(q, ang + rnd.uniform(-0.8, 0.8), min(1.3, max(0.2, elev + rnd.uniform(-0.3, 0.4))), L * 0.62, w * 0.6, depth + 1)
    n0 = 5
    for k in range(n0):
        branch((x, y, zt), 2 * math.pi * k / n0 + rnd.uniform(-0.3, 0.3), rnd.uniform(0.6, 1.0), r * 0.75, t0 * 0.7, 0)

def hedge(mb, p0, p1, h, t, m="hedge"):
    """Clipped hedge with a slightly rounded top, along a straight line (world coords, mb frame must be identity)."""
    mb.beam((p0[0], p0[1], h * 0.45), (p1[0], p1[1], h * 0.45), t, h * 0.9, m)
    mb.beam((p0[0], p0[1], h * 0.92), (p1[0], p1[1], h * 0.92), t * 0.8, h * 0.16, m)
