"""Offline project state, history and native-bank exports for Dialogue Studio."""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import threading
import uuid

import audio_formats as audio
import audio_processing
import dialogue_formats as dialogue

LANGUAGES = {"fr": ("Français", "French.xbr", "french"),
             "en": ("English", "english.xbr", "english"),
             "de": ("Deutsch", "German.xbr", "german")}
MAX_BANK_BYTES = audio.MAX_ARCHIVE_BYTES
MAX_PROJECT_BYTES = 4 * 1024 * 1024
MAX_HISTORY = 50
FORMAT = "azurik-dialogue-studio"
HASH = re.compile(r"[a-f0-9]{64}")


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _json(data):
    return json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8") + b"\n"


def _pairs(rows):
    result = {}
    for key, value in rows:
        if key in result:
            raise ValueError("Clé JSON dupliquée dans le projet.")
        result[key] = value
    return result


def _read_json(path):
    if path.stat().st_size > MAX_PROJECT_BYTES:
        raise ValueError("Le projet dépasse 4 Mo.")
    with path.open("rb") as stream:
        blob = stream.read(MAX_PROJECT_BYTES + 1)
    if len(blob) > MAX_PROJECT_BYTES:
        raise ValueError("Le projet dépasse 4 Mo.")
    try:
        return json.loads(blob.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("Nombre JSON non fini.")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Le fichier projet n’est pas un JSON UTF-8 valide.") from exc


def _atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _data_url(blob, mime):
    return f"data:{mime};base64," + base64.b64encode(blob).decode("ascii")


class StudioProject:
    def __init__(self, data_root: Path):
        self.data_root = Path(data_root).expanduser().resolve()
        self._lock = threading.RLock()
        self._baselines = {}
        self._banks = {}
        self._texts = {}
        self._voices = {}
        self._undo = []
        self._redo = []
        self._source_path = None
        self._source_kind = None
        self._last_export = None
        self._project_path = None

    def _require(self):
        if not self._baselines:
            raise ValueError("Ouvrez d’abord un dossier du jeu ou une ISO Xbox.")

    def _bank(self, language):
        self._require()
        if not isinstance(language, str) or language not in self._baselines:
            raise ValueError("Cette langue n’est pas disponible dans la source ouverte.")
        return self._baselines[language]

    def _protect_destination(self, path):
        path = Path(path).expanduser().resolve()
        if self._source_kind == "dump" and path.is_relative_to(Path(self._source_path)):
            raise ValueError("Enregistrez hors du dump original pour conserver ses fichiers.")
        if self._source_kind == "iso" and path == Path(self._source_path):
            raise ValueError("Le fichier ISO original doit rester inchangé.")
        return path

    def _read_source(self, path):
        path = Path(path).expanduser().resolve()
        baselines, banks = {}, {}
        if path.is_dir():
            matches = [child for child in path.iterdir() if child.is_dir() and child.name.casefold() == "gamedata"]
            gamedata = matches[0] if len(matches) == 1 else path if path.name.casefold() == "gamedata" else None
            if gamedata is None:
                raise ValueError("Choisissez le dossier du dump qui contient gamedata.")
            source, kind = gamedata.parent, "dump"
            if self.data_root.is_relative_to(source):
                raise ValueError("Le cache de l’éditeur doit être situé hors du dump original.")
            paths = {}
            for child in gamedata.iterdir():
                key = child.name.casefold()
                if key in paths:
                    raise ValueError("Deux fichiers source ont le même nom sans distinction de casse.")
                paths[key] = child
            for language, (_label, filename, token) in LANGUAGES.items():
                file = paths.get(filename.casefold())
                if file is None:
                    continue
                if not file.is_file() or not 64 <= file.stat().st_size <= MAX_BANK_BYTES:
                    raise ValueError(f"Banque {filename} absente, invalide ou supérieure à 512 Mo.")
                with file.open("rb") as stream:
                    data = stream.read(MAX_BANK_BYTES + 1)
                if len(data) > MAX_BANK_BYTES:
                    raise ValueError("La banque a grandi pendant sa lecture.")
                banks[language] = {"gamePath": "gamedata/" + file.name, "filePath": str(file.resolve())}
                baselines[language] = data
        elif path.is_file() and path.suffix.casefold() in (".iso", ".xiso"):
            from xbox_iso import XboxISO
            source, kind = path, "iso"
            image = XboxISO(path)
            files = {row["path"].casefold(): row for row in image.entries if not row["directory"]}
            with path.open("rb") as stream:
                for language, (_label, filename, token) in LANGUAGES.items():
                    row = files.get("gamedata/" + filename.casefold())
                    if row is None:
                        continue
                    if not 64 <= row["size"] <= MAX_BANK_BYTES:
                        raise ValueError(f"La banque {filename} dépasse la taille maximale.")
                    offset = image._extent(row["sector"], row["size"])
                    stream.seek(offset)
                    data = stream.read(row["size"])
                    if len(data) != row["size"]:
                        raise ValueError("La banque de langue a été tronquée dans l’ISO.")
                    baselines[language] = data
                    banks[language] = {"gamePath": row["path"], "filePath": str(path), "offset": offset, "size": row["size"]}
        else:
            raise ValueError("Choisissez un dossier de dump ou un fichier ISO/XISO Xbox local.")
        if not baselines:
            raise ValueError("Aucune banque english.xbr, French.xbr ou German.xbr trouvée.")
        for language, data in baselines.items():
            token = LANGUAGES[language][2]
            dialogs = dialogue.scan_dialogues(data, token)
            voices = audio.list_voices(data)
            if not dialogs or not voices:
                raise ValueError("La source ne contient pas les dialogues et voix Azurik attendus.")
            if any(not row["key"].startswith(f"loc/{token}/") for row in voices):
                raise ValueError("La banque de langue ne correspond pas à son nom de fichier.")
            banks[language].update(sourceSha256=_digest(data), size=len(data), dialogues=dialogs, voices=voices)
        return str(source), kind, baselines, banks

    def load_source(self, path) -> dict:
        with self._lock:
            source, kind, baselines, banks = self._read_source(path)
            self._source_path, self._source_kind = source, kind
            self._baselines, self._banks = baselines, banks
            self._texts, self._voices, self._undo, self._redo = {}, {}, [], []
            self._last_export = self._project_path = None
            return self.state()

    def state(self) -> dict:
        with self._lock:
            languages = []
            for language, (label, filename, token) in LANGUAGES.items():
                if language not in self._banks:
                    continue
                bank = self._banks[language]
                dialogs, voices = [], []
                for item in bank["dialogues"]:
                    edit = self._texts.get((language, item["resource"]))
                    dialogs.append(dict(item, modified=edit is not None,
                                        kind=edit.get('kind', 'text') if edit else 'text',
                                        importedName=edit.get('name') if edit else None,
                                        text=edit["text"] if edit else None,
                                        options=copy.deepcopy(edit["options"]) if edit else dialogue.default_text_options(item["width"], item["height"])))
                for item in bank["voices"]:
                    edit = self._voices.get((language, item["key"]))
                    voices.append(dict(item, modified=edit is not None,
                                       importedName=edit.get("name") if edit else None,
                                       options=copy.deepcopy(edit.get('options', {'gainDb': 0, 'trimStartSeconds': 0})) if edit else {'gainDb': 0, 'trimStartSeconds': 0},
                                       replacement=copy.deepcopy(edit.get("metadata")) if edit else None))
                languages.append({"id": language, "label": label, "gamePath": bank["gamePath"],
                                  "sourceSha256": bank["sourceSha256"], "dialogues": dialogs, "voices": voices})
            return {"format": FORMAT, "version": 1, "sourcePath": self._source_path, "sourceKind": self._source_kind,
                    "projectPath": self._project_path, "languages": languages,
                    "edits": {"texts": len(self._texts), "voices": len(self._voices), "total": len(self._texts) + len(self._voices)},
                    "canUndo": bool(self._undo), "canRedo": bool(self._redo), "lastExport": copy.deepcopy(self._last_export)}

    def _snapshot(self):
        return copy.deepcopy((self._texts, self._voices))

    def _change(self):
        self._undo.append(self._snapshot())
        self._undo = self._undo[-MAX_HISTORY:]
        self._redo.clear()
        self._last_export = None

    def _text_options(self, language, resource, options):
        data = self._bank(language)
        if not isinstance(resource, str):
            raise ValueError("Référence de dialogue invalide.")
        matches = [r for r in self._banks[language]["dialogues"] if r["resource"] == resource]
        if len(matches) != 1:
            raise ValueError("Ce dialogue n’existe pas dans la langue sélectionnée.")
        config = dialogue.default_text_options(matches[0]["width"], matches[0]["height"])
        current = self._texts.get((language, resource))
        if current:
            config.update(copy.deepcopy(current["options"]))
        if options is not None:
            if not isinstance(options, dict):
                raise ValueError("Options de texte invalides.")
            config.update(options)
        return data, config, matches[0]

    def dialogue_preview(self, language, resource, text=None, options=None) -> dict:
        with self._lock:
            data, config, metadata = self._text_options(language, resource, options)
            edit = self._texts.get((language, resource))
            authored = edit["text"] if text is None and edit else text
            original = dialogue.decode_popup_png(data, resource)
            if text is None and edit and edit.get('kind') == 'image':
                preview = dialogue.render_popup_image(data, resource, self._image_input(edit['sha256']))
            else:
                preview = dialogue.render_popup_text(data, resource, authored, config) if authored else original
            return {"original": _data_url(original, "image/png"), "preview": _data_url(preview, "image/png"),
                    "text": authored or "", "options": config, "metadata": dict(metadata, sourceKind="bitmap")}

    def set_text(self, language, resource, text, options=None) -> dict:
        with self._lock:
            data, config, metadata = self._text_options(language, resource, options)
            dialogue.render_popup_text(data, resource, text, config)
            value = {"text": text, "options": config}
            if self._texts.get((language, resource)) != value:
                self._change()
                self._texts[language, resource] = value
            return self.state()

    def import_text(self, language, resource, path):
        with self._lock:
            path = Path(path).expanduser().resolve()
            if not path.is_file() or path.suffix.casefold() != '.txt' or not 1 <= path.stat().st_size <= 16384:
                raise ValueError('Choisissez un fichier TXT UTF-8 de moins de 16 Ko.')
            try:
                text = path.read_bytes().decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
            except UnicodeDecodeError as exc:
                raise ValueError('Enregistrez votre fichier texte en UTF-8.') from exc
            return self.set_text(language, resource, text)

    def _image_input(self, sha):
        if not isinstance(sha, str) or not HASH.fullmatch(sha):
            raise ValueError('Référence d’image importée invalide.')
        path = self.data_root / 'imports' / (sha + '.png')
        if not path.is_file() or not 8 <= path.stat().st_size <= 16 * 1024 * 1024:
            raise ValueError('Image importée absente du cache ; importez-la à nouveau.')
        data = path.read_bytes()
        if _digest(data) != sha:
            raise ValueError('L’image du cache a changé.')
        return data

    def import_image(self, language, resource, path):
        with self._lock:
            data, options, metadata = self._text_options(language, resource, None)
            path = Path(path).expanduser().resolve()
            if not path.is_file() or path.suffix.casefold() != '.png' or not 8 <= path.stat().st_size <= 16 * 1024 * 1024:
                raise ValueError('Choisissez une image PNG de moins de 16 Mo.')
            image = path.read_bytes()
            dialogue.render_popup_image(data, resource, image)
            sha = _digest(image)
            cache = self.data_root / 'imports' / (sha + '.png')
            if cache.exists() and (not cache.is_file() or _digest(cache.read_bytes()) != sha):
                raise ValueError('Conflit avec une image déjà présente dans le cache.')
            if not cache.exists():
                _atomic_write(cache, image)
            value = {'kind': 'image', 'sha256': sha, 'name': path.name, 'text': '', 'options': options}
            if self._texts.get((language, resource)) != value:
                self._change()
                self._texts[language, resource] = value
            return self.state()

    def _input(self, sha):
        if not isinstance(sha, str) or not HASH.fullmatch(sha):
            raise ValueError("Référence de voix importée invalide.")
        path = self.data_root / "imports" / (sha + ".wav")
        if not path.is_file() or not 44 <= path.stat().st_size <= audio.MAX_WAV_BYTES:
            raise ValueError("Voix importée absente du cache ; importez-la à nouveau.")
        data = path.read_bytes()
        if _digest(data) != sha:
            raise ValueError("La voix importée a été modifiée dans le cache.")
        return data

    def _store_input(self, data):
        sha = _digest(data)
        path = self.data_root / "imports" / (sha + ".wav")
        if path.exists():
            if not path.is_file() or _digest(path.read_bytes()) != sha:
                raise ValueError("Conflit avec une voix déjà présente dans le cache.")
        else:
            _atomic_write(path, data)
        return sha

    def import_voice(self, language, resource, path) -> dict:
        with self._lock:
            data = self._bank(language)
            path = Path(path).expanduser().resolve()
            if not path.is_file() or path.suffix.casefold() != ".wav" or not 44 <= path.stat().st_size <= audio.MAX_WAV_BYTES:
                raise ValueError("Choisissez un fichier WAV PCM local de moins de 128 Mo.")
            with path.open("rb") as stream:
                wav = stream.read(audio.MAX_WAV_BYTES + 1)
            if len(wav) > audio.MAX_WAV_BYTES:
                raise ValueError("Le WAV dépasse 128 Mo.")
            prepared, processing = self._prepare_voice(wav, {'gainDb': 0, 'trimStartSeconds': 0})
            metadata = audio.replacement_info(data, resource, prepared)
            metadata['processing'] = processing
            sha = self._store_input(wav)
            value = {"sha256": sha, "name": path.name, "metadata": metadata,
                     "options": {'gainDb': 0, 'trimStartSeconds': 0}}
            if self._voices.get((language, resource)) != value:
                self._change()
                self._voices[language, resource] = value
            return self.state()

    @staticmethod
    def _prepare_voice(wav, options):
        if not isinstance(options, dict) or set(options) != {'gainDb', 'trimStartSeconds'}:
            raise ValueError('Réglages de voix invalides : gainDb et trimStartSeconds requis.')
        return audio_processing.prepare_wav(wav, options['gainDb'], options['trimStartSeconds'])

    def _processed_voice(self, edit):
        return self._prepare_voice(self._input(edit['sha256']), edit.get('options', {'gainDb': 0, 'trimStartSeconds': 0}))

    def set_voice_options(self, language, resource, options):
        with self._lock:
            data = self._bank(language)
            current = self._voices.get((language, resource))
            if current is None:
                raise ValueError('Importez votre WAV avant de régler son volume ou son début.')
            wav, processing = self._prepare_voice(self._input(current['sha256']), options)
            metadata = audio.replacement_info(data, resource, wav)
            metadata['processing'] = processing
            value = dict(current, options=copy.deepcopy(options), metadata=metadata)
            if value != current:
                self._change()
                self._voices[language, resource] = value
            return self.state()

    def voice_preview(self, language, resource, modified=False) -> dict:
        with self._lock:
            data = self._bank(language)
            edit = self._voices.get((language, resource)) if modified else None
            if edit:
                prepared, processing = self._processed_voice(edit)
                data, metadata = audio.replace_voice(data, resource, prepared)
                metadata['processing'] = processing
            else:
                metadata = next((m for m in self._banks[language]["voices"] if m["key"] == resource), None)
                if metadata is None:
                    raise ValueError("Voix absente de la langue sélectionnée.")
            wav = audio.voice_wav(data, resource)
            return {"audio": _data_url(wav, "audio/wav"), "metadata": dict(metadata, modified=edit is not None)}

    def _resource_blob(self, kind, language, resource, modified):
        data = self._bank(language)
        if kind in ('text', 'png', 'txt'):
            data, options, metadata = self._text_options(language, resource, None)
            edit = self._texts.get((language, resource)) if modified else None
            if kind == 'txt':
                if not edit or edit.get('kind') == 'image':
                    raise ValueError('Le texte original est une image. Exportez son PNG ; le TXT est disponible pour votre texte rédigé.')
                return edit['text'].encode('utf-8'), '.txt'
            if edit:
                data = (dialogue.replace_popup_image(data, resource, self._image_input(edit['sha256']))
                        if edit.get('kind') == 'image' else dialogue.replace_popup_text(data, resource, edit['text'], options))
            return dialogue.decode_popup_png(data, resource), '.png'
        if kind == 'voice':
            edit = self._voices.get((language, resource)) if modified else None
            if edit:
                data, _ = audio.replace_voice(data, resource, self._processed_voice(edit)[0])
            return audio.voice_wav(data, resource), '.wav'
        raise ValueError('Choisissez un panneau PNG, votre texte TXT ou une voix WAV.')

    def export_resource(self, kind, language, resource, destination, modified=True):
        """Save an actual decoded PNG/WAV or authored TXT, without a browser download."""
        with self._lock:
            path = self._protect_destination(destination)
            self._verify_original(language)
            if path.exists():
                raise ValueError('Ce fichier existe déjà. Choisissez un nouveau nom pour conserver vos fichiers.')
            blob, extension = self._resource_blob(kind, language, resource, modified)
            if path.suffix.casefold() != extension:
                raise ValueError('Le fichier doit utiliser l’extension ' + extension + '.')
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(blob)
            if _digest(path.read_bytes()) != _digest(blob):
                raise ValueError('La vérification du fichier exporté a échoué.')
            return {'path': str(path), 'resource': resource, 'language': language, 'modified': bool(modified),
                    'size': len(blob), 'sha256': _digest(blob)}

    def export_library(self, kind, language, new_destination, progress=None):
        """Export one active language, sorted by native folders, into a new directory."""
        with self._lock:
            self._bank(language)
            self._verify_original(language)
            if kind not in ('text', 'voice'):
                raise ValueError('Choisissez la bibliothèque des panneaux ou des voix.')
            destination = self._protect_destination(new_destination)
            if destination.exists():
                raise ValueError('Choisissez un nouveau dossier de bibliothèque.')
            source_rows = self._banks[language]['dialogues' if kind == 'text' else 'voices']
            rows = [row for row in source_rows if kind == 'text' or row.get('editable')]
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(destination.name + '.partial-' + uuid.uuid4().hex)
            temporary.mkdir()
            files = []
            try:
                for index, row in enumerate(rows):
                    resource = row['resource' if kind == 'text' else 'key']
                    blob, extension = self._resource_blob(kind, language, resource, True)
                    parts = resource.split('/')[2:]
                    folders = [re.sub(r'[^a-zA-Z0-9_.-]', '_', part).strip(' .') or 'ressource' for part in parts[:-1]]
                    name = re.sub(r'[^a-zA-Z0-9_.-]', '_', parts[-1]).strip(' .') or 'ressource'
                    if kind == 'text' and name.lower().endswith('.tif'):
                        name = name[:-4]
                    # Resource index also prevents basename/case collisions on Windows.
                    relative = Path(*folders) / (f"{row.get('index', row.get('resourceIndex')):04d}-" + name + extension)
                    target = temporary / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open('xb') as stream:
                        stream.write(blob)
                    if _digest(target.read_bytes()) != _digest(blob):
                        raise ValueError('La vérification d’une ressource exportée a échoué.')
                    files.append({'file': relative.as_posix(), 'resource': resource, 'size': len(blob), 'sha256': _digest(blob)})
                    if progress:
                        progress((index + 1) * 100 / len(rows), f'Export {index + 1} / {len(rows)} · {name}')
                report = {'language': language, 'kind': kind, 'destination': str(destination),
                          'sourceSha256': self._banks[language]['sourceSha256'], 'files': files,
                          'count': len(files), 'originalsPreserved': True}
                _atomic_write(temporary / 'catalogue.json', _json(report))
                if destination.exists():
                    raise ValueError('Le dossier de destination a été créé pendant l’export.')
                temporary.rename(destination)
                return report
            finally:
                resolved = temporary.resolve()
                if (temporary.exists() and not temporary.is_symlink() and resolved.parent == destination.parent
                        and resolved.name.startswith(destination.name + '.partial-')):
                    shutil.rmtree(resolved)

    def restore(self, kind, language, resource) -> dict:
        with self._lock:
            self._bank(language)
            values = self._texts if kind in ("text", "dialogue", "dialogue-text") else self._voices if kind == "voice" else None
            if values is None:
                raise ValueError("Choisissez un dialogue ou une voix à restaurer.")
            if (language, resource) in values:
                self._change()
                del values[language, resource]
            return self.state()

    def reset(self) -> dict:
        with self._lock:
            self._require()
            if self._texts or self._voices:
                self._change()
                self._texts, self._voices = {}, {}
            return self.state()

    def undo(self) -> dict:
        with self._lock:
            if self._undo:
                self._redo.append(self._snapshot())
                self._texts, self._voices = self._undo.pop()
                self._last_export = None
            return self.state()

    def redo(self) -> dict:
        with self._lock:
            if self._redo:
                self._undo.append(self._snapshot())
                self._texts, self._voices = self._redo.pop()
                self._last_export = None
            return self.state()

    def _project_file(self, path):
        path = self._protect_destination(path)
        if not path.name.casefold().endswith(".azdialog.json"):
            raise ValueError("Enregistrez avec l’extension .azdialog.json.")
        return path

    def save_project(self, path) -> dict:
        with self._lock:
            self._require()
            path = self._project_file(path)
            if path.exists():
                previous = _read_json(path)
                if not isinstance(previous, dict) or previous.get("format") != FORMAT or previous.get("version") != 1:
                    raise ValueError("Ce fichier existe et n’est pas un projet Dialogue Studio.")
            inputs, asset_dir = {}, path.with_name(path.name[:-5] + ".assets")
            for edit in self._voices.values():
                sha = edit["sha256"]
                if sha in inputs:
                    continue
                wav = self._input(sha)
                asset = asset_dir / (sha + ".wav")
                if asset.exists() and (not asset.is_file() or _digest(asset.read_bytes()) != sha):
                    raise ValueError("Un fichier de voix du projet existe avec un contenu différent.")
                if not asset.exists():
                    _atomic_write(asset, wav)
                inputs[sha] = {"file": asset_dir.name + "/" + asset.name, "sha256": sha, "size": len(wav)}
            for edit in self._texts.values():
                if edit.get('kind') != 'image':
                    continue
                sha = edit['sha256']
                image = self._image_input(sha)
                asset = asset_dir / (sha + '.png')
                if asset.exists() and (not asset.is_file() or _digest(asset.read_bytes()) != sha):
                    raise ValueError('Une image du projet existe avec un contenu différent.')
                if not asset.exists():
                    _atomic_write(asset, image)
                inputs[sha] = {'file': asset_dir.name + '/' + asset.name, 'sha256': sha, 'size': len(image)}
            document = {"format": FORMAT, "version": 1, "sourcePath": self._source_path, "sourceKind": self._source_kind,
                        "fingerprints": {lang: b["sourceSha256"] for lang, b in self._banks.items()},
                        "texts": [{"language": lang, "resource": key, **copy.deepcopy(value)} for (lang, key), value in self._texts.items()],
                        "voices": [{"language": lang, "resource": key, "sha256": value["sha256"], "name": value["name"],
                                    "options": copy.deepcopy(value.get('options', {'gainDb': 0, 'trimStartSeconds': 0}))} for (lang, key), value in self._voices.items()],
                        "inputs": inputs}
            blob = _json(document)
            if len(blob) > MAX_PROJECT_BYTES:
                raise ValueError("Le projet dépasse 4 Mo.")
            _atomic_write(path, blob)
            self._project_path = str(path)
            return {"path": str(path), "inputs": len(inputs), "edits": self.state()["edits"]}

    def load_project(self, path) -> dict:
        with self._lock:
            path = Path(path).expanduser().resolve()
            if not path.name.casefold().endswith(".azdialog.json") or not path.is_file():
                raise ValueError("Choisissez un projet .azdialog.json existant.")
            document = _read_json(path)
            if (not isinstance(document, dict) or document.get("format") != FORMAT or type(document.get("version")) is not int
                    or document["version"] != 1 or set(document) != {"format", "version", "sourcePath", "sourceKind", "fingerprints", "texts", "voices", "inputs"}):
                raise ValueError("Format du projet Dialogue Studio invalide.")
            if (not isinstance(document["sourcePath"], str) or document["sourceKind"] not in ("dump", "iso")
                    or not isinstance(document["fingerprints"], dict) or not isinstance(document["texts"], list)
                    or not isinstance(document["voices"], list) or not isinstance(document["inputs"], dict)
                    or len(document["texts"]) + len(document["voices"]) > 3000):
                raise ValueError("Structure du projet invalide.")
            candidate = StudioProject(self.data_root)
            source_missing = not Path(document["sourcePath"]).expanduser().exists()
            if source_missing:
                if not self._source_path:
                    raise ValueError("La source enregistrée dans le projet n’est plus disponible. Ouvrez votre dump ou ISO du jeu, puis ouvrez à nouveau le projet.")
                candidate.load_source(self._source_path)
            else:
                candidate.load_source(document["sourcePath"])
            if ((not source_missing and candidate._source_kind != document["sourceKind"])
                    or {lang: b["sourceSha256"] for lang, b in candidate._banks.items()} != document["fingerprints"]):
                raise ValueError("La source ne correspond plus aux empreintes du projet.")
            texts, voices, imported = {}, {}, {}
            for sha, item in document["inputs"].items():
                extension = '.png' if isinstance(item, dict) and str(item.get('file', '')).endswith('.png') else '.wav'
                expected = path.name[:-5] + ".assets/" + sha + extension
                if (not HASH.fullmatch(sha) or not isinstance(item, dict) or set(item) != {"file", "sha256", "size"}
                        or item["file"] != expected or item["sha256"] != sha or type(item["size"]) is not int
                        or not (8 if extension == '.png' else 44) <= item["size"] <= (16 * 1024 * 1024 if extension == '.png' else audio.MAX_WAV_BYTES)):
                    raise ValueError("Une voix importée référence un fichier extérieur au projet.")
                file = path.parent / expected
                if not file.is_file() or not file.resolve().is_relative_to(path.parent) or file.stat().st_size != item["size"]:
                    raise ValueError("Une voix du projet est absente, liée hors du dossier ou tronquée.")
                wav = file.read_bytes()
                if _digest(wav) != sha:
                    raise ValueError("Empreinte d’une voix importée incorrecte.")
                imported[sha] = wav
            for row in document["texts"]:
                expected_keys = ({'language', 'resource', 'text', 'options', 'kind', 'sha256', 'name'}
                                 if isinstance(row, dict) and row.get('kind') == 'image' else {'language', 'resource', 'text', 'options'})
                if not isinstance(row, dict) or set(row) != expected_keys:
                    raise ValueError("Dialogue du projet invalide.")
                key = row["language"], row["resource"]
                if not all(isinstance(v, str) for v in key) or key in texts:
                    raise ValueError("Dialogue dupliqué ou invalide.")
                data, options, metadata = candidate._text_options(*key, row["options"])
                if row.get('kind') == 'image':
                    if row.get('sha256') not in imported or row['text'] != '' or not isinstance(row.get('name'), str) or len(row['name']) > 255:
                        raise ValueError('Image du projet absente ou invalide.')
                    dialogue.render_popup_image(data, key[1], imported[row['sha256']])
                    texts[key] = {name: copy.deepcopy(row[name]) for name in ('kind', 'sha256', 'name', 'text', 'options')}
                else:
                    dialogue.render_popup_text(data, key[1], row["text"], options)
                    texts[key] = {"text": row["text"], "options": options}
            for row in document["voices"]:
                if not isinstance(row, dict) or set(row) not in ({"language", "resource", "sha256", "name"}, {"language", "resource", "sha256", "name", "options"}):
                    raise ValueError("Voix du projet invalide.")
                key = row["language"], row["resource"]
                if (not all(isinstance(v, str) for v in key) or key in voices or not isinstance(row["sha256"], str)
                        or row["sha256"] not in imported or not isinstance(row["name"], str) or len(row["name"]) > 255):
                    raise ValueError("Voix dupliquée ou import absent.")
                options = row.get('options', {'gainDb': 0, 'trimStartSeconds': 0})
                prepared, processing = self._prepare_voice(imported[row['sha256']], options)
                metadata = audio.replacement_info(candidate._bank(key[0]), key[1], prepared)
                metadata['processing'] = processing
                voices[key] = {"sha256": row["sha256"], "name": row["name"], "metadata": metadata,
                               "options": copy.deepcopy(options)}
            used = {row["sha256"] for row in voices.values()} | {row['sha256'] for row in texts.values() if row.get('kind') == 'image'}
            if used != set(imported):
                raise ValueError("Le projet contient une voix importée non référencée.")
            for sha, blob in imported.items():
                if any(edit.get('sha256') == sha and edit.get('kind') == 'image' for edit in texts.values()):
                    _atomic_write(self.data_root / 'imports' / (sha + '.png'), blob)
                else:
                    self._store_input(blob)
            self._source_path, self._source_kind = candidate._source_path, candidate._source_kind
            self._baselines, self._banks = candidate._baselines, candidate._banks
            self._texts, self._voices = texts, voices
            self._undo, self._redo, self._last_export = [], [], None
            self._project_path = str(path)
            return self.state()

    def _verify_original(self, language):
        bank = self._banks[language]
        file = Path(bank["filePath"])
        if not file.is_file():
            raise ValueError("La source originale n’est plus disponible.")
        with file.open("rb") as stream:
            if self._source_kind == "iso":
                stream.seek(bank["offset"])
            data = stream.read(bank["size"] + (0 if self._source_kind == "iso" else 1))
        if len(data) != bank["size"] or _digest(data) != bank["sourceSha256"]:
            raise ValueError("La banque source a changé depuis son ouverture. Rouvrez votre source avant d’exporter.")

    def export_mod(self, new_destination) -> dict:
        with self._lock:
            self._require()
            if not self._texts and not self._voices:
                raise ValueError("Modifiez un texte ou une voix avant d’exporter.")
            destination = self._protect_destination(new_destination)
            if destination.exists():
                raise ValueError("Choisissez un nouveau dossier d’export ; aucun dossier existant ne sera écrasé.")
            changed_languages = {language for language, key in self._texts} | {language for language, key in self._voices}
            for language in changed_languages:
                self._verify_original(language)
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(destination.name + ".partial-" + uuid.uuid4().hex)
            temporary.mkdir()
            rows, changes = [], []
            try:
                for language in sorted(changed_languages):
                    data = self._bank(language)
                    baseline = data
                    for (lang, resource), edit in self._texts.items():
                        if lang == language:
                            if edit.get('kind') == 'image':
                                data, metadata = dialogue.popup_image_change(data, resource, self._image_input(edit['sha256']))
                            else:
                                data, metadata = dialogue.popup_change(data, resource, edit["text"], edit["options"])
                            changes.append(dict(metadata, language=language))
                    for (lang, resource), edit in self._voices.items():
                        if lang == language:
                            prepared, processing = self._processed_voice(edit)
                            data, metadata = audio.replace_voice(data, resource, prepared)
                            metadata['processing'] = processing
                            changes.append({"kind": "voice", "language": language, "resource": resource,
                                            "inputSha256": edit["sha256"], "inputName": edit["name"], "metadata": metadata})
                    if len(data) > MAX_BANK_BYTES or audio._archive(data)[1] != audio._archive(baseline)[1]:
                        raise ValueError("Les références de la banque modifiée n’ont pas été conservées.")
                    bank = self._banks[language]
                    row = {"path": bank["gamePath"], "sourceSha256": bank["sourceSha256"], "sha256": _digest(data)}
                    target = temporary.joinpath(*row["path"].split("/"))
                    _atomic_write(target, data)
                    if _digest(target.read_bytes()) != row["sha256"]:
                        raise ValueError("L’export de la banque n’a pas été vérifié.")
                    rows.append(row)
                plan = {"format": "azurik-level-iso", "version": 1, "gameFiles": rows}
                _atomic_write(temporary / "iso-plan.json", _json(plan))
                report = {"format": FORMAT + "-export", "version": 1, "sourceKind": self._source_kind,
                          "sourcePath": self._source_path, "destination": str(destination), "gameFiles": rows,
                          "edits": self.state()["edits"], "changes": changes, "originalsPreserved": True,
                          "isoPlan": str(destination / "iso-plan.json")}
                _atomic_write(temporary / "dialogue-export.json", _json(report))
                if destination.exists():
                    raise ValueError("Le dossier de destination a été créé pendant l’export.")
                temporary.rename(destination)
                self._last_export = {"destination": str(destination), "gameFiles": rows, "edits": report["edits"], "isoPlan": report["isoPlan"]}
                return report
            finally:
                # Only this newly allocated staging directory may be removed.
                resolved = temporary.resolve()
                if (temporary.exists() and not temporary.is_symlink() and resolved.parent == destination.parent
                        and resolved.name.startswith(destination.name + ".partial-")):
                    shutil.rmtree(resolved)
