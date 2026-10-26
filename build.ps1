param([string]$PythonExe = '')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not $PythonExe -and (Test-Path -LiteralPath '.venv312\Scripts\python.exe')) {
    $PythonExe = Join-Path $PSScriptRoot '.venv312\Scripts\python.exe'
}
if (-not $PythonExe -and -not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw '請先安裝 Python 3.12（64 位元）與 Python Launcher。' }
}
if (-not $PythonExe) { $PythonExe = Join-Path $PSScriptRoot '.venv\Scripts\python.exe' }
& $pythonExe -c "import sys; assert sys.version_info[:2] == (3, 12), '需要 Python 3.12'"
if ($LASTEXITCODE -ne 0) { throw '虛擬環境版本不正確。' }
& $pythonExe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw '安裝依賴失敗。' }
& $pythonExe -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw '測試失敗。' }
& $pythonExe -m PyInstaller --noconfirm FocusLock.spec
if ($LASTEXITCODE -ne 0) { throw '打包失敗。' }
& $pythonExe -m PyInstaller --noconfirm BrowserHost.spec
if ($LASTEXITCODE -ne 0) { throw '瀏覽器橋接打包失敗。' }
Write-Output '已產生 dist\FocusLock.exe 與 dist\FocusLockBrowserHost.exe；橋接安裝時使用 -ReleaseDir dist。'
