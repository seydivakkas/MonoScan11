"""N1 synthetic tests: NOT evidence of actual iPhone depth accuracy."""
import unittest

import numpy as np

from monoscan_core.camera import (
    CameraGeometryError, adjusted_intrinsics, arkit_to_cv_pose,
    bearing, camera_to_world, project, world_to_camera,
)


class NativeCameraTests(unittest.TestCase):
    def test_rotated_projection_round_trip(self):
        theta = np.deg2rad(20)
        c, s = np.cos(theta), np.sin(theta)
        pose = np.eye(4)
        pose[:3, :3] = [[c, 0, s], [0, 1, 0], [-s, 0, c]]
        pose[:3, 3] = [1.2, 0.3, -2.0]
        k = [[780, 0, 640], [0, 790, 480], [0, 0, 1]]
        cv_point = np.array([[0.4, -0.2, 3.0]])
        world = cv_point @ pose[:3, :3].T + pose[:3, 3]
        uv = project(world, k, pose)
        ray = bearing(uv, k)[0]
        expected = cv_point[0] / np.linalg.norm(cv_point[0])
        np.testing.assert_allclose(ray, expected, atol=1e-10)
        np.testing.assert_allclose(world_to_camera(pose) @ pose, np.eye(4), atol=1e-10)

    def test_arkit_forward_is_cv_forward(self):
        pose = arkit_to_cv_pose(np.eye(4))
        np.testing.assert_allclose(pose[:3, :3], np.diag([1, -1, -1]))
        # Apple camera forward -Z projects at the principal point.
        xy = project([[0, 0, -2]], [[800, 0, 320], [0, 800, 240], [0, 0, 1]], pose)
        np.testing.assert_allclose(xy[0], [320, 240])

    def test_scale_intrinsics(self):
        k = [[800, 0, 400], [0, 600, 300], [0, 0, 1]]
        np.testing.assert_allclose(adjusted_intrinsics(k, (800, 600), (400, 300)),
                                   [[400, 0, 200], [0, 300, 150], [0, 0, 1]])

    def test_improper_pose_rejected(self):
        bad = np.eye(4); bad[0, 0] = -1
        with self.assertRaises(CameraGeometryError):
            camera_to_world(bad)

    def test_behind_camera_rejected(self):
        with self.assertRaises(CameraGeometryError):
            project([[0, 0, -2]], np.eye(3), np.eye(4))


if __name__ == "__main__":
    unittest.main()
