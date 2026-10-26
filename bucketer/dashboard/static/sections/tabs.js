{const tabs=[...document.querySelectorAll("#tabs [role=tab]")],names=tabs.map(t=>t.dataset.tab);
 if(!D.jev)$("tab-selected").title="Fills in after the jev step";
 function select(name,focus){if(!names.includes(name))name=names[0];
  tabs.forEach(t=>{const on=t.dataset.tab==name;t.setAttribute("aria-selected",on);t.tabIndex=on?0:-1;$("panel-"+t.dataset.tab).hidden=!on;if(on&&focus)t.focus()});
  if(location.hash!="#"+name)history.replaceState(null,"","#"+name)}
 tabs.forEach((t,i)=>{t.onclick=()=>select(t.dataset.tab);
  t.onkeydown=e=>{const k={ArrowRight:1,ArrowLeft:-1}[e.key];let n=-1;
   if(k)n=(i+k+tabs.length)%tabs.length;else if(e.key=="Home")n=0;else if(e.key=="End")n=tabs.length-1;
   if(n>=0){e.preventDefault();select(names[n],true)}}});
 window.addEventListener("hashchange",()=>select(location.hash.slice(1)));
 select(location.hash.slice(1))}
