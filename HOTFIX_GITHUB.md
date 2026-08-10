# V18.1 GitHub hotfix

GitHub reposunda yalnız iki ana dosyanın değiştirilmesi yeterlidir:

1. `RADAR_UPDATE.py`
2. `.github/workflows/radar-update.yml`

Ayrıca `radar_config.json` daha hızlı tarama için güncellenmiştir.

Değişiklikler:
- 22 radar adayı
- en fazla 12 yayın
- konu başına en fazla 4 Google News sonucu
- HTTP isteklerinde ~9 sn üst sınır
- Google News decoder için Unix'te 7 sn üst sınır
- toplam radar çalışması ~210 sn'de kısmi sonuçla kapanır
- workflow radar adımı maksimum 5 dakika
- güncel haber bulunamazsa workflow kırmızıya düşmez
