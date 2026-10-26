const cards=D.clusters.map((c,i)=>{const more=el("div",{className:"more"},...c.tags.map(chip));
 if(c.covers.length)more.append(el("div",{className:"thumbs"},...c.covers.map(v=>art(v.url,v.title))));
 more.append(el("div",{className:"ex",textContent:"e.g. "+c.examples.map(e=>e.artist+" - "+e.album+" ("+e.songs+(e.songs==1?" song":" songs")+")").join("; ")}));
 if(c.similar.length)more.append(el("div",{className:"ex",textContent:"similar artists not in your playlist: "+c.similar.join(", ")}));
 more.append(el("button",{className:"more",textContent:"Browse "+c.albums+" albums",onclick:()=>openBucket(c.seed)}));
 const head=el("button",{className:"head",type:"button",onclick:()=>card.classList.toggle("open")},el("span",{className:"rank",textContent:"#"+(i+1)}),
  el("h3",{textContent:c.label_tags.join(" · "),title:"seed tag: "+c.seed}),el("span",{className:"sub",textContent:c.albums+" albums · "+c.songs+" songs"}),
  el("span",{className:"sub",title:"Mean overlap between the albums carrying each pair of this bucket's tags: higher means the tags describe the same albums.",textContent:c.cohesion==null?"cohesion: n/a (single tag)":"cohesion "+Math.round(c.cohesion*100)+"%"}));
 const card=el("div",{className:"card"+(D.clusters.length<=12?" open":"")},head,more);card.style.setProperty("--c",COLORS[i%COLORS.length]);$("clusters").append(card);return card});
if(cards.length>12)$("clusters").before(el("div",{className:"tools"},el("button",{className:"btn",textContent:"Expand all",onclick:()=>cards.forEach(c=>c.classList.add("open"))}),
 el("button",{className:"btn",textContent:"Collapse all",onclick:()=>cards.forEach(c=>c.classList.remove("open"))}),el("span",{className:"sub",textContent:" click a bucket to open it"})));
