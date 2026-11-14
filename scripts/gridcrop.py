"""Crop an image region and overlay a labelled pixel grid (full-resolution pixel coordinates) for reading features.
usage: python gridcrop.py <image> x0,y0,x1,y1 <out> [--step 50] [--scale 1.0]"""
import sys, argparse
from PIL import Image, ImageDraw
ap = argparse.ArgumentParser(); ap.add_argument("img"); ap.add_argument("box"); ap.add_argument("out")
ap.add_argument("--step", type=int, default=50); ap.add_argument("--scale", type=float, default=1.0)
a = ap.parse_args(); x0, y0, x1, y1 = [int(v) for v in a.box.split(",")]
im = Image.open(a.img).convert("RGB").crop((x0, y0, x1, y1))
if a.scale != 1: im = im.resize((int(im.width * a.scale), int(im.height * a.scale)))
d = ImageDraw.Draw(im); s = a.scale
for x in range((x0 // a.step + 1) * a.step, x1, a.step):
    X = (x - x0) * s; big = x % (a.step * 2) == 0
    d.line([(X, 0), (X, im.height)], fill=(255, 255, 0) if big else (0, 255, 255), width=1)
    if big: d.text((X + 2, 2), str(x), fill=(255, 255, 0))
for y in range((y0 // a.step + 1) * a.step, y1, a.step):
    Y = (y - y0) * s; big = y % (a.step * 2) == 0
    d.line([(0, Y), (im.width, Y)], fill=(255, 255, 0) if big else (0, 255, 255), width=1)
    if big: d.text((2, Y + 2), str(y), fill=(255, 255, 0))
im.save(a.out); print(a.out, im.size)
