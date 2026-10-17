# N9-A — Gerçek ARKitScenes RGB zamansal karşılaştırması, N4/N5/N6

**Tarih:** 18 Ekim 2026 (Türkiye). **Güncel durum:** PARTIAL / REVIEW_REQUIRED.
**Girdi:** Apple ARKitScenes Validation, video 41069046, iPad Pro ile çekilmiş gerçek RGB; iPhone 11 değildir.
**Tam sayısal kanıt:** [N9-A JSON](evidence/N9A_TEMPORAL_REAL_N4_N5_N6_2026-10-18.json), [Actions koşusu](https://github.com/seydivakkas/MonoScan11/actions/runs/39073111223), [özgün JSON artefaktı](https://github.com/seydivakkas/MonoScan11/actions/runs/39073111223/artifacts/12115703660).

## Zamansal gruplar — dört grubun tamamı raporlandı

| Önceden tanımlı RGB seçimi | Süre | Kaydedilen kamera | N4 sparse nokta | Ortanca reprojeksiyon | N4 durumu |
|---|---:|---:|---:|---:|---|
| Önceki tüm kayıt aralığı | 119,784 sn | 3/16 | 28 | 0,269 px | PARTIAL |
| İlk 4 saniyelik pencere | 3,816 sn | 13/16 | 96 | 0,566 px | PARTIAL |
| Orta 4 saniyelik pencere | 3,898 sn | 15/16 | 172 | 0,880 px | PARTIAL |
| Son 4 saniyelik pencere | 3,899 sn | **16/16** | **215** | 0,703 px | **SUCCESS_SPARSE** |

**Seçim kuralı:** en fazla kayıtlı kamera → en fazla seyrek nokta → en yüksek kayıt oranı → düşük reprojeksiyon hatası. Tüm başarısız ve kısmi adaylar raporda saklandı; sonuçlar sonradan seçilerek gizlenmedi.

## Hata düzeltmesi — N4 gözlem bütünlüğü

İlk gerçek denemede N5, 'Duplicate track image/feature observation' gerekçesiyle reddedilmişti. N4 nokta izlerini genişletirken aynı 3B noktaya aynı kameradan ikinci bir keypoint bağlayabiliyordu. Bu mükerrer gözlem N4'te yasaklandı; geometri yazılmadan önce tekillik sözleşmesi denetleniyor. Kaynaktaki RGB, .pincam veya ARKit trajektori üzerinde değişiklik yapılmadı.

## N5 — Gerçek RGB girdisinden oluşturulan 16 kameralı model

| Metrik | Sonuç |
|---|---:|
| Kayıtlı kamera | 16 |
| BA giriş seyrek nokta | 215 |
| Fotoğraf gözlemi | 685 |
| Ortanca reprojeksiyon önce | 0,703 px |
| Ortanca reprojeksiyon sonra | **0,239 px** |
| p90 reprojeksiyon önce | 2,152 px |
| p90 reprojeksiyon sonra | **0,686 px** |
| Native N5 durumu | **PARTIAL** |

N5 çıktısı ve optimization.json dosyası gerçek hesaplamayla oluştu, SHA-256 kayıtları kanıt JSON'unda. Hata düşüşü **içsel 2B reprojeksiyon uyumudur**; bağımsız metre hassasiyeti veya sensör kovaryansı değildir. Native 'PARTIAL' etiketi başarıya yükseltilmedi.

## N6 — Aynı pencerenin sekiz gerçek karelik ayrı alt oturumu

N6 prototipi 3–8 kayıtlı kameraya izin verdiği için 16 kameralı modelden kamera silinmedi. Kaynak ARKitScenes kayıtlarından aynı gerçek 4 saniyelik pencerede yeni 8 karelik oturum kuruldu; özgün PNG/K/poz bilgileri doğrulandı.

| İşlem | Ölçüm |
|---|---:|
| Gerçek N4 kayıt oranı | **8/8 kamera** |
| N4 seyrek nokta | 102 |
| N5 ortanca reprojeksiyon (önce → sonra) | 0,523 → 0,177 px |
| Nominal ARKit derinlik aralığı | 0,64257–2,07584 (bağımsız fiziksel metre değil) |
| Seyrek derinlik örneği | 816 |
| N6 düzlem sayısı / görüntü max kenar | 24 / 96 px |
| Füzyon noktası | **675** |
| Açık mesh köşesi | **2.606** |
| Açık mesh yüzü | **3.365** |
| Native N6 durumu | **SYNTHETIC_GEOMETRY_ONLY** |

N6 görüntü girdileri **gerçek** iPad Pro RGB'dir; 'SYNTHETIC_GEOMETRY_ONLY' ise prototipin deneysel çıktı durum etiketidir. Mesh **açık** ve ölçüm doğruluğu, su geçirmezlik ve fiziksel ölçek bakımından onaylanmamıştır. Derinlik sınırları N4/N5 sparse modelindeki pozitif kamera derinliklerinin p10/p90 ölçümünden türetilmiştir; bunlar **harici referansla ölçülmüş değerler değildir**.

## Son kabul kararı

- **N9-A:** gerçek RGB kaynak erişimi PASS, zaman penceresi N4 sparse başarı PASS (16/16), N5 çıktı **PARTIAL**, N6 deneysel çıktı **REVIEW_REQUIRED**. **Genel N9-A durumu PARTIAL / REVIEW_REQUIRED**.
- **N9-B:** gerçek iPhone 11/Xcode, lens, bağımsız kör metrik referans, fiziksel Windows installer ve kullanıcı erişilebilirlik kabulü **NOT TESTED**. Sekiz B01–B08 kapısı açık.
- Resmî Apple fotoğrafları, orijinal K/poz verileri, PLY ve OBJ artefaktları depoya yüklenmedi. GitHub'da yalnız kaynak/artefakt hash'leri ve sayısal değerlendirme var.
- Bu çalışma 3B yüzeyin fiziksel doğruluğunu veya LiDAR eşdeğerliğini kanıtlamaz. Bağımsız ölçümler ve gerçek cihaz testleri ileride ayrı kabul gerektirir.

**Tam JSON SHA-256:** 9236b1b680e02b33b3f7a76c59db376219c47f8f408cca43230498ecc1abe886
