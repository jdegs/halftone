"""Find the covers in a new grid image and preview how panel-shaped frames fit them.

  python tools/grid.py SOURCE.jpg [PREVIEW.jpg]

Prints X / Y edge lists to paste into a new set in crop.py, and saves a preview with
each cover's centred frame for 9:16 (684x1216, red) and 3:5 (480x800, blue) drawn on.

How it works: the background is taken from the top-left corner. Columns / rows that
differ from it give the coarse grid; each edge is then refined to the first sharp
step (>10 grey levels between neighbouring pixels) scanning inward from outside the
cover, which skips soft drop shadows.
"""
import sys
import numpy as np
from PIL import Image, ImageDraw


def runs(profile, thresh, min_len=200):
    out, start = [], None
    for i, on in enumerate(profile > thresh):
        if on and start is None:
            start = i
        elif not on and start is not None:
            if i - start > min_len:
                out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(profile)))
    return out


def refine(profile, edge, inward, reach=160):
    """First index, scanning inward from just outside `edge`, where the profile jumps
    by >10 between neighbours. Soft shadows change by ~1/px and are skipped; `reach`
    covers long shadows that make the coarse edge sit well outside the cover."""
    if inward > 0:
        xs = range(max(edge - 50, 1), min(edge + reach, len(profile)))
    else:
        xs = range(min(edge + 50, len(profile) - 1), max(edge - reach, 0), -1)
    prev = None
    for x in xs:
        if prev is not None and abs(profile[x] - prev) > 10:
            return x if inward > 0 else x + 1      # right/bottom edges are exclusive
        prev = profile[x]
    return None


def find_grid(a):
    bg = np.median(a[:60, :60])
    m = np.abs(a - bg) > 12
    # low threshold: pale paper covers barely differ from a light background
    cols = runs(m.mean(0), 0.15)
    rows = runs(m.mean(1), 0.15)
    # Measure every cover on its own middle band, then take each grid line as the
    # median over its row / column (a low-contrast cover can't skew the result).
    L, R, T, B = ({} for _ in range(4))
    for r, (y0, y1) in enumerate(rows):
        for c, (x0, x1) in enumerate(cols):
            q = (y1 - y0) // 4
            hband = np.median(a[y0 + q:y1 - q, :], axis=0)
            q = (x1 - x0) // 4
            vband = np.median(a[:, x0 + q:x1 - q], axis=1)
            L.setdefault(c, []).append(refine(hband, x0, 1))
            R.setdefault(c, []).append(refine(hband, x1, -1))
            T.setdefault(r, []).append(refine(vband, y0, 1))
            B.setdefault(r, []).append(refine(vband, y1, -1))
    med = lambda v: int(np.median([x for x in v if x is not None]))
    X = [(med(L[c]), med(R[c])) for c in range(len(cols))]
    Y = [(med(T[r]), med(B[r])) for r in range(len(rows))]
    return X, Y


if __name__ == "__main__":
    src = sys.argv[1]
    im = Image.open(src).convert("RGB")
    a = np.asarray(im.convert("L")).astype(float)
    X, Y = find_grid(a)
    print(f'src="{src}",')
    print("X=" + repr(X) + ",")
    print("Y=" + repr(Y) + ",")
    for (x0, x1) in X[:1]:
        for (y0, y1) in Y[:1]:
            w, h = x1 - x0, y1 - y0
            print(f"# cover ~{w} x {h} (aspect {w / h:.3f}); 9:16 frame keeps "
                  f"{100 * h * 684 / 1216 / w:.0f}% of the width, 3:5 keeps {100 * h * 0.6 / w:.0f}%")
    if len(sys.argv) > 2:
        prev = im.copy()
        d = ImageDraw.Draw(prev)
        for (y0, y1) in Y:
            for (x0, x1) in X:
                d.rectangle((x0, y0, x1, y1), outline=(0, 200, 0), width=4)
                for aspect, col in ((684 / 1216, (255, 0, 0)), (0.6, (0, 150, 255))):
                    w = (y1 - y0) * aspect
                    l = x0 + ((x1 - x0) - w) / 2
                    for x in (l, l + w):
                        d.line([(x, y0), (x, y1)], fill=col, width=4)
        prev.thumbnail((1600, 1600))
        prev.save(sys.argv[2])
        print("preview:", sys.argv[2])
