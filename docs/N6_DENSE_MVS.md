# N6 — Sentetik çoklu-görüş derinlik, füzyon ve açık mesh

**Durum:** COLMAP'sız N6 ilk CPU sürümü. Algoritma piksellerden derinlik
hesaplar, programatik olarak üretilmiş sahnelerle test edilir.
**Gerçek fotoğraf, fiziksel iPhone ve saha doğruluğu kabulü yalnız N9'dadır.**

## Üretim kodu

- `monoscan_core/dense_mvs.py` — native plane-sweep MVS, sahneye
  bağımlı olmayan kamera ışınlarının rekonstrüksiyonu, çoklu kamera
  görüntü örnekleme, yama tabanlı fotometrik maliyet.
- Her referans görüntü için **en az iki başka görüntü** tarafından
  desteklenen derinlik hipotezleri kabul edilir.
- Tekdüze veya düşük dokulu yüzey, fotometrik hata, düşük en iyi/ikinci
  en iyi maliyet farkı, sınırda/taşan derinlik hipotezleri reddedilir.
- `cross_view_consistency`: referans piksellerinin 3B karşılığı diğer
  kameraya taşınır; o kameranın *bağımsız hesaplanmış* derinlik haritasındaki
  kamera-`z` değeri ile karşılaştırılır. Yeterli eşleşme yoksa bu piksel
  geçersiz kılınır. Ground truth derinlik bu işleme dahil değildir.
- `fuse_voxels`: geçerli ve çoklu kamera tarafından doğrulanmış derinlikler
  dünya koordinatlarında voxel hücrelerine aktarılır. Çıktı noktası için
  **en az iki farklı referans kameradan katkı** gerekir.
- `grid_mesh`: en fazla doğrulanmış piksele sahip tek referans haritadan
  komşu hücreler arasında, belirgin derinlik sıçraması ya da aşırı 3B
  kenar uzunluğu yoksa üçgenler kurulur. Sonuç **açık, su geçirmez olmayan
  (non-watertight) yüzeydir**; delikleri hayalî geometriyle doldurmaz.

## Girdiler

`dense <native-sparse-run> <session-root>` komutu N3/N4/N5 modellerinden
birini ve `session-root/images` altındaki **orijinal** görüntüleri ister.
Kamera `K` ve `camera_to_world_cv` N3/N4/N5'ten alınır. Görüntülerin
SHA-256 değerleri girişteki `summary.json.input_sha256` ile eşleşmeden
MVS başlatılmaz. N3/N4 görüntü çözünürlük ölçeklemesi (maksimum 1600)
ve N6 maksimum çözünürlük (varsayılan 192) arasındaki K dönüşümü açıktır.

**N6 CPU ilk sürüm sınırları:**

| Koşul | Sınır |
|---|---|
| Kayıtlı kamera | 3–8 |
| CPU çalışma kenar boyutu | 48–384 piksel |
| Derinlik hipotezleri | 8–128, varsayılan 40 |
| Kamera intrinsics | Kalibrasyon matrisi sabit; distorsiyon düzeltilmiş kabul edilir |
| Füzyon | Dışarıdan verilen poz birimleriyle voxel; en az 2 kamera |
| Mesh | Tek derinlik görünümünden açık, üçgenli yüzey |

Bu sınırlar **sürümün mühendislik kapasitesidir**; gelecekteki GPU,
ölçekleme, keyfi çoklu sahne ve yüksek çözünürlüklü sonuçların kanıtı değildir.
Gerçek iPhone lens distorsiyonu ve görüntü yönü N9'da sınanacaktır.

## Komut — yalnız prosedürel/sentetik geliştirici oturumlarında

```powershell
python -m pip install -r requirements-native.txt
python -m unittest discover -s tests -v
python tools/monoscan.py dense "C:\test\synthetic-session\reconstruction\runs\run-xyz\refinements\n5-xyz" "C:\test\synthetic-session" --min-depth 1.7 --max-depth 3.0 --planes 43 --max-side 112 --voxel-size 0.10
```

Derinlik aralığı ve voxel boyutu **girdi uzayının birimlerindedir**.
PHOTO_ONLY için bunlar keyfî SfM ölçek birimleri; ARKit-guided için
yaklaşık ARKit VIO metre birimleri olup ölçüm sertifikası değildir.

## Çıktılar ve kaynak kimliği

Orijinal sparse/BA klasörlerini değiştirmez.
Kaynak run altında `dense/n6-<uuid>/` klasörüne:
- `depth_maps.npz` — her kamera için depth/support/margin, NumPy dizileri
  (`allow_pickle=False` ile açılabilir).
- `dense.ply` — iki veya daha çok kameradan katkılı renkli voxel noktaları.
- `mesh.obj` — tek görünüm destekli üçgenler; watertight değil.
- `summary.json` — kamera sayısı, geçerli derinlik istatistikleri, voxel
  sayısı, yüzey üçgenleri, kaynak görüntü SHA-256 ve sparse JSON hashleri,
  gösterim birimleri, bilinmeyen belirsizlikler ve N9 durumu.

`metric_scale_known=false`, `real_world_validated=false`,
`pose_covariance_calibrated=false`,
`lens_distortion_calibrated=false` değerleri korunur.
Sentetik bir düzlemin analitik derinliğine yakın çıkmak gerçek tarama
hassasiyetine genellenemez.

## Sentetik CI doğrulama

`tests/test_dense_mvs.py` yalnız programatik olarak üretilen görüntüleri
kullanır; derinlik tahmincisine analitik düzlem gerçeğini vermez.
Hedefler:
- Farklı baz çizgilerine sahip 4 sentetik kamerayla derinlik üretme ve
  analitik ground truth'a **yalnız test kapsamında** yakınlık kontrolü.
- Çapraz görünüm tutarlılığı ile yanlış pikselleri eleme.
- Çoklu referanslı voxel füzyon ve geçerli OBJ yüzleri.
- N5 biçimindeki sparse JSON'dan başlatma.
- PHOTO_ONLY keyfî ölçek / ARKit yaklaşık metre birimi ayrımı.
- Dokusu olmayan, değiştirilmiş hashli, tekrarlı kamera kayıtlı ve
  sıfır-baseline sahnelerde başarısızlık — **sahte model yayımlanmaz**.
- Her N6 koşusu yeni klasör oluşturur; girişler aynen korunur.
- Windows/Linux Python ve Swift/ZIP CI zinciri bozulmaz.

## Takip eden mühendislik kapıları

N7: Windows/SwiftUI etkileşim ve model gösterimi, ilerleme ve hata durumları,
görüntü–bulgu ilişkileri. N8: daha büyük sentetik sahne, bellek/süre
ölçümleri, tekrar edilebilirlik ve paketleme. N9: gerçek görüntü/camera
kabulü ve bağımsız boyutsal ölçüm.
