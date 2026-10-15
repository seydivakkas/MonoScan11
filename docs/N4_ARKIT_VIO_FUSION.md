# N4 — ARKit VIO priors and COLMAP-free SfM integration

Status: **N4 code implementation, synthetic verification only**. Real captures, camera
calibration, real imagery and physical accuracy acceptance are reserved for N9.

## Scope delivered

- `monoscan_core/arkit_fusion.py`: strict session.json v1 pose priors, explicit
  CV +Z / ARKit -Z camera frame conversion, no fabricated covariance,
  deterministic robust Sim(3) alignment diagnostics for PHOTO_ONLY camera centers.
- `monoscan_core/arkit_guided.py`: opt-in triangulation in ARKit world using
  reciprocal SIFT matches, geometric cheirality/parallax/reprojection checks;
  projects existing landmarks before expanding tracks; rejects conflicts;
  writes independent run folder and clearly labelled uncertainty.
- `tools/monoscan.py`: `reconstruct --mode arkit-guided` and
  `align-arkit <native-photo-run> <session-folder>` CLI commands.
- `tests/test_arkit_fusion.py`: synthetic-only pose convention, missing tracking
  quality, low baseline, corrupt manifests, scale/rotation/translation recovery,
  collinearity rejection, outlier rejection, guided 3-camera point clouds and
  no-fake-success guards.

## Supported reconstruction modes

| Mode | Camera orientation/position | Scale and provenance |
|---|---|---|
| `photo-only` | Native image-only essential/PnP; never silently replaced by ARKit | Arbitrary |
| `arkit-guided` | Captured ARKit 4x4 transforms from session.json v1 | ARKit VIO nominal meters; not metrologically verified |
| `align-arkit` | Non-mutating, diagnostic similarity alignment of PHOTO_ONLY pose centers to saved ARKit centers | Sim(3) scale + inlier/outlier residual; not independent uncertainty |

The `align-arkit` command DOES NOT overwrite or rescale existing PHOTO_ONLY PLY
and does not declare metric correctness. Passing different scene sessions or
insufficient/non-collinear camera centers must fail closed. The resulting
residuals reflect **agreement between two pose sources**, not physical truth.

## CLI

```powershell
python -m pip install -r requirements-native.txt
python tools/monoscan.py validate "C:\scan-data\synthetic-session"
python tools/monoscan.py reconstruct "C:\scan-data\synthetic-session" --mode arkit-guided
python tools/monoscan.py align-arkit "C:\scan-data\synthetic-session\reconstruction\runs\run-..." "C:\scan-data\synthetic-session"
```

The last command accepts **PHOTO_ONLY runs only**. Direct `arkit-guided` mode
requires exactly matched image names and a valid ARKit v1 session. **Do not
run these commands on actual photos before N9**; these are documented
interfaces intended for synthetic developers/CI in N4–N8.

## Uncertainty and acceptance boundaries

- `SessionFrame` in Swift currently stores `file`, `timestamp`,
  `width`, `height`, `intrinsics`, `cameraToWorld`. It does
  **not** store calibrated per-frame covariance or reliable numerical
  translation/rotation uncertainty. Therefore
  `translation_sigma_m=null`, `rotation_sigma_deg=null` and
  `pose_covariance_available=false` are REQUIRED.
- `trackingState` is NOT present in existing v1 captures. Its absence maps
  to `unreported`, never inferred `normal`. If an optional future synthetic
  record explicitly says `limited` or `notAvailable`, N4 rejects it.
  Future real-device metadata/validated uncertainty schema needs separate
  N7/N9 review.
- Internal reprojection residuals (pixels), Sim(3) inlier errors (ARKit nominal
  metres) and movement baselines cannot prove physical length accuracy.
- `metric_scale_known=false` and `real_world_validated=false` remain set
  in native run reports. No LiDAR/dense-scan claim.
- `arkit-guided` does **not** implement Bundle Adjustment; that remains N5.
  It does not infer dense depth; that remains N6.
- ARKit camera pose conversion changes only the camera axes; ARKit world is
  retained as-is. `K` must correspond to the exact image orientation and
  dimensions; distorted/unverified camera inputs remain an N9 limitation.
- A source with little translation, insufficient track support, bad pose input
  or weak Sim(3) consensus fails without creating a successful model.
- Raw image input, session manifest and prior output runs are never changed.
  Output files are created under distinct `reconstruction/runs/run-*` paths.

## Next implementation gates

1. **N5:** pose-prior-aware sparse Bundle Adjustment with genuine measured
   covariance only when available, otherwise explicit conservative weights/
   diagnostics without pretending sensor uncertainty is calibrated.
2. **N6:** multi-view depth consistency, dense fusion and mesh from generated
   synthetic scenes.
3. **N7–N8:** make all options accessible across Windows/iOS workflow; run
   synthetic CI, security and artifact/metadata consistency checks.
4. **N9 FINAL:** real iPhone11, real photos, true intrinsics/lens/exposure
   behavior, multi-scene accuracy references and user acceptance.

