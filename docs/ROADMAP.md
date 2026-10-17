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
| **N6** | CPU plane-sweep MVS, çoklu derinlik tutarlılığı, voxel füzyonu, açık OBJ mesh ve PLY | **Hayır** | **Deneysel kodlandı.** Prosedürel sentetik 4-kamera görüntüleriyle geometrik test; 3–8 kamera, düşük çözünürlüklü CPU sınırı |
| **N7** | Windows Tkinter proje yönetimi, güvenli iPhone ZIP import, aşama bazlı işlem hattı, gerçek PLY/OBJ önizleme, kanıt ve belirsizlik panelleri | **Hayır** | **İlk arayüz kodlandı; Windows Tk açılış smoke testi ve Swift ZIP→N7 import sözleşmesi CI PASS.** Son ergonomik ve gerçek cihaz kabulü bekliyor |
| **N8** | Prosedürel ZIP→N4→N5→N6→N7 gerçek algoritma akışı; tekrar edilebilirlik, süre/bellek raporu, klavye/kontrast, güvenli kurtarma ve kaynak ZIP | **Hayır** | **Kodlandı; sentetik CI doğrulaması.** Kaynak ZIP bağımsız kurulum değildir; fiziksel Windows/iPhone kabulü N9 |
| **N9-A** | Kullanım hakları incelenmiş **kamusal gerçek iPhone/iPad görüntüleri**; özgün SHA, gerçek native SfM/BA/MVS kanıtı ve başarısızlık raporu | **Evet, N9-A'da** | **BLOCKED — SOURCE UNAVAILABLE:** dış veri adaptörleri ve ayrı N9-A değerlendirme CLI hazır; indirilen gerçek fotoğraf ve gerçek SfM koşusu yok | 
| **N9-B — SON** | Gerçek **iPhone 11/Xcode**, lens/K/distorsiyon kalibrasyonu, bağımsız ölçüm, fiziksel Windows ve erişilebilirlik kabulü | **Evet; donanım/ölçüm zorunlu** | **NOT TESTED:** sekiz bağımsız fiziksel kanıt kapısı; otomatik CI ile başarı verilemez |

**N0–N3:** Kodlanmış deneysel temel var; sentetik CI bulguları gerçek dünya doğruluğunu kanıtlamaz.
**N4:** ARKit VIO pozlarını doğrudan kullanan native guided sparse mod, robust Sim(3) hizalama ve bilinmeyen kovaryans beyanı kodlandı. Sentetik regresyon mevcut; gerçek cihaz/gerçek ölçüm kabulü N9'da. Ayrıntı: [N4_ARKIT_VIO_FUSION.md](N4_ARKIT_VIO_FUSION.md).
**N5:** Deneysel sparse BA motoru yazıldı; sentetik CI/güvenlik doğrulaması yapılıyor. [N5 BA sözleşmesi](N5_SPARSE_BUNDLE_ADJUSTMENT.md). Gerçek fotoğraf kabulü yok.
**N6:** CPU plane-sweep, farklı kameralarda derinlik tutarlılığı, voxel füzyonu ve açık mesh kodlandı. Sentetik testler ve CI doğrulanıyor. [N6 Dense MVS sözleşmesi](N6_DENSE_MVS.md).
**N7:** Çevrimdışı Windows Tkinter iş istasyonu ilk sürümü ve iPhone ZIP sözleşmesi kodlandı; yalnız sentetik headless testler ve Windows Tk açılış smoke testi tamam. [N7 arayüz entegrasyonu](N7_WINDOWS_WORKSTATION.md). Gerçek fotoğraf ve fiziksel cihaz kabulü yalnız N9.
**N8:** Sentetik tam zincir testi, kaynak paketi doğrulaması, crash recovery incelemesi, Win32 bellek raporu ve erişilebilirlik aday denetimleri eklendi. [N8 kabul sözleşmesi](N8_SYNTHETIC_ACCEPTANCE.md). N9 gerçek fotoğraf ve bağımsız metrik kabulünden önce stable sürüm yok.
**N9-A:** Gerçek kamusal fotoğraf deneyleri için SHA-256 kaynak defteri, kamera modu denetimi, bağımsız kalibrasyon gereksinimi ve native hata/başarı kanıtı eklendi. [N9-A / N9-B ayrık protokol](N9A_N9B_SEPARATE_ACCEPTANCE.md). Mevcut gerçek internet arşivi indirme denemesi başarısız olduğundan **N9-A BLOCKED_SOURCE_UNAVAILABLE**. [Kanıt defteri](evidence/N9A_BASELINE_BLOCKED_2026-10-17.json).
**N9-B:** iPhone 11 cihazı, Xcode, gerçek lens/kalibrasyon, bağımsız holdout ölçümleri, fiziksel Windows ve erişilebilirlik testleri için B01–B08 denetim programı ayrı tutuldu. **Sekizi de NOT_TESTED**; SHA-256'lı dosya varlığı bile insanın fiziksel incelemesi olmadan PASS değildir. [N9 veri/cihaz kapıları](N9_DATASET_AND_DEVICE_ACCEPTANCE.md).

## Ara aşama doğrulama standardı

- **İzinli:** Analitik hesap, prosedürel sentetik görüntü, programatik/sentetik kamera pozları, mock ARKit manifesti, bağımsız birim testleri, CI, dosya sözleşmeleri, güvenlik/kod incelemesi, sentetik hız/bellek denemesi.
- **Aşama sınırı:** N0–N8 boyunca gerçek fotoğraf/kamusal sahne analizi yasaktı. **N9-A'da** erişim ve hakları doğrulanan kamusal gerçek fotoğraflarla yalnız yazılım proxy denemesi yapılabilir; **N9-B'de** fiziksel iPhone11, gerçek sahne ölçümü ve Windows kullanıcı kabulü gereklidir.
- **Yasak iddia:** Yalnız sentetik testlerden `real_world_validated=true`, "milimetre doğruluk", "LiDAR eşdeğeri", tamamlanmış dense/mesh veya sahada başarılı tarama sonucu türetilmez.
- **Kod entegrasyonu:** N0–N8 kodu CI + gözden geçirme ile birleştirilebilir, fakat **gerçek dünyada doğrulanmış/stable sürüm** N9 kabulü olmadan yayımlanmaz.
- **Geriye uyumluluk:** iOS 18 ekran ailesi, ZIP/manifest sürüm-1 sözleşmesi, orijinal görüntüleri değiştirmeme, tekrar kullanılabilir kendi SFm motoru ve ağsız çalışma korunur.

## Önceden kullanılan yol haritası

`docs/SON_ASAMAYA_BIRAKILANLAR.md` ve ilk P0–P5 planı **tarihsel belgelerdir**, geçerli geliştirme sırasını belirlemez. Öncelik çatışması varsa bu dosyadaki **N0–N9** sırası ve `docs/COLMAP_FREE_ARCHITECTURE.md` esas alınır.
