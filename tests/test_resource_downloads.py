import base64
from pathlib import Path
import tempfile
import unittest
import wave

from studio_backend import StudioProject
from test_studio_backend import archive


class ResourceDownloadTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.dump = self.root / 'original'
        (self.dump / 'gamedata').mkdir(parents=True)
        self.original = archive()
        (self.dump / 'gamedata' / 'French.xbr').write_bytes(self.original)
        self.project = StudioProject(self.root / 'cache')
        self.project.load_source(self.dump)
        self.panel = 'loc/french/popups/test00.tif'
        self.voice = 'loc/french/popups/test00-snd'

    def tearDown(self):
        self.assertEqual((self.dump / 'gamedata' / 'French.xbr').read_bytes(), self.original)
        self.directory.cleanup()

    def test_original_png_and_authored_text_are_actual_files(self):
        path = self.root / 'original.png'
        info = self.project.export_resource('png', 'fr', self.panel, path, False)
        preview = self.project.dialogue_preview('fr', self.panel)['original']
        self.assertEqual(path.read_bytes(), base64.b64decode(preview.split(',', 1)[1]))
        self.assertEqual(info['size'], path.stat().st_size)
        with self.assertRaisesRegex(ValueError, 'image'):
            self.project.export_resource('txt', 'fr', self.panel, self.root / 'original.txt')
        self.project.set_text('fr', self.panel, 'Ma réplique personnalisée.')
        self.project.export_resource('txt', 'fr', self.panel, self.root / 'modified.txt')
        self.assertEqual((self.root / 'modified.txt').read_text(encoding='utf-8'), 'Ma réplique personnalisée.')
        self.project.export_resource('png', 'fr', self.panel, self.root / 'modified.png')
        self.assertNotEqual(path.read_bytes(), (self.root / 'modified.png').read_bytes())

    def test_wav_can_be_opened_by_standard_audio_reader(self):
        path = self.root / 'voice.wav'
        self.project.export_resource('voice', 'fr', self.voice, path, False)
        with wave.open(str(path)) as stream:
            self.assertEqual((stream.getframerate(), stream.getnchannels(), stream.getsampwidth()), (22050, 1, 2))
            self.assertEqual(stream.getnframes(), 2205)

    def test_originals_existing_files_and_wrong_extensions_are_protected(self):
        existing = self.root / 'existing.wav'
        existing.write_bytes(b'user audio')
        with self.assertRaisesRegex(ValueError, 'existe'):
            self.project.export_resource('voice', 'fr', self.voice, existing)
        self.assertEqual(existing.read_bytes(), b'user audio')
        with self.assertRaisesRegex(ValueError, 'dump original'):
            self.project.export_resource('png', 'fr', self.panel, self.dump / 'test.png')
        with self.assertRaisesRegex(ValueError, 'extension'):
            self.project.export_resource('png', 'fr', self.panel, self.root / 'bad.wav')

    def test_bulk_library_is_sorted_and_its_manifest_matches_files(self):
        progress = []
        report = self.project.export_library('voice', 'fr', self.root / 'voice-library',
                                             lambda value, _stage: progress.append(value))
        self.assertEqual(report['count'], 1)
        self.assertEqual(progress[-1], 100)
        exported = self.root / 'voice-library' / report['files'][0]['file']
        self.assertEqual(exported.suffix, '.wav')
        self.assertEqual(exported.stat().st_size, report['files'][0]['size'])
        self.assertTrue((self.root / 'voice-library' / 'catalogue.json').exists())
        with self.assertRaisesRegex(ValueError, 'nouveau dossier'):
            self.project.export_library('text', 'fr', self.root / 'voice-library')


if __name__ == '__main__':
    unittest.main()
