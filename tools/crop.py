"""Crop cover grids to a panel's size.

Usage: python tools/crop.py OUTDIR [W H] [SET]     (default 684 1216, all sets)
  e.g. python tools/crop.py crops_480x800 480 800
       python tools/crop.py crops 684 1216 photo

Each SET is one source image: a grid of covers whose edges were measured from the
source (tools/grid.py). Covers named None in a set are skipped (e.g. albums and films
in 'photo'). Output files are numbered across sets: 01-12 'lit', 13-16 'photo'.

The 'lit' and 'photo' sets are worked examples from the grids this tool was built on.
Their source images aren't in the repo, so they are skipped unless you supply them;
they are kept because their per-cover fixes show each text-handling technique.
"""
from PIL import Image; import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import retext

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------- set 'lit'
# Painted covers on a light background, each ~672 x 1037 px. Edges are the sharp
# paper/background step; the soft drop shadow right and below is excluded.

def fit_line(cv, win, box, margin):
    """Scale a one-line title down (never up) so it sits inside the frame with `margin`."""
    m, paper, tight = retext.text_mask(cv, box)
    wl, wr = win
    scale = min(1.0, (wr - wl - 2 * margin) / (tight[2] - tight[0]))
    if scale == 1.0 and tight[0] >= wl + margin and tight[2] <= wr - margin:
        return                                   # already fits where it is
    layer = retext.lift(cv, tight, paper)
    retext.erase(cv, box, m)
    pad = 6
    cy = (tight[1] + tight[3]) / 2
    h = (tight[3] - tight[1]) * scale
    retext.place(cv, layer, wl + margin - pad * scale, cy - h / 2 - pad * scale, scale)


def fix_lynch(cv, win):
    fit_line(cv, win, (20, 25, 660, 100), margin=36)


def fix_craftsman(cv, win):
    fit_line(cv, win, (10, 20, 662, 110), margin=26)


def fix_kafka(cv, win):
    """Author bottom-left, title bottom-right: slide each word block to the new edges.
    Margin is tighter than the original 34px so "The" stays clear of the orange
    squiggle's tail (rightmost ink at x~451 on the title rows; "The" lands at ~468)."""
    wl, wr = win
    margin = 24
    lifted = []
    for box in [(20, 950, 260, 1020), (480, 950, 660, 1020)]:
        m, paper, tight = retext.text_mask(cv, box)
        lifted.append((retext.lift(cv, tight, paper), tight))
        retext.erase(cv, box, m)
    pad = 6
    (la, ta), (lb, tb) = lifted
    retext.place(cv, la, wl + margin - pad, ta[1] - pad)
    retext.place(cv, lb, wr - margin - (tb[2] - tb[0]) - pad, tb[1] - pad)


def lit_fixes(W, H):
    fixes = {4: fix_lynch, 10: fix_kafka}
    # A Craftsman's Legacy: on 3:5 frames the title overflows by only ~10px, so centre
    # the frame and scale the title ~90%. The 9:16 set keeps its left-biased crop.
    if W / H > 0.58:
        fixes[11] = fix_craftsman
    return fixes


def lit_shift(W, H):
    # Horizontal bias, -1 (keep left edge) .. 0 (centred) .. +1 (keep right edge).
    shift = {
        3: -0.6,   # Steppenwolf: left-aligned title
        7: 0.6,    # Into the Wild: right-aligned title
        9: 0.7,    # The Black Swan: vertical title on the right
        10: 0.4,   # The Trial: slight right bias so the title clears the orange squiggle
        11: -1,    # A Craftsman's Legacy: wide title, keep author
    }
    if W / H > 0.58:
        shift.pop(11)
    return shift


# -------------------------------------------------------------- set 'photo'
# Photographic covers, flat 869 x 1115 px rectangles with crisp edges and no shadow.
# Only the four books are cropped; albums, films and the quote poster are skipped.

def fix_walden(cv, win):
    """Frame is kept on the crouching man (right); slide the left-aligned light text
    (author top-left, paragraph bottom-left) in to the frame's left margin."""
    wl, wr = win
    margin = 24
    for box in [(25, 55, 240, 115), (30, 975, 390, 1082)]:
        retext.refit(cv, box, left=wl + margin, light=True, thresh=120, grow=2)


def fix_eden(cv, win):
    """Keep the cover's left-aligned layout: name, paragraph and title all start at the
    frame's left margin; the two big title lines shrink to the frame's width."""
    wl, wr = win
    margin = 34
    width = wr - wl - 2 * margin
    retext.refit(cv, (40, 195, 290, 345), left=wl + margin)                       # paragraph
    retext.refit(cv, (40, 40, 835, 180), left=wl + margin, width=width)          # John Steinbeck
    retext.refit(cv, (40, 900, 835, 1060), left=wl + margin, width=width, bottom=True,
                 light=True, texture_from=(0, -150))                              # East of Eden


SETS = {
    "lit": dict(
        src="HBTWJ5pbcAER4uS.jpg",
        X=[(314, 986), (1161, 1834), (2010, 2681), (2857, 3529)],
        Y=[(318, 1356), (1532, 2568), (2745, 3780)],
        inset=14,                      # trims the worn/rounded paper edge
        first=1,
        names=["crime_and_punishment", "east_of_eden", "inferno", "steppenwolf",
               "catching_the_big_fish", "wuthering_heights", "thus_spoke_zarathustra",
               "into_the_wild", "the_stranger", "the_black_swan", "the_trial",
               "a_craftsmans_legacy"],
        shift=lit_shift,
        # ('centre', x): centre the frame on cover x. ('right', x): frame's right edge at x.
        anchor={6: ("centre", 351.5)},  # Zarathustra: title sits ~16px right of centre
        fixes=lit_fixes,
    ),
    "photo": dict(
        src="HG2f_nYaYAAJFFo.jpg",
        X=[(207, 1076), (1145, 2014), (2082, 2951), (3020, 3889)],
        Y=[(207, 1322), (1391, 2506), (2574, 3689)],
        inset=4,
        first=13,
        names=["the_call_of_the_wild", None, None, "walden",
               None, "into_the_wild_krakauer", None, None,
               None, None, None, "east_of_eden_steinbeck"],
        shift=lambda W, H: {},
        anchor={3: ("right", 800),      # Walden: keep the crouching man (ends ~x790)
                11: ("centre", 430)},   # East of Eden: centre on the tree
        fixes=lambda W, H: {3: fix_walden, 11: fix_eden},
    ),
}


def crop_set(cfg, out, W, H):
    path = os.path.join(ROOT, cfg["src"])
    if not os.path.exists(path):
        print(f"skipping set: {cfg['src']} not found (source grids aren't in the repo)")
        return
    im = Image.open(path).convert("RGB")
    shift, fixes, anchor, inset = cfg["shift"](W, H), cfg["fixes"](W, H), cfg["anchor"], cfg["inset"]
    n = cfg["first"]
    i = 0
    for (y0, y1) in cfg["Y"]:
        for (x0, x1) in cfg["X"]:
            name = cfg["names"][i]
            if name is None:
                i += 1
                continue
            top, bot = y0 + inset, y1 - inset
            h = bot - top; w = h * W / H
            left, right = x0 + inset, x1 - inset
            slack = (right - left) - w
            cx = left + slack / 2 * (1 + shift.get(i, 0))
            if i in anchor:
                kind, ax = anchor[i]
                cx = x0 + ax - (w / 2 if kind == "centre" else w)
                cx = min(max(cx, left), right - w)
            box = (cx, top, cx + w, bot)
            src = im
            if i in fixes:
                cv = np.asarray(im.crop((x0, y0, x1, y1)), dtype=np.float64)
                fixes[i](cv, (cx - x0, cx + w - x0))
                src = Image.fromarray(np.clip(cv, 0, 255).round().astype(np.uint8))
                box = (cx - x0, top - y0, cx + w - x0, bot - y0)
            # resize straight from the float box so the aspect ratio is exact
            src.resize((W, H), Image.LANCZOS, box=box).save(f"{out}/{n:02d}_{name}.png")
            print(n, name, tuple(round(v) for v in box), "slack", round(slack))
            i += 1
            n += 1


if __name__ == "__main__":
    args = sys.argv[1:]
    out = args[0]
    W, H = (int(args[1]), int(args[2])) if len(args) >= 3 else (684, 1216)
    which = args[3:] or list(SETS)
    os.makedirs(out, exist_ok=True)
    for s in which:
        crop_set(SETS[s], out, W, H)
