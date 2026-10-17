# N8 — Sentetik sistem kabulü, performans, paketleme ve hata kurtarma

**Durum:** N8 aday sürüm, sentetik CI ve dokümantasyon. İlk gerçek fotoğraf,
gerçek iPhone 11, kamera/lens, bağımsız metrik ölçüm ve kullanıcı kabulü
**yalnız N9**. N8'de bunlarla ilgili başarı, hassasiyet veya cihaz uyumluluğu
iddiası üretmek yasaktır.

## N8 kapsamı

| Alan | Dosya / metodoloji | Kabul kanıtı |
|---|---|---|
| Gerçek native sentetik uçtan uca zincir | `scripts/n8_synthetic_acceptance.py` | Prosedürel ZIP → N7 güvenli importer → N4 kamera+SIFT → N5 BA/skip → N6 CPU MVS → N7 gerçek kayıt ve PLY/OBJ önizleme |
| Aynı-girdi tekrar edilebilirlik | İki ayrı native çalışma, normalize olmayan gerçek geometri çıktı SHA-256 karşılaştırması | **Aynı CI makinesinde** ardışık iki çalıştırma; platformlar arası bit düzeyinde eşitlik iddiası yok |
| Süre ve bellek | `time.perf_counter`, `tracemalloc`, OS tepe RSS | Aşamaların gerçek duvar saati saniyeleri ve süreç ölçüm kapsamı raporda |
| Kaynak bütünlüğü | Kaynak ZIP SHA-256 ve ithal görüntülerin işlemden önce/sonra SHA-256 eşitliği | Gerçek görüntü silme, yeniden yazma, telemetri yok |
| İşlem hata kurtarma | `ProjectCatalog.recovery_findings` | Yarım import, kayıt dışı oturum, temp indeks: tespit edilir, **otomatik silinmez** |
| Çocuk süreç iptal/zaman aşımı | `run_command` timeout + `communicate` veri akışı | stdout/stderr tıkanma testi, iptal, zorunlu öldürme; sahte başarı yok |
| Erişilebilirlik adayları | N7 Tk kısa yollar/focus, statik metin kontrast testi | Klavye ile 3B döndürme, kısayollar, F1 yardımı, WCAG AA metin kontrastının statik testi |
| Windows dağıtım hazırlığı | `scripts/package_n8_windows.py` | Deterministik **kaynak ZIP'i**, SHA-256 envanteri, test edilmiş verify; imzalı .exe yok |

## Prosedürel tam zincir

Sentetik sahne gerçek fotoğraftan dönüştürülmez: sabit `NumPy` seed ile
üretilen rastlantısal yüzey deseni ve geometrik işaretler, 4 farklı
kamera merkezinden sayısal pinhole projeksiyonu ile görüntüye aktarılır.
Kaydedilmiş PNG'ler gerçek görüntü dosyalarıdır ama içlerindeki sahne
**tamamen sentetiktir**. N4 görüntü içeriğini SIFT ile okur; gerçek
eşleşmelerden üçgenleme yapar, sentetik ground truth derinliği modele
verilmez. N5 optimizasyonu gerçekleştirir; başlangıç hatası çok düşükse
`skipped_already_consistent` ve `PARTIAL` raporu ile geometriyi
değiştirmeyebilir. N6 piksel tabanlı MVS, çapraz derinlik, voxel ve açık
OBJ yapar. N7 var olan run'ları diskten keşfeder ve rapor/önizleme açar.

```powershell
python -m pip install -r requirements-native.txt
python scripts/n8_synthetic_acceptance.py --repeat 2 --planes 36 --max-side 112 --output n8-acceptance.json
```

Rapor alanları: `duration_total_seconds`, `runs[*].stage_seconds`,
`python_tracemalloc_peak_bytes`, `rss`,
`same_host_artifact_sha256_equal`, model/mesh sayı göstergeleri,
`physical_device_tested=false`, `real_world_validated=false`.

**Ölçüm sınırlaması:** `tracemalloc` yalnız N8 kontrolcüsündeki
Python tahsislerini izler; OpenCV ve SciPy native ayırıcıları içermez.
Linux'ta `resource.RUSAGE_CHILDREN.ru_maxrss` çocuk işlerin *tepe*
RSS değerini temsil eder; tüm işlemlerin anlık toplamı değildir.
Windows'la çocuk tepe RSS'si bu sürümde **ölçülmüyor (null)**.
Bu sayılar Windows/iPhone tüketici cihazları için kesin performans
garantisi veya bellek bütçesi değildir.

N8 CI'da sürekli trafik altında kırılgan mutlak milisaniye/MB geçme
eşikleri kullanılmaz. Performans raporları kaydedilir, üst sınırlar
mimari/algoritmik kapıdan kontrol edilir. Gerçek cihaz süre/ısı/bellek
kabulü N9 kapısında gerçekleştirilir.

## Güvenli işleme ve hata kurtarma

1. ZIP girişine path traversal, çoklu ad, bozuk kayıt, bilinmeyen dosya,
   şifreleme/sıkıştırma ve boyut denetimleri.
2. Oturum görüntüleri bir kaynak dizininde kalır, orijinal byte
   karşılaştırması ve dosya izi doğrulanır.
3. Her N4/N5/N6 koşusu farklı dizine yazılır. Önceden yayımlanmış
   `sparse.ply`, `depth_maps.npz`, `mesh.obj` üzerine yazılmaz.
4. Yarıda kalan `.import-*`, `.index-*.json`, katalog dışı
   `sessions/*` klasörleri `recovery_findings` ile raporlanır.
   Dosyalar **kendiliğinden silinmez**, kurtarma kararı kullanıcınındır.
5. Subprocess stdout/stderr birlikte tüketilir; iptalde child process
   sonlandırılır, önceki başarılı run korunur. İptal edilen veya
   yetersiz geometri içeren işlem `SUCCESS` durumuna yükseltilmez.
6. İlk reprojeksiyonu zaten sayısal olarak ihmal edilebilir olan N4
   modelinin BA ile bozulmasını engelleyen `N5 skipped_already_consistent`
   sonucu **optimize edilmiş başarı değildir**; rapor `PARTIAL` tutar.

## Windows arayüzü klavye sözleşmesi

| Tuş | İşlem |
|---|---|
| Tab / Shift+Tab | Denetimler arasında gezinme |
| Ctrl+O | iPhone ZIP seçicisi |
| Ctrl+L | Yerel klasör bağlama |
| Ctrl+R | Run listesi yenileme |
| F5 | Seçili sentetik oturumda işlem hattı |
| Esc | Etkin işleme iptal isteği |
| F1 | Klavye yardım penceresi |
| 3B tuval seçiliyken yön tuşları | Kamera gösterimini döndür |
| Ctrl++ / Ctrl+- | Yakınlaştır/uzaklaştır |

Pencere ve Tk denetimlerinin Windows CI'da açıldığı, klavye
bağlantıları ve metin kontrastları otomatik sınanır. **NVDA/JAWS/
Windows UIA ekran-okuyucu algılama, yüksek DPI, klavye odak sırası,
çeviri/dil ve gerçek kullanıcı ergonomi kabulü henüz tamamlanmadı.**
Bunlar bağımsız kullanıcı kabulünde açık kontrol kalemleridir.
`Tkinter Canvas` tam kapsamlı erişilebilir 3B grafik arayüzü değildir.

## Kaynak kod paketi ve kurulum sınırı

```powershell
python scripts/package_n8_windows.py --output dist/MonoScan11-N8-source.zip
python scripts/package_n8_windows.py --verify dist/MonoScan11-N8-source.zip
```

Paket yalnız `monoscan_core/`, `tools/`, `scripts/`,
`requirements-native.txt`, README, Windows .cmd ve mevcut lisans
dosyasını içeren kaynak tabanlı dağıtımdır. JSON içindeki her
kaynak dosya için SHA-256 bulunur; dosya sırası ve ZIP tarih damgası
sabitlenerek aynı depo içeriğiyle byte-identical çıktı hedeflenir.
**Tek başına Windows uygulaması değildir**. Python 3.11+,
Tkinter, NumPy/OpenCV/SciPy CPU tekerlekleri ayrı kurulmalıdır.
Gerçekten tamamen ağsız son kullanıcı kurulumu için sürüm kilidi,
lisans denetimi ve doğrulanmış Windows wheelhouse önceden
hazırlanmalıdır; bunların üretim kabulü yapılmış sayılmaz.

## Sonraki karar

N8 sentetik entegrasyon + kaynak bütünlüğü + otomatik GUI/ZIP kontrolü
kapanmadan N9 testi başlatma. **N9** gerçek iPhone 11/Xcode,
kalibrasyon, fotoğraf analizi, fiziksel boyut referansı, çoklu gerçek
sahne, gerçek Windows kurulum ve bağımsız UX/erişilebilirlik kabulüdür.
