# N9-A / N9-B — Ayrı Doğrulama ve Kabul Protokolü

Tarih: 17 Ekim 2026. N0–N8 yalnız **sentetik kabul** düzeyinde
doğrulandı; N9-A ve N9-B **birbirlerinin yerine geçmez**.

## N9-A — Gerçek internet görüntüleriyle yazılım deneyi

Amaç: Kullanım hakkı gözden geçirilmiş özgün gerçek görüntüleri
MongoScan değil **MonoScan11'in kendi COLMAP'sız N3/N4/N5/N6** motoruna
verip başarısızlıkları da dahil olmak üzere tekrarlanabilir somut dosya
kanıtları elde etmek. N9-A, iPhone 11 donanım kabulü değildir.

| Kaynak | Gerçek cihaz | Yerel giriş | Geometri modu | Sınırlama |
|---|---|---|---|---|
| [Pix4D Olympic Flame](https://support.pix4d.com/hc/en-us/articles/360000235126) | iPhone 13, 117 JPEG, 208 MB | `scripts/n9_iphone_photo_proxy.py` | `photo-only` | Bağımsız kaynaklı **piksel focal_px** gerek; ARKit VIO yok |
| [Apple ARKitScenes](https://github.com/apple-aiml-research/ARKitScenes) | iPad Pro | `scripts/n9_fetch_arkitscenes.py` ve `monoscan_core/n9_public_adapter.py` | `arkit-guided` | iPad Pro, iPhone 11 değil; .traj/.pincam zaman eşleştirme |
| [ScanNet++](https://scannetpp.mlsg.cit.tum.de/scannetpp/) | iPhone, modelin 11 olduğu kanıtlı değil | Yetkili erişim gerektiği için adaptör/cihaz iddiası yok | Belirsiz | Başvuru ve kişiye özel erişim |
 
Kaynağın indirilmesi ve işlenmesi yalnız **yerel çalışma klasöründe**
yapılır; dışarıdan elde edilen fotoğraflar repoya, GitHub CI
artefaktlarına veya herkese açık loglara dahil edilmez.

### Kullanım

```powershell
python -m pip install -r requirements-native.txt

# 1. Telif/kullanım koşullarını gözden geçirin, onaylı Pix4D ZIP'ini alın.
python scripts/n9_iphone_photo_proxy.py --archive "C:\N9-Data\olympic_flame.zip" --session-out "C:\N9-Data\iphone13-session" --training-terms-reviewed --frame-limit 24

# 2. Özgün kamera ve görüntü SHA-256 değerlerini doğrulayın.
# Kalibre edilmiş focal_px olmadan bu PHOTO_ONLY komutu çalıştırılmamalıdır.
python scripts/n9a_run.py --session "C:\N9-Data\iphone13-session" --report-dir "C:\N9-Reports\trial-preflight" --mode photo-only --focal-px $env:N9_VERIFIED_FOCAL_PX --rights-reviewed --preflight-only

# 3. Gerçek native deneme (calibrated focal px mevcut ise):
python scripts/n9a_run.py --session "C:\N9-Data\iphone13-session" --report-dir "C:\N9-Reports\trial-01" --mode photo-only --focal-px $env:N9_VERIFIED_FOCAL_PX --rights-reviewed --refine
```

Apple ARKitScenes adaptörüyle hazırlanmış **iPad Pro** oturumu için:

```powershell
python scripts/n9a_run.py --session "C:\N9-Data\ipad-pro-session" --report-dir "C:\N9-Reports\ipad-trial" --mode arkit-guided --rights-reviewed --refine
```

`--dense` ayrıca `--min-depth` ve `--max-depth` ister.
Bu aralık **gerçek bağımsız ölçüm verisiyle gerekçelendirilmelidir**;
PHOTO_ONLY'da birimler keyfî ölçeklidir. Başarısız N4/N5/N6
komutları `PROXY_FAILED` olarak kaydedilir; başarı uydurulmaz.
`--preflight-only` sadece dosya/kaynak kontrolüdür, 3B test değildir.

N9-A çıktısı yalnız yeni klasörde `n9a_report.json` olarak oluşur:

- `source_images[*].sha256`: gerçek içerik kimliği.
- `events[*].stage`, `reported_state`, `artifact_sha256`:
  gerçekten komuttan dönen native dosya delilleri.
- `PROXY_PROCESSING_COMPLETED_REVIEW_REQUIRED`: dosya işlendi,
  **metrik, fiziksel iPhone 11 veya insan kabulü değil**.
- `PROXY_FAILED`: giriş gerçek olsa bile motor başarısız oldu;
  hata metni saklanır.
- `SOURCE_PREFLIGHT_ONLY`: görüntü doğrulandı fakat SfM çalışmadı.
- `BLOCKED_PREREQUISITE`: veri / hak / kalibrasyon eksikliği.
- `n9b_status: NOT_TESTED`: her N9-A çalışmasının zorunlu etiketi.

**17 Ekim 2026 erişim durumu:** Resmî Pix4D ZIP'i (208 MB)
çalışma ortamında indirilemedi. Yetkili özgün JPEG'ler bu oturumda
yerel olarak mevcut değil. Gerçek iPhone fotoğraflarıyla **başarılı
veya başarısız native rekonstrüksiyon deneyi henüz gerçekleştirilemedi**.
Bu yüzden N9-A durumu `BLOCKED_SOURCE_UNAVAILABLE`. Kaynaklara
erişildiğinde gerçek işlemler yeniden başlatılabilir;
otomatik sentetik testler bunun yerini tutmaz.

## N9-B — Gerçek iPhone 11 ve fiziksel sistem kabulü

`monoscan_core/n9b_acceptance.py` yalnız sekiz kanıt kapısının
SHA-256 yerel dosya varlığını kaydeder. Bir dosya mevcut diye
gerçek cihaz/bağımsız kalite testi otomatik **PASS** olamaz.

| Kapı | Bağımsız gerçek kanıt |
|---|---|
| B01 | iPhone 11 model ve iOS sürümü + envanter |
| B02 | Mac/Xcode kod imzası, gerçek cihaza kurulum ve açılış günlüğü |
| B03 | Özgün iPhone 11 lens/K/distorisyon ve yeniden projeksiyon kalibrasyon raporu |
| B04 | Gerçek uygulamanın RGB + ARKit senkron çekimi, SHA, izleme kalitesi |
| B05 | Kalibre edilmiş bağımsız ölçüm aracıyla kör holdout RMSE/p95 |
| B06 | Fiziksel Windows 10/11 kurulum, CPU/RAM, uzun çalışma ve hata kayıtları |
| B07 | NVDA/UIA ekran okuyucu, DPI, klavye, gerçek kullanıcı erişilebilirliği |
| B08 | Windows kurulum paketi, offline wheelhouse, ticari lisans/SBOM |

### Yerel kanıt denetimi

```powershell
python scripts/n9b_audit.py --evidence-root "C:\N9-Physical-Evidence" --output "C:\N9-Reports\n9b-pending.json"
```

İsteğe bağlı `--manifest`: `{"schema_version":1,"records":{"B01":[{"filename":"device-photo.jpg","sha256":"..."}]}}` biçimi; dosyalar aynı kanıt kökünde tutulur.
Bulunmayan deliller `NOT_TESTED`, bozuk veya SHA eşleşmeyen
deliller `INVALID_EVIDENCE`, yalnız byte kimliği doğrulananlar
`EVIDENCE_PRESENT_REVIEW_REQUIRED` olur. **Sekiz kapının hiçbirini
otomatik olarak başarıya taşımaz.** Cihaz, uzman ve ölçüm yoksa N9-B
`NOT_TESTED` kalır.

## Karar ve sürüm güvenliği

- N9-A: dışarıdan edinilen gerçek görüntüyle sınırlı yazılım kalite
  çalışması; kullanıcı tarafından incelenmiş kullanım koşulları ve
  orijinal SHA kanıtı zorunludur.
- N9-B: fiziksel iPhone 11, bağımsız ölçüm, Xcode ve Windows kullanıcı
  kabulü, gerçek uzmanın onayıyla kapatılacak ayrı aşamadır.
- N0–N8 sentetik CI testleri `PASS` olabilir; **gerçek
  veri/cihaz kabulü kendiliğinden PASS olamaz**.
- `main` korunur, PR taslak tutulur, "stable" veya "iPhone11
  verified" etiketi N9-B gerçek bağımsız kabulüne kadar kullanılmaz.
