const max=Math.max(1,...D.tags.map(t=>t.songs));
D.tags.forEach(t=>{const f=el("div",{className:"fill"});f.style.width=(100*t.songs/max)+"%";$("tags").append(el("div",{className:"bar"+(t.umbrella?" umb":"")},el("span",{className:"t",textContent:t.tag,onclick:()=>show(t.tag)}),el("div",{},f),el("span",{className:"n",textContent:t.songs+" songs"})))});
