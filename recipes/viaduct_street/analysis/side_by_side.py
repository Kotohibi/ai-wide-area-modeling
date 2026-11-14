"""Put two images side by side at the same height with labels (e.g. LFS capture vs Blender render).

usage: python side_by_side.py <left.png> <right.png> <out.png> [height=900] [label_left] [label_right]
"""
import sys
from PIL import Image, ImageDraw
a = Image.open(sys.argv[1]).convert("RGB"); b = Image.open(sys.argv[2]).convert("RGB")
h = int(sys.argv[4]) if len(sys.argv) > 4 else 900
la = sys.argv[5] if len(sys.argv) > 5 else "LFS 3DGS"; lb = sys.argv[6] if len(sys.argv) > 6 else "Blender model"
a = a.resize((int(a.width * h / a.height), h)); b = b.resize((int(b.width * h / b.height), h))
s = Image.new("RGB", (a.width + b.width, h)); s.paste(a, (0, 0)); s.paste(b, (a.width, 0))
d = ImageDraw.Draw(s); d.text((8, 8), la, fill=(255, 255, 0)); d.text((a.width + 8, 8), lb, fill=(255, 255, 0))
s.save(sys.argv[3]); print(s.size)
