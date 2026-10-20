let sortKey="fit",asc=true;const cols=[["cover",""],["artist","artist"],["album","album"],["songs","songs"],["reason","reason"],["fit","fit"],["nearest","nearest bucket"],["tags","tags"]];
function draw(){const q=$("q").value.toLowerCase();const rows=D.outliers.filter(o=>(o.artist+" "+o.album+" "+o.tags.join(" ")).toLowerCase().includes(q))
 .sort((a,b)=>{const x=a[sortKey],y=b[sortKey];const r=typeof x=="number"?x-y:String(x).localeCompare(String(y));return asc?r:-r});
 $("oh").replaceChildren(...cols.map(([k,l])=>el("th",{textContent:l+(sortKey==k?(asc?" ▲":" ▼"):""),onclick:()=>{asc=sortKey==k?!asc:true;sortKey=k;draw()}})));
 $("ob").replaceChildren(...rows.map(o=>{const tr=el("tr");[o.cover,o.artist,o.album,o.songs,o.reason,o.fit,o.nearest||"",""].forEach((v,i)=>tr.append(i==0?el("td",{className:"cv"},art(v,o.artist+" - "+o.album)):i==7?el("td",{},...o.tags.map(chip)):el("td",{textContent:v})));return tr}))}
$("q").oninput=draw;draw();
