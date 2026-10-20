$("outsub").textContent="Fit is the share of an album's tag weight (umbrella tags ignored) that lands in its best suggested bucket: 0% means none of its tags are in a bucket, 100% means all are. Outliers fit under "+Math.round(D.outlier_fit*100)+"%, plus untagged albums. Albums by the same artist share one row, and albums with 0% fit are grouped below.";
let sortKey="fit",asc=true,zeroOpen=false;const cols=[["cover",""],["artist","artist"],["album","album"],["songs","songs"],["reason","reason"],["fit","fit"],["nearest","nearest bucket"],["tags","tags"]];
function fitCell(f){const b=el("div",{className:"fitbar",title:"fit "+Math.round(f*100)+"%"},el("i"));b.firstChild.style.width=Math.round(f*100)+"%";return el("td",{className:"fit"},Math.round(f*100)+"% ",b)}
function outlierRow(o){const tr=el("tr");[o.cover,o.artist,o.album,o.songs,o.reason,o.fit,o.nearest||"",""].forEach((v,i)=>tr.append(i==0?el("td",{className:"cv"},art(v,o.artist+" - "+o.album)):i==5?fitCell(v):i==7?el("td",{},...o.tags.map(chip)):el("td",{textContent:v})));return tr}
function draw(){const q=$("q").value.toLowerCase();const rows=D.outliers.filter(o=>(o.artist+" "+o.album+" "+o.tags.join(" ")+" "+o.reason).toLowerCase().includes(q))
 .sort((a,b)=>{const x=a[sortKey],y=b[sortKey];const r=typeof x=="number"?x-y:String(x).localeCompare(String(y));return asc?r:-r});
 const zero=rows.filter(o=>o.fit==0),rest=rows.filter(o=>o.fit>0);
 $("oh").replaceChildren(...cols.map(([k,l])=>el("th",{textContent:l+(sortKey==k?(asc?" ▲":" ▼"):""),onclick:()=>{asc=sortKey==k?!asc:true;sortKey=k;draw()}})));
 $("ob").replaceChildren(...rest.map(outlierRow));$("oz").replaceChildren(...zero.map(outlierRow));
 const open=zeroOpen||(q&&zero.length>0);$("zerobox").hidden=!open||!zero.length;$("zerotoggle").hidden=!zero.length;
 $("zerotoggle").setAttribute("aria-expanded",String(open));$("zerotoggle").textContent=(open?"Hide ":"Show ")+zero.length+" albums with 0% fit (no tag in any bucket)"}
$("zerotoggle").onclick=()=>{zeroOpen=!zeroOpen;draw()};
$("q").oninput=draw;draw();
