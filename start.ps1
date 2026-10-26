$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$projectPython = Join-Path $PSScriptRoot '.venv312\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    $projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
}
if (-not (Test-Path -LiteralPath $projectPython)) {
    throw '請先依 README 建立 Python 3.12 環境並安裝 requirements.txt。'
}
& $projectPython main.py
if ($LASTEXITCODE -ne 0) { throw 'Focus Lock 啟動失敗，請查看上方錯誤訊息。' }
