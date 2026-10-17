# MonoScan11

> **Native SfM geliştirme dalı (N0–N9 dış veri hazırlığı):** Bu dal COLMAP'sız, deneysel bir fotoğraf tabanlı 3B işlem hattına geçiş içindir. Henüz gerçek iPhone/Windows kabulü veya metrik doğruluk kanıtı yoktur. Önce [geçiş mimarisini](docs/COLMAP_FREE_ARCHITECTURE.md) okuyun.

**LiDAR'sız iPhone 11 için kamera tabanlı 3D rekonstrüksiyon araştırma projesi**

**Sürüm:** `v0.2.0-alpha` · **Lisans:** MIT · **Çalışma ilkesi:** yerel/offline-first · **Durum:** Windows Python araçları ve taşınabilir Swift veri/ZIP çekirdeği test edildi; SwiftUI kaynak ekranları hazır; Xcode derlemesi ve gerçek cihaz kabulü bekliyor.

MonoScan11, fiziksel LiDAR sensörünü taklit etmez. Birden fazla bakış açısından fotoğraf kullanarak görüntü eşleştirme, **Structure from Motion (SfM)**, **Multi-View Stereo (MVS)** ve üçgenleme (triangulation) teknikleriyle 3D geometri üretmeyi hedefler. Bu geliştirme dalında rekonstrüksiyon için harici COLMAP kurulumu gerekmez; native SfM yalnızca deneysel seviyededir. LiDAR donanımı veya garantili metrik doğruluk gerekmez; ölçüm iddiaları bağımsız değerlendirmeye tabidir.

## Gerçek durum (yayınlamadan önce okuyun)

| Bölüm | Durum | Kanıt |
|---|---|---|
| Windows / Linux Python araçları | Kaynak kodu hazır; test edildi | `python -m unittest discover -s tests -v` |
| Sentetik iki bakışlı derinlik hesabı | Tamamlandı, deterministik demo | `python tools/monoscan.py demo demo-output` |
| Fotoğraf / ARKit `session.json` denetimi | Otomatik test edildi | JPEG/PNG başlık, boyut, matris, poz, güvenli dosya adları |
| MonoScan11 native SfM + ARKit VIO + BA + MVS | N0–N6 sentetik prototip | Native PHOTO_ONLY/ARKit sparse, sparse BA, düşük çözünürlüklü CPU plane-sweep, füzyon ve açık OBJ; gerçek veri kabulü yok |
| Windows N7/N8 çalışma istasyonu | Sentetik entegrasyon ve güvenlik testleri | Tkinter proje katalogu, ZIP içe aktarımı, N4–N6 gerçek prosedürel tam zincir, kaynak ZIP doğrulama, klavye erişimi; gerçek kullanıcı kabulü yok |
| Gerçek iPhone 11 fotoğraflarından 3D rekonstrüksiyon | **Bekliyor** | Yeni native pipeline henüz gerçek iPhone/Windows ortamında kabul edilmedi |
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
| [<img src="assets/screenshots/05-home-dashboard.png" alt="MonoScan11 ana sayfa konsepti" width="180">](assets/screenshots/05-home-dashboard.png) | [<img src="assets/screenshots/08-live-capture-screen.png" alt="Canlı tarama konsepti; görsel temsili" width="180">](assets/screenshots/08-live-capture-screen.png) | [<img src="assets/screenshots/12-sparse-preview.png" alt="Veri olmayan seyrek önizleme boş durum tasarımı" width="180">](assets/screenshots/12-sparse-preview.png) | [<img src="assets/screenshots/13-export-package-screen.png" alt="Windows yerel SfM için ZIP dışa aktarım tasarımı" width="180">](assets/screenshots/13-export-package-screen.png) |

**[Bütün 18 ekranı, wireframe TXT sözleşmesini ve arayüz akışını incele](docs/ui/README.md)** · [SwiftUI uygulama ve test durumu](docs/IOS_UI_IMPLEMENTATION.md) · [PNG koleksiyonu](assets/screenshots/README.md) · [Üretici kaynak kodu](scripts/generate_ui_mockups.py). iPhone'da yoğun nokta bulutu/mesh üretildiğini ima eden bir ekran bulunmaz. Seyrek önizlemede gerçek ARKit verisi yoksa boş durum gösterilir.


## SwiftUI uygulama kaynakları (v0.2.0-alpha)

`ios/MonoScan11/` klasöründe 18 ekran ailesinin gerçek SwiftUI kaynak kodu, proje deposu (`ScanStore`), kamera/ARKit oturumu (`ScanEngine`), oturum şeması (`ProjectRecord`) ve bağımsız ZIP yazıcısı (`ZIPStore`) bulunur. `project.yml` XcodeGen proje tanımıdır.

**Doğrulanan:** Python regresyon testleri; Linux'ta Swift sözdizimi ayrıştırması; Foundation tabanlı Swift çekirdeğinin derlenmesi ve test edilmesi; ZIP CRC ve `session.json` Windows Python doğrulayıcısı. **Doğrulanmayan:** SwiftUI için iOS SDK ile typecheck/build, XcodeGen proje üretimi, iPhone üzerinde kamera çalışması, gerçek ARKit ve gerçek 3D model.

`Fotoğraf Dizisi` seçeneği ve fotoğraf silme bu sürümde bilinçli olarak devre dışı tutulmuştur. Tam durum ve ekran listesi: [iOS UI uygulama notları](docs/IOS_UI_IMPLEMENTATION.md).

## GitHub'a ilk yükleme (Windows)

[GitHub deposu](https://github.com/seydivakkas/MonoScan11) henüz boşsa proje ZIP'ini açıp **`Publish-GitHub.cmd`** dosyasını çalıştırabilirsin. Bu betik `origin` adresini doğrular, `main` hedefine yalnız normal `git push` yapar (**force-push yoktur**). Git for Windows ve GitHub kimlik doğrulaması gerekir. Betiğin gerçek Windows kabul testi henüz yapılmadı; alternatif komutlar `docs/GITHUB_YAYIN.md` içindedir. GitHub Actions sonuçları yükleme sonrası kontrol edilmelidir.

## N7 — Windows çevrimdışı çalışma istasyonu

Windows'ta deneysel arayüzü başlat:

```powershell
python -m pip install -r requirements-native.txt
python scripts/monoscan_desktop.py
```

Alternatif: Depo kökündeki `MonoScan11-Desktop.cmd` dosyasını çalıştır.
Python 3.11+, standart Tkinter ve native bağımlılıklar gerekir.
**Henüz dağıtılabilir Windows EXE/kurulum paketi veya gerçek Windows kullanıcı
kabulü bulunmuyor.** N7 arayüzünde işlem başlatmak için kullanıcı, seçilen
oturumun **sentetik test verisi olduğunu** açıkça işaretlemelidir. Gerçek
fotoğraf ve cihaz testleri N9'a ertelenmiştir.

Arayüzde iPhone `ZIPStore.swift` uyumlu ZIP import, proje katalogu,
`photo-only` ve `arkit-guided` modu, N5 BA, N6 CPU dense,
aşama bazlı gerçek durumlar, iptal, kaynak raporu ve PLY/OBJ
önizleme bulunur. Uygulama boş projelerde sahte model çizmez; gerçek
sensör hata kovaryansı veya fiziksel ölçüm kesinliği göstermez.

[Ayrıntılı N7 arayüz ve sözleşme belgesi](docs/N7_WINDOWS_WORKSTATION.md).

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

## 2. Gerçek fotoğraf analizinden önceki geliştirme sınırı (N4–N8)

**Gerçek iPhone 11 fotoğraf çekimi, gerçek sahne analizi ve bağımsız
ölçüm doğrulaması N9'a ertelendi.** N4–N8 çalışmalarında yalnız
programatik sentetik görüntüler, yapay kamera pozları ve test manifestleri
kullanılır. Gerçek fotoğraf, örnek çekim veya internetten alınmış gerçek
sahne veri seti bu aşamaların kabulü için kullanılmaz.

## 3. N4 — İki bağımsız rekonstrüksiyon modu ve poz hizalama

```powershell
python -m pip install -r requirements-native.txt
python -m unittest discover -s tests -v
# N4–N8'de yalnız sentetik oturum örnekleri üzerinde:
python tools/monoscan.py reconstruct "C:\scan-data\synthetic-session" --mode photo-only
python tools/monoscan.py reconstruct "C:\scan-data\synthetic-session" --mode arkit-guided
python tools/monoscan.py align-arkit "C:\scan-data\synthetic-session\reconstruction\runs\run-photo" "C:\scan-data\synthetic-session"
```

`photo-only`: Görüntülerden SfM ile kamera pozlarını çıkarır, **ölçek keyfîdir**.
Geçerli K içeren `session.json` yoksa kalibre edilmiş `--focal-px` gerekir.

`arkit-guided`: Yalnız `session.json` v1 içindeki ARKit VIO pozlarını kullanır;
görüntü özelliklerini yerel SfM matematiği ile üçgenler. ARKit koordinatlarının
birimleri yaklaşık metre kabul edilir ancak **bağımsız doğruluk kanıtı değildir**.

`align-arkit`: Var olan `photo-only` koşusunun kamera merkezlerini
ARKit'e Sim(3) ile hizalar. PLY'yi yeniden ölçeklendirmez; yalnız
ölçek/hizalama/aşırı sapma istatistiklerini gösterir.

Her başarılı native koşu yeni `reconstruction/runs/run-*/` dizini
oluşturur: `sparse.ply`, `cameras.json`, `tracks.json`, `summary.json`.
ARKit VIO'nun cihaz başına sayısal poz kovaryansı mevcut v1 biçiminde
bulunmadığı için belirsizlik değerleri **null** raporlanır. Yalnız reprojeksiyon
ve poz uyum kalıntıları gözlemlenebilir. N5 seyrek BA isteğe bağlı uygulanır;
N6 yoğun MVS ve gerçek cihaz kabulü henüz tamamlanmamıştır.

[Ayrıntılı N4 ARKit VIO mimarisi ve sentetik kabul sınırları](docs/N4_ARKIT_VIO_FUSION.md).

## 4. Deneysel yerel SfM mimarisi

```text
iPhone 11 RGB JPEG + (varsa) ARKit session.json
                 |
Windows MonoScan11 offline Python
                 |
  K/doğrulama -> SIFT eşleşmeleri -> RANSAC essential matrix
                 |
  İlk kamera çifti + triangulation -> artımlı PnP ve triangulation
                 |
   sparse.ply + cameras.json + tracks.json + summary.json
```

Bu dalda `photo-only` ve `arkit-guided` ayrı deneysel modlardır. ARKit VIO pozları
`arkit-guided` modunda kullanılır; ancak metrik doğruluk N9'a kadar bilinmez.
N5 sparse Bundle Adjustment ayrı, deneysel refine adımı olarak eklendi;
N6 deneysel, düşük çözünürlüklü CPU MVS/füzyon/açık mesh çekirdeği eklendi; gerçek fotoğraf kabulü N9'da.

## 5. Proje klasörleri

```text
.github/workflows/tests.yml         GitHub Actions (Windows + Ubuntu)
.github/ISSUE_TEMPLATE/             iOS ve gerçek sahne kabul iş listeleri
tools/monoscan.py                   validate / reconstruct / inspect / demo
tools/geometry.py                   Pinhole model + triangulation + sentetik demo
monoscan_core/                      Kamera, SIFT, epipolar doğrulama, SfM, yerel PLY\ntools/colmap_models.py              Yalnızca tarihsel eski çıktı okuyucusu, native motor kullanmaz
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

- MonoScan11 kaynak kodu MIT lisanslıdır. COLMAP yeni çalışma yolunda kullanılmaz; OpenCV/NumPy ve diğer bağımlılıkların lisans ve dağıtım şartları sürümlemede ayrıca doğrulanmalıdır.
- Bulut, üyelik veya ücretli API zorunlu değildir. Açık kaynak/ücretsiz araçlar kurulunca çoğu işlem internetsiz yürütülebilir.
- Ev, oda, özel mekân fotoğraflarını veya `session.json` dosyalarını GitHub'a yüklemeyin. `scans/`, `datasets/` ve `reconstruction/` Git tarafından yok sayılır; bunun dışında farklı klasöre konan özel görüntüleri de kendiniz denetleyin.
- Bu ürün ölçüm sertifikalı bir profesyonel 3D lazer tarayıcı alternatifi değildir.

**Teknik dayanaklar:** [Apple ARKit ARWorldTrackingConfiguration](https://developer.apple.com/documentation/arkit/arworldtrackingconfiguration), [ARFrame.rawFeaturePoints](https://developer.apple.com/documentation/arkit/arframe/rawfeaturepoints), [COLMAP CLI](https://colmap.github.io/cli.html).

## N5 — Sentetik Sparse Bundle Adjustment

```powershell
python -m pip install -r requirements-native.txt
# Yalnız sentetik N3/N4 koşuları için
python tools/monoscan.py refine "C:\\test\\synthetic-session\\reconstruction\\runs\\run-xyz" --max-nfev 90
python tools/monoscan.py reconstruct "C:\\test\\synthetic-session" --mode arkit-guided --bundle-adjust
```

SciPy TRF ve seyrek Jacobian ile kamera pozları ve 3B noktalar ortak optimize edilir;
fotoğraf modunda gauge korunur, ARKit modunda ayarlanabilir *heuristik* prior
kullanılır. Sensörün gerçek pose kovaryansı bilinmez. Yakınsama tamamlanmadıysa
sadece koşullu `PARTIAL` sonucu mümkündür; gerçek dünya doğruluğu iddia edilmez.
İzler, kaynak kameralar ve giriş SHA değerleri korunarak yeni
`refinements/n5-*` klasörüne yazılır. Önceki taramalar değiştirilmez.

[N5 BA teknik sözleşmesi](docs/N5_SPARSE_BUNDLE_ADJUSTMENT.md) · [N0–N9 güncel plan](docs/ROADMAP.md)


## N6 — CPU MVS, yoğun nokta ve açık mesh (yalnız sentetik)

```powershell
python -m pip install -r requirements-native.txt
python -m unittest discover -s tests -v
python tools/monoscan.py dense "C:\test\synthetic-session\reconstruction\runs\run-xyz" "C:\test\synthetic-session" --min-depth 1.7 --max-depth 3.0 --planes 43 --max-side 112 --voxel-size 0.10
```

Girişteki N3/N4/N5 kamera matrisleri ve SHA-256 ile eşleşen orijinal
sentetik görüntüler kullanılır. Çıktı, kaynağı bozmayan ayrı
`dense/n6-*` klasöründe `depth_maps.npz`, `dense.ply`, `mesh.obj`
ve `summary.json` dosyalarıdır. OBJ **açık yüzeydir**, kapalı/su
geçirmez 3B nesne ya da LiDAR eşdeğeri değildir. PHOTO_ONLY ölçeği
keyfîdir; ARKit-guided yaklaşık metre birimi bağımsız doğrulama değildir.

[N6 teknik sözleşmesi](docs/N6_DENSE_MVS.md) ·
[N0–N9 yol haritası](docs/ROADMAP.md)


## N8 — Sentetik uçtan uca sistem kabulü

Gerçek görüntü kullanılmadan sıfırdan prosedürel 4 kameralı PNG+ARKit ZIP
oluşturulur; Swift uyumlu ZIP sözleşmesiyle içe alınır ve gerçek native
N4 SfM → N5 seyrek BA (gereksizse açık `skipped_already_consistent`)
→ N6 yoğun MVS/PLY/OBJ → N7 model keşfi yürütülür:

```powershell
python -m pip install -r requirements-native.txt
python scripts/n8_synthetic_acceptance.py --repeat 2 --output n8-acceptance.json
```

Bu işlem yalnız **sentetik test verisi** üretir. Profil süreleri ve
bellek değerleri CI ortamı içindir; gerçek iPhone veya son kullanıcı
Windows performansı olarak yorumlanmaz. Aynı makinede kaynak artefaktların
SHA-256 tekrar edilebilirliği kontrol edilir.

Windows için deterministik **kaynak kod paketi**, bağımsız EXE değil:

```powershell
python scripts/package_n8_windows.py --output dist/MonoScan11-N8-source.zip
python scripts/package_n8_windows.py --verify dist/MonoScan11-N8-source.zip
```

Yarım kalan içe aktarımlar otomatik silinmez, kayıt dışı oturum olarak
gösterilir. N7 masaüstü F1 kısayol rehberi, yön tuşuyla 3B model döndürme,
F5 sentetik işlem, Esc iptal ve Ctrl+O ZIP import içerir. Ekran okuyucu,
yüksek DPI ve erişilebilirlik kullanıcı testleri **henüz son kabulden geçmedi**.
Gerçek fotoğraflar, iPhone 11/Xcode, bağımsız metrik doğrulama ve
fiziksel kullanıcı kabulü **yalnız N9**.

[Ayrıntılı N8 sistem kabulü ve açık riskler](docs/N8_SYNTHETIC_ACCEPTANCE.md).

## N9 — Gerçek görüntü referansları ve iPhone 11 kabulü

[Kaynak araştırması, veri hakları ve sekiz fiziksel kabul kapısı](docs/N9_DATASET_AND_DEVICE_ACCEPTANCE.md).

Ek internet kaynağı: [Pix4D Olympic Flame](https://support.pix4d.com/hc/en-us/articles/360000235126) — gerçek **iPhone 13 ile çekilen 117 JPEG** (208 MB). Bu kaynağı `scripts/n9_iphone_photo_proxy.py` PHOTO_ONLY oturumuna dönüştürebilir; fakat özgün ARKit VIO pozu veya güvenilir kalibrasyon otomatik mevcut değildir. Fotoğrafları bu çalışmada indirme denemesi başarılı olmadı; kullanıcı haklarını inceleyip bağımsız kaynak arşivini sağlayabilir. Kaynakların eğitim kullanım şartlarına uyulmalıdır.

N9 gerçek fotoğraf evresine **hazırlık** kodlandı: Apple ARKitScenes
(kaynağı **iPad Pro**, iPhone 11 değil) RGB/pose/intrinsics dönüştürücüsü,
yetkili indirme, yalnız orijinal geometriyle public proxy denemesi,
bağımsız mesafe/nokta holdout analizi. Lisans onayı, fiziksel iPhone 11,
Xcode, kendi RGB+ARKit çekimi, ölçülen referans ve gerçek Windows kurulum
yapılmadı. Bu nedenle gerçek cihaz veya fiziksel doğruluk geçerliliği
**kanıtlanmadı**. Kullanıcı gerçek dataset haklarını kendisi denetlemelidir.

```powershell
python scripts/n9_fetch_arkitscenes.py --video-id 41069046 --split Validation --output "C:\N9-Data\ARKitScenes\41069046" --show-urls
# --license-reviewed bayrağı ancak veri kullanım koşullarını inceledikten sonra.
```

## N9 kabulü iki ayrı aşamaya bölündü: N9-A / N9-B

[N9-A ve N9-B teknik/kabul sözleşmesi](docs/N9A_N9B_SEPARATE_ACCEPTANCE.md).

- **N9-A (kamusal gerçek görüntü işleme):** Pix4D iPhone13 PHOTO_ONLY
  veya Apple ARKitScenes iPad Pro ARKit-guided oturumunu *lisans
  kontrolünden sonra* gerçek N3–N6 motoruna vererek dosya SHA, model
  artefaktları ve gerçek hata/başarı raporu üretir.
  `scripts/n9a_run.py` ve `monoscan_core/n9a_acceptance.py` eklendi.
  **17 Ekim 2026 durum: gerçek arşivin indirilmesi başarısız;
  gerçek fotoğraf işleme N9-A kabulü `BLOCKED_SOURCE_UNAVAILABLE`.**
  [Şeffaf durum kanıtı](docs/evidence/N9A_BASELINE_BLOCKED_2026-10-17.json).
- **N9-B (fiziksel kabul):** orijinal iPhone11/Xcode, lens/K/distorisyon,
  kör bağımsız referans, gerçek Windows kurulum/bellek ve NVDA/UX
  değerlendirmesi sekiz ayrı kanıt kapısıdır. `scripts/n9b_audit.py`
  güvenli yerel SHA kontrolü sağlar fakat **asla otomatik PASS vermez**.
  **N9-B: NOT_TESTED.**
- N0–N8 sentetik CI başarıları bu iki aşamanın gerçek veri/cihaz
  sonuçları yerine kullanılmaz.

```powershell
# Kaynaklar hazırsa, orijinal görüntülerin byte ve kanıt denetimi:
python scripts/n9a_run.py --session "C:\N9-Data\iphone13-session" --report-dir "C:\N9-Reports\preflight" --mode photo-only --focal-px $env:N9_VERIFIED_FOCAL_PX --rights-reviewed --preflight-only

# Başlangıçta sekiz fiziksel kapının NOT_TESTED olduğunu göster:
python scripts/n9b_audit.py --evidence-root "C:\N9-Physical-Evidence"
```
