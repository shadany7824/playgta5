$ErrorActionPreference = 'Continue'
$log = 'E:\Malik\game\apply-optimizations-result3.txt'
Start-Transcript -Path $log -Force | Out-Null
Write-Output '=== PlayGTA5 batch part 3: pagefile revert, hibernate off, recycle bin, Videos->D:, game E:->C: ==='
Write-Output ('Date: ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))

Write-Output ''
Write-Output '--- 1/7 Pagefile back to 10240 (keeps 6 GB for the game move) ---'
$reg = 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management'
Set-ItemProperty -Path $reg -Name PagingFiles -Value 'C:\pagefile.sys 10240 10240'
Write-Output ('PagingFiles now: ' + (Get-ItemProperty -Path $reg -Name PagingFiles).PagingFiles)

Write-Output ''
Write-Output '--- 2/7 Hibernation off ---'
powercfg /h off
if (Test-Path 'C:\hiberfil.sys') { Write-Output 'WARN: hiberfil.sys still present' } else { Write-Output 'hiberfil.sys removed' }

Write-Output ''
Write-Output '--- 3/7 Empty recycle bin ---'
Clear-RecycleBin -Force -ErrorAction Continue
Write-Output 'recycle bin cleared (any errors above are harmless)'

Write-Output ''
Write-Output '--- 4/7 Move Videos to D: ---'
robocopy 'C:\Users\HP\Videos' 'D:\Videos' /E /MOVE /XF desktop.ini /R:1 /W:1 /NFL /NDL /NP
Write-Output ('robocopy exit code: ' + $LASTEXITCODE)

Write-Output ''
Write-Output '--- 5/7 Copy game E: -> C: (this takes a few minutes) ---'
robocopy 'E:\Malik\game\playgta5' 'C:\Malik\game\playgta5' /E /MT:8 /R:1 /W:1 /NFL /NDL /NP
$rc = $LASTEXITCODE
Write-Output ('robocopy exit code: ' + $rc)

Write-Output ''
Write-Output '--- 6/7 Verify + delete old copy ---'
$src = Get-ChildItem 'E:\Malik\game\playgta5' -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum
$dst = Get-ChildItem 'C:\Malik\game\playgta5' -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum
Write-Output ('E: files=' + $src.Count + ' bytes=' + $src.Sum)
Write-Output ('C: files=' + $dst.Count + ' bytes=' + $dst.Sum)
if ($rc -lt 8 -and $src.Count -eq $dst.Count -and $src.Sum -eq $dst.Sum) {
  Remove-Item 'E:\Malik\game\playgta5' -Recurse -Force -ErrorAction Continue
  if (Test-Path 'E:\Malik\game\playgta5') { Write-Output 'ERROR: old folder still exists (some files locked)' } else { Write-Output 'old E: copy deleted OK' }
  'PlayGTA5 now lives at C:\Malik\game\playgta5 -- run Play-Optimized.cmd from there.' | Out-File 'E:\Malik\game\GAME-MOVED-README.txt' -Encoding ascii
  $sh = New-Object -ComObject WScript.Shell
  $lnk = $sh.CreateShortcut('C:\Users\HP\Desktop\Play GTA5.lnk')
  $lnk.TargetPath = 'C:\Malik\game\playgta5\Play-Optimized.cmd'
  $lnk.WorkingDirectory = 'C:\Malik\game\playgta5'
  $lnk.Save()
  Write-Output 'desktop shortcut created: Play GTA5.lnk'
} else {
  Write-Output 'MISMATCH or robocopy errors -> old copy NOT deleted, manual check needed'
}

Write-Output ''
Write-Output '--- 7/7 Defrag E: analysis (was optimized earlier today) ---'
defrag.exe E: /A

Write-Output ''
Write-Output '--- final volumes ---'
Get-Volume | Where-Object DriveLetter | Select-Object DriveLetter, @{n='FreeGB';e={[math]::Round($_.SizeRemaining/1GB,2)}} | Format-Table -AutoSize

Write-Output '=== batch complete ==='
Stop-Transcript | Out-Null
