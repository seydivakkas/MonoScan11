# Mimari ve bilimsel sınırlar

## Problemin tanımı

LiDAR olmadan 3D rekonstrüksiyon, tek fotoğrafın içerdiğinden daha fazla geometrik bilgiye ihtiyaç duyar. MonoScan11, zaman veya konum olarak farklı bakış açılarından eşleşen görüntü özelliklerinden 3D konum hesaplar. Birden fazla görüntü arasındaki eşleşmeler SfM ile kamera hareketi ve seyrek 3D yapı tahmini için kullanılır. MVS yoğunlaştırma ayrı adımdır.

## Sentetik temel: iki kamera triangulation

Kamera matrisi `K`, piksel `(u,v)` ve poz `T_camera_to_world` verildiğinde, kalibre edilmiş ve distorsiyonu giderilmiş iğne-deliği kamera için ışın doğrultusu `( (u-cx)/fx, (v-cy)/fy, 1 )` olur. İki ışının en yakın noktalarının orta noktası tahmini 3D konumdur. Küçük ışın kesişim açısı, sıfır baz mesafe, negatif derinlik veya büyük eşleşme hatasında algoritma sonucu reddeder.

Düzeltmesiz lens distorsiyonunu, bilinmeyen kamera rotasyonunu ve ARKit kamera koordinatlarını yanlış şekilde burada yok sayarak gerçek cihaz hatası ölçmüş gibi davranılmamalı. `tools/geometry.py` içindeki demo kontrollü, rotasyonu olmayan sentetik rig kullanır.

## Gerçek fotoğraflar: COLMAP

`tools/monoscan.py`, gerçek fotoğraflar üzerinde COLMAP CLI'nin `feature_extractor`, `exhaustive_matcher`, `mapper` komutlarını sırasıyla çalıştırır. Varsayılan `--gpu` yoktur; temel akış CPU SIFT eşlemesi kullanır. `dense` modu ihtiyaca göre `image_undistorter`, `patch_match_stereo`, `stereo_fusion` ve `poisson_mesher` adımlarını ekler.

- `COLMAP` ayrı kurulur: hiçbir fotoğraf, API'ye gönderilmez.
- `session.json` varsa görüntüler/pozlar doğrulanır, ama COLMAP'in optimizasyonuna **poz prior'ı eklenmez**.
- SfM'de rekonstrüksiyon global ölçeği bilinmez; `sparse-cloud.ply` üzerinden ölçülen birimleri metre olarak raporlamak yanlıştır.
- `mean_reprojection_error_px` bir içsel tutarlılık metriğidir; bağımsız ölçüm hatası veya milimetre doğruluğu değildir.
- Tek kamera varsayımı (`single_camera=1`) yalnızca aynı fiziksel lens ve sabit çekim ayarı için uygundur.

## iPhone 11 ve ARKit (son aşama)

Swift kaynakları RGB kareleri, kareye karşılık gelen intrinsics `K`, dünya-koordinatlı kamera dönüşümünü ve ARKit `rawFeaturePoints` çıktısını ayrı tutar. ARKit'in 3D noktaları hareket izleme özellikleridir; LiDAR veya yoğun derinlik haritası değildir. Apple'ın ARWorldTrackingConfiguration cihazın 6-DoF hareket takibini sağlar; kararlı/metric düzeyde ölçüm sertifikası vermez.

ARKit kamera koordinat sistemi ile Python demosunun `+Z` ileri konvansiyonu aynı değildir. Rotasyon, görüntü yönü, ölçek ve Sim(3) hizalama IOS-05 ve FUS-01 kapsamında gerçek cihaz üzerinde doğrulanmalıdır.

## Gizlilik ve güvenlik

Kamera çekimi yerel dosyalara kaydedilir; taranan odalar hassas olabilir. Repository gizli anahtar barındırmamalı, otomatik telemetri eklenmemeli; örnek veri olarak yalnızca sentetik veya paylaşım izni bulunan fotoğraflar kullanılmalı. Var olan COLMAP çalışma dizini üzerine yazma varsayılan olarak engellenir.
