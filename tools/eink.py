"""
Convert an image to an N-level greyscale BMP for an e-ink panel.

Pipeline (in this order, like most e-ink wallpaper tools):
  1. colour -> grey using a channel mix (default Rec.709 luma)
  2. levels: black point / white point (input values mapped to 0 / 255)
  3. gamma          (>1 brightens midtones, <1 darkens)
  4. brightness     (-100..100, additive)
  5. contrast       (multiplier around mid-grey, 1.0 = unchanged)
  6. sharpen        (unsharp mask amount; helps edges survive dithering)
  7. snap           (push near-white/near-black to pure, so paper isn't speckled)
  8. quantise to N grey levels with a dithering algorithm
  9. save as 8-bit greyscale BMP, or 2-bit palettised BMP for 4 levels

Usage:
  python eink.py in.png out.bmp [--dither atkinson] [--black 10] [--white 240]
                 [--gamma 1.1] [--brightness 0] [--contrast 1.1] [--sharpen 0.6]
                 [--mix 0.30,0.59,0.11] [--levels 16] [--snap 0.06] [--bpp 2]
                 [--no-serpentine]
"""
import argparse
import numpy as np
from PIL import Image, ImageFilter

KERNELS = {
    # (dx, dy, weight); divisor applied below. Positions are relative to the current pixel.
    "floyd":       ([(1, 0, 7), (-1, 1, 3), (0, 1, 5), (1, 1, 1)], 16),
    "atkinson":    ([(1, 0, 1), (2, 0, 1), (-1, 1, 1), (0, 1, 1), (1, 1, 1), (0, 2, 1)], 8),  # only 6/8 diffused
    "jjn":         ([(1, 0, 7), (2, 0, 5), (-2, 1, 3), (-1, 1, 5), (0, 1, 7), (1, 1, 5), (2, 1, 3),
                     (-2, 2, 1), (-1, 2, 3), (0, 2, 5), (1, 2, 3), (2, 2, 1)], 48),
    "stucki":      ([(1, 0, 8), (2, 0, 4), (-2, 1, 2), (-1, 1, 4), (0, 1, 8), (1, 1, 4), (2, 1, 2),
                     (-2, 2, 1), (-1, 2, 2), (0, 2, 4), (1, 2, 2), (2, 2, 1)], 42),
    "burkes":      ([(1, 0, 8), (2, 0, 4), (-2, 1, 2), (-1, 1, 4), (0, 1, 8), (1, 1, 4), (2, 1, 2)], 32),
    "sierra":      ([(1, 0, 5), (2, 0, 3), (-2, 1, 2), (-1, 1, 4), (0, 1, 5), (1, 1, 4), (2, 1, 2),
                     (-1, 2, 2), (0, 2, 3), (1, 2, 2)], 32),
    "sierra_lite": ([(1, 0, 2), (-1, 1, 1), (0, 1, 1)], 4),
}
ORDERED = ("bayer4", "bayer8", "bluenoise")
ALL_DITHERS = ("none",) + tuple(KERNELS) + ORDERED


def bayer(n):
    m = np.array([[0]])
    while m.shape[0] < n:
        m = np.block([[4 * m, 4 * m + 2], [4 * m + 3, 4 * m + 1]])
    return (m + 0.5) / m.size


def blue_noise(size=64, seed=1):
    """Cheap blue-noise-ish threshold map: high-passed white noise, rank-normalised."""
    rng = np.random.default_rng(seed)
    w = rng.random((size, size))
    from scipy.ndimage import gaussian_filter
    for _ in range(4):
        w = w - gaussian_filter(w, 1.2, mode="wrap")
        w = np.argsort(np.argsort(w.ravel())).reshape(w.shape) / w.size
    return w + 0.5 / w.size


def tone(img, mix=(0.2126, 0.7152, 0.0722), black=0, white=255, gamma=1.0,
         brightness=0.0, contrast=1.0, sharpen=0.0, snap=0.0):
    rgb = np.asarray(img.convert("RGB"), dtype=np.float64)
    g = rgb @ np.asarray(mix, dtype=np.float64) / sum(mix)
    g = np.clip((g - black) / max(white - black, 1), 0, 1)
    g = g ** (1.0 / gamma)
    g = g + brightness / 255.0
    g = (g - 0.5) * contrast + 0.5
    g = np.clip(g, 0, 1)
    if sharpen > 0:
        im = Image.fromarray((g * 255).round().astype(np.uint8))
        blur = np.asarray(im.filter(ImageFilter.GaussianBlur(1.5)), dtype=np.float64) / 255
        g = np.clip(g + sharpen * (g - blur), 0, 1)
    if snap > 0:
        # Push near-white to pure white and near-black to pure black, so paper and solid
        # ink aren't sprinkled with stray dither dots (very visible with only 4 levels).
        # Linear ramps, no jump: [1-2s, 1-s] -> [1-2s, 1] and [s, 2s] -> [0, 2s].
        hi, lo = 1 - snap, snap
        g = np.where(g > hi - snap, np.minimum(1, (hi - snap) + (g - (hi - snap)) * 2), g)
        g = np.where(g < lo + snap, np.maximum(0, (lo + snap) - ((lo + snap) - g) * 2), g)
    return g  # float 0..1


def quantise(g, levels=16, dither="floyd", serpentine=True):
    q = levels - 1
    if dither == "none":
        return np.round(g * q) / q
    if dither in ORDERED:
        t = {"bayer4": lambda: bayer(4), "bayer8": lambda: bayer(8), "bluenoise": blue_noise}[dither]()
        h, w = g.shape
        th = np.tile(t, (h // t.shape[0] + 1, w // t.shape[1] + 1))[:h, :w]
        return np.clip(np.floor(g * q + th), 0, q) / q
    taps, div = KERNELS[dither]
    t = np.array([(dx, dy, wt / div) for dx, dy, wt in taps], dtype=np.float64)
    return _diffuse(np.ascontiguousarray(g, dtype=np.float64), q, t, serpentine)


def _diffuse_py(g, q, taps, serpentine):
    h, w = g.shape
    pad = 2
    buf = np.zeros((h + pad, w + 2 * pad))
    buf[:h, pad:pad + w] = g
    out = np.zeros((h, w))
    nt = taps.shape[0]
    for y in range(h):
        rev = serpentine and (y & 1)
        for i in range(w):
            x = w - 1 - i if rev else i
            xp = x + pad
            v = buf[y, xp]
            n = int(np.floor(v * q + 0.5))
            if n < 0:
                n = 0
            elif n > q:
                n = q
            nv = n / q
            out[y, x] = nv
            e = v - nv
            for k in range(nt):
                dx = int(taps[k, 0])
                if rev:
                    dx = -dx
                buf[y + int(taps[k, 1]), xp + dx] += e * taps[k, 2]
    return out


try:
    from numba import njit
    _diffuse = njit(cache=True)(_diffuse_py)
except ImportError:  # works without numba, just slowly (~30 s per image)
    _diffuse = _diffuse_py


def solidify(g, o, levels, boxes, thresh=0.12):
    """Inside each (l, t, r, b) box, pixels that stand out from the box's background
    (i.e. type) are set to their nearest level with no dither, so coloured lettering
    that falls between two levels prints solid instead of grainy."""
    q = levels - 1
    for l, t, r, b in boxes:
        sub = g[t:b, l:r]
        m = np.abs(sub - np.median(sub)) > thresh
        o[t:b, l:r][m] = np.round(sub[m] * q) / q
    return o


def convert(src, dst, levels=16, dither="floyd", serpentine=True, bpp=8, solid=(),
            solid_thresh=0.12, **tone_kw):
    """bpp=8: 8-bit greyscale BMP. bpp=2 (levels=4 only): 2-bit BMP with a 4-entry
    grey palette, which CrossPoint treats as native and draws without re-dithering.
    solid: boxes (output pixels) around type to render undithered, see solidify().
    solid_thresh: how far from the box's background a pixel must be to count as type;
    raise it where the background itself varies (fog, photos)."""
    g = tone(Image.open(src), **tone_kw)
    o = quantise(g, levels, dither, serpentine)
    if solid:
        o = solidify(g, o, levels, solid, solid_thresh)
    out = Image.fromarray((o * 255).round().astype(np.uint8), "L")
    if bpp == 2:
        assert levels == 4, "2-bit BMP holds exactly 4 levels"
        safe_save(out, dst, write=lambda path: write_bmp2(out, path))
    else:
        safe_save(out, dst, "BMP")
    return out


def write_bmp2(img, path):
    """Write an L image whose values are 0/85/170/255 as a 2-bit palettised BMP.
    PIL cannot write 2bpp BMPs. Palette index = level (0 black .. 3 white)."""
    import struct
    a = np.asarray(img)
    idx = np.round(a / 85).astype(np.uint8)
    assert np.array_equal(idx.astype(int) * 85, a), "image must hold only 0/85/170/255"
    h, w = idx.shape
    row_bytes = (w * 2 + 31) // 32 * 4
    pad_w = row_bytes * 4
    rows = np.zeros((h, pad_w), np.uint8)
    rows[:, :w] = idx
    q = rows.reshape(h, -1, 4)
    packed = (q[..., 0] << 6) | (q[..., 1] << 4) | (q[..., 2] << 2) | q[..., 3]
    pixels = packed[::-1].tobytes()                       # BMP rows run bottom-up
    palette = b"".join(bytes((v, v, v, 0)) for v in (0, 85, 170, 255))
    off = 14 + 40 + len(palette)
    with open(path, "wb") as f:
        f.write(b"BM" + struct.pack("<IHHI", off + len(pixels), 0, 0, off))
        f.write(struct.pack("<IiiHHIIiiII", 40, w, h, 1, 2, 0, len(pixels), 2835, 2835, 4, 4))
        f.write(palette + pixels)


def read_bmp2(path):
    """Decode a 2-bit BMP the way CrossPoint's Bitmap.cpp does (Pillow can't read 2bpp).
    Returns an L image of palette luminances."""
    import struct
    d = open(path, "rb").read()
    off, = struct.unpack_from("<I", d, 10)
    hsz, w, h, _, bpp, comp, _, _, _, used, _ = struct.unpack_from("<IiiHHIIiiII", d, 14)
    assert bpp == 2 and comp == 0
    used = used or 4
    pal = [(77 * d[14 + hsz + 4 * i + 2] + 150 * d[14 + hsz + 4 * i + 1] + 29 * d[14 + hsz + 4 * i]) >> 8
           for i in range(used)]
    rb = (w * 2 + 31) // 32 * 4
    raw = np.frombuffer(d, np.uint8, rb * abs(h), off).reshape(abs(h), rb)
    idx = np.stack([(raw >> s) & 3 for s in (6, 4, 2, 0)], -1).reshape(abs(h), -1)[:, :w]
    if h > 0:
        idx = idx[::-1]
    return Image.fromarray(np.asarray(pal, np.uint8)[idx], "L")


def safe_save(img, dst, fmt=None, write=None):
    """Write-then-swap with retries: viewers/sync tools on Windows briefly lock open files."""
    import os, time
    tmp = dst + ".tmp"
    if write:
        write(tmp)
    else:
        img.save(tmp, format=fmt)
    for attempt in range(20):
        try:
            os.replace(tmp, dst)
            break
        except OSError:
            time.sleep(0.25)
    else:
        raise OSError(f"could not replace {dst} (is it open in another program?); new image left at {tmp}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("src"); p.add_argument("dst")
    p.add_argument("--dither", default="floyd", choices=ALL_DITHERS)
    p.add_argument("--levels", type=int, default=16)
    p.add_argument("--black", type=float, default=0)
    p.add_argument("--white", type=float, default=255)
    p.add_argument("--gamma", type=float, default=1.0)
    p.add_argument("--brightness", type=float, default=0)
    p.add_argument("--contrast", type=float, default=1.0)
    p.add_argument("--sharpen", type=float, default=0.0)
    p.add_argument("--mix", default="0.2126,0.7152,0.0722")
    p.add_argument("--snap", type=float, default=0.0)
    p.add_argument("--bpp", type=int, default=8, choices=(2, 8))
    p.add_argument("--no-serpentine", action="store_true")
    a = p.parse_args()
    convert(a.src, a.dst, a.levels, a.dither, not a.no_serpentine, bpp=a.bpp,
            mix=tuple(float(v) for v in a.mix.split(",")), black=a.black, white=a.white,
            gamma=a.gamma, brightness=a.brightness, contrast=a.contrast, sharpen=a.sharpen,
            snap=a.snap)
