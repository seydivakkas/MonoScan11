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
| **N9-A** | Kullanım hakları incelenmiş **kamusal gerçek iPhone/iPad görüntüleri**; özgün SHA, gerçek native SfM/BA/MVS kanıtı ve başarısızlık raporu | **Evet, N9-A'da** | **PARTIAL / REVIEW_REQUIRED:** Apple iPad Pro gerçek RGB, dört zaman penceresi; en iyi N4 **16/16** ve **215** seyrek nokta. N5 **PARTIAL** (ortanca 0,703→0,239 px), 8 kameralı ayrı N6 gerçek RGB deneyinde **675** füzyon noktası ve **3.365** açık mesh yüzü. Bağımsız fiziksel ölçüm yok | 
| **N9-B — SON** | Gerçek **iPhone 11/Xcode**, lens/K/distorsiyon kalibrasyonu, bağımsız ölçüm, fiziksel Windows ve erişilebilirlik kabulü | **Evet; donanım/ölçüm zorunlu** | **NOT TESTED:** sekiz bağımsız fiziksel kanıt kapısı; otomatik CI ile başarı verilemez |

**N0–N3:** Kodlanmış deneysel temel var; sentetik CI bulguları gerçek dünya doğruluğunu kanıtlamaz.
**N4:** ARKit VIO pozlarını doğrudan kullanan native guided sparse mod, robust Sim(3) hizalama ve bilinmeyen kovaryans beyanı kodlandı. Sentetik regresyon mevcut; gerçek cihaz/gerçek ölçüm kabulü N9'da. Ayrıntı: [N4_ARKIT_VIO_FUSION.md](N4_ARKIT_VIO_FUSION.md).
**N5:** Gerçek Apple iPad Pro RGB/K/poz girdisinden oluşturulan 16 kameralı modelde BA denendi; 0,703→0,239 px iç reprojeksiyon iyileşmesi, native PARTIAL. [N5 BA sözleşmesi](N5_SPARSE_BUNDLE_ADJUSTMENT.md). Bağımsız fiziksel doğruluk kabulü yok.
**N6:** Gerçek Apple RGB'den ayrıca oluşturulan 8 kameralı N4/N5 modeli ile CPU plane-sweep çalıştırıldı; 675 voxel noktası / 3.365 yüzlü açık mesh üretildi. Çekirdek native state SYNTHETIC_GEOMETRY_ONLY, model metrik doğruluğu ispatlanmadı. [N6 Dense MVS sözleşmesi](N6_DENSE_MVS.md).
**N7:** Çevrimdışı Windows Tkinter iş istasyonu ilk sürümü ve iPhone ZIP sözleşmesi kodlandı; yalnız sentetik headless testler ve Windows Tk açılış smoke testi tamam. [N7 arayüz entegrasyonu](N7_WINDOWS_WORKSTATION.md). Gerçek fotoğraf ve fiziksel cihaz kabulü yalnız N9.
**N8:** Sentetik tam zincir testi, kaynak paketi doğrulaması, crash recovery incelemesi, Win32 bellek raporu ve erişilebilirlik aday denetimleri eklendi. [N8 kabul sözleşmesi](N8_SYNTHETIC_ACCEPTANCE.md). N9 gerçek fotoğraf ve bağımsız metrik kabulünden önce stable sürüm yok.
**N9-A:** Gerçek kamusal fotoğraf deneyleri için SHA-256 kaynak defteri, kamera modu denetimi, bağımsız kalibrasyon gereksinimi ve native hata/başarı kanıtı eklendi. [N9-A / N9-B ayrık protokol](N9A_N9B_SEPARATE_ACCEPTANCE.md). İlk ARKitScenes denemesi 3/16 kayıtta kalmıştı; 4 saniyelik üç yakın-zamanlı gerçek RGB grubuyla kayıt 13/16, 15/16 ve **16/16** oldu. N4'te tek kamerada mükerrer 3B nokta gözlemi düzeltildikten sonra N5 gerçek BA çıktısı (0,703→0,239 px, native PARTIAL), ayrı 8 kameralı gerçek N6 (675 yoğun nokta, 3.365 açık mesh yüzü) oluştu. **N9-A yazılım geometri deneyi PARTIAL/REVIEW_REQUIRED, metrik/cihaz kabulü YOK.** [18 Ekim tam analiz](N9A_TEMPORAL_REAL_TRIAL.md), [JSON kanıt](evidence/N9A_TEMPORAL_REAL_N4_N5_N6_2026-10-18.json), [ilk gerçek deney](evidence/N9A_ARKITSCENES_REAL_2026-10-17.json).
**N9-B:** iPhone 11 cihazı, Xcode, gerçek lens/kalibrasyon, bağımsız holdout ölçümleri, fiziksel Windows ve erişilebilirlik testleri için B01–B08 denetim programı ayrı tutuldu. **Sekizi de NOT_TESTED**; SHA-256'lı dosya varlığı bile insanın fiziksel incelemesi olmadan PASS değildir. [N9 veri/cihaz kapıları](N9_DATASET_AND_DEVICE_ACCEPTANCE.md).

## Ara aşama doğrulama standardı

- **İzinli:** Analitik hesap, prosedürel sentetik görüntü, programatik/sentetik kamera pozları, mock ARKit manifesti, bağımsız birim testleri, CI, dosya sözleşmeleri, güvenlik/kod incelemesi, sentetik hız/bellek denemesi.
- **Aşama sınırı:** N0–N8 boyunca gerçek fotoğraf/kamusal sahne analizi yasaktı. **N9-A'da** erişim ve hakları doğrulanan kamusal gerçek fotoğraflarla yalnız yazılım proxy denemesi yapılabilir; **N9-B'de** fiziksel iPhone11, gerçek sahne ölçümü ve Windows kullanıcı kabulü gereklidir.
- **Yasak iddia:** Yalnız sentetik testlerden `real_world_validated=true`, "milimetre doğruluk", "LiDAR eşdeğeri", tamamlanmış dense/mesh veya sahada başarılı tarama sonucu türetilmez.
- **Kod entegrasyonu:** N0–N8 kodu CI + gözden geçirme ile birleştirilebilir, fakat **gerçek dünyada doğrulanmış/stable sürüm** N9 kabulü olmadan yayımlanmaz.
- **Geriye uyumluluk:** iOS 18 ekran ailesi, ZIP/manifest sürüm-1 sözleşmesi, orijinal görüntüleri değiştirmeme, tekrar kullanılabilir kendi SFm motoru ve ağsız çalışma korunur.

## Önceden kullanılan yol haritası

`docs/SON_ASAMAYA_BIRAKILANLAR.md` ve ilk P0–P5 planı **tarihsel belgelerdir**, geçerli geliştirme sırasını belirlemez. Öncelik çatışması varsa bu dosyadaki **N0–N9** sırası ve `docs/COLMAP_FREE_ARCHITECTURE.md` esas alınır.
