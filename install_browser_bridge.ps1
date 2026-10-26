param([string]$ReleaseDir = 'dist', [ValidateSet('Chrome', 'Edge', 'Both')][string]$Browser = 'Chrome')
$ErrorActionPreference = 'Stop'
$releasePath = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot $ReleaseDir))
$hostExecutable = Join-Path $releasePath 'FocusLockBrowserHost.exe'
if (-not (Test-Path -LiteralPath $hostExecutable)) { throw "找不到本機橋接：$hostExecutable" }
$extensionId = (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'browser-extension\extension-id.txt') -Raw).Trim()
if ($extensionId -notmatch '^[a-p]{32}$') { throw '擴充功能 ID 格式錯誤。' }
$manifestPath = Join-Path $releasePath 'com.focuslock.bridge.json'
$manifest = @{name='com.focuslock.bridge'; description='Focus Lock local website policy'; path=$hostExecutable;
    type='stdio'; allowed_origins=@("chrome-extension://$extensionId/")}
$json = $manifest | ConvertTo-Json -Depth 4
[IO.File]::WriteAllText($manifestPath, $json, [Text.UTF8Encoding]::new($false))
$vendors = switch ($Browser) { 'Chrome' { @('Google\Chrome') } 'Edge' { @('Microsoft\Edge') } 'Both' { @('Google\Chrome', 'Microsoft\Edge') } }
foreach ($vendor in $vendors) {
    $key = "HKCU:\Software\$vendor\NativeMessagingHosts\com.focuslock.bridge"
    New-Item -Path $key -Force | Out-Null
    Set-Item -LiteralPath $key -Value $manifestPath
}
Write-Output "本機橋接已註冊到 $Browser（只設定目前使用者的 Native Messaging Host）。"
Write-Output "請在 Chrome 或 Edge 的擴充功能頁載入資料夾：$(Join-Path $PSScriptRoot 'browser-extension')"
Write-Output "擴充功能 ID：$extensionId"
