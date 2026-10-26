(()=>{const N=D.noise,KEY="dashboard-noise-tags";let marked=new Set();
 try{marked=new Set(JSON.parse(localStorage.getItem(KEY)||"[]"))}catch(e){}
 N.rows.forEach(r=>{if(r.reasons.includes("blocklist"))marked.add(r.tag)});
 const h=el("h2",{textContent:"Tag noise audit"}),
  sub=el("div",{className:"sub",textContent:N.flagged+" of "+N.tags+" tags are flagged: "+N.blocklist+" match the dashboard blocklist, "+N.single+" sit on a single album. Tick the ones that are not genres, then copy the list. Nothing here changes the clusters or the text sent to jev."});
 const count=el("span",{className:"sub"}),body=el("tbody");
 const save=()=>{count.textContent=marked.size+" marked";try{localStorage.setItem(KEY,JSON.stringify([...marked]))}catch(e){}};
 N.rows.forEach(r=>{const box=el("input",{type:"checkbox",checked:marked.has(r.tag),ariaLabel:"mark "+r.tag+" as noise",onchange:()=>{box.checked?marked.add(r.tag):marked.delete(r.tag);save()}});
  body.append(el("tr",{},el("td",{},box),el("td",{},chip(r.tag)),el("td",{textContent:r.albums}),el("td",{textContent:r.songs}),el("td",{textContent:r.reasons.join(", ")}),el("td",{textContent:r.example})))});
 const copy=el("button",{className:"chip",textContent:"copy marked as JSON",onclick:()=>{const t=JSON.stringify([...marked].sort());(navigator.clipboard?navigator.clipboard.writeText(t):Promise.reject()).catch(()=>prompt("Marked noise tags",t))}});
 const det=el("details",{},el("summary",{textContent:"Flagged tags ("+N.flagged+")"}),el("div",{},copy," ",count),
  el("div",{className:"scroll qlist"},el("table",{},el("thead",{},el("tr",{},...["noise","tag","albums","songs","why","example"].map(t=>el("th",{textContent:t})))),body)),
  N.flagged>N.rows.length?el("div",{className:"sub",textContent:"+"+(N.flagged-N.rows.length)+" more single-album tags not listed"}):"");
 save();$("detail").before(h,sub,det)})();
