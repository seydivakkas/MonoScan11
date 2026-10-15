# MonoScan11 — iPhone SwiftUI Implementation P1–P3 (source-alpha)

**Referans:** `docs/ui/MonoScan11-iPhone11-Wireframe-v1.txt`; `assets/screenshots/approved-storyboard-14.png` içindeki onaylanan 14 ekranlık storyboard ve kalan 4 ekran aynı lacivert/cyan tasarım sistemine bağlandı.

> Bu belge **gerçek iOS build veya iPhone kabul kanıtı değildir**. Windows/Linux üzerinde SwiftUI sözdizimi ayrıştırması, portable Swift Foundation modellerinin derlenmesi ve Windows Python sözleşme testleri yapılır. Xcode, gerçek cihaz, UI screenshots ve süre/bellek/ölçüm doğruluğu en son HOLD.

## Ekran haritası ve davranış

| # | Şartnamedeki sayfa | SwiftUI görünümü | İşlem / verinin kaynağı |
|---|---|---|---|
| 01 | Açılış | `SplashScreen` | Geçiş, sonra tanıtım veya ana sayfa |
| 02 | Nasıl çalışır | `OnboardingScreen` sayfa 1 | Tanıtım |
| 03 | Doğru çekim | `OnboardingScreen` sayfa 2 | Çekim kuralları |
| 04 | Çıktılar | `OnboardingScreen` sayfa 3 | Yerel ZIP -> Windows akışı |
| 05 | Ana sayfa | `HomeScreen` | `ScanStore.projects` gerçek kayıtları |
| 06 | Tarama ayarları | `NewScanScreen` | Validasyon; `ScanTarget`; yalnız ARKit mod etkin |
| 07 | İzinler | `PermissionsScreen` | Gerçek AVFoundation kamera izni, ARKit uyum denetimi |
| 08 | Canlı tarama | `CaptureScreen` | `ARSCNView`, `ARSession`, deklanşör, gerçek kare sayacı |
| 09 | Çekim kontrolü | `QualityScreen` | Gerçek kare sayısı/takip durumu; **puan/örtüşme hesabı yok** |
| 10 | Özet | `SummaryScreen` | `ScanStore` kayıtları |
| 11 | Fotoğraf galerisi | `GalleryScreen` | Yerel JPEG'ler; büyütülmüş inceleme |
| 12 | Seyrek önizleme | `SparseScreen` | Mevcut ASCII PLY noktaları; yoksa boş durum, **mesh değil** |
| 13 | Dışa aktarım | `ExportScreen` | `ZIPStore`, gerçek başarılı ZIP sonrası iOS share sheet |
| 14 | Projelerim | `ProjectsScreen` | Arama, gerçek durum filtreleri |
| 15 | Proje detayı | `ProjectDetailScreen` | Yeniden adlandır, silme onayı, galeri/ZIP |
| 16 | Rehber | `GuideScreen` | Çekim ipuçları ve SSS |
| 17 | Ayarlar | `SettingsScreen` | Kullanıcı tercihi ve proje sayısı, açık kapsam bilgisi |
| 18 | Hata kurtarma | `RecoveryScreen` | Duruma özgü açıklama ve yeniden deneme (ortak modül) |

## İşlevsel kararlar

- **Elle kare yakalama:** Kamera ekrandaki deklanşörle fotoğraf çeker; sayaç yalnız JPEG dosyası yazıldıktan sonra artar. ARKit takibi normal değilse kayıt yapılmaz.
- **Kamera/ARKit:** `frame.camera.intrinsics`, `frame.camera.transform` ve `rawFeaturePoints` aynı oturumda toplanır. Arka LiDAR derinliği kullanılmaz. Tek oturumdaki ARKit koordinat sistemi korunur; çekim kontrolü kamera görünümünü kaldırmaz.
- **Saklama:** `Documents/Scans/<UUID>/project.json`, `session.json`, `images/`, `arkit_sparse.ply`. Uygulama tarafından oluşturulmayan sahte proje doldurulmaz. Çekim tamamlanmadan taslak proje kalabilir.
- **Dışa aktarma:** `Documents/Exports/<UUID>-<nonce>.zip`, ZIP32 *store* yöntemi, CRC32, sürüm 1 JSON ve fotoğraflar. Kullanıcı Share Sheet ile Files/AirDrop vb. kullanır. Eski ZIP üzerine otomatik yazılmaz. Ses, konum, bulut/API veya reklam SDK'sı yok.
- **Windows uyumu:** `session.json` korunur ve `tools/monoscan.py validate <folder>` ile doğrulanır. Native SfM motoru \`PHOTO_ONLY\` çalışır; henüz ARKit poz füzyonu **yapılmıyor**.

## Açık kısıtlar / sıradaki kod işleri

- `Fotoğraf Dizisi` (ARKit'siz yedek çekim) henüz uygulanmadı ve seçenek devre dışıdır.
- Galeride tekil kare silme, JPEG/`session.json` transaction güncellemesi tasarlanana kadar devre dışıdır; proje silme uygulandı.
- Oturum başladıktan sonra uygulama kesintisi, ani kapanma, ısınma/düşük bellek, depolama dolması ve kısmi ZIP dosyalarının temizlenmesi için cihaz testleri gerekebilir.
- Taslak oturumun kaldığı yerden sürdürülmesi veya birleştirilmesi henüz uygulanmadı.
- `RecoveryScreen` duruma özgü ortak bileşendir; bütün hata türlerinin bağlama uygun UI geçişleri hâlâ tamamlanmadı.
- Bulanıklık, örtüşme, ışık, kapsama yüzdesi, metrik mesafe, dense mesh, ARKit–COLMAP hizalaması bu sürümde yoktur.
- iPhone gerçek UI ekran görüntüsü, derleme başarısı, kamera izin reddi ve ARKit takip/lens koşulları kanıtları henüz yoktur.

## Test komutları (Windows/Mac gerekmez)

```bash
python -m unittest discover -s tests -v
swiftc -frontend -parse ios/MonoScan11/*.swift   # yalnızca Linux/Swift yüklüyse
swiftc -O ios/MonoScan11/ProjectRecord.swift ios/MonoScan11/ZIPStore.swift tests/swift/main.swift -o /tmp/monoscan-core-tests
/tmp/monoscan-core-tests /tmp/monoscan-sample.zip
python tools/monoscan.py validate /tmp/monoscan-sample-folder
```

Son komut, örnek ZIP'i hedef klasöre açtıktan sonra uygulanır; `.github/workflows/tests.yml` bunu otomatik yapar. SwiftUI iOS typecheck ve binary build **ancak Xcode ile** yapılabilir.
