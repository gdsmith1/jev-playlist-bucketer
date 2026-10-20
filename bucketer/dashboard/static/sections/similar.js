(()=>{const S=D.similar_network;if(!S.rows.length)return;
 const h=el("h2",{textContent:"Similar to your outliers"}),sub=el("div",{className:"sub",textContent:"Last.fm similar artists for outlier artists ("+S.with_neighbours+" of "+S.outliers+" have some). \"In playlist\" neighbours show where an outlier sits among artists you already have; \"leans\" is the bucket they mostly belong to (it favours big buckets). \"Not in playlist\" artists are ones to add or search for."});
 const rec=el("div",{className:"simrec"},el("b",{textContent:"Most recommended artists you do not have: "}),S.recommended.map(r=>r.artist).join(", "));
 const rows=S.rows.map(r=>el("tr",{},el("td",{textContent:r.artist}),el("td",{textContent:r.inside.join(", ")||"-"}),el("td",{textContent:r.leans||"-"}),el("td",{textContent:r.outside.join(", ")||"-"})));
 const t=el("table",{},el("thead",{},el("tr",{},...["outlier artist","in playlist","leans","not in playlist"].map(x=>el("th",{textContent:x})))),el("tbody",{},...rows));
 $("detail").before(h,sub,rec,el("div",{className:"scroll"},t))})();
