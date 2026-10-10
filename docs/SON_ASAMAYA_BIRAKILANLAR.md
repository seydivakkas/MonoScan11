# MonoScan11 — En son aşamaya bırakılan işler (DONMUŞ KAPSAM)

**Karar tarihi:** 10 Ekim 2026  
**Geliştirme bilgisayarı:** Windows.  
**Mühendislik kararı:** macOS/Xcode ve fiziksel iPhone 11 gerektiren hiçbir iş, Windows P0/P1 kod/test/dokümantasyon işleri tamamlanmadan zorunlu kabul edilmeyecek.

## Şu anda tamamlanabilenler (Windows / GitHub)

- [x] Kodun yerel/offline-first mimarisi ve sınırlamalarının belgelenmesi.
- [x] Pinhole iki-görüş triangulation matematiği, degeneracy/cheirality/gap testleri.
- [x] Sentetik nokta bulutu ve matematiksel MAE/RMSE deney aracı (gerçek dünya kanıtı DEĞİL).
- [x] JPEG/PNG görüntü ve ARKit session.json kontrolleri.
- [x] COLMAP sparse/dense komut planı, dry-run, güvenli mevcut-çıktı koruması.
- [x] COLMAP `images.bin` ve `points3D.bin` çözümleyici, sparse PLY aktarımı.
- [x] Windows/Ubuntu için GitHub Actions iş akışı ve otomatik testler.
- [x] README, kaynak lisansı, ilk teknik mimari, yayınlama rehberi.
- [ ] **Gerçek çekim:** iPhone 11 normal Kamera uygulamasıyla 30–100 fotoğraf (Mac gerekmez).
- [ ] **Gerçek COLMAP:** Windows'ta sparse model, kayıtlı kamera sayısı ve reprojeksiyon raporu.
- [ ] Üç ayrı sahnede başarısızlık analizleri ve referans uzunluk ölçümleri.
- [ ] (İsteğe bağlı) Uyumlu NVIDIA GPU varsa dense MVS gerçek testi.

## En son yapılacaklar — Mac/Xcode/iPhone aşaması (BUGÜN YAPILMAYACAK)

| ID | Gecikmiş iş | Beklenen kanıt | PASS koşulu |
|---|---|---|---|
| IOS-01 | Mac üzerinde Xcode + XcodeGen ile `project.yml` projelendirme | Xcode sürümü, build log | Gerçek iPhone 11 hedefinde Build başarılı |
| IOS-02 | Kamera izinleri, ARKit yaşam döngüsü, cihaz ısınması ve bellek testi | Cihaz / iOS sürümü / test günlüğü | Aç/kapat/izin senaryolarında çökme yok |
| IOS-03 | 30+ gerçek kare ve kamera pozlarının kaydı | `session.json`, JPEG örneği, toplam kare sayısı | Windows `validate` PASS; boyut ve K uyuşuyor |
| IOS-04 | ARKit `rawFeaturePoints` çıktısı | `arkit_sparse.ply`, 3D görüntüleyici ekranı | Dosya açılır; noktalar yalnızca izleme özellikleri olarak anlatılır |
| IOS-05 | Görüntü yönü / lens kalibrasyonu | K, piksel koordinatları, arka kamera 1× deney defteri | Dönüşümler ve lens seçimi gözle doğrulanır |
| FUS-01 | ARKit VIO ve COLMAP sonuçları arasında Sim(3) hizalama | Kod, sentetik test, gerçek eşleşen kamera çiftleri | Bağımsız hata metriği açıklanır; keyfi ölçek gizlenmez |
| FUS-02 | P2 tek-görüntü derinlik / MVS karşılaştırması | Ayrı model kartları / deney raporu | Tahminlerin kalibre edilmediği açıkça belirtilir |
| QA-01 | Gerçek ölçümlerle karşılaştırma | Ölçek çıpası + bağımsız referans uzunluğu | Gerçek hata (mm, %) raporu oluşturulur |
| RELEASE-01 | Mobil uygulama dağıtımı | İmzalı iOS build, cihaz kabul tutanağı | Yalnızca testten sonra mobil sürüm yayımlanır |

## Kapı kriterleri

1. **GitHub kod deposuna gönderim:** Mac/Xcode gerektirmez. Birim testleri, dokümantasyon ve temel güvenlik kontrolü yeterli.
2. **Alpha kaynak sürümü:** `v0.1.0-alpha` etiketi uygundur; hiçbir gerçek ölçüm iddiası yok.
3. **iPhone uygulamasını çalışıyor ilan etme:** IOS-01/02/03 sonuçları olmadan yasak.
4. **Gerçek sahnede 3D tarama başarılı ilan etme:** Fotoğraftan gerçek COLMAP modeli olmadan yasak.
5. **Ölçüm doğruluğu ilan etme:** QA-01 tamamlanmadan yasak.
6. **Son ürün / stable:** Cihaz, sahada 3D model, hata metrikleri ve kullanıcı kabul testleri olmadan yasak.

**Not:** SwiftUI/ARKit prototipinin kaynak kodunu bugünden depoda tutacağız; *derlendi, cihazda açıldı veya çalışıyor* iddiasını eklemeyeceğiz. Bu dosya projenin Mac/Xcode gerektiren işleri son ana bıraktığımız kararının kayıt defteridir.
