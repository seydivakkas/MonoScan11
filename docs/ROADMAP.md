# MonoScan11 — COLMAP'sız geliştirme yol haritası

**Karar: 16 Ekim 2026 · çalışma dalı:** `feature/native-sfm-n0-n3`
**Öncelik:** Tüm modüller ve arayüzleri önce tamamla; **gerçek fotoğraf analizi, gerçek iPhone 11 ile çekim, sahada ölçüm ve bağımsız gerçek veri kabulü en son (N9)**.

## Yürürlükteki geliştirme sırası

| Aşama | Mühendislik çıktısı | Gerçek fotoğraf kullanılacak mı? | Bitirme / kapı koşulu |
|---|---|---|---|
| N0 | Yerel (native) çekirdek; COLMAP üretim bağımlılığından ayrıştırma | Hayır | Dış COLMAP çalıştırma yok; eski veri biçimleri üretim sözleşmesi değil |
| N1 | Kamera modeli, intrinsics, rotasyonlar, ARKit/CV koordinat dönüşümleri | Hayır | Sayısal ve sentetik koordinat birim testleri |
| N2 | SIFT/özellik eşleştirme, reciprocal match, geometrik aykırı değer elemesi | Hayır | Sentetik doku/özellik eşleştirme testleri |
| N3 | Yerel seyrek SfM: başlangıç çifti, kamera kaydı, PnP, triangulation, tracks | Hayır | Sentetik çoklu-görüş ve başarısızlık testleri; gerçek başarı iddiası yok |
| **N4** | ARKit VIO kamera öncülleri, CV koordinat dönüşümü, ARKit-guided seyrek SfM ve robust Sim(3) | **Hayır** | **Kodlandı; sentetik CI PASS.** VIO gerçek ölçüm/kovaryans iddiası yok; cihaz kabulü N9 |
| **N5** | SciPy sparse BA: kamera + 3B nokta eşanlı optimizasyon, gauge sabitleme, dayanıklı hata, ARKit heuristik prior ve belirsizlik raporu | **Hayır** | **Kodlandı; sentetik CI doğrulama kapısı.** N5 kaynak ve önce/sonra hata kökeni korunur. Gerçek veri yalnız N9 |
| **N6** | Yoğun derinlik (MVS), derinlik füzyonu, yüzey/mesh ve geometri dışa aktarımı | **Hayır** | Sentetik ve lisanslı, programatik üretilen sahnelerde PLY/OBJ/mesh yapısal testleri |
| **N7** | Windows komutları, hata akışı, 3B önizleme/raporlama, iOS ekran/ZIP ve veri sözleşmesi bütünleşmesi | **Hayır** | UI sözleşmeleri, sahte veri göstermeme, offline/hata kurtarma kontrolü |
| **N8** | Sentetik uçtan uca regresyon, Windows/Linux CI, kaynak güvenliği, paketleme hazırlığı, performans profilleme | **Hayır** | Örneklemeye bağımlı olmayan test seti, sürüm/bağımlılık kontrolü; gerçek sonuç iddiası yok |
| **N9 — SON** | Gerçek iPhone 11/Xcode derlemesi ve cihaz kabulü, gerçek RGB+ARKit çekimi, **ilk gerçek fotoğraf analizi**, bağımsız referansla ölçüm doğrulaması, saha performansı ve kullanıcı kabulü | **Evet, yalnızca burada** | Veri/izlenebilirlik, görsel geometri, cihaz ve metrik hatalar kayıtlı; başarısızlık açıkça raporlanmalı |

**N0–N3:** Kodlanmış deneysel temel var; sentetik CI bulguları gerçek dünya doğruluğunu kanıtlamaz.
**N4:** ARKit VIO pozlarını doğrudan kullanan native guided sparse mod, robust Sim(3) hizalama ve bilinmeyen kovaryans beyanı kodlandı. Sentetik regresyon mevcut; gerçek cihaz/gerçek ölçüm kabulü N9'da. Ayrıntı: [N4_ARKIT_VIO_FUSION.md](N4_ARKIT_VIO_FUSION.md).
**N5:** Deneysel sparse BA motoru yazıldı; sentetik CI/güvenlik doğrulaması yapılıyor. [N5 BA sözleşmesi](N5_SPARSE_BUNDLE_ADJUSTMENT.md). Gerçek fotoğraf kabulü yok.
**N6–N8:** Henüz tamamlanmış kabul edilmez; geliştirme yapılacak.
**N9:** Bilinçli olarak ertelendi. Hiçbir erken aşamada kullanıcıdan fotoğraf isteme, gerçek sahne deneyi veya gerçek fotoğraf üzerinden model performansı iddiası oluşturma.

## Ara aşama doğrulama standardı

- **İzinli:** Analitik hesap, prosedürel sentetik görüntü, programatik/sentetik kamera pozları, mock ARKit manifesti, bağımsız birim testleri, CI, dosya sözleşmeleri, güvenlik/kod incelemesi, sentetik hız/bellek denemesi.
- **Ertelenen:** Gerçek çekim, kullanıcının gerçek fotoğrafları, internetten alınmış gerçek sahne veri setiyle rekonstrüksiyon deneyi, gerçek iPhone cihaz testi, gerçek odanın ölçülmesi, metrik hassasiyet değerlendirmesi.
- **Yasak iddia:** Yalnız sentetik testlerden `real_world_validated=true`, "milimetre doğruluk", "LiDAR eşdeğeri", tamamlanmış dense/mesh veya sahada başarılı tarama sonucu türetilmez.
- **Kod entegrasyonu:** N0–N8 kodu CI + gözden geçirme ile birleştirilebilir, fakat **gerçek dünyada doğrulanmış/stable sürüm** N9 kabulü olmadan yayımlanmaz.
- **Geriye uyumluluk:** iOS 18 ekran ailesi, ZIP/manifest sürüm-1 sözleşmesi, orijinal görüntüleri değiştirmeme, tekrar kullanılabilir kendi SFm motoru ve ağsız çalışma korunur.

## Önceden kullanılan yol haritası

`docs/SON_ASAMAYA_BIRAKILANLAR.md` ve ilk P0–P5 planı **tarihsel belgelerdir**, geçerli geliştirme sırasını belirlemez. Öncelik çatışması varsa bu dosyadaki **N0–N9** sırası ve `docs/COLMAP_FREE_ARCHITECTURE.md` esas alınır.
