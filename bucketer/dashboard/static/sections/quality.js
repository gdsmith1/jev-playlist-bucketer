(()=>{const Q=D.quality,pct=(n,of)=>of?Math.round(100*n/of)+"%":"0%";
 const h=el("h2",{textContent:"Data quality"}),sub=el("div",{className:"sub",textContent:"How well Last.fm covered the playlist. Albums with only artist-level tags carry the weakest signal."});
 const tiles=el("div",{className:"stats"});
 [["album-level tags",Q.album_level],["artist tags only",Q.artist_only],["no tags at all",Q.untagged],["no cover",Q.no_cover]].forEach(([k,v])=>
  tiles.append(el("div",{className:"stat"},el("b",{textContent:v.albums+" ("+pct(v.albums,Q.total.albums)+")"}),k,el("div",{className:"sub",textContent:v.songs+" songs, "+pct(v.songs,Q.total.songs)}))));
 const rows=Q.artist_only_list,body=el("tbody");
 rows.forEach(r=>body.append(el("tr",{},el("td",{className:"cv"},art(r.cover,r.artist+" - "+r.album)),el("td",{textContent:r.artist}),el("td",{textContent:r.album}),el("td",{textContent:r.songs}),el("td",{},...r.tags.map(chip)))));
 const more=Q.artist_only.albums-rows.length;
 const det=el("details",{},el("summary",{textContent:"Albums relying only on artist tags ("+Q.artist_only.albums+")"}),
  el("div",{className:"scroll qlist"},el("table",{},el("thead",{},el("tr",{},...["","artist","album","songs","artist tags"].map(t=>el("th",{textContent:t})))),body)),
  more>0?el("div",{className:"sub",textContent:"+"+more+" more with fewer songs"}):"");
 $("detail").before(h,sub,tiles,det)})();
