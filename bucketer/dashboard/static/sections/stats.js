[["albums",D.albums],["songs",D.songs],["outlier albums",D.outliers.reduce((n,o)=>n+o.albums.length,0)],["outlier songs",D.outlier_songs],["suggested buckets",D.clusters.length]]
 .forEach(([k,v])=>$("stats").append(el("div",{className:"stat"},el("b",{textContent:v}),k)));
