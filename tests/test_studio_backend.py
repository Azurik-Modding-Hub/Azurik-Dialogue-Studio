import base64
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import wave

from PIL import Image
import audio_formats as audio
from studio_backend import StudioProject


def archive(language="french"):
    """A generated panel and short generated PCM sound in a valid v4 bank."""
    image = Image.new("RGBA", (256, 256), (0, 0, 0, 204))
    surf = bytearray(128)
    struct.pack_into("<I", surf, 0, 0x10)
    struct.pack_into("<2f", surf, 28, 256, 256)
    struct.pack_into("<i", surf, 40, 88)
    surf += image.tobytes("raw", "BGRA")
    pcm = b"\0\0" * 2205
    descriptor = struct.pack("<II4BI", 22050, 2205, 1, 16, 0, 0, 0) + pcm
    items = [(b"surf", surf, 128), (b"wave", descriptor, 8)]
    base, footer = 4096, (4096 + len(surf) + len(descriptor) + 4095) // 4096 * 4096
    data = bytearray(footer)
    struct.pack_into("<4sIIIIIII", data, 0, b"xobx", 4, 0, len(items), base, 0, footer, 0)
    struct.pack_into("<III", data, 32, footer, 0, footer)
    names = [(0, f"loc/{language}/popups/test00.tif".encode()),
             (1, f"loc/{language}/popups/test00-snd".encode())]
    table, pool = bytearray(), bytearray()
    for index, key in names:
        table += struct.pack("<II", index, len(pool))
        pool += key + b"\0"
    struct.pack_into("<IIII", data, 44, len(names), footer, footer + len(table), len(pool))
    position = 0
    for index, (tag, body, flags) in enumerate(items):
        data[base + position:base + position + len(body)] = body
        end = (position + len(body) + 3) & ~3
        struct.pack_into("<I4sII", data, 64 + index * 16, len(body), tag, flags, end)
        position = end
    return bytes(data + table + pool)


def wav(frames=1102):
    return audio.pcm_wav(struct.pack("<" + "h" * frames, *([5000] * frames)), 22050, 1)


class StudioBackendTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "original"
        (self.source / "gamedata").mkdir(parents=True)
        self.baselines = {}
        for file, language in [("French.xbr", "french"), ("english.xbr", "english"), ("German.xbr", "german")]:
            data = archive(language)
            (self.source / "gamedata" / file).write_bytes(data)
            self.baselines[file] = hashlib.sha256(data).hexdigest()
        self.studio = StudioProject(self.root / "cache")
        self.dialogue = "loc/french/popups/test00.tif"
        self.voice = "loc/french/popups/test00-snd"
        self.voice_path = self.root / "my voice.wav"
        self.voice_path.write_bytes(wav())

    def tearDown(self):
        self.temporary.cleanup()

    def _originals_preserved(self):
        for file, digest in self.baselines.items():
            self.assertEqual(hashlib.sha256((self.source / "gamedata" / file).read_bytes()).hexdigest(), digest)

    def test_languages_bitmap_preview_and_unedited_source(self):
        state = self.studio.load_source(self.source)
        self.assertEqual([row["id"] for row in state["languages"]], ["fr", "en", "de"])
        self.assertEqual(state["edits"]["total"], 0)
        self.assertFalse(state["canUndo"])
        preview = self.studio.dialogue_preview("fr", self.dialogue)
        self.assertEqual(preview["original"], preview["preview"])
        self.assertEqual(preview["text"], "")
        self.assertIsNone(preview["metadata"]["text"])
        self._originals_preserved()

    def test_history_restores_parameters_and_cached_voice(self):
        self.studio.load_source(self.source)
        self.studio.set_text("fr", self.dialogue, "Test du joueur.")
        self.studio.import_voice("fr", self.voice, self.voice_path)
        self.assertEqual(self.studio.state()["edits"], {"texts": 1, "voices": 1, "total": 2})
        self.assertEqual(self.studio.undo()["edits"]["voices"], 0)
        self.assertTrue(self.studio.state()["canRedo"])
        self.assertEqual(self.studio.redo()["edits"]["total"], 2)
        self.assertEqual(self.studio.restore("text", "fr", self.dialogue)["edits"]["total"], 1)
        self.assertEqual(self.studio.reset()["edits"]["total"], 0)
        self.assertEqual(self.studio.undo()["edits"]["total"], 1)
        before = self.voice_path.read_bytes()
        result = self.studio.voice_preview("fr", self.voice, modified=True)
        raw = base64.b64decode(result["audio"].split(",", 1)[1])
        with wave.open(io.BytesIO(raw), "rb") as source:
            self.assertEqual(source.getnframes(), 1102)
        self.assertTrue(result["metadata"]["modified"])
        self.assertEqual(self.voice_path.read_bytes(), before)
        self._originals_preserved()

    def test_invalid_changes_do_not_change_history(self):
        self.studio.load_source(self.source)
        state = self.studio.state()
        with self.assertRaises(ValueError):
            self.studio.set_text("fr", self.dialogue, "word " * 1000)
        invalid_audio = self.root / "invalid.wav"
        invalid_audio.write_bytes(b'not a PCM WAV')
        with self.assertRaises(ValueError):
            self.studio.import_voice("fr", self.voice, invalid_audio)
        self.assertEqual(self.studio.state(), state)

    def test_new_export_only_changed_bank_with_verified_iso_plan(self):
        self.studio.load_source(self.source)
        self.studio.set_text("fr", self.dialogue, "Texte de test.")
        self.studio.import_voice("fr", self.voice, self.voice_path)
        destination = self.root / "new mod"
        report = self.studio.export_mod(destination)
        self.assertTrue(report["originalsPreserved"])
        self.assertEqual(report["edits"]["total"], 2)
        files = sorted(p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file())
        self.assertEqual(files, ["dialogue-export.json", "gamedata/French.xbr", "iso-plan.json"])
        plan = json.loads((destination / "iso-plan.json").read_text("utf-8"))
        row = plan["gameFiles"][0]
        self.assertEqual(plan["format"], "azurik-level-iso")
        self.assertEqual(row["sourceSha256"], self.baselines["French.xbr"])
        patched = (destination / row["path"]).read_bytes()
        self.assertEqual(hashlib.sha256(patched).hexdigest(), row["sha256"])
        self.assertNotEqual(patched, (self.source / row["path"]).read_bytes())
        self.assertEqual(self.studio.state()["lastExport"]["destination"], str(destination))
        with self.assertRaises(ValueError):
            self.studio.export_mod(destination)
        with self.assertRaises(ValueError):
            self.studio.export_mod(self.source / "new mod")
        self._originals_preserved()

    def test_recording_can_outlast_original_and_export_keeps_all_frames(self):
        self.studio.load_source(self.source)
        self.voice_path.write_bytes(wav(5000))
        self.studio.import_voice('fr', self.voice, self.voice_path)
        result = self.studio.voice_preview('fr', self.voice, True)
        with wave.open(io.BytesIO(base64.b64decode(result['audio'].split(',', 1)[1]))) as stream:
            self.assertEqual(stream.getnframes(), 5000)
        report = self.studio.export_mod(self.root / 'long-voice-export')
        exported = (self.root / 'long-voice-export' / report['gameFiles'][0]['path']).read_bytes()
        self.assertEqual(audio.list_voices(exported)[0]['frames'], 5000)
        self.assertGreater(len(exported), (self.source / 'gamedata' / 'French.xbr').stat().st_size)
        self._originals_preserved()

    def test_voice_gain_start_history_and_portable_project_are_consistent(self):
        self.studio.load_source(self.source)
        self.studio.import_voice('fr', self.voice, self.voice_path)
        before = self.voice_path.read_bytes()
        options = {'gainDb': 6, 'trimStartSeconds': 0.01}
        self.studio.set_voice_options('fr', self.voice, options)
        result = self.studio.voice_preview('fr', self.voice, True)
        raw = base64.b64decode(result['audio'].split(',', 1)[1])
        with wave.open(io.BytesIO(raw)) as stream:
            self.assertEqual(stream.getnframes(), 1102 - round(0.01 * 22050))
            self.assertGreater(int.from_bytes(stream.readframes(1), 'little', signed=True), 5000)
        self.assertEqual(self.studio.state()['languages'][0]['voices'][0]['options'], options)
        saved = self.root / 'audio-options.azdialog.json'
        self.studio.save_project(saved)
        other = StudioProject(self.root / 'other-cache')
        other.load_project(saved)
        self.assertEqual(other.voice_preview('fr', self.voice, True)['audio'], result['audio'])
        self.studio.undo()
        self.assertEqual(self.studio.state()['languages'][0]['voices'][0]['options']['gainDb'], 0)
        self.studio.redo()
        self.assertEqual(self.studio.voice_preview('fr', self.voice, True)['audio'], result['audio'])
        self.assertEqual(before, self.voice_path.read_bytes())

    def test_voice_settings_noop_and_invalid_start_do_not_change_project(self):
        self.studio.load_source(self.source)
        self.studio.import_voice('fr', self.voice, self.voice_path)
        snapshot = self.studio._snapshot()
        self.studio.set_voice_options('fr', self.voice, {'gainDb': 0, 'trimStartSeconds': 0})
        self.assertEqual(self.studio._snapshot(), snapshot)
        with self.assertRaises(ValueError):
            self.studio.set_voice_options('fr', self.voice, {'gainDb': 6, 'trimStartSeconds': 10})
        self.assertEqual(self.studio._snapshot(), snapshot)

    def test_export_refuses_changed_original(self):
        self.studio.load_source(self.source)
        self.studio.set_text("fr", self.dialogue, "Texte de test.")
        file = self.source / "gamedata" / "French.xbr"
        data = bytearray(file.read_bytes()); data[12] ^= 1; file.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "changé"):
            self.studio.export_mod(self.root / "bad export")
        self.assertFalse((self.root / "bad export").exists())

    def test_project_roundtrip_portable_user_audio_and_restore(self):
        self.studio.load_source(self.source)
        self.studio.set_text("fr", self.dialogue, "Une nouvelle phrase.", {"fontSize": 18})
        self.studio.import_voice("fr", self.voice, self.voice_path)
        file = self.root / "project.azdialog.json"
        saved = self.studio.save_project(file)
        self.assertEqual(saved["inputs"], 1)
        document = json.loads(file.read_text("utf-8"))
        self.assertNotIn("data", document)
        self.assertEqual(len(document["inputs"]), 1)
        reopened = StudioProject(self.root / "other cache")
        state = reopened.load_project(file)
        self.assertEqual(state["edits"]["total"], 2)
        self.assertFalse(state["canUndo"])
        self.assertEqual(reopened.dialogue_preview("fr", self.dialogue)["text"], "Une nouvelle phrase.")
        self.assertEqual(reopened.export_mod(self.root / "roundtrip export")["edits"]["total"], 2)
        self._originals_preserved()

    def test_refuse_unrelated_json_clobber_and_project_audio_escape(self):
        self.studio.load_source(self.source)
        file = self.root / "unrelated.azdialog.json"
        original = b'{"private":true}'
        file.write_bytes(original)
        with self.assertRaises(ValueError):
            self.studio.save_project(file)
        self.assertEqual(file.read_bytes(), original)
        self.studio.import_voice("fr", self.voice, self.voice_path)
        file = self.root / "project.azdialog.json"
        self.studio.save_project(file)
        document = json.loads(file.read_text("utf-8"))
        next(iter(document["inputs"].values()))["file"] = "../my voice.wav"
        file.write_text(json.dumps(document), "utf-8")
        before = self.studio.state()
        with self.assertRaises(ValueError):
            self.studio.load_project(file)
        self.assertEqual(self.studio.state(), before)

    def test_portable_project_uses_opened_identical_source_when_old_path_missing(self):
        self.studio.load_source(self.source)
        self.studio.set_text("fr", self.dialogue, "Projet partagé avec le joueur.")
        self.studio.import_voice("fr", self.voice, self.voice_path)
        file = self.root / "portable.azdialog.json"
        self.studio.save_project(file)
        document = json.loads(file.read_text("utf-8"))
        document["sourcePath"] = str(self.root / "old PC source no longer exists")
        file.write_text(json.dumps(document), "utf-8")
        moved_source = self.root / "source on another PC"
        (moved_source / "gamedata").mkdir(parents=True)
        for bank in (self.source / "gamedata").iterdir():
            (moved_source / "gamedata" / bank.name).write_bytes(bank.read_bytes())
        reopened = StudioProject(self.root / "new cache")
        with self.assertRaisesRegex(ValueError, "Ouvrez votre dump ou ISO"):
            reopened.load_project(file)
        reopened.load_source(moved_source)
        state = reopened.load_project(file)
        self.assertEqual(state["sourcePath"], str(moved_source))
        self.assertEqual(state["edits"]["total"], 2)
        self.assertEqual(reopened.export_mod(self.root / "portable export")["edits"]["total"], 2)
        self._originals_preserved()

    def test_missing_source_fallback_rejects_different_opened_fingerprints(self):
        self.studio.load_source(self.source)
        self.studio.set_text("fr", self.dialogue, "Projet partagé avec le joueur.")
        file = self.root / "portable.azdialog.json"
        self.studio.save_project(file)
        document = json.loads(file.read_text("utf-8"))
        document["sourcePath"] = str(self.root / "absent original path")
        file.write_text(json.dumps(document), "utf-8")
        different = self.root / "different source"
        (different / "gamedata").mkdir(parents=True)
        for bank in (self.source / "gamedata").iterdir():
            data = bytearray(bank.read_bytes())
            if bank.name == "english.xbr":
                data[4096 + 128] ^= 1
            (different / "gamedata" / bank.name).write_bytes(data)
        reopened = StudioProject(self.root / "new cache")
        reopened.load_source(different)
        before = reopened.state()
        with self.assertRaisesRegex(ValueError, "empreintes"):
            reopened.load_project(file)
        self.assertEqual(reopened.state(), before)

    def test_source_load_is_transactional_and_history_bounded(self):
        self.studio.load_source(self.source)
        with self.assertRaises(ValueError):
            self.studio.load_source(self.root / "absent.iso")
        self.assertEqual(self.studio.state()["sourcePath"], str(self.source))
        for i in range(52):
            self.studio.set_text("fr", self.dialogue, f"Phrase {i}.")
        self.assertEqual(len(self.studio._undo), 50)
        self.assertTrue(all(isinstance(entry[0], dict) for entry in self.studio._undo))
        self.studio.undo()
        self.studio.set_text("fr", self.dialogue, "Autre choix.")
        self.assertFalse(self.studio.state()["canRedo"])

    def test_iso_source_reads_only_language_bank_extents(self):
        bank = archive()
        path = self.root / "test.iso"
        path.write_bytes(b"prefix" + bank + b"untouched tail")
        class MockISO:
            entries = [{"path": "gamedata/French.xbr", "directory": False, "sector": 7, "size": len(bank)},
                       {"path": "gamedata/town.xbr", "directory": False, "sector": 999, "size": 123}]
            def __init__(self, path): pass
            def _extent(self, sector, size):
                assert sector == 7
                return 6
        with patch("xbox_iso.XboxISO", MockISO):
            state = self.studio.load_source(path)
        self.assertEqual(state["sourceKind"], "iso")
        self.assertEqual([row["id"] for row in state["languages"]], ["fr"])
        self.studio.set_text("fr", self.dialogue, "Le texte importé.")
        self.studio.export_mod(self.root / "iso mod")
        self.assertEqual(path.read_bytes(), b"prefix" + bank + b"untouched tail")


if __name__ == "__main__":
    unittest.main()
