# N9 — Gerçek veri araştırması ve donanım kabulü (16 Ekim 2026)

**Durum: DIŞ VERİ ARAÇLARI KODLANDI; GERÇEK iPHONE 11 / FİZİKSEL WINDOWS / METRİK KABUL YAPILMADI.**

N0–N8 sentetik doğrulamalar gerçek donanım veya boyutsal ölçüm
doğruluğu değildir. İnternette bulunan başka Apple donanımı kaynakları
ile testler yalnızca "public real-data proxy" olabilir.

## Doğrulanan dış veri kaynakları

| Kaynak | Veri ve cihaz | Erişim | İddia edilmemesi gereken |
|---|---|---|---|
| [ScanNet++](https://scannetpp.mlsg.cit.tum.de/scannetpp/) | iPhone RGB video, ARKit 4×4, intrinsics, LiDAR, yüksek kaliteli lazer ölçümleri | Hesap, başvuru, onaylı kişisel token ve kullanım koşulları gerektirir | iPhone modelinin 11 olduğu doğrulanmadı |
| [Apple ARKitScenes](https://github.com/apple-aiml-research/ARKitScenes) | iPad Pro, RGB, .pincam, .traj, derinlik, bazı sekanslarda FARO lazer | Resmî download_data.py, veri/yazılım kullanım haklarının ayrıca incelenmesi | iPhone 11 verisi değildir |
| [ScaleMaster](https://scalemaster-dataset.github.io/) | iPhone 14 Pro RGB/ARKit, bazı sahnelerde bağımsız Livox | Bireysel sekans erişimi/Git LFS/anket | iPhone 11 kabulü değildir |
| [TMO](https://github.com/JH-Choi/TMO) | iPhone 13 Pro RGB/pose/LiDAR | Google Drive ve kullanım koşulları | iPhone 11 kabulü değildir |
| [Pix4D Olympic Flame](https://support.pix4d.com/hc/en-us/articles/360000235126) | **Gerçek iPhone 13**: 117 JPEG, 208 MB ZIP, işlenmiş OPF/geometri | Resmî [ZIP](https://data.pix4d.com/misc/example_datasets/olympic_flame.zip); örneklerin kişisel/mesleki **eğitim kullanımı** koşulları geçerli | RGB fotoğraf için iyi PHOTO_ONLY proxy; **ARKit VIO veya iPhone 11 değildir** |

Verilerin hiçbirinin kullanımı otomatik lisans devri ya da yeniden
yayınlama hakkı vermez. Dataset görüntülerini GitHub'a yüklemeyin.

## Uygulanan araçlar

- `monoscan_core/n9_public_adapter.py`: Apple .traj kayıtlarını
  dünya→kamera SE(3) biçiminden tersine çevirir, CV→ARKit kamera bazını
  açıkça düzeltir; .pincam kamera matrisi ve orijinal PNG çözünürlüğünü
  doğrular. Kare/pose zaman farkı 20 ms sınırında eşleştirilir; eksik
  karelere poz uydurulmaz. Kaynak PNG baytları ve SHA-256 değişmez;
  provenance dosyası orijinal cihazın **iPad Pro** olduğunu kaydeder.
- `scripts/n9_fetch_arkitscenes.py`: yalnız resmî Apple alan adından
  RGB, intrinsics, trajectory indirimi. `--license-reviewed` bayrağı
  olmadan veri indirmez; arşiv dosya adı ve boyut kapılarını uygular.
- `scripts/n9_public_trial.py`: yetkili yerel veri geldiğinde native
  N4'ü ve isteğe bağlı N5/N6'yı çalıştırır; hata halinde başarısız
  rapor üretir, başka cihazın başarılı ölçümünü iPhone 11 kabulüne çevirmez.
- `monoscan_core/n9_reference.py`: bağımsız ölçülmüş
  3B nokta–track kimlikleriyle **ayrı kalibrasyon ve holdout**
  grupları kullanır. Yalnız rijit SE(3) hizalama (ölçek=1) ve
  holdout RMSE/medyan/p95 üretir; tanımlanmamış kaynak doğruluğuna
  otomatik sertifika vermez.
- `tests/test_n9_public_adapter.py`,
  `tests/test_n9_reference.py`, `tests/test_n9_fetch.py, `tests/test_n9_iphone_photo_proxy.py``:
  sentetik sözleşme, sahte metrik kabulü reddi, veri dosyası bozulması
  ve platform regresyonu. **Bunlar gerçek veri deneyleri değil.**

## Üçüncü taraf gerçek veri denemesi (yalnız haklar kontrol edildiyse)

Resmî Apple kaynağında Validation video ID `41069046`
bulunuyor; *bu sekansın başarıyla indirilip işlendiği henüz iddia edilmez.*

```powershell
python -m pip install -r requirements-native.txt
# Kaynak veri koşullarını inceleyip hak sahibi olduğunuzda:
python scripts/n9_fetch_arkitscenes.py --video-id 41069046 --split Validation --output "C:\N9-Data\ARKitScenes\41069046" --license-reviewed
# Gerçek görüntülerin özgün pose/intrinsics eşleştirmesi; başarısız olabilir:
python scripts/n9_public_trial.py --source "C:\N9-Data\ARKitScenes\41069046" --output "C:\N9-Trials\iPadProxy01" --video-id 41069046 --max-frames 24
```

Gerçek iPhone 13 RGB örnek arşivi için **ayrı**, ARKit'siz yol:

```powershell
# Resmî ZIP kullanım haklarını inceledikten sonra:
python scripts/n9_iphone_photo_proxy.py --download-to "C:\N9-Data\iphone13-olympic.zip" --session-out "C:\N9-Trials\iphone13-photo-only" --training-terms-reviewed --frame-limit 24

# KALİBRE EDİLMİŞ bir gerçek odak uzunluğunuz (piksel) varsa:
python tools/monoscan.py reconstruct "C:\N9-Trials\iphone13-photo-only" --mode photo-only --focal-px "$env:MONOSCAN_CALIBRATED_FOCAL_PX"
```

Buradaki ortam değişkeni gerçek, doğrulanmış piksel odak uzunluğunu
kullanıcı tarafından sağlamalıdır; MonoScan11 odağı tahmin edip metrik
kalibrasyon kanıtı üretmez.
Bu arşivin çalışma konteynerinde doğrudan indirilmesi denendi ancak
indirme gerçekleşmedi; gerçek veri üzerinden MonoScan11 test edildiği
iddia edilmez.

256×192 RGB örnekleri SIFT için yetersiz kalabilir; bu durumda
N4 model üretmek zorunda değildir. Kullanıcıdan gerçek iPhone görüntüleri
gelmedikçe ya da çevrimiçi dış kaynağın yetkili erişimi doğrulanmadıkça
N9 fiziksel onay sırası başlatılmış sayılamaz.

## N9 zorunlu açık kabul maddeleri

| ID | Kanıt / denetim | Şimdiki durum |
|---|---|---|
| N9-D1 | Fiziksel iPhone 11 model, iOS sürümü ve donanım envanteri | **AÇIK** |
| N9-D2 | Xcode gerçek derleme, uygulama imzası, gerçek cihaz çalışması | **AÇIK** |
| N9-D3 | iPhone 11 RGB kamera/lens/odak/K ve distorsiyon kalibrasyonu | **AÇIK** |
| N9-D4 | Gerçek cihazdan ARKit poz + RGB + tam kaynak SHA ve izleme statüsü | **AÇIK** |
| N9-D5 | Bağımsız referans ölçüm + kör holdout metrik hata kabulü | **AÇIK** |
| N9-D6 | Yetkili Windows kurulum, uzun işlem süre/RSS ve çökme testi | **AÇIK** |
| N9-D7 | Ekran okuyucu, yüksek DPI, klavye/ergonomi gerçek kullanıcı kabulü | **AÇIK** |
| N9-D8 | İzin/lisans, Windows installer ve gerçek dağıtım sözleşmesi | **AÇIK** |

**Kapatma kararı:** Gerçek görüntü/ARKit/kalibrasyon/ölçüm ve fiziksel
Windows/iPhone kanıtı olmadan N9 tamamlanmış değildir. Dış dataset
proxy testleri bu tabloyu otomatik kapatmaz. Draft PR ve main dalı
korunur; üretim/stable yayımlanmaz.
