#!/usr/bin/env python3
from __future__ import annotations

import argparse
import email.utils
import hashlib
import html
import json
import re
import signal
import time
import urllib.parse
import urllib.request
import io
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from pathlib import Path

try:
    from googlenewsdecoder import gnewsdecoder
except ImportError:
    print("HATA: googlenewsdecoder paketi kurulu değil.")
    print("RADAR_UPDATE.bat dosyasını çalıştırın; paket otomatik kurulacaktır.")
    raise SystemExit(1)

try:
    from PIL import Image
except ImportError:
    print("HATA: Pillow paketi kurulu değil.")
    print("RADAR_UPDATE.bat dosyasını çalıştırın; gerekli paketler otomatik kurulacaktır.")
    raise SystemExit(1)

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "radar_config.json"
BLOCKED_SOURCES = ROOT / "blocked_sources.json"
PREFERRED_SOURCES = ROOT / "preferred_sources.json"
NEWS = ROOT / "news.json"
DATA_JS = ROOT / "data.js"
IMAGES = ROOT / "images"
STATE = ROOT / "radar_state.json"
PREVIEW = ROOT / "radar_preview.json"
ERRORS = ROOT / "radar_last_errors.txt"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/127 Safari/537.36"

RUN_DEADLINE_SECONDS = 210
PER_DECODE_SECONDS = 7
PER_HTTP_SECONDS = 9

class DecodeTimeout(Exception):
    pass

def _alarm_handler(signum, frame):
    raise DecodeTimeout("decode timeout")


# Deliberately conservative: the radar contains many conversational / lifestyle topics
# that are not news stories. These are excluded before verification.
BLOCK_PHRASES = [
    "güne bir şarkı", "gune bir sarki", "evlenilecek", "sevgili", "flört", "flort",
    "kadınlardan erkeklere", "erkeklerden kadınlara", "erkeklere ulaşmanın",
    "burcu", "burç", "burc", "sevebilmek", "samimiyet kurma",
    "spor yapmak için gerekli motivasyon", "kalori açığı", "kalori acigi",
    "insanları kusurlarıyla", "insanlari kusurlariyla",
    "saygı görmek istiyorsan", "saygi gormek istiyorsan",
    "birini tanımanın", "birini tanimanin", "pazar sabahı", "pazar sabahi",
    "kocanı elinden aldım", "kocani elinden aldim",
    "günün şarkısı", "gunun sarkisi", "geceye bir", "sabahına bir", "sabahina bir",
]

# Strong news/event cues. A topic can still pass without these if verification finds
# multiple independent publishers, but these cues improve ranking.
NEWS_CUES = [
    "gözaltı","gozalti","tutuk","deprem","yangın","yangin","yasa","mahkeme",
    "bakan","başkan","baskan","parti","meclis","tbmm","saldırı","saldiri",
    "maçı","maci","transfer","istifa","açıklama","aciklama","zam","enflasyon",
    "faiz","dolar","euro","anlaşma","anlasma","savaş","savas","seçim","secim",
    "yök","yok","ösym","osym","üniversite","universite","grev","kaza","ölü",
    "olu","yaralı","yarali","yasak","karar","soruşturma","sorusturma",
    "operasyon","görevden","gorevden","atama","ihale","dava","rekor"
]

class AgendaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows=[]
        self._active=False
        self._href=""
        self._buf=[]
    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        d=dict(attrs)
        href=d.get("href","")
        if href.startswith("/"):
            self._active=True
            self._href=href
            self._buf=[]
    def handle_data(self, data):
        if self._active:
            self._buf.append(data)
    def handle_endtag(self, tag):
        if tag.lower()=="a" and self._active:
            text=" ".join("".join(self._buf).split()).strip()
            if text:
                self.rows.append((text,self._href))
            self._active=False
            self._href=""
            self._buf=[]

class MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.og_image=None
        self.og_image_width=None
        self.og_image_height=None
        self.twitter_image=None
        self.image_src=None
        self.description=None
        self.canonical=None
        self.inline_images=[]
        self.jsonld_blocks=[]
        self._in_jsonld=False
        self._jsonld_buf=[]
    def handle_starttag(self, tag, attrs):
        d={str(k).lower():v for k,v in attrs}
        tag=tag.lower()
        if tag=='meta':
            key=(d.get('property') or d.get('name') or d.get('itemprop') or '').lower()
            content=d.get('content')
            if key=='og:image' and content and not self.og_image: self.og_image=content
            elif key=='og:image:width' and content and not self.og_image_width: self.og_image_width=content
            elif key=='og:image:height' and content and not self.og_image_height: self.og_image_height=content
            elif key=='twitter:image' and content and not self.twitter_image: self.twitter_image=content
            elif key=='image' and content and not self.image_src: self.image_src=content
            elif key in ('description','og:description') and content and not self.description: self.description=content
        elif tag=='link':
            rel=(d.get('rel') or '').lower(); href=d.get('href')
            if 'canonical' in rel and href and not self.canonical: self.canonical=href
            if 'image_src' in rel and href and not self.image_src: self.image_src=href
        elif tag=='img':
            src=d.get('src') or d.get('data-src') or d.get('data-original')
            srcset=d.get('srcset') or d.get('data-srcset') or ''
            if src or srcset:
                self.inline_images.append({'src':src,'srcset':srcset,'width':d.get('width'),'height':d.get('height'),'class':((d.get('class') or '')+' '+(d.get('id') or '')).lower(),'alt':(d.get('alt') or '').lower()})
        elif tag=='script' and (d.get('type') or '').lower()=='application/ld+json':
            self._in_jsonld=True; self._jsonld_buf=[]
    def handle_data(self, data):
        if self._in_jsonld: self._jsonld_buf.append(data)
    def handle_endtag(self, tag):
        if tag.lower()=='script' and self._in_jsonld:
            text=''.join(self._jsonld_buf).strip()
            if text: self.jsonld_blocks.append(text)
            self._in_jsonld=False; self._jsonld_buf=[]

def absolutize(url, base):
    if not url:
        return None
    return urllib.parse.urljoin(base, url)

def likely_bad_image(url, meta=None):
    low=(url or "").lower()
    bad_words=["logo","sprite","icon","favicon","avatar","placeholder","blank"]
    if any(w in low for w in bad_words):
        return True
    if meta:
        cls=(meta.get("class") or "")
        alt=(meta.get("alt") or "")
        combo=cls+" "+alt
        if any(w in combo for w in bad_words):
            return True
    return False

def parse_srcset(srcset, base):
    out=[]
    if not srcset: return out
    for part in srcset.split(','):
        part=part.strip()
        if not part: continue
        bits=part.split(); url=absolutize(bits[0],base); width_hint=0
        if len(bits)>1:
            m=re.match(r'(\\d+)w',bits[1])
            if m: width_hint=int(m.group(1))
        if url: out.append((url,width_hint))
    return out

def extract_jsonld_images(blocks, base):
    found=[]
    def walk(obj):
        if isinstance(obj,dict):
            for k,v in obj.items():
                kl=str(k).lower()
                if kl in {'image','thumbnailurl','contenturl'}:
                    if isinstance(v,str): found.append(absolutize(v,base))
                    elif isinstance(v,list):
                        for x in v:
                            if isinstance(x,str): found.append(absolutize(x,base))
                            elif isinstance(x,dict): walk(x)
                    elif isinstance(v,dict):
                        if isinstance(v.get('url'),str): found.append(absolutize(v['url'],base))
                        if isinstance(v.get('contentUrl'),str): found.append(absolutize(v['contentUrl'],base))
                else: walk(v)
        elif isinstance(obj,list):
            for x in obj: walk(x)
    for block in blocks:
        try: walk(json.loads(block))
        except Exception: pass
    return [u for u in found if u]

def declared_size(width,height):
    try: return int(width),int(height)
    except Exception: return None,None

def image_probe(url):
    """
    Download an image candidate and return dimension/quality metadata.
    Returns None for invalid or tiny images.
    """
    try:
        raw, final, ctype = request(url, timeout=PER_HTTP_SECONDS)
    except Exception:
        return None
    if ctype and not ctype.startswith("image/"):
        return None
    if len(raw) < 12000:
        return None
    try:
        img = Image.open(io.BytesIO(raw))
        width, height = img.size
    except Exception:
        return None
    if width < 700 or height < 390:
        return None
    pixels = width * height
    # Penalize extreme logo-like aspect ratios.
    ratio = width / max(1, height)
    if ratio > 4.0 or ratio < 0.35:
        return None
    return {
        "url": final or url,
        "raw": raw,
        "ctype": ctype,
        "width": width,
        "height": height,
        "pixels": pixels,
    }

def best_image_from_candidates(candidates):
    """
    candidates = [{'url':..., 'priority':...}, ...]
    Choose the highest-quality candidate by dimensions, with priority as tiebreaker.
    """
    best = None
    seen = set()
    for c in candidates:
        url = c.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        probe = image_probe(url)
        if not probe:
            continue
        probe["priority"] = c.get("priority", 0)
        score = probe["pixels"] + (probe["priority"] * 100000)
        probe["score"] = score
        if (best is None) or (score > best["score"]):
            best = probe
    return best
def request(url, timeout=PER_HTTP_SECONDS, accept=None):
    headers={
        "User-Agent":UA,
        "Accept-Language":"tr-TR,tr;q=0.9,en;q=0.5",
    }
    if accept:
        headers["Accept"]=accept
    req=urllib.request.Request(url,headers=headers)
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return r.read(), r.geturl(), r.headers.get_content_type()

def strip_tags(value):
    if not value:
        return ""
    value=html.unescape(value)
    value=re.sub(r"<script\b[^>]*>.*?</script>"," ",value,flags=re.I|re.S)
    value=re.sub(r"<style\b[^>]*>.*?</style>"," ",value,flags=re.I|re.S)
    value=re.sub(r"<[^>]+>"," ",value)
    return re.sub(r"\s+"," ",value).strip()

def parse_date(value):
    if not value:
        return None
    try:
        dt=email.utils.parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

def slugify(text, seed):
    trans=str.maketrans("çğıöşüÇĞİÖŞÜ","cgiosuCGIOSU")
    s=text.translate(trans).lower()
    s=re.sub(r"[^a-z0-9]+","-",s).strip("-")[:55]
    h=hashlib.sha1(seed.encode("utf-8")).hexdigest()[:7]
    return f"{s}-{h}" if s else f"haber-{h}"

def radar_score(title, count):
    low=title.lower()
    score=count
    if any(cue in low for cue in NEWS_CUES):
        score += 100
    # Dates and years often indicate concrete events.
    if re.search(r"\b(?:0?[1-9]|[12]\d|3[01])\s+(?:ocak|şubat|mart|nisan|mayıs|haziran|temmuz|ağustos|eylül|ekim|kasım|aralık)\b",low):
        score += 60
    if re.search(r"\b20\d{2}\b",low):
        score += 30
    return score

def fetch_radar(cfg):
    raw, _, _=request(cfg["radar_url"])
    text=raw.decode("utf-8","replace")
    p=AgendaParser()
    p.feed(text)

    seen=set()
    out=[]
    for text,href in p.rows:
        m=re.match(r"^(.*?)(?:\s+(\d+))$",text)
        if not m:
            continue
        title=html.unescape(m.group(1)).strip()
        count=int(m.group(2))
        low=title.lower()
        if len(title)<4 or len(title)>120:
            continue
        if any(x in low for x in BLOCK_PHRASES):
            continue
        norm=re.sub(r"\W+"," ",low).strip()
        if norm in seen:
            continue
        seen.add(norm)
        out.append({
            "radar_title":title,
            "count":count,
            "score":radar_score(title,count),
        })
    out.sort(key=lambda x:x["score"], reverse=True)
    return out[:cfg["radar_scan_limit"]]

def google_news_url(topic,cfg):
    g=cfg["google_news"]
    q=f'"{topic}" when:{g.get("when","1d")}'
    params={
        "q":q,
        "hl":g["hl"],
        "gl":g["gl"],
        "ceid":g["ceid"],
    }
    return g["base"]+"?"+urllib.parse.urlencode(params)

def parse_google_news(topic,cfg):
    url=google_news_url(topic,cfg)
    raw,_,_=request(url,accept="application/rss+xml,application/xml,text/xml,*/*")
    root=ET.fromstring(raw)
    channel=root.find("channel")
    if channel is None:
        return []
    results=[]
    for item in channel.findall("item")[:cfg["max_news_results_per_topic"]]:
        title=(item.findtext("title") or "").strip()
        link=(item.findtext("link") or "").strip()
        pub=parse_date(item.findtext("pubDate") or "")
        source_el=item.find("source")
        source=(source_el.text or "").strip() if source_el is not None else ""
        desc=strip_tags(item.findtext("description") or "")
        if title and link and source:
            results.append({
                "title":title,
                "link":link,
                "source":source,
                "published":pub,
                "description":desc,
            })
    return results

def distinct_publishers(results):
    seen=[]
    lowered=set()
    for r in results:
        key=re.sub(r"\s+"," ",r["source"].lower()).strip()
        if key and key not in lowered:
            lowered.add(key)
            seen.append(r["source"])
    return seen

def decode_google_url(url):
    """Decode Google News URL with a strict per-item time limit on Unix runners."""
    host=urllib.parse.urlparse(url).netloc.lower()
    if "news.google.com" not in host:
        return url

    old_handler = None
    can_alarm = hasattr(signal, "SIGALRM")
    try:
        if can_alarm:
            old_handler = signal.signal(signal.SIGALRM, _alarm_handler)
            signal.alarm(PER_DECODE_SECONDS)

        result=gnewsdecoder(url, interval=0.15)

        if result and result.get("status") and result.get("decoded_url"):
            decoded=result["decoded_url"]
            dhost=urllib.parse.urlparse(decoded).netloc.lower()
            if dhost and "google" not in dhost:
                return decoded
    except (DecodeTimeout, Exception):
        return None
    finally:
        if can_alarm:
            signal.alarm(0)
            if old_handler is not None:
                signal.signal(signal.SIGALRM, old_handler)
    return None

def resolve_article_meta(google_url):
    publisher_url=decode_google_url(google_url)
    if not publisher_url: return None
    phost=urllib.parse.urlparse(publisher_url).netloc.lower()
    if not phost or 'google' in phost: return None
    try: raw,final,ctype=request(publisher_url,timeout=PER_HTTP_SECONDS)
    except Exception: return None
    final_host=urllib.parse.urlparse(final).netloc.lower()
    if not final_host or 'google' in final_host: return None
    parser=MetaParser()
    try: parser.feed(raw.decode('utf-8','replace'))
    except Exception: pass
    desc=strip_tags(parser.description)
    if 'google haberler' in desc.lower() or 'google news' in desc.lower(): desc=''
    image_candidates=[]
    for priority,u in [(8,parser.og_image),(7,parser.twitter_image),(6,parser.image_src)]:
        u=absolutize(u,final)
        if u and not likely_bad_image(u): image_candidates.append({'url':u,'priority':priority})
    ow,oh=declared_size(parser.og_image_width,parser.og_image_height)
    if parser.og_image and ow and oh and ow>=900 and oh>=450:
        u=absolutize(parser.og_image,final)
        if u and not likely_bad_image(u): image_candidates.append({'url':u,'priority':12})
    for u in extract_jsonld_images(parser.jsonld_blocks,final):
        if u and not likely_bad_image(u): image_candidates.append({'url':u,'priority':9})
    for img in parser.inline_images[:40]:
        cls=img.get('class') or ''; base_pr=2
        if any(k in cls for k in ['hero','featured','article','main','post-image','content-image','news-image']): base_pr=5
        src=absolutize(img.get('src'),final)
        if src and not likely_bad_image(src,img): image_candidates.append({'url':src,'priority':base_pr})
        for srcset_url,width_hint in parse_srcset(img.get('srcset',''),final):
            if not srcset_url or likely_bad_image(srcset_url,img): continue
            pr=base_pr
            if width_hint>=1200: pr+=5
            elif width_hint>=900: pr+=4
            elif width_hint>=700: pr+=3
            elif width_hint>=500: pr+=1
            image_candidates.append({'url':srcset_url,'priority':pr})
    best=best_image_from_candidates(image_candidates)
    return {'url':final,'image':best['url'] if best else None,'description':desc,'imageWidth':best['width'] if best else None,'imageHeight':best['height'] if best else None,'imagePixels':best['pixels'] if best else None}

def ext_from(url,ctype):
    path=urllib.parse.urlparse(url).path.lower()
    for ext in (".jpg",".jpeg",".png",".webp"):
        if path.endswith(ext):
            return ".jpg" if ext==".jpeg" else ext
    return {
        "image/jpeg":".jpg",
        "image/png":".png",
        "image/webp":".webp",
    }.get(ctype,".jpg")

def download_image(url,article_id):
    probe=image_probe(url)
    if not probe:
        raise ValueError("yüksek çözünürlüklü görsel bulunamadı")
    ext=ext_from(probe["url"],probe["ctype"])
    dest=IMAGES/f"radar-{article_id}{ext}"
    dest.write_bytes(probe["raw"])
    return f"images/{dest.name}", probe["width"], probe["height"]

def format_local(dt):
    if not dt:
        return "Güncel"
    local=dt.astimezone(timezone(timedelta(hours=3)))
    months=["","Ocak","Şubat","Mart","Nisan","Mayıs","Haziran","Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"]
    return f"{local.day} {months[local.month]} {local.year} · {local:%H:%M}"

def usable_description(meta_list, topic, results):
    # Prefer publisher meta descriptions. Never use Google News generic prose.
    candidates=[]
    for m in meta_list:
        d=(m.get("description") or "").strip()
        low=d.lower()
        if "google haberler" in low or "google news" in low:
            continue
        if 80 <= len(d) <= 650:
            candidates.append(d)
    if candidates:
        d=max(candidates,key=len)
        if len(d)>480:
            d=d[:477].rsplit(" ",1)[0]+"…"
        return d

    # Fallback uses a real publisher headline, not system/meta language.
    if results:
        headline=clean_publisher_suffix(results[0]["title"],results[0]["source"])
        if headline:
            return headline.rstrip(".") + "."
    return topic.rstrip(".") + "."

def build_article(topic, results, meta_list, image_path, article_id):
    publishers=distinct_publishers(results)
    latest=max((r["published"] for r in results if r["published"]), default=datetime.now(timezone.utc))
    lead=usable_description(meta_list, topic, results)

    flow_items=[]
    for r in sorted(results,key=lambda x:x["published"] or datetime.min.replace(tzinfo=timezone.utc))[:4]:
        when=(r["published"].astimezone(timezone(timedelta(hours=3))).strftime("%H:%M")
              if r["published"] else "—")
        clean_title=clean_publisher_suffix(r["title"],r["source"])
        flow_items.append({
            "text":f"{when} · {r['source']} — {clean_title}",
            "tone":["blue","yellow","green","pink"][len(flow_items)%4]
        })

    sources=[]
    for r,m in zip(results,meta_list):
        url=(m or {}).get("url") or r["link"]
        clean_title=clean_publisher_suffix(r["title"],r["source"])
        sources.append({"label":f"{r['source']} — {clean_title}","url":url})
    # remove duplicate source URLs
    unique_sources=[]
    seen=set()
    for s in sources:
        if s["url"] not in seen:
            seen.add(s["url"])
            unique_sources.append(s)

    display_title=topic
    if generic_radar_title(topic) and results:
        candidate=clean_publisher_suffix(results[0]["title"],results[0]["source"])
        if len(candidate)>=12:
            display_title=candidate

    return {
        "id":article_id,
        "category":"Gündem",
        "date":format_local(latest),
        "title":display_title,
        "lead":lead,
        "hero":{
            "src":image_path,
            "alt":topic,
            "caption":f"Fotoğraf: ilgili haber kaynağı."
        },
        "sections":[
            {
                "type":"summary_cards",
                "items":[
                    {"label":"Son durum","text":lead,"tone":"yellow"},
                    {"label":"Öne çıkan ayrıntı","text":clean_publisher_suffix(results[1]["title"],results[1]["source"]) if len(results)>1 else lead,"tone":"green"},
                    {"label":"Yayın zamanı","text":format_local(latest),"tone":"blue"}
                ]
            },
            {
                "type":"highlight_paragraph",
                "heading":"Ayrıntılar",
                "paragraphs":[{"text":lead,"highlights":[]}]
            },
            {
                "type":"flow",
                "heading":"Haberlerde öne çıkanlar",
                "items":flow_items
            },
            {
                "type":"key_takeaway",
                "title":"Meselenin özü",
                "text":lead
            },
            {
                "type":"sources",
                "items":unique_sources[:5]
            }
        ],
        "generatedBy":"radar-verified",
        "verification":{
            "publisherCount":len(publishers),
            "publishers":publishers[:6]
        }
    }


def load_blocked_sources():
    try:
        data=json.loads(BLOCKED_SOURCES.read_text(encoding="utf-8"))
    except Exception:
        data={}
    domains=[d.lower().strip() for d in data.get("blocked_domains",[]) if d.strip()]
    publishers=[p.lower().strip() for p in data.get("blocked_publishers",[]) if p.strip()]
    return domains,publishers

def source_is_blocked(source_name, url):
    domains,publishers=load_blocked_sources()
    sname=(source_name or "").lower().strip()
    host=urllib.parse.urlparse(url or "").netloc.lower()
    host=host.split(":")[0]
    for p in publishers:
        if sname == p or p in sname:
            return True
    for d in domains:
        if host == d or host.endswith("." + d):
            return True
    return False


def load_preferred_sources():
    try:
        data=json.loads(PREFERRED_SOURCES.read_text(encoding="utf-8"))
    except Exception:
        data={}
    publishers=[p.lower().strip() for p in data.get("preferred_publishers",[]) if p.strip()]
    domains=[d.lower().strip() for d in data.get("preferred_domains",[]) if d.strip()]
    return publishers,domains

def preference_score(source_name, url):
    publishers,domains=load_preferred_sources()
    name=(source_name or "").lower().strip()
    host=urllib.parse.urlparse(url or "").netloc.lower().split(":")[0]
    score=0
    for i,p in enumerate(publishers):
        if name==p or p in name:
            score=max(score, 100-i)
    for i,d in enumerate(domains):
        if host==d or host.endswith("." + d):
            score=max(score, 100-i)
    return score

def clean_publisher_suffix(title, source=""):
    title=(title or "").strip()
    # Google News commonly appends " - Publisher". Remove only the final suffix.
    if source:
        suffix=r"\s*-\s*"+re.escape(source)+r"\s*$"
        title=re.sub(suffix,"",title,flags=re.I).strip()
    # Defensive cleanup for duplicated separators.
    title=re.sub(r"\s+[|–—-]\s*$","",title).strip()
    return title

def generic_radar_title(title):
    words=[w for w in re.split(r"\s+",(title or "").strip()) if w]
    low=(title or "").lower()
    if len(words)<=3:
        return True
    if low in {"gündem","son dakika","galatasaray","fenerbahçe","beşiktaş","chp","akp","mhp"}:
        return True
    return False

def article_result_score(result, meta):
    score=preference_score(result.get("source",""), meta.get("url",""))
    # Prefer newer reporting.
    pub=result.get("published")
    if pub:
        age=max(0,(datetime.now(timezone.utc)-pub).total_seconds()/3600)
        score += max(0, 24-int(age))
    # Prefer publisher pages with a real image and useful description.
    if meta.get("image"):
        score += 20
    d=(meta.get("description") or "").strip()
    if 100 <= len(d) <= 650:
        score += 15
    return score

def dedupe_similar_results(pairs):
    out=[]
    seen=set()
    for r,m in pairs:
        title=clean_publisher_suffix(r.get("title",""), r.get("source",""))
        norm=re.sub(r"[^a-z0-9çğıöşü]+"," ",title.lower()).strip()
        key=" ".join(norm.split()[:10])
        if key in seen:
            continue
        seen.add(key)
        out.append((r,m))
    return out

def verify_topic(topic,cfg,cutoff):
    raw_results=parse_google_news(topic["radar_title"],cfg)
    raw_results=[
        r for r in raw_results
        if r["published"] is None or r["published"] >= cutoff
    ]

    # Decode each Google News result to its real publisher page.
    resolved_pairs=[]
    for r in raw_results:
        # Block by publisher name even before URL resolution.
        if source_is_blocked(r.get("source",""), ""):
            continue
        meta=resolve_article_meta(r["link"])
        if not meta or not meta.get("url"):
            continue
        # Block again by the actual resolved publisher domain.
        if source_is_blocked(r.get("source",""), meta.get("url","")):
            continue
        resolved_pairs.append((r,meta))

    if not resolved_pairs:
        return None

    # Rank by editorial preference + recency + completeness, then remove near-duplicates.
    resolved_pairs.sort(
        key=lambda pair: article_result_score(pair[0],pair[1]),
        reverse=True
    )
    resolved_pairs=dedupe_similar_results(resolved_pairs)

    # Distinct publisher requirement is checked after resolution.
    results=[r for r,_ in resolved_pairs]
    meta_list=[m for _,m in resolved_pairs]
    pubs=distinct_publishers(results)
    if len(pubs)<cfg["min_distinct_publishers"]:
        return None

    # Require an actual publisher image, never Google branding.
    image_candidates=[]
    for meta in meta_list:
        u=meta.get("image")
        if not u:
            continue
        host=urllib.parse.urlparse(u).netloc.lower()
        low=u.lower()
        if "google" in host or "google" in low or "gnews" in low:
            continue
        image_candidates.append(u)

    if cfg.get("require_image",True) and not image_candidates:
        return None

    article_id=slugify(topic["radar_title"],"|".join(sorted(pubs)))
    image_path=None
    chosen_w=None
    chosen_h=None
    for image_url in image_candidates:
        try:
            image_path, chosen_w, chosen_h = download_image(image_url,article_id)
            break
        except Exception:
            continue

    if cfg.get("require_image",True) and not image_path:
        return None

    article=build_article(
        topic["radar_title"],
        results,
        meta_list,
        image_path,
        article_id
    )

    visible=json.dumps({
        "title":article["title"],
        "lead":article["lead"],
        "sections":article["sections"]
    },ensure_ascii=False).lower()
    forbidden=[
        "google haberler tarafından",
        "sonraki güncelleme turunda",
        "otomasyon",
        "şablon",
        "tasarım motoru",
        "kaynak çeşitliliği",
        "bu başlık"
    ]
    if any(x in visible for x in forbidden):
        return None
    return article

def main():
    ap=argparse.ArgumentParser(description="Gündem radarı + çok kaynaklı ücretsiz doğrulama")
    ap.add_argument("--dry-run",action="store_true")
    args=ap.parse_args()

    cfg=json.loads(CONFIG.read_text(encoding="utf-8"))
    cutoff=datetime.now(timezone.utc)-timedelta(hours=cfg["max_age_hours"])

    print("V17 — GÜNDEM RADARI + ÇOK KAYNAKLI DOĞRULAMA")
    print("="*62)
    print("Kaynak politikası: blocked_sources.json aktif")
    print("Görsel politikası: srcset + JSON-LD + meta veriden yüksek çözünürlüklü görsel seçilir")
    print("Radar okunuyor...")
    radar=fetch_radar(cfg)
    print(f"{len(radar)} aday başlık alındı.")
    print()

    verified=[]
    errors=[]
    started=time.monotonic()
    for idx,topic in enumerate(radar,1):
        elapsed=time.monotonic()-started
        if elapsed >= RUN_DEADLINE_SECONDS:
            print(f"Süre sınırına ulaşıldı ({int(elapsed)} sn). Bulunan haberlerle devam ediliyor.")
            break
        if len(verified)>=cfg["publish_limit"]:
            break

        print(f"[{idx:02d}/{len(radar):02d}] {topic['radar_title'][:72]}", flush=True)
        try:
            article=verify_topic(topic,cfg,cutoff)
            if not article:
                print("    elendi", flush=True)
                continue
            verified.append(article)
            print(f"    KABUL: {article['verification']['publisherCount']} yayın", flush=True)
        except Exception as e:
            errors.append(f"{topic['radar_title']}: {e}")
            print("    hata:",e, flush=True)

    if not verified:
        print()
        print("HATA: Bu turda doğrulanmış ve görselli güncel haber bulunamadı.")
        if errors:
            ERRORS.write_text("\n".join(errors),encoding="utf-8")

        current=json.loads(NEWS.read_text(encoding="utf-8"))
        manual=[a for a in current.get("articles",[]) if a.get("generatedBy")!="radar-verified"]
        empty_data={
            "articles":manual,
            "feed":[],
            "updatedAt":datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "updateMode":"radar-no-current-results"
        }
        text=json.dumps(empty_data,ensure_ascii=False,indent=2)
        NEWS.write_text(text,encoding="utf-8")
        DATA_JS.write_text("window.NEWS_DATA = "+text+";\n",encoding="utf-8")
        STATE.write_text(json.dumps({
            "lastSuccess":None,
            "lastAttempt":empty_data["updatedAt"],
            "count":0
        },ensure_ascii=False,indent=2),encoding="utf-8")
        print("Bu tur boş akış olarak kaydedildi.")
        return

    # Only verified current topics appear on homepage.
    feed=[{
        "id":a["id"],
        "articleId":a["id"],
        "category":"GÜNDEM",
        "title":a["title"],
        "spot":a["lead"],
        "image":a["hero"]["src"],
        "ready":True
    } for a in verified]

    current=json.loads(NEWS.read_text(encoding="utf-8"))
    manual=[a for a in current.get("articles",[]) if a.get("generatedBy")!="radar-verified"]
    new_data={
        "articles":manual+verified,
        "feed":feed,
        "updatedAt":datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "updateMode":"radar-multisource"
    }

    preview={
        "updatedAt":new_data["updatedAt"],
        "count":len(feed),
        "items":[
            {
                "title":a["title"],
                "publishers":a["verification"]["publishers"],
                "image":a["hero"]["src"]
            } for a in verified
        ]
    }
    PREVIEW.write_text(json.dumps(preview,ensure_ascii=False,indent=2),encoding="utf-8")

    if args.dry_run:
        print()
        print(f"DRY RUN: {len(feed)} doğrulanmış haber hazır.")
        return

    text=json.dumps(new_data,ensure_ascii=False,indent=2)
    NEWS.write_text(text,encoding="utf-8")
    DATA_JS.write_text("window.NEWS_DATA = "+text+";\n",encoding="utf-8")
    STATE.write_text(json.dumps({
        "lastSuccess":new_data["updatedAt"],
        "count":len(feed)
    },ensure_ascii=False,indent=2),encoding="utf-8")

    print()
    print(f"BAŞARILI: {len(feed)} doğrulanmış konu ana sayfaya yazıldı. Süre: {int(time.monotonic()-started)} sn.")
    for i,a in enumerate(verified,1):
        print(f"{i:02d}. {a['title']} [{a['verification']['publisherCount']} yayın]")

if __name__=="__main__":
    main()
