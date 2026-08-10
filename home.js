let feed=[];
let slides=[];
let pagerButtons=[];
let current=0;

function esc(value=""){
  return String(value).replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
}

function renderSlide(item,i){
  const media = item.image
    ? `<img src="${esc(item.image)}" alt="${esc(item.title)}" draggable="false">`
    : `<div class="feed-placeholder" style="--placeholder:${esc(item.tone || "#33465b")}"></div>`;

  const action = `<span class="home-open-label">haberi aç →</span>`;

  return `<article class="home-slide ${i===0?"active":""}" data-article="${esc(item.articleId || "")}">
    <div class="home-media">
      ${media}
      <span class="home-category">${esc(item.category)}</span>
      <span class="home-swipe">← sürükle →</span>
      <button class="home-arrow prev" aria-label="Önceki">‹</button>
      <button class="home-arrow next" aria-label="Sonraki">›</button>
    </div>
    <div class="home-copy">
      <h1>${esc(item.title)}</h1>
      <p>${esc(item.spot)}</p>
      ${action}
    </div>
  </article>`;
}

function build(){
  document.getElementById("homeSlides").innerHTML=feed.map(renderSlide).join("");
  document.getElementById("homePager").innerHTML=feed.map((_,i)=>
    `<button class="${i===0?"active":""}" data-i="${i}" aria-label="${i+1}. haber">${i+1}</button>`
  ).join("");

  slides=[...document.querySelectorAll(".home-slide")];
  pagerButtons=[...document.querySelectorAll(".home-pager button")];

  document.querySelectorAll(".home-arrow.prev").forEach(btn=>{
    btn.addEventListener("click",e=>{e.preventDefault();e.stopPropagation();show(current-1);});
  });
  document.querySelectorAll(".home-arrow.next").forEach(btn=>{
    btn.addEventListener("click",e=>{e.preventDefault();e.stopPropagation();show(current+1);});
  });
  pagerButtons.forEach((btn,i)=>{
    btn.addEventListener("click",e=>{e.preventDefault();e.stopPropagation();show(i);});
  });

  slides.forEach(slide=>{
    slide.addEventListener("click",e=>{
      if(e.target.closest(".home-arrow") || slide.dataset.dragged==="1") return;
      const id=slide.dataset.article;
      if(id) location.href=`article.html?id=${encodeURIComponent(id)}`;
    });
  });

  document.querySelectorAll(".home-media").forEach(bindPointerDrag);
}

function show(i){
  current=(i+feed.length)%feed.length;
  slides.forEach((s,n)=>s.classList.toggle("active",n===current));
  pagerButtons.forEach((b,n)=>b.classList.toggle("active",n===current));
  pagerButtons[current]?.scrollIntoView({behavior:"smooth",block:"nearest",inline:"center"});
}

function bindPointerDrag(area){
  let active=false,startX=0,startY=0,lastX=0,moved=false;
  const slide=area.closest(".home-slide");

  area.addEventListener("pointerdown",e=>{
    if(e.target.closest("button")) return;
    active=true;moved=false;
    startX=lastX=e.clientX; startY=e.clientY;
    area.classList.add("dragging");
    try{area.setPointerCapture(e.pointerId);}catch{}
  });

  area.addEventListener("pointermove",e=>{
    if(!active) return;
    lastX=e.clientX;
    if(Math.abs(e.clientX-startX)>7) moved=true;
  });

  function finish(e){
    if(!active) return;
    active=false; area.classList.remove("dragging");
    const endX=Number.isFinite(e.clientX)?e.clientX:lastX;
    const endY=Number.isFinite(e.clientY)?e.clientY:startY;
    const dx=endX-startX,dy=endY-startY;
    slide.dataset.dragged=moved?"1":"0";
    if(Math.abs(dx)>45 && Math.abs(dx)>Math.abs(dy)){
      show(current+(dx<0?1:-1));
    }
    setTimeout(()=>slide.dataset.dragged="0",100);
  }

  area.addEventListener("pointerup",finish);
  area.addEventListener("pointercancel",finish);
  area.addEventListener("dragstart",e=>e.preventDefault());
}

document.addEventListener("keydown",e=>{
  if(e.key==="ArrowLeft") show(current-1);
  if(e.key==="ArrowRight") show(current+1);
});


try{
  feed = (window.NEWS_DATA && window.NEWS_DATA.feed) ? window.NEWS_DATA.feed : [];
  if(!feed.length) throw new Error("Güncel haber akışı henüz oluşmadı");
  const updated = window.NEWS_DATA && window.NEWS_DATA.updatedAt;
  const updatedEl = document.getElementById("homeUpdated");
  if(updated && updatedEl){
    const d = new Date(updated);
    updatedEl.textContent = `Son güncelleme: ${d.toLocaleString("tr-TR", {dateStyle:"short", timeStyle:"short"})}`;
  }
  build();
}catch(err){
  document.getElementById("homeSlides").innerHTML=
    `<div class="home-error"><h1>Ana sayfa yüklenemedi</h1><p>${esc(err.message)}</p></div>`;
}
