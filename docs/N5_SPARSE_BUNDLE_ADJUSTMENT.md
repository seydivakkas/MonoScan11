# N5 — Native Sparse Bundle Adjustment / sentetik doğrulama

**Durum:** N5 deneysel algoritma uygulaması; gerçek fotoğraf analizi ve fiziksel
iPhone 11/kalibrasyon/ölçüm kabulü **N9** aşamasındadır.

## Mimari

MonoScan11 kendi seyrek BA işlem hattını kullanır: `monoscan_core/bundle_adjustment.py`.
Harici COLMAP veya COLMAP biçimine ihtiyaç duymaz. `scipy.optimize.least_squares`
(TRF, seyrek Jacobian, `soft_l1` kaybı) aracılığıyla şunları birlikte optimize eder:

- Dünya-koordinatlarına göre 3B iz noktaları `X_j`.
- Birinci kamera hariç tüm kayıtlı kameraların world-to-camera dönme
  vektörleri `r_i` (Rodrigues) ve ötelemesi `t_i`.
- İç kamera matrisi `K_i` doğruluğu bağımsız şekilde doğrulanmadığı için sabit tutulur.

`min Σρ(||π(K_i,R_i,t_i,X_j)-u_ij||²)` temel reprojeksiyon hedefidir.
Görüntü-kamera-topoloji grafiği bağlı değilse veya başlangıçta kamera arkasında
iz varsa işlem başarısız olur. Uygulama, N5 ilk sürümünde tek optimizasyonda
**en fazla 5.000 nokta** kabul eder; daha büyük modeller için N8'de pencereleme
ve artımlı BA tasarlanacaktır.

## Gauge ve ARKit belirsizliği

**PHOTO_ONLY**: birinci kamera tamamen sabitlenir; ikinci kamera merkezleri
arasındaki *başlangıç* uzaklığı göreli ölçeği sabitlemek için ceza terimidir.
Buradaki ölçek gerçek dünya metre birimi anlamına gelmez.

**ARKIT_GUIDED**: birinci kamera sabitlenir; diğer kameralara N4 VIO
pozlarından oluşturulan *sezgisel/yapay ağırlıklı* regularization uygulanır.
Poz ötelemesi nominal ARKit dünya koordinatlarında ve dönme farkı radyan
üzerinden ölçeklenir. `prior_weight` bir sensör kovaryansı/standart sapma/
ölçüm doğruluğu değildir. Çıktıda `metric_scale_known=false`,
`real_world_validated=false`, `bundle_adjustment_pose_covariance_calibrated=false`.

Optimizasyon iterasyon sınırına ulaşırsa, fiziksel/geometrik güvenlik şartlarını
ve anlamlı reprojeksiyon iyileşmesini sağlayan bir sonuç ancak
`bundle_adjustment="partial_nonconverged"` ve `state="PARTIAL"` ile
aktarılabilir. Yetersiz iyileşme, negatif derinlik, geçersiz input ve ölçek
gauge sapması **başarı üretmeden hata** döndürür.

## Komutlar — N5 geliştirirken yalnız sentetik veri

```powershell
python -m pip install -r requirements-native.txt
python -m unittest discover -s tests -v

# Zaten var olan, sentetik N3/N4 örnek run için:
python tools/monoscan.py refine "C:\test\synthetic-session\reconstruction\runs\run-xyz" --max-nfev 90

# Tek komutta sentetik rekonstrüksiyon + N5:
python tools/monoscan.py reconstruct "C:\test\synthetic-session" --mode arkit-guided --bundle-adjust --prior-weight 2.0

# PHOTO_ONLY aynı komutla:
python tools/monoscan.py reconstruct "C:\test\synthetic-session" --mode photo-only --bundle-adjust
```

`--prior-weight` yalnız ARKit-guided regularization için kullanılır; ayarlamak
ölçülen sensör hassasiyeti atamak anlamına gelmez.

## İzlenebilir artefaktlar

Orijinal N3/N4 koşusu **değiştirilmez**.
`run-*/refinements/n5-*/` klasörüne yeni `sparse.ply`,
`tracks.json`, `cameras.json`, `summary.json` ve
`optimization.json` yazılır. Her birinin girdi kayıtları ve SHA-256
kökeni saklanır. Geometri değerleri optimize edilirken gözlem `uv`, görüntü
kimliği, iz ilişkisi, renkler ve veri kaynakları korunur.

Başlangıç ve son reprojeksiyon ortanca/ortalama/p90 (piksel), optimizer
durumu, kamera/iz/gözlem sayısı, kaynak SHA ve gauge bilgisi saklanır.
Raporlanan hatalar **iç tutarlılık** ölçüleridir; gerçek dünya doğruluğu,
ölçek hassasiyeti veya VIO güven aralığı olarak kullanılmaz.

## N5 sentetik kabul matrisi

- Sayısal olarak üretilen kamera/3B sahnede kamera ve nokta parametrelerinin
  birlikte değişmesi; reprojeksiyon medyanının iyileşmesi.
- PHOTO_ONLY birinci kamera pose gauge'inin sabit kalması.
- ARKit VIO `pose_source=arkit_vio`, kovaryansın bilinmiyor statüsünün
  tüm çıktılarda korunması.
- Tekil outlier'a dayanıklılık; iterasyon bütçesi aşımında PARTIAL ayrımı.
- Eksik/bozuk/geçersiz kameralar, duplicate görüntü-iz ve negatif derinlik
  hatalarının çıktısız başarısız olması.
- Orijinal N3/N4 koşusunun değişmemesi; her N5 çalışmasının ayrı dizin ve
  SHA kökeniyle üretilmesi.
- Linux/Windows Python 3.11/3.13, Swift/ZIP sözleşmesinin kırılmaması.
- **N9'a kadar gerçek fotoğraf, gerçek iPhone ve metrik saha kabulü yapılmaz.**

## Sonraki iş

N6: çoklu-görüş derinlik, tutarlılık ve nokta füzyonu; yüzey örme,
programatik sentetik sahnelerle doğrulanacak. N7–N8 arayüz/sistem ve sentetik
kabul; N9 fiziksel/gerçek fotoğraf kabulü.
