# Is jev still worth it? Tag clustering vs jev scoring

Recommendation: **hybrid, provisionally.** Let the tag clustering propose buckets and do the cheap bulk assignment, and keep jev as the judge for the albums the tags cannot settle. The evidence is thin (see Limits): it supports "jev is not redundant" and "tags alone are not enough", not a measured accuracy. Do not drop jev, and do not make it the only path either.

## Limits of this evidence (read first)

| Fact | Consequence |
|---|---|
| `jev_cache.json` holds only **10 paid-for albums**, not the seed-7 sample. Only 4 of them are in the seed-7 sample (266 albums). | The comparison is 10 albums x 12 buckets. Treat every rate as an anecdote, not a measurement. |
| 6 of the 10 cache entries no longer match the current `format_for_jev` text/tag cache (the cache key changed after tag filtering moved on). I matched them by their stored `label` (album key) instead. | Those 6 scores were produced from slightly different tags than I compared against. The cache also stores no record of which buckets were asked; the 12 score keys do equal the current non-`other` buckets in `buckets.json`. |
| Mapping jev buckets to tag sets was done by hand (list in the scratchpad script, not committed). | Results depend on that mapping. `alternative_rock` is mostly umbrella tags, which the dashboard never clusters, so I scored it on all tags. |
| No token or cost data exists in the repo (`jev.usage` is only printed). | Cost cannot be answered from existing data (see Cost). |

## Method

1. Rebuilt each album's tags from `lastfm_cache.json` only (no network), using the dashboard's own `album_tags` weights (album and artist tags merged, weights under 0.15 dropped).
2. jev assignment: score >= 1.0 (project default) and, for context, >= 0.5. Scores run 0-2 (three levels).
3. Tag-only assignment: **fit** = share of the album's non-umbrella tag weight that lands in the hand-mapped tag set for that bucket (same definition as the dashboard outlier fit), assigned at >= 0.3 (the dashboard's `OUTLIER_FIT`), also tried at 0.2 and 0.4, plus a "strongest matching tag weight >= 0.5" rule.
4. Also ran the current `analyze()` clustering on the seed-7 sample and the full cached playlist (2,855 albums, 8,763 songs) to see what clustering can and cannot express.

## Agreement (10 albums x 12 buckets = 120 yes/no pairs)

| jev threshold | tag rule | albums with identical bucket set | pairs agreeing | both yes | tag-only yes | jev-only yes |
|---|---|---|---|---|---|---|
| 1.0 | fit >= 0.3 | 6/10 | 116/120 | 3 | 4 | 0 |
| 1.0 | fit >= 0.2 | 3/10 | 113/120 | 3 | 7 | 0 |
| 1.0 | fit >= 0.4 | 7/10 | 117/120 | 3 | 3 | 0 |
| 1.0 | max tag weight >= 0.5 | 7/10 | 116/120 | 3 | 4 | 0 |
| 0.5 | fit >= 0.3 | 3/10 | 108/120 | 6 | 1 | 11 |
| 0.5 | fit >= 0.2 | 2/10 | 107/120 | 7 | 3 | 10 |

Pair agreement is inflated by the many "no" pairs; the album-set column is the honest one. Correlation of jev score with tag fit over all 120 pairs: Pearson 0.76, Spearman 0.50 (the strongest agreement is on the albums that clearly belong; the middle of the scale is noisy). The top bucket matches for 6 of 10 albums.

Two things stand out. At the project threshold of 1.0 jev assigns only **3 of 10** albums to any bucket (7 go to `other`), so jev is much stricter than tags; a tag rule at 0.3 assigns 6 of 10. And at 1.0 jev never assigns something the tags miss, but jev at 0.5 assigns many more than tags (11 jev-only pairs).

## Disagreements by cause

| Cause | Albums | What happened | Who is right |
|---|---|---|---|
| Genre-defining album, misleading or generic tags | Mastodon *Stairway to Nick John* (no album tags; artist tags `progressive metal`, `sludge`) | Tag rule puts it in stoner/sludge (fit 0.44). jev spreads 0.9 / 0.87 / 0.59 / 0.56 over stoner, death-thrash, post-metal, alt-metal and assigns none at 1.0. | Debatable. Tags are crisp but the only bucket they can reach is the sludge one; jev correctly sees it spans several buckets. |
| Tags too generic to land in a bucket | Mew *And the Glass Handed Kites* (`indie rock`, `indie`, `danish`) | Both choose `alternative_rock` (fit 0.67, jev 1.22). jev also gives post-punk 0.62 and post-rock 0.49 that tags cannot see. | Agree on the main call. jev adds secondary labels. |
| Tags point at the wrong bucket | David Bowie *Reality* (`glam rock`, `rock`, `classic rock`) | Tag rule says `classic_hard_rock_metal` (fit 0.33, driven only by `classic rock`). jev gives it nothing above 0.56 and rejects the metal bucket (not in its scores). | jev. A hard-rock bucket pulled in a glam/art-rock album purely through the tag `classic rock`. |
| Few/wrong-kind tags, bucket defined by a description | Soulwax *Much Against Everyone's Advice* (`electronic`, `alternative`, `indie`; all umbrella) | Tag rule: `alternative_rock` (fit 0.42). jev: industrial/electronic 0.95, alt rock 0.82, post-punk 0.58; none at 1.0. | Unclear. jev reads `electro` and `dance` artist tags and "similar artists" (Justice, Simian Mobile Disco) and ranks electronic first; tags rank it by an umbrella. |
| Artist-only tags (album not found on Last.fm) | Giraffes? Giraffes! *Death Breath*; Mondo Generator *Shooter's Bible* | Mondo: both agree (stoner, fit 0.75, jev 1.99, the cleanest case). Giraffes: tags (`math rock`, `post-rock` at 0.24) give fit 0.16, below any threshold; jev 0.94 for post-metal/post-rock. | jev, mildly. Tag fit is diluted by `math rock`, which is not in the post-metal set; jev reads it as the same neighbourhood. |
| No bucket exists for it | Johnny Cash *American IV*, Sublime *Sublime* | Both leave them out (jev all <= 0.48; fit < 0.3). | Agree. |
| Multi-label | Power Trip *Manifest Decimation* (`thrash metal`, `hardcore`, `crossover`) | Tag rule: death-thrash 0.54 and punk-hardcore 0.46 (both assigned). jev: death-thrash 1.8, punk 0.79 (only the first at 1.0). | Tags give a defensible two-bucket answer; jev's threshold forces one. |
| Slint *Tweez* | `noise rock`, `post-rock`, `math rock`, `post-hardcore` | Fit 0.28 for post-metal (just under 0.3). jev puts post-punk top (0.78), post-metal 0.58; none at 1.0. | Neither confident; the bucket set has no post-hardcore/math-rock bucket. |

What the 10 albums cannot test: description-defined buckets ("in the vein of", `soundtrack_game_score`, which no sampled album matches), and untagged albums (only 6 of 2,855 albums have no tags at all, 483 lack album-level tags, 104 have two or fewer usable tags). Both are untested here, not shown to be fine.

## What clustering can and cannot do (full cached playlist)

- The current `analyze()` yields 12 clusters on both the sample and the full playlist (cap `MAX_CLUSTERS`), mostly with crisp tag names: hard rock, indie rock, progressive rock, new wave, heavy metal, alternative metal, progressive metal, stoner rock, punk, grunge, hardcore, death metal.
- Outliers: 34 of 266 albums (37 songs) in the sample; 514 of 2,855 albums (1,258 songs, 14% of songs) in the full playlist.
- Using the hand-mapped buckets with fit >= 0.3 on the full playlist, songs by number of buckets matched: 0 buckets 1,446 (16.5%), 1 bucket 5,317 (60.7%), 2 buckets 1,896 (21.6%), 3 buckets 104 (1.2%). So tags alone leave one song in six unplaced and one in four in several buckets.
- Clusters are tag co-occurrence groups, not musical definitions. The user's buckets in `buckets.json` are partly descriptions ("detuned riffs and melodic-to-aggressive vocal shifts", "music composed for a film or game rather than a standalone artist release"). Tags cannot express those, and umbrella tags (`alternative rock`, `indie`) are excluded from clustering by design, so an `alternative_rock` style bucket cannot come from the clustering at all.

## Does jev score correlate with tag fit?

Yes, moderately (Pearson 0.76, Spearman 0.50 on 120 pairs). The strongest jev scores (Mondo Generator 1.99, Power Trip 1.8, Mew 1.22) are exactly the albums with the highest tag fit (0.75, 0.54, 0.67). Where they diverge (Bowie, Soulwax, Slint, Mastodon) jev either withholds a call or uses information tags do not carry (similar artists, release context, description match). With n=10 do not read more into it.

## Hybrid: what jev adds

In the design "clustering proposes buckets, the user ticks, jev assigns", jev's value, as far as 10 albums show:

1. It can say "none of these" (Cash, Bowie, Sublime) where a tag rule produces a false positive from a single generic tag (Bowie via `classic rock`).
2. It handles secondary or fuzzy membership with a graded score (Mew, Soulwax, Mastodon) where tags give all-or-nothing.
3. It can use evidence beyond the tag share (similar artists, album-vs-artist, year) and a bucket's written description. That matters most once the user ticks a suggested bucket that is a tag cluster turned into a description by a fixed template (the checkpoint step); jev then judges against "tagged X, Y, Z, in the vein of A, B, C", not against a tag set.
4. It costs money and is stricter: at threshold 1.0 it assigned 3 of 10 albums. In a hybrid that threshold needs re-tuning (or `other` will swallow most of the playlist).

What clustering adds on top of jev: it picks the bucket set from the library itself and gives a free, instant first pass, which already gets 6 of 10 albums to the same bucket set as jev at the project threshold.

## Recommendation

- **Keep jev, as the assignment step in the hybrid.** Replace is not supported: tag-only misassigns on generic or single-tag evidence (Bowie), cannot express description-defined buckets, and leaves 16.5% of songs unplaced with the hand mapping.
- **Build the two-pass flow and bucket selection.** They are worth it either way.
- Optional cost saver for 11c, to test before relying on it: skip jev for albums where the tag fit is already very high and unambiguous (for example fit >= 0.7 in one bucket, such as Mondo Generator at 0.75) and send only the middle and the no-fit albums. On the 10 albums this would have skipped 1 call; it needs more data to know whether it is safe.
- Re-check the default threshold of 1.0: it produced 7 of 10 `other` here.

## Cost (step 5, not run)

Known: one jev call per album; all buckets are questions in the same call; a 300-song sample is about 270 calls; the SDK response exposes `usage.input_tokens/output_tokens` and `JevClient.usage` accumulates them, but nothing is stored in the repo or the cache, so tokens per call and price are **unknown**. Prompt and output size should grow roughly linearly with the bucket count (each bucket adds an instruction string plus three level strings to the input and a score plus confidence to the output), so 30 buckets is about 2.5x the question payload of 12; the fixed album text (<= 600 characters) does not grow. The fixed overhead of the SDK or model prompt is unknown, so the real multiplier could be lower.

A small approved run would need:
- Owner approval and `TYPESAFE_API_KEY`.
- Run A: 12 current buckets over about 40 albums, chosen to cover what the 10 cached albums could not test (several untagged or artist-only albums, a `soundtrack_game_score` candidate, a few high-fit "easy" albums, a few two-cluster albums), fresh `--jev-cache` path so nothing is overwritten. Record `usage` from the run summary (calls, input and output tokens).
- Run B: the same 10 albums with a 30-bucket `--buckets` file (suggested clusters turned into descriptions) to measure the tokens-per-call slope. 10 calls are enough for a ratio.
- Price per token from the owner's jev plan, since the repo does not record it. With these two runs the cost of the full 2,855-album playlist (about 2,800 calls) at 12 and at 30 buckets can be computed.
- Because the cache key is only the album text hash, use a separate cache file for run B or it will return the 12-bucket scores.
