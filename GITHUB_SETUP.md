# V18 — GitHub'a canlı kurulum

## 1. Yeni bir GitHub reposu oluştur
Public repo önerilir. Örneğin: `gundem-defteri`.

## 2. Bu klasörün İÇİNDEKİ tüm dosyaları repo köküne yükle
`.github` klasörü de mutlaka yüklenmeli.

## 3. GitHub Pages'i Actions'a bağla
Repo → **Settings** → **Pages** → **Build and deployment** → **Source: GitHub Actions**.

## 4. İlk testi elle çalıştır
Repo → **Actions** → `Gündem Defteri - 30 Dakika Güncelle ve Yayınla` → **Run workflow**.

İşlem başarılıysa aynı workflow:
- gündemi tarar,
- haberleri doğrular,
- fotoğrafları indirir,
- `news.json` / `data.js` dosyalarını günceller,
- değişiklikleri repo'ya commit eder,
- siteyi aynı çalışma içinde GitHub Pages'e deploy eder.

## 5. Bundan sonra otomatik
Cron: `13,43 * * * *`

Yani yaklaşık her 30 dakikada bir, saatin **13. ve 43. dakikalarında** çalışır.

## Sitede kontrol
Logonun altında `Son güncelleme:` satırı görünür.
Bu zaman değişmiyorsa Actions sekmesindeki son workflow çalışmasını kontrol et.

## Ücretli API yok
Bu sürüm:
- OpenAI API kullanmaz,
- API anahtarı istemez,
- radar + Google News RSS + gerçek yayıncı sayfalarıyla çalışır.

## Kaynak politikası
`blocked_sources.json`: kullanılmayacak kaynaklar.
`preferred_sources.json`: tercih sırası yüksek kaynaklar.
