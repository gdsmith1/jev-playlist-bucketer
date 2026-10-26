{const host=$("panel-selected");
if(!D.jev){host.append(el("div",{className:"note",textContent:"Nothing here yet. This tab fills in after the jev step: once you tick buckets and jev scores every album, it shows the buckets you scored, where the songs ended up and what fell into other. Dry runs and --no-dashboard runs stop before that."}))}
else{const J=D.jev,recs=D.album_records,T=J.threshold,keys=J.buckets.map(b=>b.key);
 const sec=el("div",{id:"yourbuckets"});host.append(sec);
 const stat=(k,v)=>el("div",{className:"stat"},el("b",{textContent:v}),k);
 const unit=x=>x.albums+" albums · "+x.songs+" songs";
 const sp=n=>(100*n/Math.max(1,D.songs)).toFixed(1)+"%";
 const h2=(t,s)=>{sec.append(el("h2",{textContent:t}));if(s)sec.append(el("div",{className:"sub",textContent:s}))};
 const colorOf=k=>COLORS[keys.indexOf(k)%COLORS.length];
 const best=r=>Object.entries(r.jev.scores).sort((a,b)=>b[1]-a[1])[0]||["",0];
 const isOther=r=>!r.jev.matched.length;
 const drill=el("div",{className:"drill",hidden:true});
 function browse(title,rows){const list=el("div",{className:"scroll"});albumTable(rows,list);
  drill.hidden=false;drill.replaceChildren(el("div",{className:"drillhead"},el("h3",{textContent:title+": "+rows.length+" albums"}),el("button",{className:"more",textContent:"Close",onclick:()=>{drill.hidden=true}})),list);
  drill.scrollIntoView({block:"nearest"})}
 const hbars=(rows,aria)=>{const top=Math.max(1,...rows.map(r=>r.value));
  return el("div",{role:"img","aria-label":aria},...rows.map(r=>{const i=el("i");i.style.width=(100*r.value/top)+"%";i.style.background=r.color;
   return el("div",{className:"hbar",title:r.label+": "+r.text},el("span",{className:"t",textContent:r.label}),el("div",{className:"track"},i),el("span",{className:"n",textContent:r.text}))}))};

 h2("Selected buckets","The buckets you scored with jev, kept separate from the recommendations. An album is in a bucket when its score reaches "+T+".");
 sec.append(el("div",{className:"stats"},stat("buckets",J.bucket_count),stat("in one bucket",unit(J.one)),stat("in 2+ buckets",unit(J.several)),stat("in other",unit(J.other)),stat("threshold",T)));

 h2("Songs per bucket","A song counts in every bucket its album reached, so bars can add up to more than the "+D.songs+" songs; other holds albums that reached none. Percent is of all songs.");
 const rows=J.buckets.map(b=>({label:b.key,value:b.songs,text:b.songs+" songs · "+sp(b.songs),color:colorOf(b.key)}));
 rows.push({label:"other",value:J.other.songs,text:J.other.songs+" songs · "+sp(J.other.songs),color:"#75715e"});
 sec.append(hbars(rows,"Songs per selected bucket and other"));

 h2("Albums by number of buckets matched");
 const mc=[0,0,0,0],ms=[0,0,0,0];recs.forEach(r=>{const n=Math.min(3,r.jev.matched.length);mc[n]++;ms[n]+=r.songs});
 sec.append(hbars(["0 (other)","1","2","3 or more"].map((l,i)=>({label:l,value:mc[i],text:mc[i]+" albums · "+ms[i]+" songs",color:i?["","#a6e22e","#66d9ef","#ae81ff"][i]:"#75715e"})),"Albums by number of buckets matched"));

 h2("Bucket cards");
 const cards=el("div",{className:"cards"});
 const mk=(title,badge,sub,color,body,cls)=>{const card=el("div",{className:"card"});card.style.setProperty("--c",color);
  const head=el("button",{className:"head",type:"button",onclick:()=>card.classList.toggle("open")},el("h3",{textContent:title}),badge?el("span",{className:"badge "+(cls||badge),textContent:badge}):"",el("span",{className:"sub",textContent:sub}));
  card.append(head,body);cards.append(card);return card};
 J.buckets.forEach(b=>{const body=el("div",{className:"more"});
  if(b.description)body.append(el("div",{className:"ex",textContent:b.description}));
  if(b.shared)body.append(el("div",{className:"sub",textContent:b.shared+" of these albums are also in another bucket"}));
  if(b.agreement){const a=b.agreement;body.append(el("div",{className:"ex",title:"Albums jev put here versus albums whose tags fit the suggested bucket of the same name.",
   textContent:"jev vs tag fit: "+a.both+" both · "+a.jev_only+" jev only · "+a.tags_only+" tags only ("+a.jev+" by jev, "+a.tags+" by tags)"}))}
  body.append(el("div",{className:"ex",textContent:"top by score: "+(b.top.length?b.top.map(t=>t.artist+" - "+t.album+" ("+t.score.toFixed(2)+")").join("; "):"none")}));
  body.append(el("button",{className:"more",textContent:"Browse "+b.albums+" albums",onclick:()=>browse(b.key,recs.filter(r=>r.jev.matched.includes(b.key)).sort((x,y)=>y.jev.scores[b.key]-x.jev.scores[b.key]||y.songs-x.songs))}));
  mk(b.key,b.source,b.albums+" albums · "+b.songs+" songs",colorOf(b.key),body,b.source=="custom"?"custom":"")});
 {const body=el("div",{className:"more"},el("div",{className:"ex",textContent:"Albums that reached the threshold in no bucket."}),
   el("button",{className:"more",textContent:"Browse "+J.other.albums+" albums",onclick:()=>browse("other",recs.filter(isOther))}));
  mk("other","fallback",unit(J.other),"#75715e",body)}
 sec.append(cards,drill);

 h2("Score distribution","Every album-bucket score from jev. The dashed line is the threshold; the orange bars sit within "+J.borderline_below+" below it, the near-misses.");
 const sel=el("select",{"aria-label":"bucket for the score histogram"},el("option",{value:"",textContent:"all buckets"}),...keys.map(k=>el("option",{value:k,textContent:k})));
 const histBox=el("div");sec.append(el("div",{className:"filters"},sel),histBox);
 const STEP=0.25;
 function drawHist(){const only=sel.value,vals=[];recs.forEach(r=>Object.entries(r.jev.scores).forEach(([k,v])=>{if(keys.includes(k)&&(!only||k==only))vals.push(v)}));
  if(!vals.length){histBox.replaceChildren(el("div",{className:"sub",textContent:"no scores"}));return}
  const lo=Math.min(0,Math.floor(Math.min(...vals)/STEP)*STEP),hi=Math.max(T,Math.max(...vals))+1e-9,n=Math.max(1,Math.ceil((hi-lo)/STEP)),bins=Array(n).fill(0);
  vals.forEach(v=>{bins[Math.min(n-1,Math.floor((v-lo)/STEP))]++});const top=Math.max(...bins);
  const hist=el("div",{className:"hist",role:"img","aria-label":"Histogram of "+vals.length+" scores, threshold "+T+", "+vals.filter(v=>v>=T-J.borderline_below&&v<T).length+" within "+J.borderline_below+" below it"});
  bins.forEach((c,i)=>{const a=lo+i*STEP,col=el("div",{className:"col",title:a.toFixed(2)+" to "+(a+STEP).toFixed(2)+": "+c+" scores"},el("span",{textContent:c||""}));
   const bar=el("i");bar.style.height=(100*c/top*.85)+"%";bar.style.background=a>=T-1e-9?"#a6e22e":a>=T-J.borderline_below-1e-9?"#fd971f":"#75715e";col.append(bar);hist.append(col)});
  const line=el("div",{className:"thr"},el("span",{textContent:"threshold "+T}));line.style.left="calc(4px + (100% - 8px) * "+((T-lo)/(n*STEP))+")";hist.append(line);
  histBox.replaceChildren(hist,el("div",{className:"haxis"},...bins.map((c,i)=>el("span",{textContent:(lo+i*STEP).toFixed(2)}))))}
 sel.onchange=drawHist;drawHist();

 h2("What if the threshold were different","Songs that would land in other at each threshold, from the scores already collected (no new jev calls). Current threshold outlined.");
 const ths=[...new Set([0.5,0.75,1,1.25,1.5,T])].sort((a,b)=>a-b);
 sec.append(el("div",{className:"whatif"},...ths.map(t=>{const o=recs.filter(r=>Math.max(...keys.map(k=>r.jev.scores[k]??-Infinity))<t);
  const s=el("div",{className:"stat"+(t==T?" cur":""),title:o.length+" albums"},el("b",{textContent:o.reduce((n,r)=>n+r.songs,0)+" songs"}),"in other at "+t+(t==T?" (current)":""),el("div",{className:"sub",textContent:o.length+" albums · "+sp(o.reduce((n,r)=>n+r.songs,0))}));return s})));

 h2("Bucket overlap","Albums in both buckets (row and column); the diagonal is the bucket's own album count. Brighter = more shared albums relative to the smaller bucket.");
 {const m=keys.map(a=>keys.map(b=>recs.filter(r=>r.jev.matched.includes(a)&&r.jev.matched.includes(b)).length));
  const tbl=el("table",{className:"ov"},el("thead",{},el("tr",{},el("th"),...keys.map(k=>el("th",{textContent:k,scope:"col"})))),
   el("tbody",{},...keys.map((a,i)=>el("tr",{},el("th",{className:"rh",textContent:a,scope:"row"}),...keys.map((b,j)=>{const td=el("td",{textContent:m[i][j],className:i==j?"d":"",title:a+" and "+b+": "+m[i][j]+" albums"});
    if(i!=j){td.style.background="rgba(174,129,255,"+(.08+.8*m[i][j]/Math.max(1,Math.min(m[i][i],m[j][j])))+")"}return td})))));
  sec.append(el("div",{className:"scroll",style:"padding:8px"},tbl))}

 h2("What fell into other","Biggest albums and artists that reached no bucket, with their best-scoring bucket: a score just under "+T+" means a near-miss.");
 {const oth=recs.filter(isOther).sort((a,b)=>b.songs-a.songs);
  const row=(cells)=>el("tr",{},...cells.map(v=>el("td",{textContent:v})));
  const tbl=(heads,body)=>el("div",{className:"scroll",style:"max-height:340px"},el("table",{},el("thead",{},el("tr",{},...heads.map(h=>el("th",{textContent:h})))),el("tbody",{},...body)));
  sec.append(el("h3",{textContent:"Albums"}),tbl(["artist","album","songs","best bucket","score"],oth.slice(0,20).map(r=>{const[k,v]=best(r);return row([r.artist,r.album,r.songs,k,v.toFixed(2)])})));
  const by={};oth.forEach(r=>{const a=by[r.artist]||(by[r.artist]={artist:r.artist,albums:0,songs:0,top:r});a.albums++;a.songs+=r.songs;if(best(r)[1]>best(a.top)[1])a.top=r});
  sec.append(el("h3",{textContent:"Artists"}),tbl(["artist","albums","songs","best bucket","score"],Object.values(by).sort((a,b)=>b.songs-a.songs).slice(0,15).map(a=>{const[k,v]=best(a.top);return row([a.artist,a.albums,a.songs,k,v.toFixed(2)])})))}

 h2("Borderline albums",J.borderline.total+" album-bucket scores within "+J.borderline_below+" below the threshold"+(J.borderline.total>J.borderline.rows.length?" (top "+J.borderline.rows.length+" shown)":""));
 const body=el("tbody");J.borderline.rows.forEach(b=>body.append(el("tr",{},...[b.artist,b.album,b.bucket,b.score.toFixed(2)].map(v=>el("td",{textContent:v})))));
 sec.append(el("div",{className:"scroll",style:"max-height:320px"},el("table",{},el("thead",{},el("tr",{},...["artist","album","bucket","score"].map(h=>el("th",{textContent:h})))),body)))}}
