# MonoScan11 — native SfM migration (N0–N3)

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
5. subsequent iterations: local bundle adjustment; ARKit pose quality and priors
6. subsequent iterations: physically grounded dense MVS and optional meshing

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
