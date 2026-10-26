$ErrorActionPreference = 'Stop'
foreach ($vendor in @('Google\Chrome', 'Microsoft\Edge')) {
    $key = "HKCU:\Software\$vendor\NativeMessagingHosts\com.focuslock.bridge"
    if (Test-Path -LiteralPath $key) { Remove-Item -LiteralPath $key }
}
Write-Output 'Focus Lock 的本機橋接登錄已移除。請另在瀏覽器移除擴充功能。'
