# Azurik Dialogue Studio — 1.0.0

An offline Windows application to **edit existing dialogue panels and replace voice recordings** in the European English/French/German edition of *Azurik: Rise of Perathia*.

[Download the official 1.0.0 release](https://github.com/Azurik-Modding-Hub/Azurik-Dialogue-Studio/releases/tag/v1.0.0) · [Français](README.fr.md) · [User guide](GUIDE.md)

Download the Windows ZIP, extract it and double-click **`windows/Azurik Dialogue Studio.exe`**. The standalone EXE is also available as a release attachment. Python is not required to run the executable. The interface supports French and English; the game resource language is selected separately.

## Features

- Open your local extracted game folder or Xbox ISO/XISO.
- Browse **248 dialogue panels** across English, French and German banks, with original/replacement previews.
- Type replacement text, or **import a UTF-8 TXT file**, and adjust font, size, colour and alignment. Authored text retains the original frame and Continue prompt.
- **Import a PNG to replace an entire panel**, including its frame and prompt. The image is resized to the original texture dimensions; native encoding and all mip levels are rebuilt.
- Preview and replace voices, including **49 English, 50 French and 50 German oracle recordings**.
- Import integer PCM WAV recordings (8/16/24/32-bit, mono/stereo), with a duration independent of the original voice. Native resources are resized to keep your recording without speeding it up or truncating it. Limits: 10 minutes and 128 MiB per WAV.
- Adjust imported voice gain from −12 to +12 dB with a linked peak limiter. An optional playback-start setting explicitly removes a chosen initial portion; both settings default to zero.
- Export individual PNG, TXT and decoded WAV files, or sorted panel/voice libraries for the active language.
- Undo, redo, restore originals and save portable projects with their imported PNG/WAV sidecar files.
- Export modified banks, or build **a new verified ISO** while preserving the existing executable, levels and other disc files.

All processing runs locally. No account, subscription, payment, voice cloning or online AI service is needed. **Game files and personal recordings are not included.**

## Interface illustrations

![Dialogue panels, TXT import and PNG replacement](docs/screenshots/dialogue-editor-1.0.0.png)

![Oracle voice preview, replacement and audio settings](docs/screenshots/oracle-voice-editor-1.0.0.png)

The version 1.0.0 interface is rendered with an isolated demonstration project.
The voice example uses synthetic audio. These illustrations show editing tools;
in-game playback validation remains separate.

## Quick start

1. Choose **File → Open game folder** or **Open ISO**.
2. Select the game language, then **Text** or **Voices**.
3. Select a panel and apply your text, import a TXT, or replace its PNG. For a voice, import your WAV and preview the converted result.
4. Save the project, then choose **Export mod** or **Build a new ISO**.
5. Launch the new ISO with the corresponding game language and test the existing dialogue event.

The original game text is stored as **bitmap images**, not plaintext. The application displays the original and lets you author or import its replacement; it does not perform OCR. Applying authored text after importing a PNG replaces that PNG with a text panel using the original game frame.

**Ctrl+S** saves, **Ctrl+F** searches, **Ctrl+Z** undoes and **Ctrl+Shift+Z** redoes applied changes. Inside the text field, undo affects typing; the ↶ / ↷ buttons operate on project changes. **Ctrl+Enter** applies text.

## Scope and validation

This release replaces existing resources. Adding new dialogue events, placing triggers in Level Studio and changing Bink cinematic audio are future work. See [Events and Level Studio](EVENTS.md).

The archive codecs, project roundtrips, source protection, native interface and ISO readback have been tested. See [Validation](VALIDATION.md). **Modified dialogue playback in Xemu still needs an in-game test.** File validation alone does not validate every gameplay situation.

Windows needs **Microsoft Edge WebView2 Runtime**. The application does not install it automatically. The EXE is currently unsigned.

## Cache and saves

EDIT : You need to clear the cache for the changes you make to take effect ! Don’t worry, this won’t affect your save files in any way!

First check that Xemu is loading the new ISO and the modified language, then restart it completely. If old game resources remain cached, clear only the Xbox cache partitions **X, Y and Z** with a suitable tool for your installation. Saves are on **E**; preserve that partition and the virtual hard-drive image. Dialogue Studio does not clear any cache automatically.

## Build from source

Use Windows and Python 3.10 or later. Install `requirements-desktop.txt`, then run `build-desktop.ps1`. The script accepts `-Python` for an explicit interpreter. It installs dependencies only when `-InstallDependencies` is explicitly supplied. `python desktop.py` runs the source application.

## License and project boundaries

Application code is [MIT licensed](LICENSE). Reused ISO tools retain their [third-party license and attribution](THIRD_PARTY_LICENSES.md).

This application is separate from Azurik Level Studio and the human-only Azurik-Decomp project. Keep game banks, disc images, extracted audio, personal recordings, user projects and private research out of public repositories.
