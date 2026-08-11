#!/usr/bin/env python3
import RADAR_UPDATE as core
from multi_radar import fetch_multi_radar

legacy_fetch = core.fetch_radar

# Çoklu radarın kaynak toplama süresi de workflow süresine dahil.
# Doğrulama için yaklaşık 2.5-3 dakika bırakıyoruz.
core.RUN_DEADLINE_SECONDS = 165
core.PER_DECODE_SECONDS = 5
core.PER_HTTP_SECONDS = 7


def combined_fetch(cfg):
    # Çoklu radar geniş aday havuzu toplar; pahalı doğrulamaya yalnız
    # en güçlü anlık adayları göndeririz. Eski başarılı haberler workflow
    # rezervuarında tutulduğu için her turda 40 konuyu yeniden taramak gereksizdir.
    fast_cfg = dict(cfg)
    fast_cfg['max_news_results_per_topic'] = min(int(cfg.get('max_news_results_per_topic', 5)), 3)
    fast_cfg['radar_scan_limit'] = max(int(cfg.get('radar_scan_limit', 40)), 40)

    rows = fetch_multi_radar(fast_cfg, legacy_fetch)

    # Birden fazla radarda görülen konular önceliklidir; ardından tek-radar
    # yüksek puanlı konular gelir. En fazla 16 konu pahalı doğrulamaya gider.
    rows.sort(
        key=lambda x: (
            len(x.get('radar_sources', [])),
            x.get('score', 0),
            x.get('count', 0)
        ),
        reverse=True
    )
    selected = rows[:16]
    print(f'Çoklu radar: {len(rows)} adaydan en güçlü {len(selected)} konu doğrulanacak.', flush=True)
    return selected


# core.main() config'i kendi okuduğu için konu başına sonuç sınırını burada da
# uygulamak üzere parser fonksiyonuna küçük bir sarmalayıcı ekliyoruz.
_original_parse_google_news = core.parse_google_news

def fast_parse_google_news(topic, cfg):
    local = dict(cfg)
    local['max_news_results_per_topic'] = min(int(cfg.get('max_news_results_per_topic', 5)), 3)
    return _original_parse_google_news(topic, local)

core.fetch_radar = combined_fetch
core.parse_google_news = fast_parse_google_news

if __name__ == '__main__':
    core.main()
