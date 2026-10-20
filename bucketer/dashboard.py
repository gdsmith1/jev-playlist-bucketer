"""Genre dashboard: turns the Last.fm tags gathered for a run into one self-contained HTML page.

Helps pick buckets (common tag clusters) and spot outliers (albums that fit none of them). No jev involved.
"""

import json
import os
from typing import Callable

from .models import Enrichment, Group

# Wide umbrella tags: shown in Top tags (dimmed) but never suggested as buckets, never used for clustering or outlier fit. Edit freely.
UMBRELLA_TAGS = frozenset({"rock", "pop", "alternative", "alternative rock", "indie", "metal", "electronic", "instrumental", "folk"})
HEAT_TAGS = 24  # tags in the overlap matrix
TOP_TAGS = 40  # tags considered for clusters, heatmap and descriptions
MIN_WEIGHT = 0.15  # a tag only counts for an album above this share of its top tag
JOIN_SIMILARITY = 0.25  # Jaccard needed for a tag to join an existing cluster instead of seeding its own
MAX_CLUSTERS = 12
OUTLIER_FIT = 0.3  # an album is an outlier when less than this share of its tag weight lands in its best cluster
EXAMPLES_PER_CLUSTER = 6
COVERS_PER_CLUSTER = 5
UNCOUNTED_WEIGHT = 0.5  # weight for a tag that came without a count


def album_tags(enrichment: Enrichment) -> dict[str, float]:
    """Tag name -> weight (0-1) for one album, best of album-level and artist-level, weak tags dropped."""
    weights: dict[str, float] = {}
    for tags in (enrichment.album_tags, enrichment.artist_tags):
        for tag in tags or []:
            w = (tag.get("count") or 0) / 100 or UNCOUNTED_WEIGHT
            weights[tag["name"]] = max(weights.get(tag["name"], 0.0), min(w, 1.0))
    return {name: w for name, w in weights.items() if w >= MIN_WEIGHT}


def _jaccard(a: set[int], b: set[int]) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def analyze(pairs: list[tuple[Group, Enrichment]]) -> dict:
    albums = []
    for group, enrichment in pairs:
        albums.append({"artist": group.artist, "album": group.album, "songs": len(group.rows), "tags": album_tags(enrichment),
                       "similar": list(enrichment.similar_artists), "cover": enrichment.cover or ""})

    members: dict[str, set[int]] = {}  # tag -> indexes of albums carrying it
    for i, a in enumerate(albums):
        for tag in a["tags"]:
            members.setdefault(tag, set()).add(i)
    songs_of = lambda idx: sum(albums[i]["songs"] for i in idx)  # noqa: E731
    ranked = sorted(members, key=lambda t: (-songs_of(members[t]), -len(members[t]), t))
    top = [t for t in ranked if t not in UMBRELLA_TAGS][:TOP_TAGS]  # bucket candidates
    keep = set(top) | set(ranked[:TOP_TAGS])
    shown = [t for t in ranked if t in keep]  # Top tags chart also keeps umbrella tags

    tag_stats = [{"tag": t, "albums": len(members[t]), "songs": songs_of(members[t]), "umbrella": t in UMBRELLA_TAGS} for t in shown]
    heat_tags = top[:HEAT_TAGS]
    heat = [[round(_jaccard(members[x], members[y]), 3) for y in heat_tags] for x in heat_tags]

    # Greedy clustering: walk tags by popularity; join the most similar existing seed or become a new one.
    clusters: list[dict] = []
    for tag in top:
        best, best_sim = None, 0.0
        for c in clusters:
            sim = _jaccard(members[tag], members[c["seed"]])
            if sim > best_sim:
                best, best_sim = c, sim
        if best is not None and best_sim >= JOIN_SIMILARITY:
            best["tags"].append(tag)
        elif len(clusters) < MAX_CLUSTERS:
            clusters.append({"seed": tag, "tags": [tag]})
        elif best is not None:
            best["tags"].append(tag)

    for c in clusters:
        tagset = set(c["tags"])
        affinity = {i: sum(w for t, w in a["tags"].items() if t in tagset) for i, a in enumerate(albums)}
        mine = {i for i, v in affinity.items() if v > 0}
        c["albums"], c["songs"] = len(mine), songs_of(mine)
        c["examples"] = [f"{albums[i]['artist']}" for i in sorted(mine, key=lambda i: -affinity[i])][:EXAMPLES_PER_CLUSTER]
        c["examples"] = list(dict.fromkeys(c["examples"]))
        ordered = sorted(mine, key=lambda i: (-affinity[i], -albums[i]["songs"]))
        c["covers"] = [{"url": albums[i]["cover"], "title": f"{albums[i]['artist']} - {albums[i]['album']}"} for i in ordered if albums[i]["cover"]][:COVERS_PER_CLUSTER]
    clusters.sort(key=lambda c: -c["songs"])

    outliers = []
    for a in albums:
        specific = {t: w for t, w in a["tags"].items() if t not in UMBRELLA_TAGS}
        total = sum(specific.values())
        fits = [(sum(w for t, w in specific.items() if t in c["tags"]) / total if total else 0.0, c["seed"]) for c in clusters]
        fit, nearest = max(fits, default=(0.0, None))
        if total == 0 or fit < OUTLIER_FIT:
            outliers.append({"artist": a["artist"], "album": a["album"], "songs": a["songs"], "reason": ("untagged" if not a["tags"] else "only umbrella tags") if total == 0 else "no cluster fits",
                             "cover": a["cover"], "fit": round(fit, 2), "nearest": nearest if fit > 0 else None,
                             "tags": sorted(specific or a["tags"], key=lambda t: -a["tags"][t])[:6], "similar": a["similar"]})
    outliers.sort(key=lambda o: (o["fit"], -o["songs"]))

    total_songs = sum(a["songs"] for a in albums)
    return {"albums": len(albums), "songs": total_songs, "tags": tag_stats, "heat_tags": heat_tags, "heat": heat, "clusters": clusters, "outliers": outliers,
            "outlier_songs": sum(o["songs"] for o in outliers)}


def render(analysis: dict, tag_info: dict[str, dict]) -> str:
    data = json.dumps({**analysis, "info": tag_info}, ensure_ascii=False).replace("</", "<\\/")
    return PAGE.replace("/*DATA*/null", data)


def write_dashboard(run_dir: str, pairs: list[tuple[Group, Enrichment]], tag_info: Callable[[str], dict | None]) -> str:
    analysis = analyze(pairs)
    info = {}
    for row in analysis["tags"]:
        found = tag_info(row["tag"])
        if found and found.get("summary"):
            info[row["tag"]] = {"summary": found["summary"], "reach": found.get("reach", 0)}
    path = os.path.join(run_dir, "dashboard.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(render(analysis, info))
    return path


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Genre Dashboard</title>
<style>
:root{--bg:#272822;--panel:#2f302a;--line:#49483e;--fg:#f8f8f2;--muted:#75715e;--pink:#f92672;--green:#a6e22e;--blue:#66d9ef;--orange:#fd971f;--purple:#ae81ff;--yellow:#e6db74}
*{box-sizing:border-box}body{margin:0;padding:0 16px 48px;background:var(--bg);color:var(--fg);font:14px/1.5 ui-monospace,Menlo,Consolas,monospace}
main{max-width:1100px;margin:0 auto}h1{color:var(--green);font-size:20px;margin:24px 0 4px}h2{color:var(--pink);font-size:16px;margin:32px 0 8px}
.sub{color:var(--muted)}.stats{display:flex;flex-wrap:wrap;gap:12px;margin:16px 0}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:8px 14px}.stat b{display:block;color:var(--yellow);font-size:20px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.card{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--c);border-radius:6px;padding:12px}
.card h3{margin:0 0 4px;color:var(--c);font-size:15px}.chip{display:inline-block;margin:2px 4px 2px 0;padding:0 8px;border:1px solid var(--line);border-radius:10px;color:var(--blue);cursor:pointer;background:none;font:inherit}
.chip:hover,.chip:focus{border-color:var(--blue);outline:none}.ex{color:var(--muted);margin-top:6px}
.bar{display:grid;grid-template-columns:140px 1fr 80px;gap:8px;align-items:center;margin:2px 0}.bar .t{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;cursor:pointer;color:var(--blue)}
.bar .fill{height:12px;background:var(--orange);border-radius:2px}.bar .n{color:var(--muted);text-align:right}
.scroll{overflow:auto;border:1px solid var(--line);border-radius:6px}table{border-collapse:collapse;width:100%}
th,td{padding:4px 8px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--yellow);cursor:pointer;position:sticky;top:0;background:var(--panel)}
input{background:var(--panel);border:1px solid var(--line);color:var(--fg);padding:6px 10px;border-radius:6px;font:inherit;width:100%;max-width:320px;margin-bottom:8px}
#detail{position:sticky;bottom:8px;background:var(--panel);border:1px solid var(--blue);border-radius:6px;padding:10px 14px;margin-top:16px;display:none}
#detail b{color:var(--blue)}.heat{display:grid;gap:1px;font-size:10px}.heat div{aspect-ratio:1;background:var(--purple)}.legend{color:var(--muted);margin-top:4px}
.thumbs{display:flex;gap:4px;margin:8px 0 2px}.thumbs img,.ph{width:48px;height:48px;border-radius:3px;object-fit:cover;background:var(--line)}
.ph{display:inline-flex;align-items:center;justify-content:center;color:var(--muted);font-size:18px}.cv{width:40px;padding-right:0}.cv img,.cv .ph{width:40px;height:40px}
.bar.umb{opacity:.45}.bar.umb .t::after{content:" (umbrella)";color:var(--muted)}
table.hm{border-collapse:separate;border-spacing:1px;width:auto}table.hm th{position:static;background:none;font-weight:400;color:var(--blue);padding:0 4px;white-space:nowrap;border:0}
table.hm thead th{writing-mode:vertical-rl;transform:rotate(180deg);height:170px;text-align:left;vertical-align:bottom}
table.hm td{width:24px;height:24px;min-width:24px;padding:0;border:0;text-align:center;font-size:9px;color:var(--bg);background:rgba(174,129,255,var(--a))}
table.hm td.self{background:var(--line)}table.hm th.rh{text-align:right;position:sticky;left:0;background:var(--bg)}
</style></head><body><main>
<h1>Genre Dashboard</h1><div class="sub">Built from Last.fm tags; no jev involved. Click any tag for its Last.fm description (when it has one).</div>
<div class="stats" id="stats"></div>
<h2>Suggested buckets</h2><div class="sub">Tags that tend to appear on the same albums, biggest first. A starting point, not a final answer.</div><div class="cards" id="clusters"></div>
<h2>Top tags</h2><div id="tags"></div>
<h2>Tag overlap</h2><div class="sub">Share of albums two tags have in common (Jaccard, shown as a percentage in each cell; brighter = more overlap). Umbrella tags are left out.</div>
<div class="scroll" style="padding:8px"><table class="hm" id="heat"></table></div><div class="legend" id="heatlegend"></div>
<h2>Outliers</h2><div class="sub">Albums where under 30% of the tag weight lands in any suggested bucket, plus untagged albums.</div>
<input id="q" placeholder="filter artist, album or tag" aria-label="filter outliers">
<div class="scroll"><table><thead><tr id="oh"></tr></thead><tbody id="ob"></tbody></table></div>
<div id="detail"></div>
<script>
const D=/*DATA*/null;const COLORS=["#a6e22e","#66d9ef","#f92672","#fd971f","#ae81ff","#e6db74"];
const $=id=>document.getElementById(id);
function el(tag,props,...kids){const e=document.createElement(tag);Object.assign(e,props||{});kids.forEach(k=>e.append(k));return e}
function show(tag){const i=D.info[tag];const d=$("detail");d.style.display="block";d.replaceChildren(el("b",{},tag),i?el("span",{}," ("+i.reach.toLocaleString()+" listeners) "+i.summary):el("span",{className:"sub"}," no description on Last.fm"))}
function art(url,title,cls){if(!url)return el("span",{className:"ph",textContent:"♪",title:title||"no cover on Last.fm"});
 const i=el("img",{src:url,alt:title||"",title:title||"",loading:"lazy",referrerPolicy:"no-referrer"});i.onerror=()=>i.replaceWith(el("span",{className:"ph",textContent:"♪",title:"cover failed to load"}));return i}
function chip(t){return el("button",{className:"chip",textContent:t,onclick:()=>show(t),title:D.info[t]?D.info[t].summary:""})}
[["albums",D.albums],["songs",D.songs],["outlier albums",D.outliers.length],["outlier songs",D.outlier_songs],["suggested buckets",D.clusters.length]]
 .forEach(([k,v])=>$("stats").append(el("div",{className:"stat"},el("b",{textContent:v}),k)));
D.clusters.forEach((c,i)=>{const card=el("div",{className:"card"},el("h3",{textContent:c.seed}),el("div",{className:"sub",textContent:c.albums+" albums · "+c.songs+" songs"}));
 card.style.setProperty("--c",COLORS[i%COLORS.length]);c.tags.forEach(t=>card.append(chip(t)));if(c.covers.length)card.append(el("div",{className:"thumbs"},...c.covers.map(v=>art(v.url,v.title))));card.append(el("div",{className:"ex",textContent:"e.g. "+c.examples.join(", ")}));$("clusters").append(card)});
const max=Math.max(1,...D.tags.map(t=>t.songs));
D.tags.forEach(t=>{const f=el("div",{className:"fill"});f.style.width=(100*t.songs/max)+"%";$("tags").append(el("div",{className:"bar"+(t.umbrella?" umb":"")},el("span",{className:"t",textContent:t.tag,onclick:()=>show(t.tag)}),el("div",{},f),el("span",{className:"n",textContent:t.songs+" songs"})))});
const HT=D.heat_tags;const peak=Math.max(0.01,...D.heat.flatMap((r,x)=>r.filter((v,y)=>x!=y)));
{const hm=$("heat");const head=el("tr",{},el("th"));HT.forEach(t=>head.append(el("th",{textContent:t,onclick:()=>show(t)})));hm.append(el("thead",{},head));
 const body=el("tbody");D.heat.forEach((row,x)=>{const tr=el("tr",{},el("th",{className:"rh",textContent:HT[x],onclick:()=>show(HT[x])}));
  row.forEach((v,y)=>{const td=el("td",{title:HT[x]+" × "+HT[y]+": "+Math.round(v*100)+"% of albums in common",textContent:x!=y&&v>=0.05?Math.round(v*100):""});
   if(x==y)td.className="self";else td.style.setProperty("--a",Math.max(0.05,v/peak).toFixed(2));tr.append(td)});body.append(tr)});hm.append(body)}
$("heatlegend").textContent="Hover a cell for the tag pair; click a tag name for its description.";
let sortKey="fit",asc=true;const cols=[["cover",""],["artist","artist"],["album","album"],["songs","songs"],["reason","reason"],["fit","fit"],["nearest","nearest bucket"],["tags","tags"]];
function draw(){const q=$("q").value.toLowerCase();const rows=D.outliers.filter(o=>(o.artist+" "+o.album+" "+o.tags.join(" ")).toLowerCase().includes(q))
 .sort((a,b)=>{const x=a[sortKey],y=b[sortKey];const r=typeof x=="number"?x-y:String(x).localeCompare(String(y));return asc?r:-r});
 $("oh").replaceChildren(...cols.map(([k,l])=>el("th",{textContent:l+(sortKey==k?(asc?" ▲":" ▼"):""),onclick:()=>{asc=sortKey==k?!asc:true;sortKey=k;draw()}})));
 $("ob").replaceChildren(...rows.map(o=>{const tr=el("tr");[o.cover,o.artist,o.album,o.songs,o.reason,o.fit,o.nearest||"",""].forEach((v,i)=>tr.append(i==0?el("td",{className:"cv"},art(v,o.artist+" - "+o.album)):i==7?el("td",{},...o.tags.map(chip)):el("td",{textContent:v})));return tr}))}
$("q").oninput=draw;draw();
</script></main></body></html>
"""
