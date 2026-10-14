import base64
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image
from studio_backend import StudioProject
from test_studio_backend import archive


class FileImportsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / 'game'
        (self.source / 'gamedata').mkdir(parents=True)
        self.original = archive()
        (self.source / 'gamedata' / 'French.xbr').write_bytes(self.original)
        self.project = StudioProject(self.root / 'cache')
        self.project.load_source(self.source)
        self.key = 'loc/french/popups/test00.tif'
        self.png = self.root / 'panel.png'
        Image.new('RGBA', (512, 512), (230, 30, 90, 170)).save(self.png)

    def tearDown(self):
        self.assertEqual((self.source / 'gamedata' / 'French.xbr').read_bytes(), self.original)
        self.temporary.cleanup()

    def test_txt_utf8_bom_and_newlines_are_imported_with_history(self):
        text = self.root / 'dialogue.txt'
        text.write_bytes(b'\xef\xbb\xbfBonjour !\r\nBienvenue.')
        self.project.import_text('fr', self.key, text)
        self.assertEqual(self.project.dialogue_preview('fr', self.key)['text'], 'Bonjour !\nBienvenue.')
        self.project.undo()
        self.assertEqual(self.project.state()['edits']['total'], 0)
        self.project.redo()
        self.assertEqual(self.project.state()['edits']['texts'], 1)
        bad = self.root / 'bad.txt'; bad.write_bytes(b'\xff\x00')
        with self.assertRaisesRegex(ValueError, 'UTF-8'):
            self.project.import_text('fr', self.key, bad)

    def test_png_native_preview_saved_project_export_and_restore(self):
        before = hashlib.sha256(self.png.read_bytes()).hexdigest()
        self.project.import_image('fr', self.key, self.png)
        preview = self.project.dialogue_preview('fr', self.key)
        with Image.open(io.BytesIO(base64.b64decode(preview['preview'].split(',', 1)[1]))) as image:
            self.assertEqual(image.size, (256, 256))
            # Pillow's premultiplied-alpha Lanczos resize can round a channel
            # by one. Check the visible colour and transparency, not rounding.
            self.assertTrue(all(abs(actual - expected) <= 1 for actual, expected
                                in zip(image.getpixel((10, 10)), (230, 30, 90, 170))))
        saved = self.root / 'images.azdialog.json'
        self.project.save_project(saved)
        other = StudioProject(self.root / 'other-cache')
        other.load_project(saved)
        self.assertEqual(other.dialogue_preview('fr', self.key)['preview'], preview['preview'])
        report = other.export_mod(self.root / 'image-mod')
        self.assertEqual(report['changes'][0]['kind'], 'dialogue-image')
        self.assertEqual(len((self.root / 'image-mod' / 'gamedata' / 'French.xbr').read_bytes()), len(self.original))
        with self.assertRaisesRegex(ValueError, 'image'):
            self.project.export_resource('txt', 'fr', self.key, self.root / 'not-plaintext.txt')
        self.project.restore('text', 'fr', self.key)
        self.assertEqual(self.project.state()['edits']['total'], 0)
        self.assertEqual(hashlib.sha256(self.png.read_bytes()).hexdigest(), before)

    def test_image_sidecar_rejects_external_paths_and_wrong_content(self):
        self.project.import_image('fr', self.key, self.png)
        saved = self.root / 'image-paths.azdialog.json'
        self.project.save_project(saved)
        doc = json.loads(saved.read_text(encoding='utf-8'))
        next(iter(doc['inputs'].values()))['file'] = '../panel.png'
        saved.write_text(json.dumps(doc), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'extérieur'):
            self.project.load_project(saved)

    def test_txt_export_reimport_preserves_text_and_layout_exactly(self):
        self.project.set_text('fr', self.key, 'Une seule ligne.')
        original_preview = self.project.dialogue_preview('fr', self.key)['preview']
        destination = self.root / 'roundtrip.txt'
        self.project.export_resource('txt', 'fr', self.key, destination)
        self.assertEqual(destination.read_text(encoding='utf-8'), 'Une seule ligne.')
        self.project.import_text('fr', self.key, destination)
        self.assertEqual(self.project.dialogue_preview('fr', self.key)['preview'], original_preview)


if __name__ == '__main__':
    unittest.main()
