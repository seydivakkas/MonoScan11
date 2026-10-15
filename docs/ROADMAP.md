> **2026-10-15 native dalı notu:** COLMAP bağımlılığından ayrışma N0–N3
> kod çalışması açılmıştır. N1 kamera testleri ve N2/N3 deneysel pipeline mevcut;
> gerçek cihaz, gerçek sahne, BA, yoğun MVS ve ölçüm kabulü tamamlanmamıştır.
> Aşağıdaki önceki plan tarihsel referanstır, yeni üretim iş akışı değildir.

# MonoScan11 yol haritası — Windows öncelikli

| Aşama | Kapsam | Durum |
|---|---|---|
| P0 | Kod tabanı, sentetik triangulation, fotoğraf/manifest validasyonu, COLMAP runner, otomatik testler, GitHub CI | **Kod tamam / yerel Python test PASS** |
| P1-WIN | Windows'ta gerçek iPhone 11 fotoğraflarıyla COLMAP sparse, sonuç raporu, örnek benchmark; blur/örtüşme analizi | **Gerçek veri bekliyor** |
| P1-DENSE | Uygun GPU varsa dense MVS, fused PLY ve mesh; sparse baseline ile karşılaştırma | **Donanım doğrulaması bekliyor** |
| P2-IOS | XcodeGen/Xcode build, iPhone 11 ARKit yaşam döngüsü, 30+ RGB/pose yakalama, dosya aktarımı | **En son aşama: macOS gerekli** |
| P3-FUSION | ARKit VIO ile SfM pozları Sim(3) hizalama, hareket belirsizliği, ön/arka kamera ve kalibrasyon denetimleri | **P2 sonrası** |
| P4-QUALITY | 3 sahnede kalibre edilmiş referanslar, metrik hata, tekrar edilebilirlik, kullanıcı kabulü | **Gerçek deney bekliyor** |
| P5-RELEASE | iOS dağıtım paketi, stabil sürüm ve sahadan kabul kanıtı | **Hepsi PASS olmadan yapılmayacak** |

Açık işlerin tek kaynağı [`SON_ASAMAYA_BIRAKILANLAR.md`](SON_ASAMAYA_BIRAKILANLAR.md) ve [`VALIDATION_PLAN.md`](VALIDATION_PLAN.md).
