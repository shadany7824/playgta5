$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
try { $host.UI.RawUI.WindowTitle = 'GTA5 Server (auto)' } catch {}

$lock = Join-Path $root 'server-watch.pid'
if (Test-Path $lock) {
  $old = Get-Content $lock -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($old -and (Get-Process -Id $old -ErrorAction SilentlyContinue)) { exit }
}
Set-Content -Path $lock -Value $PID

Add-Content -Path (Join-Path $root 'server-log.txt') -Value ((Get-Date).ToString('yyyy-MM-dd HH:mm:ss') + ' watcher started (PID ' + $PID + ')')

while ($true) {
  $ok = $false
  try {
    $c = New-Object Net.Sockets.TcpClient
    $c.Connect('127.0.0.1', 8000)
    $c.Close()
    $ok = $true
  } catch {}
  if (-not $ok) {
    Add-Content -Path (Join-Path $root 'server-log.txt') -Value ((Get-Date).ToString('yyyy-MM-dd HH:mm:ss') + ' server down - starting')
    Start-Process -FilePath (Join-Path $root 'runtime\python.exe') -ArgumentList (Join-Path $root 'serve_local.py') -WorkingDirectory $root -WindowStyle Minimized
    Start-Sleep -Seconds 25
  } else {
    Start-Sleep -Seconds 10
  }
}
