# N9-A / N9-B — Ayrı Doğrulama ve Kabul Protokolü

İlk karar: 17 Ekim 2026. Güncelleme: **18 Ekim 2026**. N0–N8 sentetik kabul düzeyinde doğrulandı; N9-A ve N9-B **birbirlerinin yerine geçmez**.

**Güncel N9-A kanıtı:** Resmî Apple ARKitScenes iPad Pro gerçek RGB/K/poz kayıtlarıyla [4 zamansal grup + N5/N6 bağımsız deney raporu](N9A_TEMPORAL_REAL_TRIAL.md) oluşturuldu: en iyi N4 **16/16 kayıtlı**, 215 sparse nokta; N5 (native **PARTIAL**) BA sonrası ortanca 0,239 px; N6 sekiz gerçek görüntüde 675 fused nokta ve 3.365 açık mesh yüzü (native **SYNTHETIC_GEOMETRY_ONLY**). **N9-A genel durum PARTIAL / REVIEW_REQUIRED**, N9-B fiziksel iPhone 11 kabulü **NOT TESTED**. [Kanıt](evidence/N9A_TEMPORAL_REAL_N4_N5_N6_2026-10-18.json).

## N9-A — Gerçek internet görüntüleriyle yazılım deneyi

Amaç: Kullanım hakkı gözden geçirilmiş özgün gerçek görüntüleri
**MonoScan11'in kendi COLMAP'sız N3/N4/N5/N6** motoruna
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
- `PROXY_PARTIAL_REVIEW_REQUIRED`: gerçek algoritmalar dosya üretti, ancak sparse/BA durumu `PARTIAL` veya N6 geometrisi yalnız deneysel; eksiksiz kabul değildir.
- `PROXY_FAILED`: giriş gerçek olsa bile motor başarısız oldu;
  hata metni saklanır.
- `SOURCE_PREFLIGHT_ONLY`: görüntü doğrulandı fakat SfM çalışmadı.
- `BLOCKED_PREREQUISITE`: veri / hak / kalibrasyon eksikliği.
- `n9b_status: NOT_TESTED`: her N9-A çalışmasının zorunlu etiketi.

**17 Ekim 2026 TARİHSEL İLK gerçek veri deneyi (yerine 18 Ekim 2026 sonuçları geçti):** Pix4D iPhone 13 ZIP'ine bu
ortamdan erişim hâlâ sağlanamadı; **ancak Apple ARKitScenes Validation
video 41069046** GitHub Actions'ın geçici çalışma ortamında indirildi
ve özgün RGB/K/ARKit trajektori ile MonoScan11 N4 native motoru çalıştırıldı.
Bu nedenle `BLOCKED_SOURCE_UNAVAILABLE` artık **tarihsel ilk deneme**
durumudur, genel N9-A güncel durumu değildir.

| N9-A gerçek kanıt | Ölçülen değer |
|---|---|
| Gerçek RGB girdisi | 16 Apple iPad Pro PNG |
| Kayıtlı kamera / girdi | **3 / 16** (13 kayıt dışı) |
| Seyrek 3B nokta | **28** |
| Görüntü gözlemi ve aday eşleşme | **56 gözlem / 71 aday eşleşme** |
| Ortanca / ortalama reprojeksiyon | **0,2686 / 0,4957 px** |
| Nominal ARKit kamera baseline | 3,3227 m (*fiziksel ölçüm değil*) |
| N4 kaynak modeller | `sparse.ply`, `tracks.json`, `cameras.json`, `summary.json` ve SHA |
| N5 BA / N6 MVS | **NOT RUN** |
| Resmî sonuç | `PROXY_PARTIAL_REVIEW_REQUIRED` |
| N9-B iPhone 11 / fiziksel Windows | **NOT TESTED** |

İşleme alanı özel GitHub runner'ında geçiciydi; telifli fotoğraflar
depoya veya rapor artefaktına eklenmedi. Resmî üç kaynak varlığı ve
16 görüntü için SHA-256 izleri kayıtlıdır. 13/16 görüntünün kayıt
edilememesi nedeniyle **N9-A tam kabulü henüz PASS değil**.
Ayrıca düşük reprojeksiyon hatası **bağımsız metrik doğruluk kanıtı
değildir**. [Gerçek sonuç JSON kanıtı](evidence/N9A_ARKITSCENES_REAL_2026-10-17.json);
[GitHub Actions gerçek veri koşusu](https://github.com/seydivakkas/MonoScan11/actions/runs/39048623303);
[tam JSON artefaktı](https://github.com/seydivakkas/MonoScan11/actions/runs/39048623303/artifacts/12107001317).

**Sonraki N9-A kalite kapısı:** gerçek karelerin yakın zamanlı ve
yeterli parallax içeren alt kümelerini bağımsız biçimde değerlendirip
kayıtlı kamera oranını artırmak; N5/N6'yı çalıştırmadan önce
rekonstrüksiyonun destek ve ölçek sınırlarını doğrulamak.

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

## 18 Ekim 2026 bağımsız gerçek N9-A kalite ilerlemesi

4 saniyelik gerçek kare kümeleri (uniform 3/16, erken 13/16, orta 15/16, son 16/16) ile önceki kayıt engeli çözüldü. N4'ün aynı kameradan aynı 3B noktaya iki keypoint bağlama hatası onarıldı. Gerçek görüntüden N5 ve N6 çıktı üretildi; native PARTIAL/deneysel geometri bayrakları aynen korundu. Ayrıntılar: [Tam kaynaklı N4/N5/N6 raporu](N9A_TEMPORAL_REAL_TRIAL.md). Harici ölçüm, lens kalibrasyonu ve fiziksel iPhone11 testleri hâlâ N9-B kapısıdır.
