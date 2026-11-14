r"""Photo-projection texture bake, stage 2 (outside Blender): read <group>_texels.npz from bl_photo_bake.py, sample the
training photos (bilinear, masked pixels skipped), blend the best two views, fill unseen texels with the material
colour, pad UV islands, and write <group>_BaseColor.png.

usage: python photo_bake_sample.py <cameras_model.npz> <bake_dir> <group> [<group> ...] [--pad 8] [--sharp 4]
  --sharp  exponent on the view scores when blending two photos (higher = trust the best view more)
"""
import sys, os, argparse, numpy as np
from PIL import Image

ap = argparse.ArgumentParser(); ap.add_argument("cameras"); ap.add_argument("bake_dir"); ap.add_argument("groups", nargs="+")
ap.add_argument("--pad", type=int, default=8); ap.add_argument("--sharp", type=float, default=4.0)
a = ap.parse_args()
cz = np.load(a.cameras); photos = cz["photos"]; masks = cz["masks"]

def bilinear(img, u, v):
    h, w = img.shape[:2]
    u = np.clip(u - 0.5, 0, w - 1.001); v = np.clip(v - 0.5, 0, h - 1.001)
    x0 = u.astype(np.int64); y0 = v.astype(np.int64); fx = (u - x0)[:, None]; fy = (v - y0)[:, None]
    p = img.astype(np.float32)
    if p.ndim == 2: p = p[:, :, None]
    c = (p[y0, x0] * (1 - fx) * (1 - fy) + p[y0, x0 + 1] * fx * (1 - fy) + p[y0 + 1, x0] * (1 - fx) * fy + p[y0 + 1, x0 + 1] * fx * fy)
    return c

for g in a.groups:
    d = np.load(os.path.join(a.bake_dir, g + "_texels.npz")); W, H = [int(x) for x in d["res"]]
    pix = d["pix"]; n = pix.size
    acc = np.zeros((n, 3), np.float32); wsum = np.zeros(n, np.float32)
    jobs = {}
    for slot in (1, 2):
        cam = d["cam%d" % slot]; uv = d["uv%d" % slot].astype(np.float32) / 16.0; w = d["w%d" % slot] ** a.sharp
        for ci in np.unique(cam[cam >= 0]):
            jobs.setdefault(int(ci), []).append((np.where(cam == ci)[0], uv, w))
    for k, (ci, lst) in enumerate(sorted(jobs.items())):
        img = np.asarray(Image.open(photos[ci]).convert("RGB"))
        msk = np.asarray(Image.open(masks[ci]).convert("L")) if masks[ci] else None
        for idx, uv, w in lst:
            u, v = uv[idx, 0], uv[idx, 1]
            col = bilinear(img, u, v)
            ok = np.ones(idx.size, bool)
            if msk is not None: ok = bilinear(msk, u, v)[:, 0] > 127                 # skip the masked rig/operator
            # sky behind an eave/edge (model and photo never align to the pixel): bright blue or near-white sky
            # pixels get 2% weight, so the other view or the material colour wins
            r_, g_, b_ = col[:, 0], col[:, 1], col[:, 2]
            sky = ((b_ > r_ + 20) & (b_ > 140)) | ((r_ > 215) & (g_ > 215) & (b_ > 215))
            ww = w[idx] * ok * np.where(sky, 0.02, 1.0)
            acc[idx] += col * ww[:, None]; wsum[idx] += ww
    tex = np.zeros((H * W, 3), np.float32); filled = np.zeros(H * W, bool)
    seen = wsum > 0
    tex[pix[seen]] = acc[seen] / wsum[seen][:, None]
    tex[pix[~seen]] = d["fallback"][~seen].astype(np.float32)
    filled[pix] = True
    tex = tex.reshape(H, W, 3); filled = filled.reshape(H, W)
    for _ in range(a.pad):                                                          # pad islands (mip/bilinear seams)
        nb = np.zeros_like(tex); cnt = np.zeros((H, W), np.float32)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            sf = np.roll(filled, (dy, dx), (0, 1)); st = np.roll(tex, (dy, dx), (0, 1))
            nb += st * sf[:, :, None]; cnt += sf
        grow = (~filled) & (cnt > 0)
        tex[grow] = nb[grow] / cnt[grow][:, None]; filled |= grow
    # rows in the npz are UV v from the bottom (Blender); image rows go from the top
    out = os.path.join(a.bake_dir, g + "_BaseColor.png")
    Image.fromarray(np.clip(tex[::-1], 0, 255).astype(np.uint8)).save(out)
    print(g, "%dx%d" % (W, H), "photos used", len(jobs), "seen %.1f%%" % (100 * seen.mean()), out)
