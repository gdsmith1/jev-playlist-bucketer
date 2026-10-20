const HT=D.heat_tags;const peak=Math.max(0.01,...D.heat.flatMap((r,x)=>r.filter((v,y)=>x!=y)));
{const hm=$("heat");const head=el("tr",{},el("th"));HT.forEach(t=>head.append(el("th",{textContent:t,onclick:()=>show(t)})));hm.append(el("thead",{},head));
 const body=el("tbody");D.heat.forEach((row,x)=>{const tr=el("tr",{},el("th",{className:"rh",textContent:HT[x],onclick:()=>show(HT[x])}));
  row.forEach((v,y)=>{const td=el("td",{title:HT[x]+" × "+HT[y]+": "+Math.round(v*100)+"% of albums in common",textContent:x!=y&&v>=0.05?Math.round(v*100):""});
   if(x==y)td.className="self";else td.style.setProperty("--a",Math.max(0.05,v/peak).toFixed(2));tr.append(td)});body.append(tr)});hm.append(body)}
$("heatlegend").textContent="Hover a cell for the tag pair; click a tag name for its description.";
