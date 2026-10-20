const D=/*DATA*/null;const COLORS=["#a6e22e","#66d9ef","#f92672","#fd971f","#ae81ff","#e6db74"];
const $=id=>document.getElementById(id);
function el(tag,props,...kids){const e=document.createElement(tag);Object.assign(e,props||{});kids.forEach(k=>e.append(k));return e}
function show(tag){const i=D.info[tag];const d=$("detail");d.style.display="block";d.replaceChildren(el("b",{},tag),i?el("span",{}," ("+i.reach.toLocaleString()+" listeners) "+i.summary):el("span",{className:"sub"}," no description on Last.fm"))}
function art(url,title,cls){if(!url)return el("span",{className:"ph",textContent:"♪",title:title||"no cover on Last.fm"});
 const i=el("img",{src:url,alt:title||"",title:title||"",loading:"lazy",referrerPolicy:"no-referrer"});i.onerror=()=>i.replaceWith(el("span",{className:"ph",textContent:"♪",title:"cover failed to load"}));return i}
function chip(t){return el("button",{className:"chip",textContent:t,onclick:()=>show(t),title:D.info[t]?D.info[t].summary:""})}
