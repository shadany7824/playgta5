# DeepWatch: while the game runs, samples game-log growth + chrome CPU/RAM every 5 s
# (plus free RAM / battery / game-process check every 30 s) into watch-trace.txt.
# Purpose: capture the exact system state during cutscene hangs.
$ErrorActionPreference = 'SilentlyContinue'
$root  = 'C:\Malik\game\playgta5'
$log   = Join-Path $root 'game-log.txt'
$out   = Join-Path $root 'watch-trace.txt'
$cores = [Environment]::ProcessorCount
$prevCpu = -1.0; $prevT = Get-Date; $prevSize = -1; $idle = 0; $line = 0
"=== DeepWatch start $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') cores=$cores ===" | Add-Content $out
while ($line -lt 4320) {
    Start-Sleep -Seconds 5
    $line++
    $t = Get-Date; $dt = ($t - $prevT).TotalSeconds
    $size = -1; $last = ''; $deltaKB = 0
    if (Test-Path $log) {
        $size = (Get-Item $log).Length
        if ($prevSize -ge 0) { $deltaKB = [math]::Round(($size - $prevSize) / 1KB, 1) }
        try {
            $fs = [System.IO.File]::Open($log, 'Open', 'Read', 'ReadWrite')
            $len = [Math]::Min(4096, $fs.Length)
            if ($len -gt 0) {
                [void]$fs.Seek(-$len, 'End')
                $buf = New-Object byte[] $len
                [void]$fs.Read($buf, 0, $len)
                $txt = [System.Text.Encoding]::UTF8.GetString($buf)
                $rows = $txt -split "`n" | Where-Object { $_.Trim().Length -gt 0 }
                if ($rows.Count -gt 0) { $last = $rows[$rows.Count - 1] }
            }
            $fs.Close()
        } catch {}
    }
    $prevSize = $size
    $cpu = 0.0; $ws = 0; $n = 0
    foreach ($p in (Get-Process chrome)) { $cpu += $p.TotalProcessorTime.TotalSeconds; $ws += $p.WorkingSet64; $n++ }
    $cpuPct = ''
    if ($prevCpu -ge 0 -and $dt -gt 0) { $cpuPct = [math]::Round((($cpu - $prevCpu) / ($dt * $cores)) * 100, 0) }
    $prevCpu = $cpu
    $freeMB = ''; $bat = ''; $gm = ''
    if ($line % 6 -eq 0) {
        $freeMB = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1KB, 0)
        $bat = (Get-CimInstance Win32_Battery).EstimatedChargeRemaining
        $gm = @(Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" | Where-Object { $_.CommandLine -match 'localhost:8000' }).Count
    }
    if ($last.Length -gt 110) { $last = $last.Substring(0, 110) }
    ('{0} logKB={1} d={2}KB chrome={3}p cpu={4}% ws={5}MB free={6}MB bat={7}% gm={8}' -f $t.ToString('HH:mm:ss'), [math]::Round($size / 1KB, 0), $deltaKB, $n, $cpuPct, [math]::Round($ws / 1MB, 0), $freeMB, $bat, $gm) | Add-Content $out
    if ($last) { ('    last: ' + $last) | Add-Content $out }
    if ($line % 6 -eq 0) { if ($gm -eq 0) { $idle++ } else { $idle = 0 } }
    if ($idle -ge 20) { "=== DeepWatch exit (no game for ~10 min) $(Get-Date -Format 'HH:mm:ss') ===" | Add-Content $out; break }
}
