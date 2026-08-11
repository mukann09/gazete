#!/usr/bin/env python3
import RADAR_UPDATE as core
from multi_radar import fetch_multi_radar

legacy_fetch = core.fetch_radar

# GitHub Actions içinde güvenli çalışma süresi.
core.RUN_DEADLINE_SECONDS = 150
core.PER_DECODE_SECONDS = 4
core.PER_HTTP_SECONDS = 6


def combined_fetch(cfg):
    fast_cfg = dict(cfg)
    fast_cfg['max_news_results_per_topic'] = min(int(cfg.get('max_news_results_per_topic', 5)), 3)
    fast_cfg['radar_scan_limit'] = max(int(cfg.get('radar_scan_limit', 40)), 40)

    rows = fetch_multi_radar(fast_cfg, legacy_fetch)
    rows.sort(
        key=lambda x: (
            len(x.get('radar_sources', [])),
            x.get('score', 0),
            x.get('count', 0)
        ),
        reverse=True
    )

    # Rezervuar sistemi nedeniyle her turda yalnız en güçlü 12 yeni aday yeterli.
    selected = rows[:12]
    print(f'Çoklu radar: {len(rows)} adaydan en güçlü {len(selected)} konu doğrulanacak.', flush=True)
    return selected


_original_parse_google_news = core.parse_google_news

def fast_parse_google_news(topic, cfg):
    local = dict(cfg)
    local['max_news_results_per_topic'] = min(int(cfg.get('max_news_results_per_topic', 5)), 3)
    return _original_parse_google_news(topic, local)


# Asıl darboğaz: bazı yayıncı sayfalarında onlarca görsel adayı tek tek
# indirilip Pillow ile ölçülüyordu. Yalnız en yüksek öncelikli 5 adayı test et.
_original_best_image = core.best_image_from_candidates

def fast_best_image_from_candidates(candidates):
    unique = {}
    for c in candidates:
        url = c.get('url')
        if not url:
            continue
        prev = unique.get(url)
        if prev is None or c.get('priority',0) > prev.get('priority',0):
            unique[url] = c
    ranked = sorted(
        unique.values(),
        key=lambda c: c.get('priority',0),
        reverse=True
    )[:5]
    return _original_best_image(ranked)


core.fetch_radar = combined_fetch
core.parse_google_news = fast_parse_google_news
core.best_image_from_candidates = fast_best_image_from_candidates

if __name__ == '__main__':
    core.main()
