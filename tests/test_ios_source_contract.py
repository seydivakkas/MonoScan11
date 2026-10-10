"""Windows-compatible static checks: not a replacement for Xcode build."""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
IOS = ROOT / 'ios' / 'MonoScan11'


class SwiftSourceContract(unittest.TestCase):
    def test_18_screen_families_present(self):
        required = {
            'SplashScreen', 'OnboardingScreen', 'HomeScreen', 'NewScanScreen',
            'PermissionsScreen', 'CaptureScreen', 'QualityScreen', 'SummaryScreen',
            'GalleryScreen', 'SparseScreen', 'ExportScreen', 'ProjectsScreen',
            'ProjectDetailScreen', 'GuideScreen', 'SettingsScreen', 'RecoveryScreen',
        }
        sources = '\n'.join(p.read_text(encoding='utf-8') for p in IOS.glob('*.swift'))
        found = set(re.findall(r'\bstruct\s+(\w+)\s*:\s*View\b', sources))
        self.assertFalse(required - found, f'Missing view types: {required - found}')

    def test_real_data_no_mock_counters(self):
        engine = (IOS / 'ScanEngine.swift').read_text(encoding='utf-8')
        self.assertIn('frame.camera.intrinsics', engine)
        self.assertIn('frame.camera.transform', engine)
        self.assertIn('frame.rawFeaturePoints', engine)
        self.assertIn('UIImage(cgImage: cg).jpegData', engine)
        self.assertNotIn('sceneDepth =', engine)

    def test_project_and_zip_contracts(self):
        store = (IOS / 'ScanStore.swift').read_text(encoding='utf-8')
        zipper = (IOS / 'ZIPStore.swift').read_text(encoding='utf-8')
        self.assertIn('project.json', store)
        self.assertIn('ScanContract.validateManifest', store)
        self.assertIn('session.json', zipper)
        self.assertIn('0x04034B50', zipper)
        self.assertIn('0x02014B50', zipper)
        self.assertIn('0x06054B50', zipper)
        self.assertIn('output.synchronize()', zipper)

    def test_project_sources_in_xcodegen(self):
        yml = (ROOT / 'project.yml').read_text(encoding='utf-8')
        self.assertIn('path: ios/MonoScan11', yml)
        self.assertIn('NSCameraUsageDescription:', yml)
        self.assertIn('UIFileSharingEnabled:', yml)

    def test_test_fixture_exists(self):
        self.assertTrue((ROOT / 'tests/fixtures/tiny8.jpg').is_file())
        self.assertTrue((ROOT / 'assets/screenshots/approved-storyboard-14.png').is_file())

if __name__ == '__main__':
    unittest.main()
