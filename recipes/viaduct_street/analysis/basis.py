"""Build the 'site frame' basis from ground.npy (written by ground.py).

site frame: x = right, y = forward, h = up, origin = reference camera, h measured from the road plane.
usage: python basis.py <scratch_dir>
Writes <scratch_dir>/basis.npy = [right(3), fwd(3), up(3)] in the raw (COLMAP/dataset) frame.
`fwd0` is the raw-frame direction the reference camera looks along; change it if your reference camera looks elsewhere.
"""
import sys, numpy as np
SP = sys.argv[1]
fwd0 = np.array([0, 0, 1.0])
g = np.load(SP + r"\ground.npy"); n = g[0:3]            # n points DOWN in the raw frame (COLMAP y is down)
up = -n / np.linalg.norm(n)
fwd = fwd0 - (fwd0 @ up) * up; fwd /= np.linalg.norm(fwd)
right = np.cross(fwd, up); right /= np.linalg.norm(right)
np.save(SP + r"\basis.npy", np.concatenate([right, fwd, up]))
print("right", right, "fwd", fwd, "up", up)
