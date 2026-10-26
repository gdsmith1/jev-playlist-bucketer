const PAGE=50;
function pct(x){return Math.round(x*100)+"%"}
function meter(share,color){const b=el("span",{className:"meter"},el("i"));b.firstChild.style.width=pct(share);if(color)b.firstChild.style.background=color;return b}
function albumDetail(r){
 const tags=el("div",{className:"dcol"},el("h4",{textContent:"Tags"}),...(r.tags.length?r.tags.map(t=>el("div",{className:"drow"},el("span",{textContent:t.name}),meter(t.weight),el("span",{className:"sub",textContent:pct(t.weight)+" · "+t.source}))):[el("div",{className:"sub",textContent:"no tags"})]));
 const fits=Object.entries(r.cluster_fits).filter(([,v])=>v>0).sort((a,b)=>b[1]-a[1]);
 const fit=el("div",{className:"dcol"},el("h4",{textContent:"Fit to buckets"}),...(fits.length?fits.map(([k,v])=>el("div",{className:"drow"},el("span",{textContent:k}),meter(v,"var(--blue)"),el("span",{className:"sub",textContent:pct(v)}))):[el("div",{className:"sub",textContent:"fits no bucket"})]));
 const sim=el("div",{className:"dcol"},el("h4",{textContent:"Similar artists"}),el("div",{className:r.similar.length?"":"sub",textContent:r.similar.length?r.similar.join(", "):"none on Last.fm"}));
 const cols=[tags,fit,sim];
 if(r.jev){const sc=Object.entries(r.jev.scores).sort((a,b)=>b[1]-a[1]);
  cols.splice(2,0,el("div",{className:"dcol"},el("h4",{textContent:"jev scores"}),...sc.map(([k,v])=>el("div",{className:"drow"},el("span",{textContent:k}),meter(Math.max(0,Math.min(1,v)),r.jev.matched.includes(k)?"var(--green)":"var(--muted)"),el("span",{className:"sub",textContent:v.toFixed(2)+(r.jev.matched.includes(k)?" · matched":"")})))))}
 return el("div",{className:"detailgrid"},...cols)}
function albumTable(records,host,seed){
 let shown=PAGE;
 function draw(){
  const body=el("tbody");
  records.slice(0,shown).forEach(r=>{
   const tr=el("tr",{className:"arow",tabIndex:0});let open=null;
   const best=seed?pct(r.cluster_fits[seed]):(r.best_cluster||"");
   [el("td",{className:"cv"},art(r.cover,r.artist+" - "+r.album)),el("td",{textContent:r.artist}),el("td",{textContent:r.album}),el("td",{textContent:r.songs}),el("td",{textContent:best})].forEach(td=>tr.append(td));
   const toggle=()=>{if(open){open.remove();open=null;tr.setAttribute("aria-expanded","false")}else{open=el("tr",{className:"adetail"},el("td",{colSpan:5},albumDetail(r)));tr.after(open);tr.setAttribute("aria-expanded","true")}};
   tr.onclick=toggle;tr.onkeydown=e=>{if(e.key=="Enter"||e.key==" "){e.preventDefault();toggle()}};body.append(tr)});
  const head=el("thead",{},el("tr",{},...["","artist","album","songs",seed?"fit":"best bucket"].map(h=>el("th",{textContent:h}))));
  const kids=[el("table",{},head,body)];
  if(!records.length)kids.push(el("div",{className:"sub pad",textContent:"no albums match"}));
  if(shown<records.length)kids.push(el("button",{className:"more",textContent:"Show "+Math.min(PAGE,records.length-shown)+" more ("+shown+" of "+records.length+")",onclick:()=>{shown+=PAGE;draw()}}));
  host.replaceChildren(...kids)}
 draw()}
function openBucket(seed){
 const c=D.clusters.find(x=>x.seed==seed);const tagset=new Set(c.tags);
 const members=D.album_records.filter(r=>r.cluster_fits[seed]>0).sort((a,b)=>b.cluster_fits[seed]-a.cluster_fits[seed]||b.songs-a.songs);
 const share={};let total=0;members.forEach(r=>r.tags.forEach(t=>{if(tagset.has(t.name)){share[t.name]=(share[t.name]||0)+t.weight;total+=t.weight}}));
 const bars=Object.entries(share).sort((a,b)=>b[1]-a[1]).map(([k,v])=>el("div",{className:"drow"},el("span",{textContent:k}),meter(v/total,"var(--orange)"),el("span",{className:"sub",textContent:pct(v/total)})));
 const list=el("div",{className:"scroll"});albumTable(members,list,seed);
 const d=$("bucketdrill");d.hidden=false;
 d.replaceChildren(el("div",{className:"drillhead"},el("h3",{textContent:seed+": "+members.length+" albums, weakest fit last"}),el("button",{className:"more",textContent:"Close",onclick:()=>{d.hidden=true}})),
  el("h4",{textContent:"Share of the bucket's tag weight"}),el("div",{className:"dcol"},...bars),list);
 d.scrollIntoView({block:"nearest"})}
{const sorted=[...D.album_records].sort((a,b)=>a.artist.localeCompare(b.artist)||a.album.localeCompare(b.album));
 const host=$("allalbums");const redraw=()=>{const q=$("aq").value.toLowerCase();albumTable(sorted.filter(r=>(r.artist+" "+r.album+" "+r.tags.map(t=>t.name).join(" ")).toLowerCase().includes(q)),host)};
 $("aq").oninput=redraw;redraw()}
