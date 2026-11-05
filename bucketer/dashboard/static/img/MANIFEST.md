# Image manifest

All WebP with alpha unless noted. Sizes are pixels (w x h).

| File | Size | What | Layout notes |
|---|---|---|---|
| aero_cloud_1.webp | 800x665 | tall shaded cumulus tower | hard-ish left/bottom crop edge fades; place with bottom partly behind hills/other clouds |
| aero_cloud_2.webp | 800x420 | soft white puffy cumulus | flat bottom (faded), float freely |
| aero_cloud_3.webp | 900x245 | long low cumulus bank | flat faded bottom |
| aero_cloud_4.webp | 900x514 | cumulus mass with wispy cirrus streaks, deep-blue-sky origin so shading is bluer | right edge is a straight crop edge; put it at the right viewport edge or behind something |
| aero_hill_far.webp | 3200x693 | rendered: hazy blue-green far ridge, tree-line speckle, sunlit rim | bottom-align, blade-detailed; ridge y~120-270 at this size (same silhouette as the old 2400x520); no tiling |
| aero_hill_mid.webp | 3200x693 | rendered: lit meadow slopes, multi-scale grass texture, hedgerows, tiny tree clusters, lime crest rim | bottom-align, blade-detailed; ridge y~100-390 at this size |
| aero_hill_near.webp | 3200x693 | rendered: deep green hill, individual grass blades along the whole crest and across the body | bottom-align, blade-detailed; ridge y~139-468 at this size; bottom row opaque |
| aero_plane.webp | 640x169 | Airbus A380 in climb attitude, nose up-left, tail right | livery painted out (unmarked white jet) |
| aero_skyline.webp | 1400x429 | glass towers, cyan tint | bottom-align; three separate groups with gaps; alpha solid inside silhouettes (opaque) |
| aero_water.webp | 512x512 | OPAQUE seamless tile, cyan ripples/caustics | `background-repeat: repeat` |
| aero_earth.webp | 600x600 | Blue Marble globe, circular alpha | add gloss overlay in CSS |
| aero_butterfly.webp | 700x502 | monarch, side view facing right | |
| aero_bird.webp | 560x540 | black tern in flight, wings spread, diving left | |
| aero_dolphin_leap.webp | 700x450 | spinner dolphin leaping, natural slate-grey grade (no gradient map; same orientation as before) | aspect 1.56 |
| aero_clownfish_big.webp | 700x413 | clownfish facing left | aspect 1.69 (was 1.71) |
| aero_moorish_idol.webp | 700x538 | Moorish idol, long dorsal filament now included, yellow | aspect 1.30 (was 1.17, old one cropped the filament) |
| aero_goldfish.webp | 700x521 | red-cap goldfish, long fins | aspect 1.34 (was 1.35) |

| aero_monitor.webp | 780x795 | photo of a flat-panel monitor (3/4 view), shell recoloured to the site blues, landscape photo on screen | stacks exactly with aero_monitor_water.webp; screen quad on canvas about (123,276) (542,271) (549,619) (131,638) |
| aero_monitor_water.webp | 780x795 | real wave-spray photo keyed to white water, erupting from the screen's bottom centre up and to the right | same canvas as aero_monitor.webp; the fish goes between the two |
