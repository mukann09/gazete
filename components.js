const COLORS = new Set(["yellow","green","pink","blue","orange"]);

function esc(value=""){
  return String(value).replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
}

function safeUrl(url=""){
  try{
    const u=new URL(url, location.href);
    return ["http:","https:"].includes(u.protocol) ? u.href : "#";
  }catch{
    return "#";
  }
}

function applyHighlights(text, highlights=[]){
  let out=esc(text);
  for(const h of highlights){
    const color=COLORS.has(h.color)?h.color:"yellow";
    const needle=esc(h.text||"");
    if(needle) out=out.replace(needle, `<mark class="hl-${color}">${needle}</mark>`);
  }
  return out;
}

function sectionByType(article,type){
  return (article.sections||[]).find(s=>s.type===type);
}

const renderers={
  summary_cards(section){
    return `<section class="summary-grid premium-summary">${(section.items||[]).map((item,i)=>`
      <article class="summary-card tone-${esc(item.tone||"yellow")} summary-card-${i+1}">
        <div class="summary-index">${String(i+1).padStart(2,"0")}</div>
        <div class="summary-rule"></div>
        <h2>${esc(item.label)}</h2>
        <p>${esc(item.text)}</p>
      </article>`).join("")}</section>`;
  },
  highlight_paragraph(section){
    return `<section class="notebook-block editorial-note">
      <div class="section-kicker">DOSYA NOTU</div>
      <h2 class="section-title hand">${esc(section.heading||"")}</h2>
      ${(section.paragraphs||[]).map(p=>`<p>${applyHighlights(p.text,p.highlights)}</p>`).join("")}
    </section>`;
  },
  quote(section){
    return `<aside class="quote-note">
      <div class="quote-mark">“</div>
      <p>${esc(section.text)}</p>
      <span>${esc(section.note||"")}</span>
    </aside>`;
  },
  flow(section){
    return `<section class="infographic timeline-card">
      <div class="section-kicker">AKIŞ</div>
      <h2 class="section-title hand">${esc(section.heading||"")}</h2>
      <div class="timeline">${(section.items||[]).map((item,i)=>`
        <div class="timeline-item">
          <div class="timeline-dot">${String(i+1).padStart(2,"0")}</div>
          <div class="timeline-line"></div>
          <div class="timeline-body tone-${esc(item.tone||"blue")}">${esc(item.text)}</div>
        </div>`).join("")}</div>
    </section>`;
  },
  key_takeaway(section){
    return `<section class="takeaway premium-takeaway">
      <div class="takeaway-eyebrow">KISA DEĞERLENDİRME</div>
      <span class="takeaway-label hand">${esc(section.title||"")}</span>
      <p>${esc(section.text||"")}</p>
    </section>`;
  },
  sources(section){
    return `<section class="sources premium-sources">
      <div class="section-kicker">DOĞRULAMA</div>
      <h2 class="section-title hand">Kaynaklar</h2>
      <div class="source-list">${(section.items||[]).map((item,i)=>
        `<a href="${safeUrl(item.url)}" target="_blank" rel="noopener"><span>${String(i+1).padStart(2,"0")}</span><b>${esc(item.label)}</b><em>↗</em></a>`
      ).join("")}</div>
    </section>`;
  }
};

function renderArticle(article){
  document.title=`${article.title} — Gündem Defteri`;
  const sources=sectionByType(article,"sources");
  const sourceCount=(sources?.items||[]).length;
  return `<article class="article hand premium-article">
    <header class="article-head premium-head">
      <div class="article-topline">
        <div class="article-meta">
          <span>${esc(article.category||"Gündem")}</span><span>·</span><span>${esc(article.date||"")}</span>
        </div>
        <div class="source-count">${sourceCount ? `${sourceCount} kaynak` : "güncel dosya"}</div>
      </div>
      <div class="headline-mark">GÜNDEM DEFTERİ / DOSYA</div>
      <h1>${esc(article.title)}</h1>
      <p class="lead">${esc(article.lead||"")}</p>
    </header>
    ${article.hero ? `<figure class="hero-photo premium-hero">
      <div class="hero-frame"><img src="${esc(article.hero.src||"")}" alt="${esc(article.hero.alt||article.title)}"></div>
      <figcaption><span>FOTOĞRAF</span>${esc(article.hero.caption||"")}</figcaption>
    </figure>` : ""}
    <div class="article-content premium-content">${(article.sections||[]).map(section=>{
      const fn=renderers[section.type];
      return fn ? fn(section) : "";
    }).join("")}</div>
  </article>`;
}

function boot(){
  const root=document.getElementById("articleRoot");
  try{
    const data=window.NEWS_DATA||{};
    const id=new URLSearchParams(location.search).get("id");
    const list=data.articles||[];
    const article=(id ? list.find(a=>a.id===id) : null) || list[0];
    if(!article) throw new Error("Haber bulunamadı.");
    root.innerHTML=renderArticle(article);
  }catch(err){
    root.innerHTML=`<div class="engine-error"><h1>Haber yüklenemedi</h1><p>${esc(err.message||err)}</p></div>`;
  }
}

if(document.readyState==="loading"){
  document.addEventListener("DOMContentLoaded",boot);
}else{
  boot();
}
