# Image credits

Photographic scenery in the dashboard. Everything here is public domain or CC0 (no attribution required, credited anyway), or generated from code. Sources are Wikimedia Commons file pages. Originals were cropped, background-removed (rembg `birefnet-general-lite`, plus manual mask repair for the clownfish) or colour-keyed, colour-graded and recompressed to WebP. The files in this folder are the processed results.

| File here | Source file | Author | Licence |
|---|---|---|---|
| `dolphin.webp` | [Common bottlenose dolphin jumping.jpg](https://commons.wikimedia.org/wiki/File:Common_bottlenose_dolphin_jumping.jpg) | NOAA Fisheries | Public domain |
| `clownfish.webp` | [Common clownfish.jpg](https://commons.wikimedia.org/wiki/File:Common_clownfish.jpg) | Janderk | Public domain |
| `butterflyfish.webp` | [Chaetodon paucifasciatus 150452375.jpg](https://commons.wikimedia.org/wiki/File:Chaetodon_paucifasciatus_150452375.jpg) | Jean-Paul Boerekamps | CC0 |
| `cloud1.webp`, `cloud2.webp`, `cloud3.webp` | [Bright blue sky with scenic white cloud patterns.jpg](https://commons.wikimedia.org/wiki/File:Bright_blue_sky_with_scenic_white_cloud_patterns.jpg) (colour-keyed off the blue sky) | Trixia Lao | CC0 |
| `meadow.webp` | [Meadow full of daisies, Idstein.jpg](https://commons.wikimedia.org/wiki/File:Meadow_full_of_daisies,_Idstein.jpg) | Gerda Arendt | CC0 |
| `water.webp` | [Bottlenose Dolphin Leap (43530653511).png](https://commons.wikimedia.org/wiki/File:Bottlenose_Dolphin_Leap_(43530653511).png) (turquoise sea, lower part only) | drytortugasnps (US National Park Service) | Public domain |
| `dandelion.webp` | [Dandelion seeds close-up.jpg](https://commons.wikimedia.org/wiki/File:Dandelion_seeds_close-up.jpg) (luminance-keyed off the dark background) | Oleksandr K | CC0 |
| `leaf.webp` | [Droplets on a maple leaf (Unsplash).jpg](https://commons.wikimedia.org/wiki/File:Droplets_on_a_maple_leaf_(Unsplash).jpg) | Sander Smeekes | CC0 |
| `bubble_clear.webp`, `bubble_rainbow.webp` | Rendered procedurally (thin-film colour, specular highlights); no source photo | this repo | n/a |

Licence status was read from each file's Commons page metadata when downloaded. Re-check the file page if you need to rely on it.

## lane: hero

- `hero-earth.webp`: NASA Blue Marble 2002 "Earth Western Hemisphere transparent background" (Wikimedia Commons, File:Earth_Western_Hemisphere_transparent_background.png), NASA Goddard / Reto Stockli, public domain. Resized to 720px, land channel tinted neon green, 1px alpha erode plus soft edge. Licence per Commons PD-USGov-NASA; not re-verified via the Commons API (rate limited).
- Dome skyline, meadow, frond, droplets, airliner and horizon skyline are original inline SVG/CSS, no external assets.
## lane: water

No new image files. The water, ice, drops, splash ribbons and daisies are SVG/CSS drawn in this repo; the hill and leaves reuse `meadow.webp` and `leaf.webp` (credited above).
## lane: animals

Background-removed with rembg `birefnet-general-lite` (clownfish stripe gaps closed by morphological closing), colour-graded (dolphin gradient-mapped to saturated blue, Moorish idol hue-shifted teal to yellow, clownfish stripes whitened), 1px light rim, WebP. High-res sources, downsized by CSS for retina.

| File here | Source file | Author | Licence |
|---|---|---|---|
| `aero_dolphin_leap.webp` | [HIHWNMS - Spinner Dolphin (28354954591).jpg](https://commons.wikimedia.org/wiki/File:HIHWNMS_-_Spinner_Dolphin_(28354954591).jpg) (dolphin only) | NOAA National Marine Sanctuaries | Public domain |
| `aero_clownfish_big.webp` | [Ocellaris clownfish bright.jpg](https://commons.wikimedia.org/wiki/File:Ocellaris_clownfish_bright.jpg) | Bruxton | CC0 |
| `aero_moorish_idol.webp` | [Zanclus cornutus 387908169.jpg](https://commons.wikimedia.org/wiki/File:Zanclus_cornutus_387908169.jpg) (left fish) | Andra Waagmeester | CC0 |
| `aero_goldfish.webp` | [Aquarium tropical de Pierrefitte-Nestalas 03082018 Carassius auratus Lionhead goldfish 2.jpg](https://commons.wikimedia.org/wiki/File:Aquarium_tropical_de_Pierrefitte-Nestalas_03082018_Carassius_auratus_Lionhead_goldfish_2.jpg) | see file page | CC0 |
