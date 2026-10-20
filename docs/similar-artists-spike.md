# Similar-artists spike

Question: does Last.fm `artist.getSimilar` add anything the tag clusters do not?

## Method

- Fetched `artist.getSimilar` (limit 30, `match` kept) for all 992 cached artists on a copy of `lastfm_cache.json`: 991 calls, 0 errors, one artist unknown. The throttle allows 4 calls/s but the API latency made it about 1.5 calls/s, so a cold run takes about 11 minutes, not 4.
- Analysed the full cached playlist (2855 albums, 12 suggested buckets, 300 outlier rows) with the current `analyze`.
- "In playlist" = the neighbour is also an artist in the run. Bucket of an artist = the best cluster of its non-outlier albums.

## Findings

| Question | Result |
|---|---|
| Neighbours in the playlist per artist | top 30: 9.9 on average, 944 of 992 artists have at least one. The 5 already stored: 1.9, 763 of 992 |
| Is the signal consistent with tags? A neighbour vote (weighted by `match`) reproduces an artist's own best tag cluster | 83% over 737 artists with the 30 list, 80% with the stored 5. Majority-cluster baseline is 15%. So similar artists agree with tags, they do not contradict them |
| Outlier artists with at least one in-playlist neighbour | 239 of 300 rows with 30, 142 with 5 |
| Outlier artists linked (match >= 0.3) to another outlier | 219 of 292 |

What it adds:

1. **Placing outliers.** Most outliers are "no tag in a suggested bucket", where tags say nothing. Neighbours give a direction for 80% of them. Caveat: the vote favours big buckets (it mostly answers "grunge" or "indie rock"), so it is a hint, not an assignment.
2. **Missing buckets.** Linking outliers to each other finds coherent groups the 12-cluster cap leaves out: 15 garage/psych-punk artists (Ty Segall, Thee Oh Sees, Wavves, Fuzz, FIDLAR), 2-tone ska (Madness, The Specials, The Beat, UB40), rockabilly/swing (Reverend Horton Heat, Stray Cats, Squirrel Nut Zippers), trip-hop (Tricky, Sneaker Pimps), synthwave (Kavinsky, Perturbator, Carpenter Brut), plus one 158-artist blob of 90s alt/pop rock that is too connected to be useful. Tag clustering with more clusters may find several of these on its own, so this is evidence rather than a new capability.
3. **Artists you do not have.** The outliers' most recommended non-playlist artists are The Verve Pipe, The Wallflowers, Hootie & The Blowfish, Sister Hazel, Vertical Horizon, Spin Doctors: a coherent 90s radio post-grunge group. That is new information tags cannot give, but it is a discovery feature, not a bucketing one.

What it does not add: the top-5 list already stored gives 80% agreement against 83%, and the per-album tag fit is still the primary signal. Similar artists do not help albums by artists with no Last.fm data (none in this playlist).

## Recommendation

Modest but real value, cheap to keep. Built the small version only: no graph. A "Similar to your outliers" section (`sections/similar.js`, `bucketer/dashboard/similar.py`) lists each outlier artist's in-playlist neighbours, the bucket they lean to, and neighbours not in the playlist, plus the most recommended missing artists. Grouping outliers into candidate buckets stays out of scope.

## Cache and flag

- `artist` entries gain `extras.similar_full`: `[{name, match}]`, up to 30. Older entries are upgraded lazily; `[]` means Last.fm knows no similar artists; errors are never cached; `extras.similar_artists` (the 5 sent to jev) is untouched, so jev cache keys do not change.
- Only `--similar` makes the extra calls (one per artist without `similar_full`). Without it the dashboard uses whatever is cached.
