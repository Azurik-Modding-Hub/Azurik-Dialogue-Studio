from pathlib import Path
import tempfile
import threading
import time
import unittest

from desktop import StudioAPI
from studio_backend import StudioProject
from test_studio_backend import archive


class FakeWebview:
    OPEN_DIALOG, SAVE_DIALOG, FOLDER_DIALOG = "open", "save", "folder"


class FakeWindow:
    def __init__(self):
        self.paths = []
        self.confirmations = []
        self.confirm_result = True

    def create_file_dialog(self, kind, **kwargs):
        return self.paths.pop(0) if self.paths else None

    def create_confirmation_dialog(self, title, message):
        self.confirmations.append((title, message))
        return self.confirm_result


class DesktopAPITests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "original"
        (self.source / "gamedata").mkdir(parents=True)
        (self.source / "gamedata" / "French.xbr").write_bytes(archive())
        self.project = StudioProject(self.root / "cache")
        self.project.load_source(self.source)
        self.api = StudioAPI(self.project, FakeWebview)
        self.window = FakeWindow()
        self.api._window = self.window
        self.resource = "loc/french/popups/test00.tif"

    def tearDown(self):
        self.temporary.cleanup()

    def apply(self, text="Texte écrit par le joueur."):
        result = self.api.apply_text("fr", self.resource, text, None)
        self.assertTrue(result["ok"], result)
        return result

    def save(self):
        self.window.paths.append([str(self.root / "test.azdialog.json")])
        result = self.api.save_project()
        self.assertTrue(result["ok"], result)
        self.assertFalse(result["dirty"])

    def wait_job(self):
        limit = time.monotonic() + 3
        while time.monotonic() < limit:
            job = self.api.get_job()["data"]
            if job and job["status"] != "running":
                return job
            time.sleep(0.005)
        self.fail("Export job did not complete")

    def test_saved_changes_removed_by_undo_require_close_confirmation(self):
        self.apply()
        self.save()
        result = self.api.undo()
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["edits"]["total"], 0)
        self.assertTrue(result["dirty"])
        self.window.confirm_result = False
        self.assertFalse(self.api.close_allowed())
        self.assertIn("non enregistrées", self.window.confirmations[-1][0])
        redone = self.api.redo()
        self.assertFalse(redone["dirty"])
        self.assertTrue(self.api.close_allowed())

    def test_reset_and_restore_saved_edit_still_dirty(self):
        self.apply()
        self.save()
        result = self.api.reset()
        self.assertTrue(result["dirty"])
        self.assertEqual(result["data"]["edits"]["total"], 0)
        self.assertFalse(self.api.undo()["dirty"])
        restored = self.api.restore("text", "fr", self.resource)
        self.assertTrue(restored["dirty"])

    def test_noop_apply_or_history_does_not_mark_saved_project_dirty(self):
        self.assertFalse(self.api.undo()["dirty"])
        self.assertFalse(self.api.redo()["dirty"])
        self.apply()
        self.save()
        result = self.apply()
        self.assertFalse(result["dirty"])
        self.assertFalse(self.api.restore("text", "fr", "missing")["dirty"])

    def test_cancelled_save_and_open_do_not_clear_unsaved_changes(self):
        self.apply()
        self.assertTrue(self.api.save_project()["dirty"])
        self.window.confirm_result = False
        state = self.project.state()
        result = self.api.choose_source()
        self.assertTrue(result["dirty"])
        self.assertEqual(self.project.state(), state)
        self.assertIn("non enregistrées", self.window.confirmations[-1][0])

    def test_unapplied_draft_requires_confirmation_without_fake_game_edit(self):
        self.assertTrue(self.api.set_draft(True)["ok"])
        self.assertFalse(self.api.boot()["data"]["dirty"])
        self.assertEqual(self.project.state()["edits"]["total"], 0)
        self.window.confirm_result = False
        self.assertFalse(self.api.close_allowed())
        self.assertFalse(self.api._discard_allowed())
        self.assertFalse(self.api.set_draft("not a bool")["ok"])
        self.assertTrue(self.api.set_draft(False)["ok"])
        self.assertTrue(self.api.close_allowed())

    def test_native_bridge_does_not_expose_modules_or_window_objects(self):
        # pywebview recursively introspects public objects to expose methods.
        # Keeping modules/windows/backends private avoids huge traversal hangs.
        self.assertTrue(all(name.startswith("_") for name in vars(self.api)))
        for name in dir(self.api):
            if not name.startswith("_"):
                value = getattr(self.api, name)
                self.assertTrue(callable(value) or isinstance(value, bool), name)

    def test_job_start_response_does_not_wait_for_backend_export_lock(self):
        started, release, returned = threading.Event(), threading.Event(), threading.Event()
        def locked_export(_folder):
            with self.project._lock:
                started.set()
                if not release.wait(3):
                    raise RuntimeError("test export timeout")
                return {"verified": True}
        self.apply()
        self.window.paths.append([str(self.root)])
        self.project.export_mod = locked_export
        def call_export():
            result = self.api.export_mod()
            self.assertTrue(result["ok"], result)
            returned.set()
        caller = threading.Thread(target=call_export)
        caller.start()
        try:
            self.assertTrue(started.wait(1))
            self.assertTrue(returned.wait(1), "Job response waited for export to finish")
        finally:
            release.set()
            caller.join(3)
        self.assertEqual(self.wait_job()["status"], "done")

    def test_pending_export_blocks_all_mutations_and_second_job(self):
        self.apply()
        started, release = threading.Event(), threading.Event()
        def export():
            started.set()
            if not release.wait(3):
                raise RuntimeError("test export timeout")
            return {"verified": True}
        self.api._start_job(export)
        self.assertTrue(started.wait(1))
        before = self.project.state()
        try:
            for operation in [lambda: self.api.apply_text("fr", self.resource, "Autre texte.", None),
                              self.api.undo, self.api.redo, self.api.reset,
                              lambda: self.api.restore("text", "fr", self.resource),
                              self.api.save_project, self.api.open_project, self.api.choose_source,
                              lambda: self.api.choose_voice("fr", "loc/french/popups/test00-snd")]:
                result = operation()
                self.assertFalse(result["ok"], result)
                self.assertIn("export", result["error"])
            with self.assertRaisesRegex(ValueError, "export"):
                self.api._start_job(lambda: {})
            self.assertEqual(self.project.state(), before)
            self.assertFalse(self.api.close_allowed())
        finally:
            release.set()
        job = self.wait_job()
        self.assertEqual(job["status"], "done")
        self.assertEqual(job["progress"], 100)
        self.assertEqual(job["result"], {"verified": True})

    def test_job_failure_exposes_error_and_unlocks_project(self):
        def failing():
            self.api._progress(23, "Validation")
            raise ValueError("Synthetic source mismatch")
        self.api._start_job(failing)
        job = self.wait_job()
        self.assertEqual(job["status"], "error")
        self.assertEqual(job["error"], "Synthetic source mismatch")
        self.assertEqual(job["progress"], 23)
        self.assertIsNone(job["result"])
        self.assertTrue(self.apply()["dirty"])

    def test_confirmation_during_export_does_not_hold_job_lock(self):
        release = threading.Event()
        def exporting():
            release.wait(3)
            return {"verified": True}
        self.api._start_job(exporting)
        original_confirmation = self.window.create_confirmation_dialog
        def confirm(title, message):
            release.set()
            # The callback can finish while the modal native dialog is open.
            self.assertEqual(self.wait_job()["status"], "done")
            return original_confirmation(title, message)
        self.window.create_confirmation_dialog = confirm
        self.assertFalse(self.api.close_allowed())


if __name__ == "__main__":
    unittest.main()
