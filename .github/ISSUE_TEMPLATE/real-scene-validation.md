---
name: Windows gerçek fotoğraf COLMAP doğrulaması
about: macOS gerektirmeyen gerçek rekonstrüksiyon kabulü
labels: ['validation', 'windows']
---

## Ortam

- Windows sürümü / Python / COLMAP sürümü:
- CPU / RAM / (varsa GPU):
- Kişisel fotoğraf paylaşılmayacak; örnekler varsa açık rıza ve lisans:

## Beklenen kanıt

- [ ] 30–100 adet aynı lensle çekilmiş JPEG/PNG
- [ ] `validate` çıktı özeti (özel dosya adlarını gerekirse anonimleştir)
- [ ] `--dry-run` parametreleri ve gerçek COLMAP komutu
- [ ] `reconstruction/sparse/0` kaydı ve `inspect` sonucu
- [ ] Kayıtlı görüntü oranı, nokta sayısı, reprojeksiyon hatası
- [ ] Başarısız görüntüler, süre, CPU/RAM ölçümü
- [ ] Fiziksel referans uzunluğunun bağımsız kontrolü (metre ölçeklendirmeden önce ölçüm iddiası yok)

**Durum:** PENDING; algoritma test PASS'ı gerçek fotoğraf deneyi yerine geçmez.
