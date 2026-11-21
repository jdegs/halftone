"""Render the cover crops to e-ink BMPs using presets.py, plus a contact sheet for review.

  python tools/make_wallpapers.py                      # 684x1216, 16 greys (default profile)
  python tools/make_wallpapers.py --profile x4         # 480x800, 4 greys, 2-bit BMP
  python tools/make_wallpapers.py --profile x4 inferno # only names containing 'inferno'

Profiles are defined in presets.py. Crops come from the profile's crops folder, made by
  python tools/crop.py <crops folder> W H
"""
import argparse, glob, os, sys
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from eink import convert, safe_save
from presets import PROFILES, settings

ap = argparse.ArgumentParser()
ap.add_argument("filter", nargs="?", default="")
ap.add_argument("--profile", default="eink16", choices=sorted(PROFILES))
args = ap.parse_args()
prof = PROFILES[args.profile]

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
crop_dir = os.path.join(root, prof["crops"])
out_dir = os.path.join(root, prof["out"])
os.makedirs(out_dir, exist_ok=True)
srcs = sorted(glob.glob(os.path.join(crop_dir, "*.png")))
if not srcs:
    sys.exit(f"no crops in {crop_dir}; run crop.py with {prof['size'][0]} {prof['size'][1]} first")

done = []
for src in srcs:
    name = os.path.splitext(os.path.basename(src))[0]
    if args.filter not in name:
        continue
    s = settings(name, args.profile)
    dither = s.pop("dither")
    im = convert(src, os.path.join(out_dir, name + ".bmp"), levels=prof["levels"], dither=dither,
                 bpp=prof["bpp"], **s)
    done.append(im)
    print("wrote", name + ".bmp", dither)

if not args.filter and done:
    # 8 per row, so the 12 + 4 sets sit as two rows of 8
    cols = min(8, len(done)); rows = -(-len(done) // cols)
    tw, th = prof["size"][0] // 2, prof["size"][1] // 2
    sheet = Image.new("L", (cols * (tw + 10) + 10, rows * (th + 10) + 10), 128)
    for i, im in enumerate(done):
        sheet.paste(im.resize((tw, th), Image.BOX), (10 + (i % cols) * (tw + 10), 10 + (i // cols) * (th + 10)))
    safe_save(sheet, os.path.join(out_dir, "_contact_sheet.png"), "PNG")
