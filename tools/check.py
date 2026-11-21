"""Review and verify rendered wallpapers.

  python tools/check.py verify
      Check every output file as the device will read it: size, bit depth, and that
      only the profile's grey levels occur (16-grey: multiples of 17; 4-grey: 2-bit
      BMP with palette 0/85/170/255, which CrossPoint draws without re-dithering).

  python tools/check.py zoom OUT.png NAME:l,t,r,b [NAME:l,t,r,b ...] [--profile x4] [--scale 2]
      Paste regions of rendered wallpapers side by side at 1:1 (or --scale, nearest
      neighbour) so dithering and text edges can be judged. NAME is any unique part
      of a file name; coordinates are output pixels.
      e.g. python tools/check.py zoom z.png walden:0,0,480,140 eden:0,600,480,800 --profile x4

  python tools/check.py strips OUT.png [--profile x4]
      Top and bottom strips of every wallpaper at 1:1 - where nearly all titles sit -
      for spotting grainy or clipped type.
"""
import argparse, glob, os, struct, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from eink import read_bmp2
from presets import PROFILES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(path):
    with open(path, "rb") as f:
        bpp = struct.unpack_from("<H", f.read(30), 28)[0]
    return read_bmp2(path) if bpp == 2 else Image.open(path).convert("L")


def files(profile):
    return sorted(glob.glob(os.path.join(ROOT, PROFILES[profile]["out"], "*.bmp")))


def find(profile, part):
    hits = [f for f in files(profile) if part in os.path.basename(f)]
    if len(hits) != 1:
        sys.exit(f"'{part}' matches {len(hits)} files in {PROFILES[profile]['out']}")
    return hits[0]


def verify():
    ok = True
    for name, prof in PROFILES.items():
        fs = files(name)
        step = 255 // (prof["levels"] - 1)
        for f in fs:
            d = open(f, "rb").read()
            _, w, h, _, bpp, comp, _, _, _, used, _ = struct.unpack_from("<IiiHHIIiiII", d, 14)
            a = np.asarray(load(f))
            problems = []
            if (w, abs(h)) != prof["size"]:
                problems.append(f"size {w}x{h}")
            if bpp != prof["bpp"] or comp != 0:
                problems.append(f"bpp {bpp} comp {comp}")
            if prof["bpp"] == 2 and used != 4:
                problems.append(f"palette has {used} entries")
            if not np.all(a % step == 0):
                problems.append("values off the grey levels")
            if problems:
                ok = False
                print("FAIL", os.path.relpath(f, ROOT), ", ".join(problems))
        print(f"{name}: {len(fs)} files, {prof['size'][0]}x{prof['size'][1]}, "
              f"{prof['levels']} greys, {prof['bpp']}-bit")
    print("all OK" if ok else "problems found")
    return ok


def zoom(out, specs, profile, scale):
    tiles = []
    for spec in specs:
        part, box = spec.split(":")
        box = tuple(int(v) for v in box.split(","))
        im = load(find(profile, part)).crop(box)
        tiles.append(im.resize((im.width * scale, im.height * scale), Image.NEAREST))
    W = sum(t.width for t in tiles) + 10 * (len(tiles) - 1)
    H = max(t.height for t in tiles)
    sheet = Image.new("L", (W, H), 128)
    x = 0
    for t in tiles:
        sheet.paste(t, (x, 0)); x += t.width + 10
    sheet.save(out)
    print("saved", out)


def strips(out, profile):
    w, h = PROFILES[profile]["size"]
    sh = h // 4
    fs = files(profile)
    cols = 4
    rows = -(-len(fs) // cols)
    sheet = Image.new("L", (cols * (w + 10), rows * (2 * sh + 20)), 128)
    for i, f in enumerate(fs):
        im = load(f)
        x, y = (i % cols) * (w + 10), (i // cols) * (2 * sh + 20)
        sheet.paste(im.crop((0, 0, w, sh)), (x, y))
        sheet.paste(im.crop((0, h - sh, w, h)), (x, y + sh + 4))
    sheet.save(out)
    print("saved", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("verify", "zoom", "strips"))
    ap.add_argument("args", nargs="*")
    ap.add_argument("--profile", default="eink16", choices=sorted(PROFILES))
    ap.add_argument("--scale", type=int, default=2)
    a = ap.parse_args()
    if a.cmd == "verify":
        sys.exit(0 if verify() else 1)
    elif a.cmd == "zoom":
        zoom(a.args[0], a.args[1:], a.profile, a.scale)
    else:
        strips(a.args[0], a.profile)
