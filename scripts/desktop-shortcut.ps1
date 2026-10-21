$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
$shell = New-Object -ComObject WScript.Shell
$shortcutPath = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Jarvis AI.lnk'
# Do not replace a shortcut belonging to the user's existing Jarvis installation.
if (Test-Path $shortcutPath) {
    $shortcutPath = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Jarvis AI - UI proba.lnk'
}
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $env:SystemRoot 'System32\wscript.exe'
$shortcut.Arguments = '"' + (Join-Path $projectPath 'JARVIS.vbs') + '"'
$shortcut.WorkingDirectory = $projectPath
$shortcut.Description = 'Jarvis AI - kulon asztali alkalmazas'
$shortcut.IconLocation = (Join-Path $projectPath 'electron\node_modules\electron\dist\electron.exe') + ',0'
$shortcut.Save()
Write-Host "Asztali parancsikon: $shortcutPath"
