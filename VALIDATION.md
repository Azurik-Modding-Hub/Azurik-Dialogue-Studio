# Validation — 1.0.0

Checks completed on 14 October 2026 using the European English/French/German edition.

| Game language | Dialogue panels | Voices | Oracle voices |
|---|---:|---:|---:|
| French | 84 | 223 | 50 |
| English | 82 | 234 | 49 |
| German | 82 | 223 | 50 |

**85 automated tests and 37 subtests pass.** Coverage includes native text and image codecs, audio encoding and variable resource duration, voice gain/start processing, project save/load, imported PNG/WAV sidecars, TXT roundtrips, history, file exports, source protection, background jobs and ISO construction.

The native Windows interface passed **17 integration checks**: real catalogue and original panel decoding, authored text, undo/redo, English interface, TXT import, whole-panel PNG import and refresh, original voice playback control, WAV import, voice settings and converted preview, project saving, individual WAV export and sorted panel-library export. These checks use the same bridge and frontend as the desktop application.

All 248 original panels were decoded. Text replacements across all three banks retained native sizes, resource references, frames and Continue prompts. A high-resolution PNG was converted to the English training panel's 256 × 256 DXT3 texture with all nine mip levels rebuilt; other bank resources remained unchanged.

Xbox IMA ADPCM decoding was compared to an independent local decoder. Voice replacements with shorter and longer durations preserve the other bank resources and update archive offsets, resource counters and relocations. Audio gain/start processing is tested with synthetic PCM signals, including stereo-linked peak limiting and preservation of the unprocessed input.

Private test ISO builds were reread and all **93 game files** were checked. The language-bank export preserves the source executable and every unrelated disc file. The source dump, input ISO and imported files remain unchanged. Freecam executable patching is a separate project and is not part of the Dialogue Studio release.

The frozen Windows executable recognizes all three language banks. Its embedded resources contain application code, UI, icon and dependencies. Release packaging uses an explicit allowlist and file hashes; no game bank, disc image, personal recording, imported panel, user project or research file is shipped.

**In-game dialogue and voice testing in Xemu is still required.** These checks validate files and application behavior; they do not replace gameplay verification of timings, rendering or event transitions.
