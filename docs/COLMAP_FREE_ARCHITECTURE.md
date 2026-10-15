# MonoScan11 — native SfM migration (N0–N5)

**Branch:** `feature/native-sfm-n0-n3` | **Status:** experimental / no real-device validation

Decision: MonoScan11 reconstruction must not invoke `colmap`, `pycolmap`,
or any COLMAP sparse/database format. Existing `tools/colmap_models.py` is
historical read-only tooling; native production code MUST NOT import it.

The iPhone 11 SwiftUI capture/gallery/project/export flow, `session.json` v1,
JPEG names, intrinsics, ARKit camera-to-world matrix and offline ZIP contract
remain unchanged. iOS binary/device testing remains a final acceptance gate.

Native pipeline:
1. input and calibration validation (existing `tools/monoscan.py validate`)
2. geometry: explicit CV (+Z camera forward) and ARKit (-Z camera forward)
3. local OpenCV features + epipolar RANSAC, track identities
4. PHOTO_ONLY essential-matrix pair initialization / incremental PnP
5. N4: strict ARKit VIO pose prior loader, opt-in ARKit-guided triangulation and robust Sim(3) diagnostics
6. N5: robust sparse BA with simultaneous camera and point optimization, fixed photo gauge and explicitly heuristic ARKit priors
7. N6 (pending): physically grounded dense MVS and optional meshing

Constraints:
- PHOTO_ONLY has **arbitrary scale** without an external scale anchor.
- ARKit poses are approximately metric, not independent metrological proof.
- `rawFeaturePoints` are ARKit tracking features, not LiDAR or dense depth.
- Missing camera calibration must not be silently replaced with false precision.
- Never overwrite earlier reconstructions or create SUCCESS artifacts from failure.
- Work without Internet, telemetry, paid API, or camera-image uploads.
- Actual reconstruction of iPhone images, Windows installer, Xcode build, iPhone
  performance and physical dimensional accuracy remain **unverified**.

N1 coordinate convention: raw/unrotated image x right y down, CV camera
x right y down +z forward. ARKit x right y up -z forward. Matrix conversion:
`T_cvCamera_to_arkitWorld = T_arkitCamera_to_arkitWorld @ diag(1,-1,-1,1)`.
A camera pose is not equivalent to a world-coordinate basis conversion.
Input intrinsics K belong to the exact image buffer dimensions and orientation.

N1/N3 implementation limit: camera projection currently assumes undistorted
pixel coordinates. Lens distortion calibration/correction and EXIF rotations
have NOT yet been accepted on a real iPhone. Do not market 3D accuracy.


## Yürürlükteki doğrulama ertelemesi — 16 Ekim 2026

**Gerçek fotoğraf analizi SON AŞAMA (N9) olarak donduruldu.**
Geliştirmenin başında fotoğraf örneği toplama veya gerçek dünya SfM doğrulama kapısı yoktur.

Sıra: **N0–N3 (deneysel temel) → N4 (sentetik ARKit poz-füzyonu) →
N5 (sentetik BA/optimizasyon) → N6 (sentetik yoğun MVS/mesh) →
N7 (Windows/iOS arayüz ve veri entegrasyonu) →
N8 (CI, sentetik uçtan uca, performans/güvenlik, paketleme hazırlığı) →
N9 (gerçek iPhone, gerçek fotoğraf analizi ve bağımsız ölçüm kabulü)**.

N4–N8 yalnız programatik olarak üretilen fotoğraf görüntüleri, yapay kamera
pozu/kamera matrisi, sentetik nokta bulutu ve sentetik ARKit manifesti ile
doğrulanabilir. Veri kaynağı her test raporunda `synthetic` olarak etiketlenir.
Gerçek sahne fotoğrafları veya çevrim içi fotoğraf veri setleri de N9'dan önce
rekonstrüksiyon doğrulamasına sokulmaz.

**PR/review kapısı:** N0–N8 kod incelemesi ve sentetik CI sonucu yeterli ise
kod tabanına birleştirme mümkündür; gerçek veri doğrulaması PR birleştirme
için zorunlu değildir. N9 olmadan ürünün gerçek tarama performansı onaylanmaz.
Ayrıntılı sıra: [ROADMAP.md](ROADMAP.md).

## N4 implementation pointer

See [N4 ARKit VIO fusion](N4_ARKIT_VIO_FUSION.md). The existing iPhone v1 session stores camera transforms, but it does **not** contain trustworthy per-frame covariance; sigma values must be null and image reprojection disagreement must not be treated as sensor standard deviation. The N4 synthetic code is tested on CI; actual iPhone performance is N9-only.

## N5 source and contract

[Native Sparse Bundle Adjustment](N5_SPARSE_BUNDLE_ADJUSTMENT.md) implements local SciPy-based reprojection optimization in independent refinement run directories; it does not call a COLMAP executable or assert real-data acceptance. Optimization uncertainties are unknown unless measured and validated by a future reviewed acquisition schema.
