/* fx: mouse parallax + cursor bloom, count-up on stat numbers, optional WebAudio chimes (off by default, speaker button in the taskbar) */
{const root=document.documentElement,calm=matchMedia("(prefers-reduced-motion:reduce)").matches;
 if(!calm){let mx=0,my=0,raf=0;const bloom=document.createElement("div");bloom.className="v3-bloom";document.body.appendChild(bloom);
  addEventListener("pointermove",e=>{mx=e.clientX/innerWidth*2-1;my=e.clientY/innerHeight*2-1;
   if(!raf)raf=requestAnimationFrame(()=>{raf=0;root.style.setProperty("--mx",mx.toFixed(3));root.style.setProperty("--my",my.toFixed(3));bloom.style.transform=`translate(${e.clientX}px,${e.clientY}px)`;bloom.style.opacity=.55})},{passive:true});
  document.addEventListener("pointerleave",()=>{bloom.style.opacity=0});
  document.querySelectorAll(".stat b").forEach(el=>{const m=el.textContent.match(/^(\D*)([\d,]+)(\D*)$/);if(!m)return;
   const end=+m[2].replace(/,/g,""),t0=performance.now(),dur=900;if(!(end>0))return;
   const tick=t=>{const k=Math.min(1,(t-t0)/dur),v=Math.round(end*(1-Math.pow(1-k,3)));el.textContent=m[1]+v.toLocaleString()+m[3];if(k<1)requestAnimationFrame(tick)};requestAnimationFrame(tick)})}
 const dock=document.querySelector(".dock"),btn=document.createElement("button");btn.type="button";btn.className="sndbtn";btn.setAttribute("aria-pressed","false");btn.setAttribute("aria-label","Interface sounds (off)");btn.title="Interface sounds";dock.appendChild(btn);
 let ctx=null;const chime=(f,len,type)=>{if(btn.getAttribute("aria-pressed")!="true"||!ctx)return;const t=ctx.currentTime,o=ctx.createOscillator(),g=ctx.createGain();o.type=type||"sine";o.frequency.setValueAtTime(f,t);o.frequency.exponentialRampToValueAtTime(f*1.5,t+len);g.gain.setValueAtTime(.0001,t);g.gain.exponentialRampToValueAtTime(.07,t+.01);g.gain.exponentialRampToValueAtTime(.0001,t+len);o.connect(g).connect(ctx.destination);o.start(t);o.stop(t+len)};
 btn.onclick=()=>{const on=btn.getAttribute("aria-pressed")!="true";btn.setAttribute("aria-pressed",on);btn.setAttribute("aria-label","Interface sounds ("+(on?"on":"off")+")");if(on){ctx=ctx||new (window.AudioContext||window.webkitAudioContext)();ctx.resume();chime(660,.25)}};
 document.addEventListener("click",e=>{if(e.target.closest("#tabs [role=tab]"))chime(880,.22);else if(e.target.closest(".chip"))chime(1320,.12)})}
