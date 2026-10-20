{const C=D.coverage,pct=n=>Math.round(100*n/Math.max(1,D.songs))+"%",pctA=Math.round(C.threshold*100);
 $("covsub").textContent="An album is in a bucket when at least "+pctA+"% of its tag weight lands there, so buckets overlap: the bucket sizes below add up to "+C.bucket_song_sum+" songs for "+D.songs+" real songs. Every album is counted once in the bar: in no bucket (it would go to other), in one, or in several.";
 const parts=[["none","in no bucket","#75715e"],["one","in one bucket","#a6e22e"],["several","in several buckets","#66d9ef"]];
 $("covstack").replaceChildren(...parts.map(([k,l,c])=>{const d=el("div",{title:l+": "+C[k].albums+" albums, "+C[k].songs+" songs"});d.style.width=(100*C[k].songs/Math.max(1,D.songs))+"%";d.style.background=c;return d}));
 $("covlegend").textContent=parts.map(([k,l])=>l+": "+C[k].albums+" albums, "+C[k].songs+" songs ("+pct(C[k].songs)+")").join("  |  ");
 const top=Math.max(1,...C.buckets.map(b=>b.songs));
 C.buckets.slice().sort((a,b)=>b.songs-a.songs).forEach(b=>{const f=el("div",{className:"fill"+(b.small?" small":"")});f.style.width=(100*b.songs/top)+"%";
  $("covbars").append(el("div",{className:"bar"},el("span",{className:"t",textContent:b.seed}),el("div",{},f),el("span",{className:"n",textContent:b.songs+" songs"+(b.small?" (small)":"")})))});
 const rows=D.album_records.filter(r=>r.borderline).sort((a,b)=>b.songs-a.songs);
 function drawBord(){$("bordwrap").style.display=$("bord").checked?"block":"none";
  $("bordbody").replaceChildren(...rows.map(r=>{const t=[r.best_cluster,r.second_best_cluster];return el("tr",{},el("td",{className:"cv"},art(r.cover,r.artist+" - "+r.album)),el("td",{textContent:r.artist+" - "+r.album}),el("td",{textContent:r.songs+" songs"}),
   el("td",{textContent:t.map(s=>s+" "+Math.round(100*r.cluster_fits[s])+"%").join("  vs  ")}))}))}
 $("bord").onchange=drawBord;$("bord").parentNode.append(" ("+rows.length+" albums)");drawBord()}
