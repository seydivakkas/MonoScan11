"""Zero-dependency checks for the design-only UI assets."""
import json
import struct
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
IMG=ROOT/'assets'/'screenshots'
DOC=ROOT/'docs'/'ui'

class UIMockupManifestTests(unittest.TestCase):
    def test_all_screen_files_exist_and_are_iphone_11_size(self):
        payload=json.loads((DOC/'screens.json').read_text(encoding='utf-8'))
        self.assertEqual(payload['contract'],'UI-WF-1.0')
        self.assertEqual(len(payload['screens']),18)
        self.assertEqual([e['id'] for e in payload['screens']],list(range(1,19)))
        names=[e['file'] for e in payload['screens']]
        self.assertEqual(len(names),len(set(names)))
        self.assertEqual(names,sorted(names))
        for name in names:
            with self.subTest(name=name):
                raw=(IMG/name).read_bytes()
                self.assertTrue(raw.startswith(b'\x89PNG\r\n\x1a\n'))
                self.assertEqual(struct.unpack('>II',raw[16:24]),(828,1792))

    def test_contract_and_contact_sheet_present(self):
        self.assertTrue((DOC/'MonoScan11-iPhone11-Wireframe-v1.txt').is_file())
        self.assertTrue((IMG/'contact-sheet.png').is_file())
        readme=(DOC/'README.md').read_text(encoding='utf-8')
        self.assertIn('gerçek iPhone',readme)
        for screen in json.loads((DOC/'screens.json').read_text(encoding='utf-8'))['screens']:
            self.assertIn(screen['file'],readme)

if __name__=='__main__': unittest.main()
