$ErrorActionPreference = 'Continue'
$log = 'E:\Malik\game\playgta5\apply-optimizations-result2.txt'
Start-Transcript -Path $log -Force | Out-Null
Write-Output '=== PlayGTA5 batch part 2: pagefile (registry) + defrag E: ==='
Write-Output ('Date: ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))

Write-Output ''
Write-Output '--- Pagefile via registry (CIM method failed with value-out-of-range) ---'
$reg = 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management'
$before = (Get-ItemProperty -Path $reg -Name PagingFiles).PagingFiles
Write-Output ('PagingFiles before: ' + $before)
Set-ItemProperty -Path $reg -Name PagingFiles -Value 'C:\pagefile.sys 16384 16384'
$after = (Get-ItemProperty -Path $reg -Name PagingFiles).PagingFiles
Write-Output ('PagingFiles after:  ' + $after)
Write-Output 'Takes effect at next reboot.'

Write-Output ''
Write-Output '--- Re-check Defender exclusions (admin) ---'
$mp = Join-Path $env:ProgramFiles 'Windows Defender\MpCmdRun.exe'
if (Test-Path $mp) {
  & $mp -CheckExclusion -Path 'E:\Malik\game\playgta5\game-log.txt'
  & $mp -CheckExclusion -Path 'C:\Program Files\Google\Chrome\Application\chrome.exe'
}
Write-Output 'ExclusionPath list:'
(Get-MpPreference).ExclusionPath

Write-Output ''
Write-Output '--- Defrag E: (optimize) --- can take 30-90 minutes. Do not play while it runs.'
defrag.exe E: /O
Write-Output '--- defrag finished ---'
Stop-Transcript | Out-Null
