# Bundle only application resources; game dumps, exports and personal voices
# are never collected from the project directory.
import ast
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable,
    VarFileInfo, VarStruct, VSVersionInfo,
)

root = Path(SPECPATH).resolve()
entry = root / "desktop.py"
icon = root / "assets" / "studio.ico"
if not icon.is_file():
    raise FileNotFoundError("The application icon assets/studio.ico is required")

# Read the declared version without importing the desktop app or its backend.
tree = ast.parse(entry.read_text(encoding="utf-8"))
version = next(
    node.value.value for node in tree.body
    if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == "VERSION" for target in node.targets)
    and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
)
numeric_version = tuple(int(part) for part in version.split("."))
if len(numeric_version) != 3 or any(not 0 <= part <= 65535 for part in numeric_version):
    raise ValueError("desktop.py VERSION must contain three numeric components")
numeric_version += (0,)

data = [(str(root / "web"), "web"), (str(root / "assets"), "assets")]
data += collect_data_files("webview", subdir="js")
data += collect_data_files("webview", subdir="lib")
for package in ["pywebview", "pythonnet", "clr_loader", "bottle", "proxy_tools",
                "typing_extensions", "Pillow", "cffi", "pycparser"]:
    data += copy_metadata(package)

analysis = Analysis(
    [str(entry)], pathex=[str(root)], binaries=[], datas=data,
    hiddenimports=[
        "studio_backend", "dialogue_formats", "audio_formats", "audio_processing", "iso_export",
        "level_iso", "level_prefetch", "xbox_iso", "webview.http",
        "webview.platforms.winforms", "webview.platforms.edgechromium",
        "clr", "pythonnet", "clr_loader", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont",
    ],
    hookspath=[], runtime_hooks=[],
    excludes=[
        "pytest", "numpy", "scipy", "pandas", "matplotlib", "IPython",
        "webview.platforms.qt", "webview.platforms.gtk", "webview.platforms.cocoa",
        "webview.platforms.android", "webview.platforms.cef",
    ],
    noarchive=False,
)
archive = PYZ(analysis.pure)
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=numeric_version, prodvers=numeric_version,
                     mask=0x3F, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0, 0)),
    kids=[
        StringFileInfo([StringTable("040904B0", [
            StringStruct("CompanyName", "Azurik Modding Hub"),
            StringStruct("FileDescription", "Azurik Dialogue Studio"),
            StringStruct("FileVersion", version),
            StringStruct("InternalName", "AzurikDialogueStudio"),
            StringStruct("OriginalFilename", "Azurik Dialogue Studio.exe"),
            StringStruct("ProductName", "Azurik Dialogue Studio"),
            StringStruct("ProductVersion", version),
        ])]),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)
exe = EXE(
    archive, analysis.scripts, analysis.binaries, analysis.datas, [],
    name="Azurik Dialogue Studio", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False, icon=str(icon), version=version_info,
)
