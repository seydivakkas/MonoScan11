---
name: iPhone 11 Xcode kabul testi (SON AŞAMA)
about: macOS/Xcode gerektiren cihaz kabulünü takip et
labels: ['ios', 'deferred']
---

## Bu işi neden son aşamaya bıraktık?

Proje Windows üzerinde geliştiriliyor. macOS ve Xcode olmadan yerel ARKit iOS uygulamasını imzalamak/cihaza dağıtmak doğrulanamaz.

## Test ortamı

- Mac modeli / Xcode sürümü:
- iPhone 11 / iOS sürümü:
- Commit SHA:

## Kabul

- [ ] IOS-01: XcodeGen + Build PASS (derleme günlüğü)
- [ ] IOS-02: açılış/izin/ön plan/arka plan PASS
- [ ] IOS-03: 30+ RGB kare ve `session.json` Windows `validate` PASS
- [ ] IOS-04: `arkit_sparse.ply` açıldı; LiDAR olarak yanlış sunulmadı
- [ ] IOS-05: görüntü yönü, K ve pozlar gözle doğrulandı

**Şimdilik HOLD.** `docs/SON_ASAMAYA_BIRAKILANLAR.md`.
