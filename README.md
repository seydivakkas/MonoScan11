# MonoScan11

**LiDAR'sız iPhone 11 için kamera tabanlı 3D rekonstrüksiyon araştırma projesi**

**Sürüm:** `v0.2.0-alpha` · **Lisans:** MIT · **Çalışma ilkesi:** yerel/offline-first · **Durum:** Windows Python araçları ve taşınabilir Swift veri/ZIP çekirdeği test edildi; SwiftUI kaynak ekranları hazır; Xcode derlemesi ve gerçek cihaz kabulü bekliyor.

MonoScan11, fiziksel LiDAR sensörünü taklit etmez. Birden fazla bakış açısından fotoğraf kullanarak görüntü eşleştirme, **Structure from Motion (SfM)**, **Multi-View Stereo (MVS)** ve üçgenleme (triangulation) teknikleriyle 3D geometri üretmeyi hedefler. COLMAP, yoğun modelleme için ayrı kurulan açık kaynak bir araçtır. LiDAR donanımı veya garantili metrik doğruluk gerekmez; ölçüm iddiaları bağımsız değerlendirmeye tabidir.

## Gerçek durum (yayınlamadan önce okuyun)

| Bölüm | Durum | Kanıt |
|---|---|---|
| Windows / Linux Python araçları | Kaynak kodu hazır; test edildi | `python -m unittest discover -s tests -v` |
| Sentetik iki bakışlı derinlik hesabı | Tamamlandı, deterministik demo | `python tools/monoscan.py demo demo-output` |
| Fotoğraf / ARKit `session.json` denetimi | Otomatik test edildi | JPEG/PNG başlık, boyut, matris, poz, güvenli dosya adları |
| COLMAP komut dizisi | Unit/integration mock ile test edildi | `--dry-run`, mock model ve `inspect` |
| Gerçek iPhone 11 fotoğraflarından 3D rekonstrüksiyon | **Bekliyor** | Ayrı COLMAP kurulumu + gerçek çekim zorunlu |
| SwiftUI arayüz / iOS ARKit uygulaması | 18 ekran kodlandı; **Xcode derlenmedi** | Kaynak parse + Swift Foundation testleri; macOS/Xcode ve iPhone kabulü en sonda |
| iOS ZIP paketinin Windows uyumu | Sentetik görüntülerle PASS | Swift ZIP32 CRC -> Python `validate` zinciri; gerçek iPhone verisi değil |
| 3D modelin ölçüm doğruluğu | **Doğrulanmadı** | Gerçek referans metre/lazer ölçer karşılaştırması yok |

> **Sınır:** Sentetik demodaki çok küçük hata, ideal ve gürültüsüz geometrinin matematiksel sonucudur. iPhone 11'in gerçek tarama doğruluğu değildir. ARKit'in seyrek izleme noktaları LiDAR nokta bulutu değildir.

## iPhone 11 arayüz konsepti — 18 ekran

> **Tasarım maketidir, gerçek iPhone ekran görüntüsü değildir.** SwiftUI kaynak prototipi Xcode ile henüz derlenmedi; canlı kamera, ARKit takibi, 3D önizleme ve ölçümler fiziksel cihazda kabul edilmedi. Görseller planlanan deneyimi tanımlar; çalışan uygulama özelliklerinin kanıtı değildir.

[![MonoScan11 — onaylanan 14 ekranlık tasarım storyboardu](assets/screenshots/approved-storyboard-14.png)](docs/ui/README.md)

18 ekranlık detaylı konsept arşivi: [toplu önizleme](assets/screenshots/contact-sheet.png).

| Ana Sayfa | Canlı Tarama | Seyrek Önizleme | Windows'a Dışa Aktarım |
|---|---|---|---|
| [<img src="assets/screenshots/05-home-dashboard.png" alt="MonoScan11 ana sayfa konsepti" width="180">](assets/screenshots/05-home-dashboard.png) | [<img src="assets/screenshots/08-live-capture-screen.png" alt="Canlı tarama konsepti; görsel temsili" width="180">](assets/screenshots/08-live-capture-screen.png) | [<img src="assets/screenshots/12-sparse-preview.png" alt="Veri olmayan seyrek önizleme boş durum tasarımı" width="180">](assets/screenshots/12-sparse-preview.png) | [<img src="assets/screenshots/13-export-package-screen.png" alt="Windows COLMAP için ZIP dışa aktarım tasarımı" width="180">](assets/screenshots/13-export-package-screen.png) |

**[Bütün 18 ekranı, wireframe TXT sözleşmesini ve arayüz akışını incele](docs/ui/README.md)** · [SwiftUI uygulama ve test durumu](docs/IOS_UI_IMPLEMENTATION.md) · [PNG koleksiyonu](assets/screenshots/README.md) · [Üretici kaynak kodu](scripts/generate_ui_mockups.py). iPhone'da yoğun nokta bulutu/mesh üretildiğini ima eden bir ekran bulunmaz. Seyrek önizlemede gerçek ARKit verisi yoksa boş durum gösterilir.


## SwiftUI uygulama kaynakları (v0.2.0-alpha)

`ios/MonoScan11/` klasöründe 18 ekran ailesinin gerçek SwiftUI kaynak kodu, proje deposu (`ScanStore`), kamera/ARKit oturumu (`ScanEngine`), oturum şeması (`ProjectRecord`) ve bağımsız ZIP yazıcısı (`ZIPStore`) bulunur. `project.yml` XcodeGen proje tanımıdır.

**Doğrulanan:** Python regresyon testleri; Linux'ta Swift sözdizimi ayrıştırması; Foundation tabanlı Swift çekirdeğinin derlenmesi ve test edilmesi; ZIP CRC ve `session.json` Windows Python doğrulayıcısı. **Doğrulanmayan:** SwiftUI için iOS SDK ile typecheck/build, XcodeGen proje üretimi, iPhone üzerinde kamera çalışması, gerçek ARKit ve gerçek 3D model.

`Fotoğraf Dizisi` seçeneği ve fotoğraf silme bu sürümde bilinçli olarak devre dışı tutulmuştur. Tam durum ve ekran listesi: [iOS UI uygulama notları](docs/IOS_UI_IMPLEMENTATION.md).

## GitHub'a ilk yükleme (Windows)

[GitHub deposu](https://github.com/seydivakkas/MonoScan11) henüz boşsa proje ZIP'ini açıp **`Publish-GitHub.cmd`** dosyasını çalıştırabilirsin. Bu betik `origin` adresini doğrular, `main` hedefine yalnız normal `git push` yapar (**force-push yoktur**). Git for Windows ve GitHub kimlik doğrulaması gerekir. Betiğin gerçek Windows kabul testi henüz yapılmadı; alternatif komutlar `docs/GITHUB_YAYIN.md` içindedir. GitHub Actions sonuçları yükleme sonrası kontrol edilmelidir.

## 1. Windows'ta hemen çalıştır

**Gereken:** Python 3.10 veya daha yeni. Temel komutlar için `pip install` gerekmez.

Klasörü ZIP'ten çıkardıktan sonra:

```powershell
cd MonoScan11
python -m unittest discover -s tests -v
python tools/monoscan.py demo demo-output
```

Alternatif: `Run-Tests.cmd` ve `Demo-Triangulation.cmd` dosyalarına çift tıkla. Demo şu dosyaları oluşturur:

- `demo-output/synthetic_points.ply` — iki sentetik görüntü konumundan üçgenlenmiş 117 nokta
- `demo-output/metrics.json` — gürültüsüz referansa göre MAE/RMSE, **gerçek cihaz metriği değil**

PLY dosyasını CloudCompare veya MeshLab gibi bir 3D görüntüleyici ile açabilirsin. Demo internet gerektirmez.

## 2. iPhone 11'in normal Kamera uygulamasıyla ilk gerçek fotoğraf deneyini hazırla

Mac ve Xcode **gerekmez**. Telefonunun arka 1× ana kamerasıyla, hareketsiz ve dokulu bir nesnenin etrafından **30–100 farklı açı** çek; ardışık karelerde yaklaşık %60–80 örtüşme hedefle. Nesneyi döndürmek yerine mümkünse kamerayı çevresinde gezdir; ışığı ve odağı sabit tut. Bulanıklık, ayna, dümdüz duvar, hareket eden insan ve sadece yerinde dönme SfM için sorunludur.

**Önemli iPhone ayarı:** Ayarlar → Kamera → Biçimler → **En Uyumlu** seçeneğini kullanarak mümkünse JPEG çek. HEIC dosyaları önce JPEG/PNG'ye dönüştür; dosyanın uzantısını elle değiştirmek dönüştürme değildir. Fotoğrafları Windows'a **orijinal boyutuyla**, yeniden ölçeklendirmeden aktar.

```text
C:\scan-data\ilk-nesne\
└── images\
    ├── IMG_0001.JPG
    ├── IMG_0002.JPG
    └── ...
```

Görüntüleri kontrol et:

```powershell
python tools/monoscan.py validate "C:\scan-data\ilk-nesne"
```

ARKit kaydı olmadan da bu yöntem çalışabilir; çünkü SfM kamera pozlarını fotoğraflardan tahmin eder. Bu, aynı fotoğraflar ile COLMAP'de gerçek başarılı model üretildiğinin kanıtı **değildir**; onu ayrıca çalıştırıp test edeceğiz.

## 3. COLMAP ile fotoğraftan 3D model deneyi (Windows)

COLMAP'i **ayrı olarak** [resmî GitHub sürümlerinden](https://github.com/colmap/colmap/releases) kur. CLI yolunu `COLMAP.bat` (kuruluma göre değişebilir) olarak belirt. CPU ile ilk sparse/SfM deneyine başla:

```powershell
python tools/monoscan.py reconstruct "C:\scan-data\ilk-nesne" --colmap "C:\COLMAP\COLMAP.bat" --mode sparse --dry-run
python tools/monoscan.py reconstruct "C:\scan-data\ilk-nesne" --colmap "C:\COLMAP\COLMAP.bat" --mode sparse
```

Çıktı oluştuğunda (ve sparse/0 gerçekten mevcutsa):

```powershell
python tools/monoscan.py inspect "C:\scan-data\ilk-nesne" --export-ply "C:\scan-data\ilk-nesne\sparse-cloud.ply"
```

Beklenen dosyalar:

```text
ilk-nesne/
├── images/                 # Girdi fotoğrafları, özel veri: GitHub'a ekleme
├── reconstruction/
│   ├── database.db         # COLMAP eşleme veritabanı
│   ├── sparse/0/           # cameras.bin, images.bin, points3D.bin
│   └── summary.json        # Kayıtlı görüntü/nokta/reprojeksiyon özeti
└── sparse-cloud.ply        # Açıkça istenirse yazılır
```

**İlk denemede** `sparse` kullan; dense MVS için uyumlu CUDA/NVIDIA yapılandırması ve yeterli GPU belleği gereksinimini ayrıca değerlendir. `--gpu --mode dense` daha sonraki aşama içindir ve bu depoda gerçek donanımda doğrulanmadı. Bir tarama klasöründe `reconstruction` doluysa yazılım verileri otomatik silmez; yeni bir klasör kullan. `single_camera=1` varsayımı nedeniyle çekim boyunca **aynı fiziksel lensi** kullan.

COLMAP bir sahnede görüntüleri eşleştiremez veya model oluşturamazsa bu deney **FAIL** sayılır. Program durdurulur; yapay başarı raporu oluşturulmaz.

## 4. Mimari

```text
P0 / Mac gerekmeyen geliştirme

  iPhone 11 Kamera uygulaması ---> JPEG fotoğraflar
                  |                   |
                  v                   v
            Windows'a kopyala --> validate --> COLMAP SfM --> sparse/0
                                                     |
                                                     v
                                       inspect --> summary.json / PLY

  Bağımsız sentetik araştırma kolu:
  Kamera kalibrasyonu + iki piksel eşleşmesi --> ışınlar --> triangulation
                                                             |
                                                     sentetik PLY/MAE/RMSE

SON AŞAMADA (macOS + Xcode + fiziksel iPhone 11):

  iOS SwiftUI/ARKit prototipi --> RGB + intrinsics + VIO pose + sparse points
                                                      |
                           doğrulama ve Sim(3) hizalama (henüz entegre değil)
```

**Koordinat notu:** Python geometri demosu `camera +Z forward` iğne-deliği (pinhole) koordinatları kullanır. ARKit ise kendi kamera konvansiyonunu kullanır; dönüşümler P2 aşamasına bırakılmıştır. **ARKit pozları P0 COLMAP eşleştirmesine beslenmez**; kaydedilip doğrulanabilir ama henüz füzyon yoktur.

## 5. Proje klasörleri

```text
.github/workflows/tests.yml         GitHub Actions (Windows + Ubuntu)
.github/ISSUE_TEMPLATE/             iOS ve gerçek sahne kabul iş listeleri
tools/monoscan.py                   validate / reconstruct / inspect / demo
tools/geometry.py                   Pinhole model + triangulation + sentetik demo
tools/colmap_models.py              COLMAP binary sparse rapor/PLY
tests/                             Gerçek küçük PNG + sentetik COLMAP model fixture'ları
ios/MonoScan11/                     Henüz Xcode'da derlenmemiş SwiftUI/ARKit kaynakları
project.yml                         XcodeGen proje tarifi (Mac aşaması)
docs/SON_ASAMAYA_BIRAKILANLAR.md   Mac/Xcode ve saha işlerinin açık listesi
docs/VALIDATION_PLAN.md            Deney planı ve bağımsız metrikler
docs/GITHUB_YAYIN.md               Repo oluşturma/push/Release talimatları
```

## 6. GitHub'da yayımlama

Bu depo **kaynak kodu / alpha araştırma sürümü** olarak yayımlanabilir. Önce `Run-Tests.cmd` çalıştır; ardından [GitHub yayın rehberini](docs/GITHUB_YAYIN.md) uygula. Ana uygulamanın iPhone'da denenmiş olduğu iddiasında bulunma. GitHub Actions'da Windows ve Ubuntu testleri başarılı görünmeden `stable` etiketi kullanma.

**Plan ve sınırlamalar:** [Son aşamaya bırakılanlar](docs/SON_ASAMAYA_BIRAKILANLAR.md) · [Yol haritası](docs/ROADMAP.md) · [Doğrulama planı](docs/VALIDATION_PLAN.md) · [Mimari kararlar](docs/ARCHITECTURE.md)

## 7. Veri gizliliği, ticari kullanım ve atıf

- Kod MIT lisanslıdır. COLMAP ayrı indirilen bir araçtır; kendi [lisansını](https://github.com/colmap/colmap/blob/main/LICENSE.txt) ayrıca inceleyin.
- Bulut, üyelik veya ücretli API zorunlu değildir. Açık kaynak/ücretsiz araçlar kurulunca çoğu işlem internetsiz yürütülebilir.
- Ev, oda, özel mekân fotoğraflarını veya `session.json` dosyalarını GitHub'a yüklemeyin. `scans/`, `datasets/` ve `reconstruction/` Git tarafından yok sayılır; bunun dışında farklı klasöre konan özel görüntüleri de kendiniz denetleyin.
- Bu ürün ölçüm sertifikalı bir profesyonel 3D lazer tarayıcı alternatifi değildir.

**Teknik dayanaklar:** [Apple ARKit ARWorldTrackingConfiguration](https://developer.apple.com/documentation/arkit/arworldtrackingconfiguration), [ARFrame.rawFeaturePoints](https://developer.apple.com/documentation/arkit/arframe/rawfeaturepoints), [COLMAP CLI](https://colmap.github.io/cli.html).
