[CmdletBinding()]
param(
    [string]$Python = '',
    [string]$WindowsOutputDirectory = 'windows',
    [switch]$InstallDependencies
)

$ErrorActionPreference = 'Stop'
$dialogueRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
if ($env:OS -ne 'Windows_NT') {
    throw 'This build script creates a Windows desktop application.'
}

$dialoguePythonPrefix = @()
if ($Python) {
    $dialoguePython = (Get-Command $Python -ErrorAction Stop).Source
} else {
    $dialogueLocalPython = Join-Path $dialogueRoot '.venv-desktop\Scripts\python.exe'
    $dialogueSharedPython = Join-Path (Split-Path $dialogueRoot -Parent) 'azurik-level-studio\.venv-desktop\Scripts\python.exe'
    if (Test-Path -LiteralPath $dialogueLocalPython -PathType Leaf) {
        $dialoguePython = $dialogueLocalPython
    } elseif (Test-Path -LiteralPath $dialogueSharedPython -PathType Leaf) {
        $dialoguePython = $dialogueSharedPython
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        $dialoguePython = (Get-Command py).Source
        $dialoguePythonPrefix = @('-3')
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $dialoguePython = (Get-Command python).Source
    } else {
        throw 'Python 3.10+ is required. Pass its executable path with -Python.'
    }
}

$dialogueBuild = [System.IO.Path]::GetFullPath((Join-Path $dialogueRoot 'build\desktop'))
$dialogueDist = [System.IO.Path]::GetFullPath((Join-Path $dialogueRoot 'dist'))
$dialogueWindows = [System.IO.Path]::GetFullPath((Join-Path $dialogueRoot $WindowsOutputDirectory))
$dialoguePrefix = $dialogueRoot.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
foreach ($dialogueTarget in @($dialogueBuild, $dialogueDist, $dialogueWindows)) {
    if (-not $dialogueTarget.StartsWith($dialoguePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'Build output must stay inside the Dialogue Studio source directory.'
    }
}

# Build from this project directory so unrelated modules in the caller's CWD
# cannot shadow Python's standard library. Nothing installs unless requested.
Push-Location -LiteralPath $dialogueRoot
try {
    if ($InstallDependencies) {
        & $dialoguePython @dialoguePythonPrefix -m pip install -r (Join-Path $dialogueRoot 'requirements-desktop.txt')
        if ($LASTEXITCODE -ne 0) { throw 'Could not install desktop build dependencies.' }
    }
    & $dialoguePython @dialoguePythonPrefix -c 'import sys; assert sys.version_info >= (3, 10); import PyInstaller, webview, pythonnet; from PIL import Image'
    if ($LASTEXITCODE -ne 0) {
        throw 'Desktop dependencies are missing. Install requirements-desktop.txt or rerun with -InstallDependencies.'
    }
    foreach ($dialogueFolder in @($dialogueBuild, $dialogueDist, $dialogueWindows)) {
        [System.IO.Directory]::CreateDirectory($dialogueFolder) | Out-Null
    }
    & $dialoguePython @dialoguePythonPrefix -m PyInstaller --noconfirm --clean --distpath $dialogueDist --workpath $dialogueBuild (Join-Path $dialogueRoot 'desktop.spec')
    if ($LASTEXITCODE -ne 0) { throw 'The desktop executable build failed.' }
    $dialogueBuiltExe = Join-Path $dialogueDist 'Azurik Dialogue Studio.exe'
    if (-not (Test-Path -LiteralPath $dialogueBuiltExe -PathType Leaf)) {
        throw 'PyInstaller did not create the expected executable.'
    }
    $dialogueWindowsExe = Join-Path $dialogueWindows 'Azurik Dialogue Studio.exe'
    Copy-Item -LiteralPath $dialogueBuiltExe -Destination $dialogueWindowsExe -Force
    $dialogueHash = (Get-FileHash -LiteralPath $dialogueWindowsExe -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-Output ('Executable: ' + $dialogueWindowsExe)
    Write-Output ('SHA256: ' + $dialogueHash)
} finally {
    Pop-Location
}
