"""Create a separate Azurik disc containing only existing language-bank edits.

The shared MIT XDVDFS writer verifies source/export hashes, preserves the
executable and every other game asset, then rereads the complete new image.
No compiler, network service or paid tool is involved.
"""
from __future__ import annotations

from pathlib import Path

import level_iso


LANGUAGE_BANKS = frozenset(('gamedata/english.xbr', 'gamedata/french.xbr', 'gamedata/german.xbr'))


def inspect_export(export_dir) -> list[dict]:
    """Validate the exact edit-only contract before writing a new ISO."""
    root = Path(export_dir).absolute()
    level_iso._reject_reparse(root)
    root = root.resolve()
    changes, removed, operations = level_iso._load_plan(root)
    if removed or operations['created'] or operations['deleted']:
        raise ValueError("Cet éditeur remplace les textes et voix existants ; le plan ISO ne peut pas ajouter ou supprimer de niveaux.")
    if not changes or len(changes) > len(LANGUAGE_BANKS):
        raise ValueError("Le plan ISO doit contenir de une à trois banques de langue modifiées.")
    for item in changes:
        if item['key'] not in LANGUAGE_BANKS:
            raise ValueError("Seules les banques english.xbr, French.xbr et German.xbr peuvent être remplacées ici.")
        if item['sourceSha256'] is None:
            raise ValueError("Chaque banque doit remplacer un fichier déjà présent dans l'ISO source.")
    return [{key:item[key] for key in ('path','size','sha256','sourceSha256')} for item in changes]


def build_iso(input_iso, export_dir, output_iso, progress=None) -> dict:
    """Build, hash and reread a new disc; progress receives (percent, stage)."""
    inspect_export(export_dir)
    result = level_iso.build_iso(input_iso, export_dir, output_iso, progress)
    if not result.get('executableUnchanged') or not result.get('sourceUnchanged'):
        raise ValueError("La vérification de conservation du jeu original a échoué.")
    result['editor'] = 'Azurik Dialogue Studio'
    result['outputISO'] = str(Path(output_iso).resolve())
    result['scope'] = 'existing dialogue and voice replacements'
    return result
