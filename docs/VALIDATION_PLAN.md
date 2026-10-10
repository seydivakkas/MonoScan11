# MonoScan11 saha değerlendirme planı

## Kaynak gerçekliği (ground truth)

- Her sahnede iki fiziksel mesafeyi hassasiyeti bilinen mezura veya lazer ölçer ile ölç.
- Kayıt: gerçek ölçüm (m), model ölçümü (model birimi), ölçek çıpası, hata (mm), göreli hata (%).
- İlk fiziksel uzunlukla modeli ölçeklendir; **ikincisini bağımsız değerlendirmede kullan**.
- SfM ölçüsü tek başına mutlak metrik ölçek sağlamaz; ARKit VIO ölçeği ayrıca test edilmelidir.

## Deney matrisi

| Deney | Sahne | Değişken | Başarısızlık senaryosu |
|---|---|---|---|
| T1 | Kutu/kitap/masa | 30–60 görüntü, sabit ışık | Düşük örtüşme |
| T2 | Küçük oda | 50–100 görüntü | Tek renkli duvar |
| T3 | Koridor | 50–100 görüntü | Tekrarlayan geometri |

## İzlenecek metrikler

- Kaydedilen / eşlenen / COLMAP tarafından kayıt edilen görüntü sayıları
- 3D nokta sayısı; yeniden projeksiyon hatası (COLMAP çıktıları üzerinden)
- Nokta bulutu/mesh bütünlüğü; duvar düzlemsellik kalıntıları (geliştirme aşaması)
- Ölçeklenmiş modelde uzunluk göreli hatası ve mutlak hatası
- Toplam rekonstrüksiyon süresi, bellek tepe kullanımı, CPU/GPU yapılandırması
- Düşük ışık, doku eksikliği, ayna, hareketli insan ve bulanıklık için ayrı başarısızlık kaydı

## Raporlama kuralı

Sahada çalıştırılmamış kod için 'gerçek cihazda doğrulandı', gerçek görüntüyle denetlenmemiş rekonstrüksiyon için '3D model başarıyla üretildi' ifadelerini kullanmayın. Metrik ve başarı eşiği ancak test protokolü ve ground-truth ölçümlerinden sonra sabitlenecek.
