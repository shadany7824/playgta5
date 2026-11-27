$ErrorActionPreference = 'Continue'
$log = 'E:\Malik\game\playgta5\apply-optimizations-result.txt'
Start-Transcript -Path $log -Force | Out-Null
Write-Output '=== PlayGTA5 optimization batch (admin part) ==='
Write-Output ('Date: ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))

Write-Output ''
Write-Output '--- 1/4 Defender exclusions ---'
Add-MpPreference -ExclusionPath 'E:\Malik\game\playgta5'
Add-MpPreference -ExclusionPath 'C:\Program Files\Google\Chrome\Application\chrome.exe'
Write-Output 'ExclusionPath now:'
(Get-MpPreference).ExclusionPath
$mp = Join-Path $env:ProgramFiles 'Windows Defender\MpCmdRun.exe'
if (Test-Path $mp) { & $mp -CheckExclusion -Path 'E:\Malik\game\playgta5' }

Write-Output ''
Write-Output '--- 2/4 SysMain (Superfetch) off ---'
sc.exe stop SysMain
sc.exe config SysMain start= disabled
Get-Service SysMain | Select-Object Name, Status, StartType | Format-List

Write-Output ''
Write-Output '--- 3/4 Pagefile: fixed 16 GB on C: ---'
$cs = Get-CimInstance Win32_ComputerSystem
if ($cs.AutomaticManagedPagefile) {
  Set-CimInstance -InputObject $cs -Property @{ AutomaticManagedPagefile = $false }
  Write-Output 'Automatic pagefile management: turned OFF'
} else {
  Write-Output 'Automatic pagefile management: already OFF'
}
$pf = Get-CimInstance Win32_PageFileSetting | Where-Object { $_.Name -like 'C:*' } | Select-Object -First 1
if ($pf) {
  Set-CimInstance -InputObject $pf -Property @{ InitialSize = 16384; MaximumSize = 16384 }
  Write-Output 'C: pagefile updated to fixed 16384 MB (applies at next reboot)'
} else {
  New-CimInstance -ClassName Win32_PageFileSetting -Property @{ Name = 'C:\pagefile.sys'; InitialSize = 16384; MaximumSize = 16384 } | Out-Null
  Write-Output 'C: pagefile created at fixed 16384 MB (applies at next reboot)'
}
Write-Output 'All pagefiles now:'
Get-CimInstance Win32_PageFileSetting | Select-Object Name, InitialSize, MaximumSize | Format-Table -AutoSize

Write-Output ''
Write-Output '--- 4/4 HDD E: fragmentation analysis (read-only) ---'
defrag.exe E: /A
Write-Output ''
Write-Output '=== batch complete ==='
Stop-Transcript | Out-Null
