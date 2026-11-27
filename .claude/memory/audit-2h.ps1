param([int]$DurationSec = 7200, [int]$IntervalSec = 10)

$root = 'E:\gta\playgta5\.claude\memory'
$csv  = Join-Path $root 'audit-2026-11-20.csv'
$sum  = Join-Path $root 'audit-2026-11-20-summary.md'
$start = Get-Date
$end = $start.AddSeconds($DurationSec)
$prev = @{}
$rows = @()

function Get-Gpu {
    $out = @{}
    try {
        $samples = Get-Counter '\GPU Engine(*)\Utilization Percentage' -ErrorAction Stop
        foreach ($s in $samples.CounterSamples) {
            if ($s.CookedValue -le 0.3) { continue }
            $name = $s.InstanceName
            $eng = 'other'
            if ($name -match 'engtype_(3d|video_decode|video_encode|copy|compute)') { $eng = $matches[1] }
            $procId = 0
            $procName = 'unknown'
            if ($name -match 'pid_(\d+)') {
                $procId = [int]$matches[1]
                $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
                if ($p) { $procName = $p.ProcessName }
            }
            $key = "$eng|$procName|$procId"
            if (-not $out.ContainsKey($key)) { $out[$key] = 0.0 }
            $out[$key] += $s.CookedValue
        }
    } catch {}
    return $out
}

"# 2-hour live audit - started $($start.ToString('yyyy-MM-dd HH:mm:ss'))" | Set-Content -Path $sum
"Source: detached PowerShell sampler, every $IntervalSec s for $DurationSec s." | Add-Content -Path $sum
"Machine: i3-7100U / HD 620 / 20 GB RAM. Game: E:\gta\playgta5 on localhost:8000." | Add-Content -Path $sum
"" | Add-Content -Path $sum
"time,gpu3d_pct,gpu_top_proc,gpu_top_pct,gpu_copy_pct,ram_used_pct,ram_free_gb,chrome_procs,edge_procs,chrome_private_gb,opencode_ws_mb,server_pid,log_mb,top_cpu_1,top_cpu_1_pct,top_cpu_2,top_cpu_2_pct" | Set-Content -Path $csv

while ((Get-Date) -lt $end) {
    $now = Get-Date
    $gpu = Get-Gpu
    $gpu3d = 0.0; $gpuTopName = '-'; $gpuTopPct = 0.0; $gpuCopy = 0.0
    foreach ($k in $gpu.Keys) {
        $v = $gpu[$k]
        if ($k -like '3d|*') { $gpu3d += $v; if ($v -gt $gpuTopPct) { $gpuTopPct = $v; $gpuTopName = ($k -split '\|')[1] } }
        if ($k -like 'copy|*') { $gpuCopy += $v }
    }
    $os = Get-CimInstance Win32_OperatingSystem
    $ramUsed = [math]::Round(100 * (1 - $os.FreePhysicalMemory / $os.TotalVisibleMemorySize), 1)
    $ramFree = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
    $procs = Get-Process
    $chrome = @($procs | Where-Object { $_.ProcessName -eq 'chrome' })
    $edge = @($procs | Where-Object { $_.ProcessName -eq 'msedge' })
    $chromePriv = [math]::Round((($chrome | Measure-Object PrivateMemorySize64 -Sum).Sum) / 1GB, 2)
    $opencode = ($procs | Where-Object { $_.ProcessName -eq 'opencode' } | Select-Object -First 1)
    $opWs = if ($opencode) { [math]::Round($opencode.WS / 1MB, 0) } else { 0 }
    $srv = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    $srvPid = if ($srv) { $srv.OwningProcess } else { 0 }
    $logPath = 'E:\gta\playgta5\game-log.txt'
    $logMb = if (Test-Path $logPath) { [math]::Round((Get-Item $logPath).Length / 1MB, 1) } else { 0 }
    $cur = @{}
    foreach ($p in $procs) { $cur[$p.Id] = $p.CPU }
    $top = @()
    foreach ($id in $cur.Keys) {
        if ($prev.ContainsKey($id)) {
            $d = $cur[$id] - $prev[$id]
            if ($d -gt 0) {
                $p = $procs | Where-Object { $_.Id -eq $id } | Select-Object -First 1
                if ($p) { $top += [PSCustomObject]@{ Name = $p.ProcessName; Delta = [math]::Round($d, 2) } }
            }
        }
    }
    $top = $top | Sort-Object Delta -Descending | Select-Object -First 2
    $t1 = if ($top.Count -gt 0) { $top[0].Name } else { '-' }; $t1p = if ($top.Count -gt 0) { $top[0].Delta } else { 0 }
    $t2 = if ($top.Count -gt 1) { $top[1].Name } else { '-' }; $t2p = if ($top.Count -gt 1) { $top[1].Delta } else { 0 }
    $prev = $cur
    "$($now.ToString('HH:mm:ss')),$([math]::Round($gpu3d,1)),$gpuTopName,$([math]::Round($gpuTopPct,1)),$([math]::Round($gpuCopy,1)),$ramUsed,$ramFree,$($chrome.Count),$($edge.Count),$chromePriv,$opWs,$srvPid,$logMb,$t1,$t1p,$t2,$t2p" | Add-Content -Path $csv
    $rows += [PSCustomObject]@{ T = $now; Gpu3d = $gpu3d; Ram = $ramUsed; Chrome = $chrome.Count }
    if (($rows.Count % 60) -eq 0) {
        $last = $rows | Select-Object -Last 60
        "" | Add-Content -Path $sum
        "## $(($now).ToString('HH:mm')) - last 10 min" | Add-Content -Path $sum
        "GPU 3D avg $([math]::Round(($last | Measure-Object Gpu3d -Average).Average,1))% / max $([math]::Round(($last | Measure-Object Gpu3d -Maximum).Maximum,1))%; RAM avg $([math]::Round(($last | Measure-Object Ram -Average).Average,1))%; chrome procs avg $([math]::Round(($last | Measure-Object Chrome -Average).Average,1))" | Add-Content -Path $sum
    }
    Start-Sleep -Seconds $IntervalSec
}
"" | Add-Content -Path $sum
"## FINAL" | Add-Content -Path $sum
"Audit ended $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss')). Samples: $($rows.Count). Full data: $csv" | Add-Content -Path $sum
