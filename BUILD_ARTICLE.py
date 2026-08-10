#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
NEWS = ROOT / "news.json"
DATA_JS = ROOT / "data.js"
IMAGES = ROOT / "images"

ALLOWED_TYPES = {
    "summary_cards",
    "highlight_paragraph",
    "quote",
    "flow",
    "key_takeaway",
    "sources",
}

FORBIDDEN_VISIBLE_PHRASES = [
    "otomasyon slotu",
    "geliştirme slotu",
    "işlev testi",
    "şablon testi",
    "bu kart neden var",
    "tasarım motoru",
    "otomasyon kuyruğu",
    "doğrulama / içerik üretimi bekliyor",
    "bir sonraki otomasyon aşamasında",
]

def fail(message: str) -> None:
    print(f"HATA: {message}")
    raise SystemExit(1)

def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"Dosya bulunamadı: {path}")
    except json.JSONDecodeError as e:
        fail(f"JSON hatası: {e}")

def text_fields(obj):
    if isinstance(obj, dict):
        for value in obj.values():
            yield from text_fields(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from text_fields(value)
    elif isinstance(obj, str):
        yield obj

def validate_visible_text(article):
    joined = "\n".join(text_fields(article)).lower()
    # URLs and technical keys are not visible prose, but these phrases should never appear anywhere
    # in generated article content.
    for phrase in FORBIDDEN_VISIBLE_PHRASES:
        if phrase in joined:
            fail(f"Görünür metinde yasak geliştirme ifadesi bulundu: {phrase!r}")

def validate_payload(payload, current):
    required = ["id", "category", "date", "title", "lead", "hero", "sections"]
    for key in required:
        if not payload.get(key):
            fail(f"Eksik zorunlu alan: {key}")

    if not re.match(r"^[a-z0-9][a-z0-9-]{2,80}$", payload["id"]):
        fail("id yalnız küçük harf, rakam ve tire içermeli.")

    hero = payload["hero"]
    for key in ["src", "alt", "caption"]:
        if not hero.get(key):
            fail(f"hero.{key} eksik.")

    if not isinstance(payload["sections"], list) or not payload["sections"]:
        fail("sections boş olamaz.")

    types = []
    for i, section in enumerate(payload["sections"], start=1):
        t = section.get("type")
        if t not in ALLOWED_TYPES:
            fail(f"{i}. bölümde bilinmeyen modül: {t}")
        types.append(t)

    if "sources" not in types:
        fail("Her yayımlanabilir haberde sources modülü bulunmalı.")

    source_sections = [s for s in payload["sections"] if s.get("type") == "sources"]
    links = []
    for section in source_sections:
        links.extend(section.get("items", []))
    if not links:
        fail("Kaynak listesi boş.")
    for item in links:
        if not item.get("label") or not item.get("url", "").startswith(("http://", "https://")):
            fail("Kaynakların label ve http(s) URL alanları olmalı.")

    validate_visible_text(payload)

    existing_article = next((a for a in current.get("articles", []) if a.get("id") == payload["id"]), None)
    image_ref = hero["src"].replace("\\", "/")

    # A local image must live under images/.
    if not image_ref.startswith("images/"):
        fail("hero.src site içinde images/... biçiminde olmalı.")

    # Prevent accidental reuse of another article's hero image.
    for article in current.get("articles", []):
        if article.get("id") == payload["id"]:
            continue
        other = article.get("hero", {}).get("src")
        if other and other == image_ref:
            fail(f"Aynı ana görsel başka haberde kullanılıyor: {article.get('title')}")

    return existing_article is not None

def install_image(spec, article_id):
    IMAGES.mkdir(exist_ok=True)
    image = spec.get("image")
    if not image:
        fail("Üst düzey image alanı eksik. local_path veya url verilmeli.")

    ext = image.get("extension", "jpg").lower().lstrip(".")
    if ext not in {"jpg", "jpeg", "png", "webp"}:
        fail("Desteklenmeyen görsel uzantısı.")

    destination = IMAGES / f"{article_id}.{ext}"

    if image.get("local_path"):
        source = Path(image["local_path"]).expanduser().resolve()
        if not source.exists():
            fail(f"Yerel görsel bulunamadı: {source}")
        shutil.copy2(source, destination)
    elif image.get("url"):
        req = urllib.request.Request(
            image["url"],
            headers={"User-Agent": "Mozilla/5.0"}
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                destination.write_bytes(response.read())
        except Exception as e:
            fail(f"Görsel indirilemedi: {e}")
    else:
        fail("image.local_path veya image.url alanlarından biri gerekli.")

    if destination.stat().st_size < 10_000:
        destination.unlink(missing_ok=True)
        fail("Görsel dosyası şüpheli derecede küçük (<10 KB).")

    return f"images/{destination.name}"

def atomic_write(path: Path, text: str):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)

def main():
    parser = argparse.ArgumentParser(
        description="Gündem Defteri'ne doğrulanmış bir haberi tasarım motoru formatında ekler."
    )
    parser.add_argument("input", help="Haber JSON dosyası")
    parser.add_argument("--validate-only", action="store_true",
                        help="Dosyaları değiştirmeden yalnız doğrulama yap")
    parser.add_argument("--replace", action="store_true",
                        help="Aynı id varsa haberi güncelle")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    payload = load_json(input_path)
    current = load_json(NEWS)

    # Install/resolve image first only outside validate-only; for validation, normalize expected target.
    article = payload.get("article")
    if not article:
        fail("JSON içinde article nesnesi bulunmalı.")

    article_id = article.get("id", "")
    image_spec = payload.get("image", {})
    ext = image_spec.get("extension", "jpg").lower().lstrip(".")
    expected_src = f"images/{article_id}.{ext}"
    article.setdefault("hero", {})["src"] = expected_src

    exists = validate_payload(article, current)
    if exists and not args.replace:
        fail("Bu id zaten mevcut. Güncellemek için --replace kullanın.")

    # Feed data is intentionally separate from article prose.
    feed = payload.get("feed", {})
    if not feed.get("category"):
        feed["category"] = article["category"].upper()
    if not feed.get("title"):
        feed["title"] = article["title"]
    if not feed.get("spot"):
        feed["spot"] = article["lead"]

    for required in ["category", "title", "spot"]:
        if not feed.get(required):
            fail(f"feed.{required} eksik.")
    for phrase in FORBIDDEN_VISIBLE_PHRASES:
        if phrase in "\n".join(text_fields(feed)).lower():
            fail(f"Ana sayfa metninde yasak geliştirme ifadesi bulundu: {phrase!r}")

    if args.validate_only:
        # Validate local source existence or URL presence without writing.
        if image_spec.get("local_path"):
            p = Path(image_spec["local_path"]).expanduser()
            if not p.exists():
                fail(f"Yerel görsel bulunamadı: {p}")
        elif not image_spec.get("url"):
            fail("image.local_path veya image.url gerekli.")
        print("DOĞRULAMA BAŞARILI")
        print("Haber:", article["title"])
        print("Modüller:", ", ".join(s["type"] for s in article["sections"]))
        return

    actual_src = install_image(image_spec, article_id)
    article["hero"]["src"] = actual_src

    # Final uniqueness check after image resolution.
    validate_payload(article, current)

    articles = [a for a in current.get("articles", []) if a.get("id") != article_id]
    articles.append(article)

    feed_item = {
        "id": article_id,
        "articleId": article_id,
        "category": feed["category"],
        "title": feed["title"],
        "spot": feed["spot"],
        "image": actual_src,
        "ready": True,
    }
    feed_items = [f for f in current.get("feed", []) if f.get("articleId") != article_id]
    feed_items.append(feed_item)

    new_data = dict(current)
    new_data["articles"] = articles
    new_data["feed"] = feed_items
    new_data["updatedAt"] = datetime.now().isoformat(timespec="seconds")

    # Backups before mutation.
    backup_dir = ROOT / "backups"
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(NEWS, backup_dir / f"news-{stamp}.json")
    if DATA_JS.exists():
        shutil.copy2(DATA_JS, backup_dir / f"data-{stamp}.js")

    text = json.dumps(new_data, ensure_ascii=False, indent=2)
    atomic_write(NEWS, text)
    atomic_write(DATA_JS, "window.NEWS_DATA = " + text + ";\n")

    print("YAYINA EKLENDİ")
    print("ID:", article_id)
    print("Başlık:", article["title"])
    print("Görsel:", actual_src)
    print("Toplam haber:", len(feed_items))

if __name__ == "__main__":
    main()
