const HT=D.heat_tags;const SCALE=0.5;
const act=(t)=>({tabIndex:0,role:"button",onclick:()=>show(t),onkeydown:e=>{if(e.key=="Enter"||e.key==" "){e.preventDefault();show(t)}}});
{const hm=$("heat");const head=el("tr",{},el("th"));HT.forEach(t=>head.append(el("th",{textContent:t,...act(t)})));hm.append(el("thead",{},head));
 const body=el("tbody");D.heat.forEach((row,x)=>{const tr=el("tr",{},el("th",{className:"rh",textContent:HT[x],...act(HT[x])}));
  row.forEach((v,y)=>{const td=el("td",{title:HT[x]+" × "+HT[y]+": "+Math.round(v*100)+"% of albums in common",textContent:x!=y&&v>=0.05?Math.round(v*100):""});
   if(x==y)td.className="self";else{const a=Math.min(1,v/SCALE);td.style.setProperty("--a",(0.08+0.92*a).toFixed(2));if(a>0.55)td.classList.add("hot")}tr.append(td)});body.append(tr)});hm.append(body)}
const nTop=D.tags.filter(t=>!t.umbrella).length;
$("heatlegend").replaceChildren(el("div",{className:"hmscale"},el("span",{textContent:"0%"}),el("i"),el("span",{textContent:Math.round(SCALE*100)+"%+"}),el("span",{className:"sub",textContent:"fixed scale, the same in every cell"})),
 el("div",{textContent:"Showing the "+HT.length+" most common of "+nTop+" candidate tags (by songs) to keep the grid readable. Hover a cell for the tag pair; click or press Enter on a tag name for its description."}));
