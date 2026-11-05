# Image credits

The dashboard scenery is photographic cutouts from Wikimedia Commons (public domain, CC0 or US-government works) plus the original inline SVG/CSS (bubbles, compass, monitor, etc.). Every file below was licence-checked via the Commons API (`extmetadata`) before use. No CC-BY or CC-BY-SA material is used, so no attribution is legally required, but authors are listed. Processing: background removal with rembg (`isnet-general-use`, `birefnet-general-lite` for the Moorish idol) or colour/luminance keying with smooth ramps, 1px alpha erosion + feather, colour grading (saturation/contrast, gradient map or hue shift), optional 1px light rim on wildlife, WebP (q70-85). Commons file page = `https://commons.wikimedia.org/wiki/File:<name>`.

| File here | Source file | Author | Licence | Processing |
|---|---|---|---|---|
| `aero_dolphin_leap.webp` | HIHWNMS - Spinner Dolphin (28354954591).jpg (dolphin only) | NOAA National Marine Sanctuaries | Public domain | rembg (isnet-general-use), alpha cleaned, mild natural grade (lifted shadows, slight cool tint), no blue gradient map |
| `aero_clownfish_big.webp` | Ocellaris clownfish bright.jpg | Bruxton | CC0 | rembg, coral removed, stripes whitened |
| `aero_moorish_idol.webp` | Zanclus cornutus 387908169.jpg (left fish) | Andra Waagmeester | CC0 | rembg, hue-shifted teal to yellow, stripes darkened |
| `aero_goldfish.webp` | Aquarium tropical de Pierrefitte-Nestalas 03082018 Carassius auratus Lionhead goldfish 2.jpg | Vassil | CC0 1.0 | rembg, mild grade |
| `aero_cloud_1.webp`, `aero_cloud_4.webp` | Cumulus congestus clouds (27075262952).jpg | HO JJ (Taipei) | CC0 | saturation keying, whitened, blue-grey underside; all four cloud files unsharp-masked + contrast boost (ImageMagick) |
| `aero_cloud_2.webp`, `aero_cloud_3.webp` | Sea sky and clouds, Ibiza, Spain.jpg | Joselodos | CC0 | saturation keying, soft underside |
| `aero_hill_far.webp`, `aero_hill_mid.webp`, `aero_hill_near.webp` | none (generated) | n/a | n/a | generated procedurally (numpy/scipy/Pillow), no third-party imagery; 2x supersampled, blades drawn as tapered polygons |
| `aero_plane.webp` | A6-EDK Emirates Airbus A380-861 - cn 030 takeoff from Schiphol runway 36C pic3.JPG | Alf van Beem | Public domain | rembg, slight contrast/saturation boost; livery painted out with ImageMagick (fuselage lettering, engine logos replaced by a fuselage-tone gradient, tail stripes and red cheatline desaturated) so it reads as an unmarked jet |
| `aero_skyline.webp` | Skyscrapers by railway station (Unsplash).jpg | Tony Yeung (tkwyoung) | CC0 | sky keyed, cyan tint, alpha made solid (opaque towers) |
| `aero_water.webp` | Dalyan water 2019 G1.jpg | George Chernilevsky | Public domain | cropped, offset-blended to tile, graded to #0090d0..#00b8e6 |
| `aero_earth.webp` | Blue Marble Western Hemisphere.jpg | NASA / Reto Stöckli (Terra MODIS) | Public domain | circular mask, shadow lift, saturation boost |
| `aero_butterfly.webp` | Monarch Butterfly.(Danaus plexippus) (14256022010).jpg | Bernard Spragg | CC0 | rembg, saturation boost |
| `aero_bird.webp` | Black Tern flying (7402338502).jpg (a tern, not a gull) | U.S. Fish and Wildlife Service, Northeast Region | Public domain | rembg |
| `aero_monitor.webp` | Computer monitor remix transparent.png (derivative of Computer_monitor.jpg); screen replaced by a warped crop of Spring time in the Hill country brings on wild flowers and green grass. (24486794213).jpg | Zzubnik, derivative by AGreuet (monitor); USDA NRCS Texas (landscape) | Public domain / Public domain | shell recoloured with a navy-cobalt-aqua-white luminance ramp to match the site; landscape greens hue-shifted to lime, red flowers to yellow; perspective-warped onto the panel with inner shadow and glare; 0.45x resize |
| `aero_monitor_water.webp` | Wave splash in Brofjorden at Lahälla 3.jpg | W.carter | CC0 | white spray keyed by whiteness (min channel, low saturation) so rocks and sea drop out, cropped to the eruption, rotated 22 degrees about its base, tinted slightly aqua over a soft cyan underlay, placed at the screen's bottom centre |
