# halftone: e-ink wallpapers from cover grids

Turns grid images of covers (books, albums, posters) into sleep-screen wallpapers for
e-ink readers. Typical use: drop a grid image in the repo root and ask for wallpapers
from some of its covers. This file records the process and what was learned building
it, so a new session can start from here instead of re-deriving it.

Source grids and rendered outputs are not in the repo (see `.gitignore`); a fresh
clone has the tools, two worked example sets in `crop.py` / `presets.py` (skipped
because their images are absent), and empty output folders once you render.

## Targets (profiles in `tools/presets.py`)

| Profile | Size | Greys | File | Output folder |
| --- | --- | --- | --- | --- |
| `eink16` | 684x1216 | 16 | 8-bit greyscale BMP, values multiples of 17 | `wallpapers/` |
| `x4` | 480x800 | 4 | 2-bit BMP, palette 0/85/170/255 | `wallpapers_480x800/` |

Both targets are readers running CrossPoint firmware (crosspoint-reader/crosspoint-reader;
the 16-grey panel is the Metalio E-Ink4-Plus, gray support on branch
`feat-metalio-eink4plus`). A new target is a new entry in `PROFILES`.

## Setup

```sh
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
.venv/bin/python -m pip install -r requirements.txt       # macOS / Linux
```

Run tools with the venv's Python (written `python` below). numba matters: without it
the error-diffusion dither falls back to pure Python, ~30 s per image.

## Workflow for a new grid image

1. **Look at it** (save a thumbnail and Read it). Confirm which covers are wanted
   (e.g. only the books in a mixed grid of books, albums and films).
2. **Find the grid**: `python tools/grid.py NEW.jpg preview.jpg` prints `X=`/`Y=`
   edge lists and saves a preview with the centred 9:16 (red) and 3:5 (blue) frames.
   Read the preview to see what each frame cuts off.
3. **Add a set** to `SETS` in `tools/crop.py`: `src`, `X`, `Y`, `inset` (14 for worn
   covers with shadows, 4 for crisp rectangles), `first` (number of the set's first
   output file; the example sets use 01-16), `names` (None = skip), `shift` /
   `anchor` for framing, `fixes` for text.
4. **Crop both sizes**:
   `python tools/crop.py crops 684 1216 SETNAME` and
   `python tools/crop.py crops_480x800 480 800 SETNAME`.
   Re-crop *both* sizes after any change to a fix (stale crops caused a ghost once).
5. **Measure tone**: percentiles (0.5, 2, 50, 98, 99.5) of `eink.tone()` on each crop
   to pick black/white points; add presets to `PRESETS` in `presets.py` with a
   one-line comment saying why.
6. **Render**: `python tools/make_wallpapers.py` and `... --profile x4`.
   Add `NAME` to render only matching covers (skips the contact sheet).
7. **Review** - downscaled contact sheet (`<out>/_contact_sheet.png`) for tone,
   1:1 zooms for dither and type:
   `python tools/check.py strips s.png --profile x4` (all titles at 1:1),
   `python tools/check.py zoom z.png NAME:l,t,r,b ... --profile x4`.
   Fix grainy x4 type with `solid` boxes in `PROFILE_PRESETS["x4"]`.
8. **Verify**: `python tools/check.py verify` (sizes, bit depth, grey levels).

When refactoring shared code, check that existing crops/BMPs stay byte-identical
(render to a scratch folder and `cmp`) - outputs already on someone's device
shouldn't shift.

## Findings

### Firmware (CrossPoint) - why outputs are pre-quantised
- **16-grey sleep path** (`GfxRenderer::displayGray16Bitmap`): maps 8-bit grey to 16
  levels as `(255-lum)*15/255` and dithers the remainder with a 4x4 Bayer matrix.
  Values that are exact multiples of 17 have no remainder, so our error-diffusion
  dither reaches the glass untouched (verified: 0 pixels changed). Only used when the
  sleep cover filter is "No filter", the display isn't inverted, and the BMP is >=8bpp.
- It only scales *down*, by dropping pixels - always output exactly the panel size.
- It draws with the panel's own waveform. Real lightness of its 16 levels is
  unmeasured; the branch's `docs/gray16-tuning.md` + `scripts/gray16_tune.py` could
  measure it (`GRAY16 OFF`, `SHOW 0`, photograph, `measure`). With those numbers,
  `quantise` could diffuse error in measured-lightness space. Not done yet.
- **4-grey path** (`Bitmap.cpp`): a 1/2-bit BMP, or any palette whose entries are within
  21 of 0/85/170/255, counts as "native" and is drawn as-is. An 8-bit BMP from Pillow
  has a 256-entry palette, so the firmware would re-dither it - hence the custom
  2-bit writer (`eink.write_bmp2`). Pillow cannot read 2-bit BMPs (`eink.read_bmp2`
  decodes them like the firmware); many desktop viewers can't open them either.

### Tone
- Channel mix matters more than dither choice. Rec.709 luma is the default; per cover:
  a warm mix lifts red/orange off black (Inferno flames, Black Swan beak), a cool mix
  lifts blue (Lynch's small fish), and plain luma keeps red darker than pink
  (Wuthering Heights). Too much red weight blows flames out to white.
- Set the white point just below the paper so paper becomes pure white.
- Very dark photos (Call of the Wild) need gamma ~1.4 or detail sinks into black.

### Dithering
- 16 levels: dither mainly matters on smooth gradients (no dither = banding).
  JJN for painterly/photographic covers, Atkinson for bold graphic ink (crisp, paper
  stays white, loses some tonal range), Floyd-Steinberg otherwise.
- 4 levels: Floyd-Steinberg shows diagonal "worms" in mid-tones; JJN is the x4
  default. Atkinson stays on the ink covers.
- 4 levels needs `snap` (0.06): near-white/near-black are ramped to pure so paper
  isn't sprinkled with stray dots. It's a steepened ramp, not a threshold, so soft
  gradients don't get a contour. Grainy paper may also need a lower white point.
- 4 levels: coloured or dark type that falls between two levels dithers into grain.
  `solid` boxes (output px) snap type pixels to the nearest level, undithered.
  Use `solid_thresh` ~0.3 where the background varies (fog), else the box shows.

### Cropping and text
- Frames are cover-height, centred, with per-cover `shift` (fraction of slack) or
  `anchor` (`('centre', x)` / `('right', x)` in cover px). Centre on the *text* when a
  cover's design is itself off-centre (Zarathustra).
- Titles wider than the frame are refit with `tools/retext.py`: find type by colour
  distance from the local paper, lift it as a multiply layer, erase it, place it.
  `refit()` moves/shrinks a block; `light=True` handles light type on dark (inverts
  around the same steps); photos need a higher `thresh` (~120) so highlights aren't
  taken for type.
- Erasing: plain diffusion + random grain is fine on paper. On photos or grainy fields
  use `texture_from=(dx, dy)` pointing at nearby clean texture - never `(0, 0)`, which
  copies the old letters back as a ghost.

## Quality bar (settled in review rounds)
- Clean crops: no background border, titles centred on the text itself, nothing
  clipped. When text doesn't fit, move or scale the text; don't alter the artwork
  (bending a brushstroke out of the way was tried and rejected - its texture looked
  wrong).
- Judge at 1:1: text edges, ghosts where text was erased, paper speckle.
- Scaling type to ~0.7-0.9 to keep a whole title is fine.

## Files
- `tools/crop.py` - sets (source grids), framing, per-cover text fixes.
- `tools/retext.py` - lift / erase / place / refit text on a cover.
- `tools/eink.py` - tone curve, dithering (numba), `solid`, BMP writers/reader.
- `tools/presets.py` - profiles, per-cover tone presets, x4 overrides.
- `tools/make_wallpapers.py` - render crops to BMPs + contact sheet.
- `tools/grid.py` - find covers in a new grid image.
- `tools/check.py` - verify outputs, 1:1 zoom sheets.
- Example sets (images not included): `lit` - 12 painted book covers with shadows
  and worn edges (01-12; shows `fit_line`, the Kafka two-block move, `anchor` on
  text); `photo` - 4 photographic book covers from a 12-cover grid (13-16; shows
  `refit` with `light=True`, `texture_from`, and x4 `solid` boxes on fog).

## Gotchas
- Windows: viewers/sync tools briefly lock files; `eink.safe_save` writes a temp file
  and swaps it in with retries. If a save still fails, the file is open somewhere.
- Judge tone on the downscaled contact sheet; judge dither and type at 1:1 only.
- Cover artwork belongs to its designers - source grids and outputs stay out of the
  repo (see `.gitignore`).
