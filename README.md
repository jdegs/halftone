# halftone

Turns grid images of covers (books, albums, posters) into greyscale sleep-screen
wallpapers for e-ink readers running [CrossPoint](https://github.com/crosspoint-reader/crosspoint-reader):

| Profile | Size | Greys | Output |
| --- | --- | --- | --- |
| `eink16` | 684x1216 | 16 | 8-bit greyscale BMP |
| `x4` | 480x800 | 4 | 2-bit BMP, drawn natively (no re-dithering on device) |

For each cover, halftone:
- crops it to the panel's shape, moving or scaling titles that don't fit (light or
  dark type, on paper or photos), with the old text erased cleanly;
- tone-maps it per cover: channel mix, black/white point, gamma, contrast, sharpening;
- dithers to the panel's grey levels with error diffusion (Floyd-Steinberg, Atkinson,
  JJN, Stucki, Sierra...) or ordered/blue-noise, and keeps 4-grey type solid.

It was built in Claude Code sessions, and is meant to be continued that way:
[`CLAUDE.md`](CLAUDE.md) holds the workflow, the firmware findings behind the output
formats, and the tuning lessons, so a new session can pick it up.

## Use

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt     # .venv/Scripts/python on Windows

python tools/grid.py GRID.jpg preview.jpg      # find covers; prints X/Y for a new set
# add the set to SETS in tools/crop.py, presets to tools/presets.py
python tools/crop.py crops 684 1216            # crop all sets with a source present
python tools/crop.py crops_480x800 480 800
python tools/make_wallpapers.py                # -> wallpapers/
python tools/make_wallpapers.py --profile x4   # -> wallpapers_480x800/
python tools/check.py verify                   # sizes, bit depth, grey levels
python tools/check.py strips s.png --profile x4   # every title at 1:1, for review
```

`tools/eink.py` also converts any single image:

```sh
python tools/eink.py in.png out.bmp --levels 4 --bpp 2 --dither jjn --snap 0.06 --gamma 1.1
```

## Not included

Source grids and rendered wallpapers: cover art belongs to its designers. `crop.py`
and `presets.py` keep two worked example sets from the grids halftone was built on;
they're skipped when their images are absent, and serve as reference for each
text-handling technique.
