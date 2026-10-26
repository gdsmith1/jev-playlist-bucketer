{const host=$("panel-playlist"),J=D.jev,recs=D.album_records,rows=D.song_rows,perAlbum=D.song_rows_per_album,NONE=J?"other":"no bucket",UNTAGGED="untagged",PAGE_SONGS=100;
 const bucketsOf=s=>{const r=recs[s.g];return J?(r.jev.matched.length?r.jev.matched:[NONE]):(r.best_cluster?[r.best_cluster]:[NONE])};
 const topScore=s=>{const r=recs[s.g];return J?Math.max(...Object.values(r.jev.scores),0):(r.best_cluster?r.cluster_fits[r.best_cluster]:0)};
 const tagLine=r=>r.tags.slice(0,3).map(t=>t.name).join(", ");
 const names=J?J.buckets.map(b=>b.key):D.clusters.map(c=>c.seed);
 host.append(el("h2",{textContent:"Full playlist"}),el("div",{className:"sub",textContent:(perAlbum?"One row per album ("+rows.length+"). ":rows.length+" songs, one row each. ")+(J?"Buckets are the ones the song's album reached; the score is its album's best jev score.":"No jev yet: the bucket is the song's best-fitting recommended bucket and the score is that fit.")+" Click a row (or press Enter) for the album's tags, fits and scores."}));
 const q=el("input",{placeholder:"search title, artist, album or tag","aria-label":"search the playlist"});
 const f=el("select",{"aria-label":"filter by bucket"},el("option",{value:"",textContent:"all songs"}),...names.map(n=>el("option",{value:n,textContent:n})),el("option",{value:NONE,textContent:NONE}),el("option",{value:UNTAGGED,textContent:UNTAGGED}));
 const so=el("select",{"aria-label":"sort"},...[["playlist","playlist order"],["title","title"],["artist","artist"],["album","album"],["score","score, high first"]].map(([v,t])=>el("option",{value:v,textContent:t})));
 const count=el("span",{className:"sub"}),list=el("div",{className:"scroll"}),pager=el("div",{className:"pager"});
 host.append(el("div",{className:"filters"},q,f,so,count),list,pager);
 let page=0;
 const keyOf={title:s=>s.t.toLowerCase(),artist:s=>s.ar.toLowerCase(),album:s=>recs[s.g].album.toLowerCase()};
 function view(){const t=q.value.toLowerCase(),b=f.value;
  let out=rows.filter(s=>{const r=recs[s.g];
   if(b==UNTAGGED?r.tags.length:b&&!bucketsOf(s).includes(b))return false;
   return !t||(s.t+" "+s.ar+" "+r.album+" "+r.tags.map(x=>x.name).join(" ")).toLowerCase().includes(t)});
  const m=so.value;if(m=="score")out=out.slice().sort((x,y)=>topScore(y)-topScore(x)||x.i-y.i);else if(m!="playlist")out=out.slice().sort((x,y)=>keyOf[m](x).localeCompare(keyOf[m](y))||x.i-y.i);
  return out}
 function draw(){const out=view(),pages=Math.max(1,Math.ceil(out.length/PAGE_SONGS));page=Math.min(page,pages-1);
  count.textContent=out.length+" of "+rows.length+(perAlbum?" albums":" songs");
  const body=el("tbody");
  out.slice(page*PAGE_SONGS,(page+1)*PAGE_SONGS).forEach(s=>{const r=recs[s.g],tr=el("tr",{className:"arow",tabIndex:0});let open=null;
   const chips=el("td",{className:"chips"},...bucketsOf(s).map(n=>el("span",{className:"chip"+(n==NONE?" other":""),textContent:n})));
   [el("td",{className:"cv"},art(r.cover,r.artist+" - "+r.album)),el("td",{textContent:s.t}),el("td",{textContent:s.ar}),el("td",{textContent:r.album}),el("td",{className:"tag",textContent:tagLine(r)||"untagged"}),chips,el("td",{textContent:J?topScore(s).toFixed(2):(r.best_cluster?pct(topScore(s)):"")})].forEach(td=>tr.append(td));
   const toggle=()=>{if(open){open.remove();open=null;tr.setAttribute("aria-expanded","false")}else{open=el("tr",{className:"adetail"},el("td",{colSpan:7},albumDetail(r)));tr.after(open);tr.setAttribute("aria-expanded","true")}};
   tr.onclick=toggle;tr.onkeydown=e=>{if(e.key=="Enter"||e.key==" "){e.preventDefault();toggle()}};body.append(tr)});
  list.replaceChildren(el("table",{},el("thead",{},el("tr",{},...["","title","artist","album","tags",J?"buckets":"best bucket",J?"top score":"fit"].map(h=>el("th",{textContent:h})))),body));
  if(!out.length)list.append(el("div",{className:"sub pad",textContent:"no songs match"}));
  const go=d=>()=>{page+=d;draw();host.scrollIntoView({block:"start"})};
  pager.replaceChildren(el("button",{className:"more",textContent:"Previous",disabled:page==0,onclick:go(-1)}),el("span",{className:"sub",textContent:"page "+(page+1)+" of "+pages}),el("button",{className:"more",textContent:"Next",disabled:page>=pages-1,onclick:go(1)}))}
 q.oninput=f.onchange=so.onchange=()=>{page=0;draw()};draw()}
