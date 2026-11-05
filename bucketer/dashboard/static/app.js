const D=/*DATA*/null;const COLORS=["#4cc62f","#1fb5e0","#ffb21a","#2f7fd8","#14b8a6","#a6d62f"];
const RAMP=[[0,[244,251,255]],[.3,[140,210,248]],[.62,[30,190,228]],[1,[8,60,150]]],HOT=.82;
function ramp(a){a=Math.max(0,Math.min(1,a));let k=1;while(a>RAMP[k][0])k++;const [p,c0]=RAMP[k-1],[q,c1]=RAMP[k],t=(a-p)/(q-p);return "rgb("+c0.map((c,i)=>Math.round(c+(c1[i]-c)*t)).join(",")+")"}
function lst(prefix,items,n){const d=el("div",{className:"ex"},prefix+items.slice(0,n).join("; "));if(items.length>n)d.append(el("details",{},el("summary",{textContent:"+"+(items.length-n)+" more"}),items.slice(n).join("; ")));return d}
const $=id=>document.getElementById(id);
function el(tag,props,...kids){const e=document.createElement(tag);Object.assign(e,props||{});kids.forEach(k=>e.append(k));return e}
function show(tag){const i=D.info[tag];const d=$("detail");d.style.display="block";d.replaceChildren(el("b",{},tag),i?el("span",{}," ("+i.reach.toLocaleString()+" listeners) "+i.summary):el("span",{className:"sub"}," no description on Last.fm"))}
function art(url,title,cls){if(!url)return el("span",{className:"ph",textContent:"♪",title:title||"no cover on Last.fm"});
 const i=el("img",{src:url,alt:title||"",title:title||"",loading:"lazy",referrerPolicy:"no-referrer"});i.onerror=()=>i.replaceWith(el("span",{className:"ph",textContent:"♪",title:"cover failed to load"}));return i}
function chip(t){return el("button",{className:"chip",textContent:t,onclick:()=>show(t),title:D.info[t]?D.info[t].summary:""})}

{const root=document.documentElement,btn=$("decortoggle");
 const get=()=>{try{return localStorage.getItem("decor")}catch(e){return null}},set=v=>{try{localStorage.setItem("decor",v)}catch(e){}};
 const apply=off=>{if(off)root.setAttribute("data-decor","off");else root.removeAttribute("data-decor");btn.textContent="Scenery: "+(off?"off":"on");btn.setAttribute("aria-pressed",!off)};
 apply(get()=="off");btn.onclick=()=>{const off=root.getAttribute("data-decor")!="off";apply(off);set(off?"off":"on")};
 const pause=()=>{if(document.hidden||scrollY>innerHeight*2)root.setAttribute("data-paused","");else root.removeAttribute("data-paused")};
 document.addEventListener("visibilitychange",pause);addEventListener("scroll",pause,{passive:true})}
