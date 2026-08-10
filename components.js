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

const renderers={
  summary_cards(section){
    return `<section class="summary-grid">${(section.items||[]).map((item,i)=>`
      <article class="summary-card tone-${esc(item.tone||"yellow")}">
        <div class="summary-index">${String(i+1).padStart(2,"0")}</div>
        <h2>${esc(item.label)}</h2>
        <p>${esc(item.text)}</p>
      </article>`).join("")}</section>`;
  },
  highlight_paragraph(section){
    return `<section class="notebook-block">
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
    return `<section class="infographic">
      <h2 class="section-title hand">${esc(section.heading||"")}</h2>
      <div class="flow">${(section.items||[]).map((item,i)=>
        `${i?'<span class="flow-arrow">→</span>':''}<div class="flow-node tone-${esc(item.tone||"blue")}">${esc(item.text)}</div>`
      ).join("")}</div>
    </section>`;
  },
  key_takeaway(section){
    return `<section class="takeaway">
      <span class="takeaway-label hand">${esc(section.title||"")}</span>
      <p>${esc(section.text||"")}</p>
    </section>`;
  },
  sources(section){
    return `<section class="sources">
      <h2 class="section-title hand">Kaynaklar</h2>
      ${(section.items||[]).map(item=>
        `<a href="${safeUrl(item.url)}" target="_blank" rel="noopener">${esc(item.label)}</a>`
      ).join("")}
    </section>`;
  }
};

function renderArticle(article){
  document.title=`${article.title} — Gündem Defteri`;
  return `<article class="article hand">
    <header class="article-head">
      <div class="article-meta">
        <span>${esc(article.category||"Gündem")}</span><span>·</span><span>${esc(article.date||"")}</span>
      </div>
      <h1>${esc(article.title)}</h1>
      <p class="lead">${esc(article.lead||"")}</p>
    </header>
    ${article.hero ? `<figure class="hero-photo">
      <img src="${esc(article.hero.src||"")}" alt="${esc(article.hero.alt||article.title)}">
      <figcaption>${esc(article.hero.caption||"")}</figcaption>
    </figure>` : ""}
    <div class="article-content">${(article.sections||[]).map(section=>{
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
