"""N6 synthetic-only depth, consistency, fusion, mesh, provenance tests.

The scene exists only as deterministic procedural imagery generated from
ray-plane intersections. Actual depth is NEVER passed to the N6 estimator.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import cv2
import numpy as np

from monoscan_core.dense_mvs import (
    DenseMVSError, reconstruct_dense, plane_sweep, cross_view_consistency,
    fuse_voxels, grid_mesh,
)


def procedural_plane_fixture(folder, *, mode="photo-only", flat=False,
                             use_n5_contract=False, baseline=0.16):
    folder = Path(folder)
    root = folder / "synthetic-session"
    image_dir = root / "images"
    image_dir.mkdir(parents=True)
    run = root / "synthetic-native-sparse"
    run.mkdir()
    w, h = 112, 88
    fx, fy = 106., 106.
    k = np.asarray([[fx, 0, w/2], [0, fy, h/2], [0, 0, 1]], np.float64)
    y, x = np.indices((h, w), dtype=np.float32)
    texture = np.random.default_rng(890).integers(0, 256, (640, 640), dtype=np.uint8)
    texture = cv2.GaussianBlur(texture, (5, 5), 0.8)
    cams = [[0.0, 0., 0.], [baseline, 0., 0.],
            [-baseline * 0.72, baseline * 0.6, 0.],
            [baseline * 0.47, -baseline * 0.8, 0.]]
    images_hash = {}
    cameras = []
    z_true = 2.3
    for i, center in enumerate(cams):
        name = f"proc_{i:02}.png"
        if flat:
            gray = np.full((h, w), 120, dtype=np.uint8)
        else:
            world_x = center[0] + (x - k[0, 2]) / fx * z_true
            world_y = center[1] + (y - k[1, 2]) / fy * z_true
            tx = (world_x * 125 + 320).astype(np.float32)
            ty = (world_y * 125 + 320).astype(np.float32)
            gray = cv2.remap(texture, tx, ty, cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_REFLECT)
        image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        file = image_dir / name
        if not cv2.imwrite(str(file), image):
            raise RuntimeError("Cannot create procedural fixture")
        images_hash[name] = hashlib.sha256(file.read_bytes()).hexdigest()
        pose = np.eye(4)
        pose[:3, 3] = center
        cam = {"image": name, "K": k.tolist(), "camera_to_world_cv": pose.tolist()}
        if mode == "arkit-guided":
            cam.update({"pose_source": "arkit_vio", "translation_sigma_m": None,
                        "rotation_sigma_deg": None})
        cameras.append(cam)
    summary = {
        "engine": "monoscan-native", "mode_used": mode,
        "input_sha256": images_hash,
        "real_world_validated": False,
        "scale_status": ("arbitrary" if mode == "photo-only"
                         else "arkit_nominal_meters_unverified"),
    }
    if use_n5_contract:
        summary.update({"stage": "N5 synthetic BA model",
                        "bundle_adjustment": "applied"})
    (run / "summary.json").write_text(json.dumps(summary))
    (run / "cameras.json").write_text(json.dumps({"cameras": cameras}))
    return run, root, z_true


class DenseMVSTests(unittest.TestCase):
    def test_plane_sweep_reciprocal_depth_and_mesh_from_procedural_pixels(self):
        from monoscan_core.dense_mvs import _read_views
        with tempfile.TemporaryDirectory() as td:
            run, root, truth = procedural_plane_fixture(td)
            _, views, _, _ = _read_views(run, root, 112)
            depth = plane_sweep(views, min_depth=1.7, max_depth=3.0, planes=43)
            self.assertEqual(len(depth), 4)
            valid = depth[0]["depth"] > 0
            self.assertGreater(np.count_nonzero(valid), 500)
            self.assertLess(abs(float(np.median(depth[0]["depth"][valid])) - truth), 0.20)
            checked = cross_view_consistency(views, depth, relative_tolerance=0.075)
            self.assertGreater(checked[0]["valid_pixels"], 250)
            self.assertLessEqual(checked[0]["valid_pixels"],
                                 depth[0]["unfiltered_valid_pixels"])
            fused = fuse_voxels(views, checked, voxel_size=0.10)
            self.assertGreater(len(fused), 80)
            self.assertTrue(all(q[2] >= 2 for q in fused))
            vertices, faces = grid_mesh(views[0], checked[0])
            self.assertGreater(len(vertices), 250)
            self.assertGreater(len(faces), 250)
            self.assertTrue(np.isfinite(vertices).all())
            self.assertTrue(all(min(f) >= 1 and max(f) <= len(vertices) for f in faces))

    def test_n6_full_outputs_are_distinct_immutable_and_not_metric(self):
        with tempfile.TemporaryDirectory() as td:
            run, root, _ = procedural_plane_fixture(td, use_n5_contract=True)
            originals = {f: (run / f).read_bytes()
                         for f in ("summary.json", "cameras.json")}
            out, report = reconstruct_dense(
                run, root, min_depth=1.7, max_depth=3., planes=43,
                max_side=112, voxel_size=0.10)
            self.assertEqual(report["engine"], "monoscan-native")
            self.assertFalse(report["metric_scale_known"])
            self.assertFalse(report["real_world_validated"])
            self.assertEqual(report["depth_units"], "arbitrary_photo_only_units")
            self.assertEqual(report["mesh_type"],
                             "single-view_open_triangulated_surface_not_watertight")
            for name in ("dense.ply", "mesh.obj", "depth_maps.npz", "summary.json"):
                self.assertTrue((out / name).is_file(), name)
            for name, content in originals.items():
                self.assertEqual((run / name).read_bytes(), content)
            # Windows keeps .npz files locked while NpzFile remains open.
            with np.load(out / "depth_maps.npz", allow_pickle=False) as depths:
                self.assertIn("depth_0", depths.files)
                self.assertFalse(np.isnan(depths["depth_0"]).any())
            other, _ = reconstruct_dense(
                run, root, min_depth=1.7, max_depth=3., planes=43,
                max_side=112, voxel_size=0.10)
            self.assertNotEqual(other, out)
            self.assertTrue((other / "mesh.obj").exists())

    def test_arkit_nominal_scale_not_certified(self):
        with tempfile.TemporaryDirectory() as td:
            run, root, _ = procedural_plane_fixture(td, mode="arkit-guided")
            out, report = reconstruct_dense(
                run, root, min_depth=1.7, max_depth=3.,
                planes=43, max_side=112, voxel_size=0.10)
            self.assertEqual(report["depth_units"], "arkit_nominal_meters_unverified")
            self.assertFalse(report["pose_covariance_calibrated"])
            self.assertFalse(report["metric_scale_known"])
            self.assertFalse(report["real_world_validated"])
            self.assertTrue((out / "mesh.obj").exists())

    def test_flat_texture_fails_without_fake_depth(self):
        with tempfile.TemporaryDirectory() as td:
            run, root, _ = procedural_plane_fixture(td, flat=True)
            with self.assertRaisesRegex(DenseMVSError, "insufficient|Insufficient|No connected"):
                reconstruct_dense(run, root, min_depth=1.7, max_depth=3.0,
                                  planes=24, max_side=112, voxel_size=0.10)
            self.assertFalse((run / "dense").exists())

    def test_changed_image_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as td:
            run, root, _ = procedural_plane_fixture(td)
            file = next((root / "images").glob("*.png"))
            file.write_bytes(file.read_bytes() + b"altered")
            with self.assertRaisesRegex(DenseMVSError, "SHA-256"):
                reconstruct_dense(run, root, min_depth=1.7,
                                  max_depth=3., max_side=112)
            self.assertFalse((run / "dense").exists())

    def test_duplicate_camera_and_no_baseline_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            run, root, _ = procedural_plane_fixture(td, baseline=0.0)
            with self.assertRaisesRegex(DenseMVSError, "baseline"):
                reconstruct_dense(run, root, max_side=112)
            self.assertFalse((run / "dense").exists())
            camfile = run / "cameras.json"
            data = json.loads(camfile.read_text())
            data["cameras"][1]["image"] = data["cameras"][0]["image"]
            camfile.write_text(json.dumps(data))
            with self.assertRaisesRegex(DenseMVSError, "duplicate"):
                reconstruct_dense(run, root, max_side=112)

    def test_bad_depth_parameters_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            run, root, _ = procedural_plane_fixture(td)
            with self.assertRaisesRegex(DenseMVSError, "settings"):
                reconstruct_dense(run, root, min_depth=3, max_depth=2,
                                  planes=20, max_side=112)
            self.assertFalse((run / "dense").exists())

    def test_cli_dense_explicit_run_and_session(self):
        with tempfile.TemporaryDirectory() as td:
            run, root, _ = procedural_plane_fixture(td)
            cmd = [sys.executable, "-m", "monoscan_core.cli", "dense",
                   str(run), str(root), "--min-depth", "1.7",
                   "--max-depth", "3.0", "--planes", "43",
                   "--max-side", "112", "--voxel-size", "0.10"]
            result = subprocess.run(cmd, cwd=str(Path(__file__).resolve().parents[1]),
                                    capture_output=True, text=True, check=False,
                                    env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["real_world_validated"])
            self.assertTrue(Path(payload["run"]).joinpath("dense.ply").exists())


if __name__ == "__main__":
    unittest.main()
