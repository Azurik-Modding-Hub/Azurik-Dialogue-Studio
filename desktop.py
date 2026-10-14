"""Offline native window and file dialogs for Azurik Dialogue Studio."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import threading
import traceback
import uuid

VERSION = '1.0.0'
ASSETS = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
DATA = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'AzurikDialogueStudio'


class StudioAPI:
    def __init__(self, project, webview_module):
        self._project = project
        self._webview = webview_module
        self._window = None
        self._job = None
        self._job_lock = threading.Lock()
        self._operation_lock = threading.RLock()
        self._saved_signature = self._signature()
        self._draft_dirty = False

    def _signature(self):
        # Snapshot only project parameters, not 40-MB game banks or history.
        # A voice's input hash is essential: equal durations/names can still
        # contain different recordings. Export/job state is deliberately absent.
        # The bridge serializes mutations, while the background export reads
        # these immutable inputs. Avoid state() here: an export holds the
        # backend lock, and waiting for it would delay the initial job response.
        return (self._project._source_path, self._project._source_kind,
                tuple((language, bank['sourceSha256']) for language, bank in sorted(self._project._banks.items())),
                self._project._snapshot())

    @property
    def dirty(self):
        return self._signature() != self._saved_signature

    def _mark_saved(self):
        self._saved_signature = self._signature()

    def _result(self, action, *args, **kwargs):
        try:
            # File dialogs, mutation checks and job reservation share one lock.
            # An export cannot begin between _idle() and a project mutation.
            with self._operation_lock:
                return {'ok': True, 'data': action(*args, **kwargs), 'dirty': self.dirty}
        except Exception as exc:
            return {'ok': False, 'error': str(exc)}

    def _idle(self):
        with self._job_lock:
            if self._job and self._job['status'] == 'running':
                raise ValueError('Un export est en cours. Attendez sa fin avant de modifier le projet.')

    def _state(self):
        return dict(self._project.state(), version=VERSION, dirty=self.dirty)

    def boot(self):
        return self._result(self._state)

    def set_draft(self, active):
        """Track unapplied editor text without turning it into a game edit."""
        def action():
            if type(active) is not bool:
                raise ValueError('État de saisie invalide.')
            self._draft_dirty = active
            return {'draft': active}
        return self._result(action)

    def _dialog(self, kind, **kwargs):
        selected = self._window.create_file_dialog(kind, **kwargs)
        if not selected:
            return None
        return Path(selected[0] if isinstance(selected, (list, tuple)) else selected)

    def _discard_allowed(self):
        return not (self.dirty or self._draft_dirty) or self._window.create_confirmation_dialog(
            'Modifications non enregistrées', 'Ouvrir un autre projet et abandonner les modifications non enregistrées ?')

    def choose_source(self, kind='dump'):
        def action():
            self._idle()
            if not self._discard_allowed():
                return self._state()
            path = self._dialog(self._webview.FOLDER_DIALOG if kind == 'dump' else self._webview.OPEN_DIALOG,
                                **({} if kind == 'dump' else {'file_types': ('Xbox ISO (*.iso;*.xiso)',)}))
            if path:
                self._project.load_source(path)
                self._mark_saved()
                self._draft_dirty = False
            return self._state()
        return self._result(action)

    def preview_text(self, language, resource, text=None, options=None):
        return self._result(self._project.dialogue_preview, language, resource, text, options)

    def apply_text(self, language, resource, text, options):
        def action():
            self._idle()
            self._project.set_text(language, resource, text, options)
            self._draft_dirty = False
            return self._state()
        return self._result(action)

    def choose_text_file(self, language, resource, kind='txt'):
        def action():
            self._idle()
            if kind not in ('txt', 'image'):
                raise ValueError('Choisissez un fichier TXT ou une image PNG.')
            path = self._dialog(self._webview.OPEN_DIALOG, file_types=('Texte UTF-8 (*.txt)',) if kind == 'txt' else ('Panneau PNG (*.png)',))
            if path:
                (self._project.import_text if kind == 'txt' else self._project.import_image)(language, resource, path)
                self._draft_dirty = False
            return self._state()
        return self._result(action)

    def preview_voice(self, language, key, modified=False):
        return self._result(self._project.voice_preview, language, key, modified)

    def apply_voice_options(self, language, key, options):
        def action():
            self._idle()
            self._project.set_voice_options(language, key, options)
            return self._state()
        return self._result(action)

    def choose_voice(self, language, key):
        def action():
            self._idle()
            path = self._dialog(self._webview.OPEN_DIALOG, file_types=('WAV PCM (*.wav)',))
            if path:
                self._project.import_voice(language, key, path)
            return self._state()
        return self._result(action)

    def restore(self, kind, language, key):
        def action():
            self._idle()
            self._project.restore(kind, language, key)
            return self._state()
        return self._result(action)

    def reset(self):
        def action():
            self._idle()
            if self._project.state()['edits']['total'] and not self._window.create_confirmation_dialog(
                    'Restaurer les originaux', 'Annuler toutes les modifications de textes et de voix de ce projet ?'):
                return self._state()
            self._project.reset()
            return self._state()
        return self._result(action)

    def undo(self):
        def action():
            self._idle()
            self._project.undo()
            return self._state()
        return self._result(action)

    def redo(self):
        def action():
            self._idle()
            self._project.redo()
            return self._state()
        return self._result(action)

    def save_project(self):
        def action():
            self._idle()
            path = self._dialog(self._webview.SAVE_DIALOG, save_filename='Mon-projet.azdialog.json',
                                file_types=('Projet Azurik (*.azdialog.json)',))
            if path:
                self._project.save_project(path)
                self._mark_saved()
            return self._state()
        return self._result(action)

    def open_project(self):
        def action():
            self._idle()
            if not self._discard_allowed():
                return self._state()
            path = self._dialog(self._webview.OPEN_DIALOG, file_types=('Projet Azurik (*.azdialog.json)',))
            if path:
                self._project.load_project(path)
                self._mark_saved()
                self._draft_dirty = False
            return self._state()
        return self._result(action)

    def download_resource(self, kind, language, resource, modified=True):
        def action():
            self._idle()
            extension = '.wav' if kind == 'voice' else '.txt' if kind == 'txt' else '.png'
            name = Path(resource).name
            if name.lower().endswith('.tif'):
                name = name[:-4]
            name = ''.join(char if char.isalnum() or char in '-_.' else '_' for char in name)
            suffix = '-modifie' if modified else '-original'
            path = self._dialog(self._webview.SAVE_DIALOG, save_filename=name + suffix + extension,
                                file_types=('Ressource (*' + extension + ')',))
            if not path:
                return None
            return self._project.export_resource(kind, language, resource, path, modified)
        return self._result(action)

    def download_library(self, kind, language):
        def action():
            self._idle()
            parent = self._dialog(self._webview.FOLDER_DIALOG)
            if not parent:
                return None
            folder = parent / ('Azurik-' + ('Textes' if kind == 'text' else 'Voix') + '-' + language + '-'
                               + datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:4])
            return self._start_job(lambda: self._project.export_library(kind, language, folder, self._progress))
        return self._result(action)

    def _start_job(self, callback):
        with self._operation_lock:
            self._idle()
            job = {'status': 'running', 'progress': 0, 'stage': 'Préparation', 'result': None, 'error': None}
            with self._job_lock:
                self._job = job
        def worker():
            try:
                result = callback()
                with self._job_lock:
                    job.update(status='done', progress=100, stage='Export vérifié', result=result)
            except Exception as exc:
                with self._job_lock:
                    job.update(status='error', stage='Export arrêté', error=str(exc))
        try:
            threading.Thread(target=worker, daemon=True, name='dialogue-export').start()
        except Exception as exc:
            with self._job_lock:
                job.update(status='error', stage='Export arrêté', error=str(exc))
            raise
        return self.get_job()['data']

    def get_job(self):
        with self._job_lock:
            return {'ok': True, 'data': copy.deepcopy(self._job)}

    def _progress(self, value, stage):
        with self._job_lock:
            if self._job and self._job['status'] == 'running':
                self._job.update(progress=max(0, min(100, round(value))), stage=stage)

    def export_mod(self):
        def action():
            self._idle()
            parent = self._dialog(self._webview.FOLDER_DIALOG)
            if not parent:
                return None
            folder = parent / ('Azurik-Dialogue-Mod-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:4])
            return self._start_job(lambda: self._project.export_mod(folder))
        return self._result(action)

    def export_iso(self):
        def action():
            self._idle()
            if not self._project.state()['edits']['total']:
                raise ValueError('Appliquez au moins une modification avant d’exporter une ISO.')
            source = self._dialog(self._webview.OPEN_DIALOG, file_types=('ISO source Xbox (*.iso;*.xiso)',))
            if not source:
                return None
            output = self._dialog(self._webview.SAVE_DIALOG, save_filename='Azurik-Dialogue-Test.iso',
                                  file_types=('Nouvelle ISO Xbox (*.iso)',))
            if not output:
                return None
            export_folder = self._project.data_root / 'exports' / ('iso-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:4])
            def build():
                from iso_export import build_iso
                self._progress(0, 'Préparation des banques modifiées')
                manifest = self._project.export_mod(export_folder)
                result = build_iso(source, export_folder, output, self._progress)
                return {'iso': str(output), 'export': manifest, 'verification': result}
            return self._start_job(build)
        return self._result(action)

    def close_allowed(self):
        with self._operation_lock:
            with self._job_lock:
                running = self._job and self._job['status'] == 'running'
            if running:
                self._window.create_confirmation_dialog('Export en cours', 'Attendez la fin de l’export avant de fermer le logiciel.')
                return False
            return not (self.dirty or self._draft_dirty) or self._window.create_confirmation_dialog(
                'Modifications non enregistrées', 'Fermer sans enregistrer les modifications du projet ?')


def main():
    parser = argparse.ArgumentParser(description='Azurik Dialogue Studio — éditeur local de textes et de voix')
    parser.add_argument('--source', type=Path)
    parser.add_argument('--data', type=Path, default=DATA)
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    source = args.source.resolve() if args.source else None
    data = args.data.resolve()
    # Avoid unrelated user files shadowing standard-library imports from CWD.
    os.chdir(ASSETS)
    from studio_backend import StudioProject
    project = StudioProject(data)
    if source:
        project.load_source(source)
    if args.self_test:
        result = project.state()
        target = data / 'self-test.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return
    import webview
    api = StudioAPI(project, webview)
    window = webview.create_window('Azurik Dialogue Studio ' + VERSION, str(ASSETS / 'web' / 'index.html'),
                                  js_api=api, width=1500, height=950, min_size=(1100, 720),
                                  background_color='#101a23')
    api._window = window
    window.events.closing += api.close_allowed
    webview.start(gui='edgechromium' if os.name == 'nt' else None,
                  icon=str(ASSETS / 'assets' / 'studio.ico'), debug=args.debug)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        folder = DATA / 'logs'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'startup-error.txt').write_text(traceback.format_exc(), encoding='utf-8')
        if os.name == 'nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, 'Le lancement a échoué. Consultez ' + str(folder / 'startup-error.txt'),
                                            'Azurik Dialogue Studio', 0x10)
        else:
            raise
