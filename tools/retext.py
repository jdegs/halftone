"""Lift printed text off a cover, erase it, and put it back somewhere else / at another size.

Works on a full-resolution RGB cover (numpy float array, 0..255), in cover coordinates.
Text is found as pixels that differ strongly from the local paper colour inside a search box,
so it works for coloured type (Lynch's blue) as well as black.
"""
import numpy as np
from PIL import Image
from scipy import ndimage as ndi


def text_mask(cover, box, thresh=45):
    l, t, r, b = box
    reg = cover[t:b, l:r]
    paper = np.median(reg.reshape(-1, 3), axis=0)
    dist = np.sqrt(((reg - paper) ** 2).sum(-1))
    m = dist > thresh
    m = ndi.binary_opening(m, iterations=1) | (dist > thresh * 2)   # drop paper-grain specks
    ys, xs = np.nonzero(m)
    tight = (l + xs.min(), t + ys.min(), l + xs.max() + 1, t + ys.max() + 1)
    return m, paper, tight


def erase(cover, box, mask, grow=4, texture_from=None):
    """Fill masked pixels from their surroundings.

    Default: iterative diffusion plus random grain (good on plain paper).
    texture_from=(dx, dy): shading still comes from the diffusion, but the fine texture
    is copied from the same-shaped area offset by (dx, dy) - for photos or grainy fields,
    where smooth fills would show as blobs."""
    l, t, r, b = box
    reg = cover[t:b, l:r]
    hole = ndi.binary_dilation(mask, iterations=grow)
    known = ~hole
    fill = reg.copy()
    fill[hole] = np.median(reg[known], axis=0)
    # big holes in textured mode need longer to settle; plain mode keeps its original 200
    iters = max(200, int(2 * max(b - t, r - l))) if texture_from else 200
    for _ in range(iters):
        blur = ndi.uniform_filter(fill, size=(5, 5, 1))
        fill[hole] = blur[hole]
    if texture_from:
        dx, dy = texture_from
        src = cover[t + dy:b + dy, l + dx:r + dx]
        detail = src - ndi.gaussian_filter(src, (4, 4, 0))
        fill[hole] += detail[hole]
    else:
        rng = np.random.default_rng(0)
        grain = reg[known].std(axis=0) * 0.6
        fill[hole] += rng.normal(0, 1, (hole.sum(), 1)) * grain
    cover[t:b, l:r] = fill


def lift(cover, tight, paper, grow=2, pad=6, thresh=45):
    """Return a multiply layer (1 = paper, <1 = ink) for the text in `tight`."""
    l, t, r, b = tight
    l, t, r, b = l - pad, t - pad, r + pad, b + pad
    reg = cover[t:b, l:r].copy()
    dist = np.sqrt(((reg - paper) ** 2).sum(-1))
    keep = ndi.binary_dilation(dist > thresh, iterations=grow)
    layer = np.clip(reg / paper, 0, 1)
    layer[~keep] = 1.0
    # soften the cut-out boundary so anti-aliased edges survive
    soft = ndi.gaussian_filter(keep.astype(float), 0.8)[..., None]
    return 1 - (1 - layer) * soft


def place(cover, layer, x, y, scale=1.0):
    h, w = layer.shape[:2]
    if scale != 1.0:
        w2, h2 = round(w * scale), round(h * scale)
        chans = [np.asarray(Image.fromarray(layer[..., c].astype(np.float32), 'F')
                            .resize((w2, h2), Image.LANCZOS)) for c in range(3)]
        layer = np.clip(np.stack(chans, -1), 0, 1); h, w = h2, w2
    x, y = round(x), round(y)
    cover[y:y + h, x:x + w] *= layer
    return (x, y, x + w, y + h)


class inverted:
    """Context manager: work on light-on-dark text with the dark-ink tools by
    inverting the cover in place for the duration of the block."""
    def __init__(self, cover):
        self.cover = cover

    def __enter__(self):
        np.subtract(255.0, self.cover, out=self.cover)
        return self.cover

    def __exit__(self, *exc):
        np.subtract(255.0, self.cover, out=self.cover)
        return False


def refit(cover, box, left=None, right=None, width=None, bottom=False, light=False,
          texture_from=None, thresh=45, grow=4):
    """Move (and optionally shrink) the text block found in `box`.

    left / right: new x of the block's left or right edge (cover pixels).
    width: shrink the block to at most this width (never enlarges).
    bottom: keep the block's bottom edge where it was (default keeps the top).
    light: the text is lighter than its background (e.g. cream type on a photo).
    Returns the block's new (l, t, r, b)."""
    def run():
        m, paper, tight = text_mask(cover, box, thresh)
        tw, th = tight[2] - tight[0], tight[3] - tight[1]
        scale = min(1.0, width / tw) if width else 1.0
        layer = lift(cover, tight, paper, thresh=thresh)
        erase(cover, box, m, grow=grow, texture_from=texture_from)
        nw, nh = tw * scale, th * scale
        x = left if left is not None else (right - nw if right is not None else tight[0])
        y = tight[3] - nh if bottom else tight[1]
        pad = 6
        place(cover, layer, x - pad * scale, y - pad * scale, scale)
        return (round(x), round(y), round(x + nw), round(y + nh))
    if light:
        with inverted(cover):
            return run()
    return run()
