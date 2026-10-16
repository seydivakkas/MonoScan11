# N7 — Windows masaüstü bütünleşik arayüz ve iPhone ZIP sözleşmesi

**Durum:** N7 kodu geliştirme dalında; otomatik sentetik test sözleşmesi.
**Gerçek fotoğraf/telefon/saha performansı ve son Windows kullanıcı kabulü N9'da.**
N7 arayüzü, veri olmadığı halde 3B model, sayısal metrik doğruluk,
yüzdelik ilerleme veya tamamlanmış kamera optimizasyonu göstermemelidir.

## Windows masaüstü — nasıl çalıştırılır?

```powershell
python -m pip install -r requirements-native.txt
python scripts/monoscan_desktop.py
```

Windows'ta `MonoScan11-Desktop.cmd` dosyası da aynı uygulamayı başlatır.
Python 3.11/3.13, standart kütüphane `tkinter` ve belirtilen native bağımlılıklar
gerekir. Kullanıcıya zorunlu bulut, kayıt, ücretli API, dış COLMAP yüklemesi
ya da hesap açma sunulmaz. İşlenmiş ve orijinal veriler yerelde kalır.
Henüz imzalı EXE/MSIX veya Windows yükleyici yayımlanmadı.

## Ekran ve kullanım akışı

```text
+-----------------+-----------------------------+------------------------+
| Projeler        | 3B Önizleme                 | N3-N6 İşlem Hattı      |
|                 |                             |                        |
| iPhone ZIP      | [Yerel native run seçimi]   | PHOTO_ONLY / ARKit     |
| klasörü bağla   | [Seyrek/BA] [Yoğun] [Mesh]  | focal, BA, dense       |
|                 |                             | derinlik aralığı       |
| Kayıtlar        | Gerçek PLY/OBJ görüntüsü    | VIO heuristik prior    |
| (kullanıcı)     | döndürme/yakınlaşma         | sentetik onayı         |
|                 |                             | doğrula / başlat       |
|                 | [Kanıt / belirsizlik]       | seçili N5 / N6         |
|                 | [İşlem günlüğü]             | iptal / aşamalar       |
+-----------------+-----------------------------+------------------------+
```

**Proje katalogu:** `monoscan_core/workspace.py`
`%LOCALAPPDATA%\MonoScan11\workspace\projects.json` altında
bağımsız JSON kayıtları saklar. `ZIP` paketi yönetilen oturum dizinine
atomik içe alınır. Yerel klasör bağlantısı yalnız referans oluşturur.
Katalog kaydını kaldırma hiçbir görüntü, ZIP veya üretilmiş modeli silmez.

**iPhone ZIP içe aktarımı:** Swift `ZIPStore.swift` sözleşmesi korunur:
`session.json` v1, `images/<file>`, isteğe bağlı
`project.json` ve `arkit_sparse.ply`. Girdi SHA doğruluğu iPhone ZIP
CRC doğrulaması ile denetlenir; ZIP adı/traversal, yinelenen büyük-küçük harf,
şifreli/sıkıştırılmış veya beklenmeyen dosya, symlink ve boyut limitleri
kontrol edilmeden dosya çıkarılmaz. **Sadece Swift'in ürettiği method-0 ZIP32**
kabul edilir; genel ZIP açıcı yapılması amaçlanmaz. İçe alındıktan sonra
orijinal Python oturum doğrulayıcısı çalışır; sahte/uyumsuz paket katalogda
başarılı işaretlenmez.

**İşlem hattı:** `monoscan_core/workflow.py` mevcut
`tools/monoscan.py` komutlarını ayrı yerel Python süreçlerinde çalıştırır:

1. `validate` — kullanıcı oturum dosyaları ve matris sözleşmesi.
2. `reconstruct --mode photo-only|arkit-guided` — N3/N4 seyrek çıktı.
3. `refine` (isteğe bağlı) — N5, ayrı optimize edilmiş run.
4. `dense` (isteğe bağlı; bütünleşik akışta N5 gerekir) — N6 derinlik,
   voxel ve OBJ mesh.

Her bir aşama için `start`, `complete`, `failed`, `cancelled`
olayları üretilir. Native çekirdek henüz gerçek alt-adım yüzdeleri vermediği
için arayüz yalnız **aşama durumu** ve belirsiz (indeterminate) işlem çubuğu
gösterir; sahte %90 gibi bir ilerleme üretilmez. İptal talebi yerel child
process'e gönderilir; önceden tamamlanmış sonuçlar saklanır ve `SUCCESS`
gösterilmez. Kullanıcının mevcut N5/N6 modelini tek başına yeniden
çalıştırması mümkündür.

**3B görüntüleyici:** `monoscan_core/preview.py` yalnız halihazırda
var olan ASCII `sparse.ply`, `dense.ply` ve üçgenli `mesh.obj`
dosyalarını salt okunur açar. Kaynak noktaların rengini/koordinatlarını
koruyarak yalnız çizim performansı için örnekler. Fareyle döndürme/zoom var.
N6 yüzey **açıktır (watertight değil)** ve numune geometrisi ancak
gerçek dosyada mevcutsa çizilir. Eksik/sahte run durumunda boş ekran.

**Belirsizlik ve kanıt:** `summary.json` içindeki reprojeksiyon hatası,
çalışan mod, kayıtlı kamera, nokta sayısı, CPU MVS destek durumu,
ARKit VIO ölçeği ve `warnings` görüntülenir.
`real_world_validated` N7 tarafından kesinlikle üretilmez;
`translation_sigma_m` / `rotation_sigma_deg` v1 sözleşmesinde
bulunmadığı için gerçek ölçüm kovaryansı olarak gösterilmez.
Derinlik ölçeği PHOTO_ONLY'da keyfî, ARKit'te yalnız yaklaşık metredir.

## N7 kaynak dosyaları

| Dosya | Görev |
|---|---|
| `monoscan_core/workspace.py` | Katalog, ZIP güvenliği, CRC/natif doğrulama, atomik import |
| `monoscan_core/workflow.py` | N3–N6 süreç kontrolü, aşama olayları, kaydedilmiş run keşfi |
| `monoscan_core/preview.py` | Salt-okunur PLY/OBJ görüntü kaynağı ve 3B izdüşüm |
| `monoscan_core/desktop.py` | Tkinter proje/önizleme/işlem/kanıt panelleri |
| `scripts/monoscan_desktop.py` | Python GUI başlatıcısı |
| `MonoScan11-Desktop.cmd` | Windows çift tık başlatıcısı |
| `tests/test_desktop_workstation.py` | Sentetik ve headless entegrasyon testleri |
| `.github/workflows/tests.yml` | Windows/Linux testleri + gerçek Swift ZIP → N7 import zinciri |

## Test ve kabul sınırları

- Sentetik geçerli PNG/manifest/ZIP kullanılır; gerçek fotoğraf **yok**.
- Güvensiz ZIP, bozuk manifest, yanlış SHA, tekrarlı dosya, olmayan run
  ve çok büyük/uygunsuz PLY/OBJ kaynakları kesin başarı üretemez.
- Kararlı yerel proje kayıtları tekrar açılır; linked klasör silinmez.
- Sıralı işlerde hata veya iptal sonrası sahte sonraki aşama başarı olayı yok.
- Native çıktı yoksa 3B tuval boş durum gösterir; dijital maket demo
  gerçeği gibi pazarlanmaz.
- Swift/ZIP sözleşmesi, Swift tarafından yazılan **aynı dosyanın**
  N7 içe aktarıcısına verilmesiyle CI içinde doğrulanır.
- Linux/Windows Python 3.11/3.13 ve Swift/ZIP CI testleri otomatik çalışır.
- Kaynak dosyaların koşu ve görüntüleme sırasında üzerine yazılması yasaktır.
- Tkinter görsel/ergonomik kabul, çok büyük sahnede hız-bellek, son Windows
  yükleyici ve klavye/erişilebilirlik testleri **N8/N9'un açık maddeleridir**.
- Kullanıcının sentetik oturum onayı N7 arayüzünde zorunlu; gerçek fotoğraf
  deneyleri N9 kapısına ertelenmiştir.

## Sıradaki aşama — N8

Sentetik uçtan uca ZIP → N3/N4 → N5 → N6 → N7 akışına
performans/bellek/tekrar edilebilirlik deneyleri, geniş veri sınırları,
regresyon ve erişilebilirlik kontrolleri. Gerçek iPhone/lens/sahada hata
ölçümü ise yalnızca N9'dadır.
