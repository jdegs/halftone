"""Per-cover settings for eink.py. Tweak and re-run make_wallpapers.py."""
LUMA = (0.2126, 0.7152, 0.0722)      # standard: matches perceived brightness
WARM = (0.55, 0.38, 0.07)            # reds/oranges render lighter, pop against black
COOL = (0.15, 0.55, 0.30)            # blues render lighter

DEFAULT = dict(mix=LUMA, black=0, white=255, gamma=1.0, brightness=0, contrast=1.0,
               sharpen=0.4, dither="floyd")

PRESETS = {
    # painterly portrait, lots of soft gradients -> JJN for smooth tone, lift the dark mids
    "01_crime_and_punishment": dict(black=18, white=245, gamma=1.15, sharpen=0.5, dither="jjn"),
    # pale sky and hills: deepen mids slightly so the hills hold texture
    "02_east_of_eden": dict(black=30, white=236, gamma=0.95, contrast=1.08, sharpen=0.5),
    # flames on black: a little extra red lifts the fire off the black without blowing it out
    "03_inferno": dict(mix=(0.42, 0.5, 0.08), black=35, white=250, gamma=1.0, contrast=1.05, sharpen=0.6, dither="jjn"),
    # bold graphic ink -> crisp Atkinson, push paper to pure white
    "04_steppenwolf": dict(black=8, white=222, sharpen=0.3, dither="atkinson"),
    # blue fish on paper; cool mix lifts the small fish so the big black fish stands out
    "05_catching_the_big_fish": dict(mix=COOL, black=30, white=228, gamma=1.1, sharpen=0.5),
    # red / pink / green / black blocks: plain luma keeps red darker than the pink
    "06_wuthering_heights": dict(black=20, white=238, gamma=1.0, contrast=1.05, sharpen=0.4),
    # mostly white with black brushwork
    "07_thus_spoke_zarathustra": dict(black=32, white=230, sharpen=0.3, dither="atkinson"),
    # dense green forest, low contrast -> stretch hard and smooth with JJN
    "08_into_the_wild": dict(black=55, white=225, gamma=1.25, contrast=1.15, sharpen=0.7, dither="jjn"),
    "09_the_stranger": dict(black=50, white=234, sharpen=0.3, dither="atkinson"),
    # near-black swan; warm mix lights up the orange beak
    "10_the_black_swan": dict(mix=WARM, black=20, white=236, gamma=1.15, sharpen=0.4),
    "11_the_trial": dict(mix=WARM, black=20, white=234, gamma=0.95, sharpen=0.4),
    # red vase: luma keeps it a solid mid-grey distinct from black marks and white paper
    "12_a_craftsmans_legacy": dict(black=35, white=226, gamma=1.15, contrast=1.05, sharpen=0.5),

    # --- photographic set (HG2f_nYaYAAJFFo.jpg): smooth tones throughout -> JJN everywhere
    # mostly black; lift the shadows so the bear's fur reads instead of sinking into black
    "13_the_call_of_the_wild": dict(black=3, white=245, gamma=1.4, sharpen=0.5, dither="jjn"),
    "14_walden": dict(black=16, white=226, gamma=1.1, contrast=1.05, sharpen=0.5, dither="jjn"),
    # foggy, low contrast: stretch, keep the fog light
    "15_into_the_wild_krakauer": dict(black=37, white=250, gamma=0.95, contrast=1.05, sharpen=0.5,
                                      dither="jjn"),
    # beige paper -> white, so the fog and type sit on clean paper like the printed cover
    "16_east_of_eden_steinbeck": dict(black=15, white=212, sharpen=0.4, dither="jjn"),
}


# Output targets. `crops` is made by: python tools/crop.py <crops> W H
PROFILES = {
    "eink16": dict(size=(684, 1216), levels=16, bpp=8, crops="crops", out="wallpapers"),
    "x4":     dict(size=(480, 800),  levels=4,  bpp=2, crops="crops_480x800", out="wallpapers_480x800"),
}

# Per-profile overrides, merged over DEFAULT + PRESETS. Filled in after reviewing renders.
# 4 levels: JJN avoids the diagonal "worms" Floyd-Steinberg shows in mid-tones; snap
# keeps paper and solid ink free of stray dots.
PROFILE_DEFAULT = {"x4": dict(snap=0.06, dither="jjn")}
PROFILE_PRESETS = {
    # With 4 levels, coloured type that falls between two greys dithers into grain.
    # `solid` boxes (output pixels, l, t, r, b) mark titles to print undithered.
    "x4": {
        "01_crime_and_punishment": dict(solid=[(90, 40, 390, 75)]),
        "02_east_of_eden": dict(solid=[(125, 295, 355, 328)]),
        "03_inferno": dict(solid=[(170, 55, 310, 92)]),
        "04_steppenwolf": dict(solid=[(25, 735, 215, 785)]),
        "05_catching_the_big_fish": dict(solid=[(20, 20, 200, 60)]),
        "08_into_the_wild": dict(solid=[(275, 740, 470, 785)]),
        "09_the_stranger": dict(solid=[(45, 120, 250, 160)]),
        "10_the_black_swan": dict(solid=[(420, 440, 470, 790)]),
        # photographic set: bright fog / paper grain leaks dither dots into the dark type
        "15_into_the_wild_krakauer": dict(solid=[(125, 58, 360, 300), (140, 308, 350, 340)],
                                          solid_thresh=0.3),
        # paper grain sits just under white and dithers into dots: whiten the paper harder
        "16_east_of_eden_steinbeck": dict(white=198, solid=[(20, 30, 460, 100), (25, 678, 470, 760)]),
    },
}


def settings(name, profile="eink16"):
    s = dict(DEFAULT)
    s.update(PROFILE_DEFAULT.get(profile, {}))
    s.update(PRESETS.get(name, {}))
    s.update(PROFILE_PRESETS.get(profile, {}).get(name, {}))
    return s
