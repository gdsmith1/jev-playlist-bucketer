(()=>{const S=D.decades;if(!S.decades.length)return;
 const h=el("h2",{textContent:"Decades"}),sub=el("div",{className:"sub",textContent:"Release decade of the albums in each suggested bucket (each album counted once, in the bucket it fits best). Flagged: one decade holds at least 60% of a bucket's dated albums."});
 const max=Math.max(1,...S.clusters.map(c=>Math.max(...c.counts)),...S.overall.counts);
 function row(name,c,flag){const bars=el("div",{className:"dec"},...S.decades.map((d,i)=>{const b=el("div",{className:"dbar",title:d+"s: "+c.counts[i]+" albums"},el("i",{style:"height:"+Math.round(100*c.counts[i]/max)+"%"}),el("span",{textContent:c.counts[i]||""}));return b}));
  const head=el("div",{className:"dname",textContent:name},flag?el("span",{className:"flag",textContent:" mostly "+c.top_decade+"s ("+Math.round(100*c.top_share)+"%)"}):"",c.unknown?el("span",{className:"sub",textContent:" "+c.unknown+" undated"}):"");
  return el("div",{className:"decrow"},head,bars)}
 const axis=el("div",{className:"dec daxis"},...S.decades.map(d=>el("span",{textContent:d+"s"})));
 $("detail").before(h,sub,el("div",{className:"decs"},row("all albums",S.overall,false),...S.clusters.map(c=>row(c.seed,c,c.dominated)),axis))})();
