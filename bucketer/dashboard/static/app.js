const D=/*DATA*/null;const COLORS=["#00b4e6","#3ddc1e","#ff9f1a","#2f6fe0","#14d1b8","#c6e61f"];
const RAMP=[[0,[255,255,255]],[.5,[0,180,230]],[1,[10,58,150]]],HOT=.55;
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

/* ===== aero fx: glass tooltip, bubble burst on click, cursor bubble trail (all decorative, motion-safe) ===== */
{const root=document.documentElement,rm=matchMedia("(prefers-reduced-motion:reduce)"),still=()=>rm.matches||root.hasAttribute("data-paused")||root.getAttribute("data-decor")=="off";
 const tip=el("div",{className:"gtip",role:"presentation"});tip.setAttribute("aria-hidden","true");document.body.append(tip);let cur=null;
 const put=(x,y)=>{const w=tip.offsetWidth,h=tip.offsetHeight;tip.style.left=Math.max(8,Math.min(innerWidth-w-8,x+14))+"px";tip.style.top=Math.max(8,y+18+h>innerHeight?y-h-10:y+18)+"px"};
 const off=()=>{if(cur){if(cur.dataset.tip)cur.setAttribute("title",cur.dataset.tip);delete cur.dataset.tip;cur=null}tip.classList.remove("on")};
 document.addEventListener("mouseover",e=>{const t=e.target.closest&&e.target.closest("[title]");if(!t||t==cur||!t.getAttribute("title"))return;off();cur=t;t.dataset.tip=t.getAttribute("title");t.removeAttribute("title");tip.textContent=t.dataset.tip;tip.classList.add("on");put(e.clientX,e.clientY)});
 document.addEventListener("mousemove",e=>{if(cur)put(e.clientX,e.clientY)});
 document.addEventListener("mouseout",e=>{if(cur&&!cur.contains(e.relatedTarget))off()});
 const bub=(x,y,sz,dx,dy,ms)=>{const b=el("span",{className:"fxb"});b.style.cssText="left:"+x+"px;top:"+y+"px;width:"+sz+"px;height:"+sz+"px";document.body.append(b);
  const a=b.animate([{transform:"translate(-50%,-50%) scale(.4)",opacity:.95},{transform:"translate(calc(-50% + "+dx+"px),calc(-50% + "+dy+"px)) scale(1)",opacity:0}],{duration:ms,easing:"ease-out"});a.onfinish=()=>b.remove()};
 document.addEventListener("click",e=>{if(still()||!e.target.closest||!e.target.closest(".btn,button.more,.tabs [role=tab],#homebtn"))return;
  for(let i=0;i<6;i++){const a=Math.PI*2*i/6+Math.random();bub(e.clientX,e.clientY,5+Math.random()*7,Math.cos(a)*(18+Math.random()*16),Math.sin(a)*(18+Math.random()*16)-6,520+Math.random()*200)}});
 let last=0;document.addEventListener("mousemove",e=>{const n=performance.now();if(n-last<70||still())return;last=n;bub(e.clientX,e.clientY,4+Math.random()*5,(Math.random()-.5)*14,-14-Math.random()*14,800)},{passive:true})}
