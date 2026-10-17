"""N9-A temporal selection regression uses generated RGB ONLY (not public data)."""
import json
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from monoscan_core.n9_public_adapter import (
    RealDatasetError, prepare_arkitscenes_session,
)
from scripts.n9a_temporal_real_ci import _depth_from_real_sparse, PREDECLARED_COHORTS


class N9ATemporalProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source=self.root/"41069046"
        (self.source/"lowres_wide").mkdir(parents=True)
        (self.source/"lowres_wide_intrinsics").mkdir()
        rng=np.random.default_rng(19)
        base=rng.integers(0,256,(192,256,3),dtype=np.uint8)
        rows=[]
        for i in range(60):
            stamp=1000.0+i*0.25
            # World->camera translation; real candidate pose has rising baseline.
            rows.append(f"{stamp:.5f} 0 0 0 {-i*0.02:.6f} 0 0")
            stem=f"41069046_{stamp:.5f}"
            cv2.imwrite(str(self.source/"lowres_wide"/(stem+".png")),
                        np.roll(base,(i//2)%12,axis=1))
            (self.source/"lowres_wide_intrinsics"/(stem+".pincam")).write_text(
                "256 192 200 200 128 96")
        (self.source/"lowres_wide.traj").write_text("\n".join(rows)+"\n")

    def test_disjoint_time_windows_are_shorter_than_whole_scan(self):
        observed=[]
        for idx, fraction in enumerate((0.1,0.5,0.8)):
            _,a=prepare_arkitscenes_session(
                self.source,self.root/f"window-{idx}",video_id="41069046",
                max_frames=12,selection_strategy="temporal-window",
                window_start_fraction=fraction,window_seconds=3.0)
            selection=a["selection"]
            self.assertEqual(selection["strategy"],"temporal-window")
            self.assertLessEqual(selection["selected_timestamp_span_seconds"],3.001)
            self.assertEqual(selection["selected_frame_count"],12)
            self.assertGreater(selection["camera_center_extent_nominal_m"],0.05)
            self.assertFalse(selection["visual_overlap_confirmed_by_selection"])
            observed.append(json.loads((self.root/f"window-{idx}"/"session.json").read_text())["frames"][0]["timestamp"])
        self.assertLess(observed[0], observed[1])
        self.assertLess(observed[1], observed[2])
        _,whole=prepare_arkitscenes_session(
            self.source,self.root/"uniform",video_id="41069046",max_frames=12)
        self.assertGreater(whole["selection"]["selected_timestamp_span_seconds"],10.0)

    def test_invalid_window_rejected_before_data_copy(self):
        for arg in (
            {"selection_strategy":"unknown"},
            {"selection_strategy":"temporal-window","window_start_fraction":1.5},
            {"selection_strategy":"temporal-window","window_seconds":0},
        ):
            with self.assertRaises(RealDatasetError):
                prepare_arkitscenes_session(
                    self.source,self.root/"invalid",
                    video_id="41069046",**arg)
        self.assertFalse((self.root/"invalid").exists())

    def test_no_synthetic_reference_depth_can_pass_without_actual_models(self):
        with self.assertRaises((OSError, ValueError)):
            _depth_from_real_sparse(self.root/"no_model")
        self.assertEqual(len(PREDECLARED_COHORTS),4)


if __name__=="__main__":
    unittest.main()
