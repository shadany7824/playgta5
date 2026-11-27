$ErrorActionPreference = 'SilentlyContinue'
$wamrc  = 'E:\gta\wamr-compiler-msvc3\Release\wamrc.exe'
$wasm   = 'E:\Malik\game\game.wasm'
$aot    = 'E:\gta\gta-orig-test.aot'
$log    = 'E:\gta\_tmp_claude\wamrc-5gb.log'
$limit  = 5GB

function W($m) {
  $t = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
  Add-Content -Path $log -Value "[$t] $m"
}

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Job5G {
  [StructLayout(LayoutKind.Sequential)]
  public struct IO_COUNTERS {
    public ulong ReadOperationCount, WriteOperationCount, OtherOperationCount;
    public ulong ReadTransferCount, WriteTransferCount, OtherTransferCount;
  }
  [StructLayout(LayoutKind.Sequential)]
  public struct JOBOBJECT_BASIC_LIMIT_INFORMATION {
    public long PerProcessUserTimeLimit, PerJobUserTimeLimit;
    public uint LimitFlags;
    public UIntPtr MinimumWorkingSetSize, MaximumWorkingSetSize;
    public uint ActiveProcessLimit;
    public UIntPtr Affinity;
    public uint PriorityClass, SchedulingClass;
  }
  [StructLayout(LayoutKind.Sequential)]
  public struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION {
    public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
    public IO_COUNTERS IoInfo;
    public UIntPtr ProcessMemoryLimit, JobMemoryLimit, PeakProcessMemoryUsed, PeakJobMemoryUsed;
  }
  [DllImport("kernel32.dll", SetLastError=true)] public static extern IntPtr CreateJobObject(IntPtr a, string name);
  [DllImport("kernel32.dll", SetLastError=true)] public static extern bool SetInformationJobObject(IntPtr job, int info, IntPtr ptr, uint size);
  [DllImport("kernel32.dll", SetLastError=true)] public static extern bool AssignProcessToJobObject(IntPtr job, IntPtr proc);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
}
"@

W "=== compile start wasm=$wasm aot=$aot limit=5GB ==="
$job = [Job5G]::CreateJobObject([IntPtr]::Zero, $null)
if ($job -eq [IntPtr]::Zero) { W 'CreateJobObject FAILED'; exit 1 }
$info = New-Object Job5G+JOBOBJECT_EXTENDED_LIMIT_INFORMATION
$info.BasicLimitInformation.LimitFlags = 0x100 -bor 0x200
$info.ProcessMemoryLimit = [UIntPtr]::new($limit)
$info.JobMemoryLimit = [UIntPtr]::new($limit)
$sz = [System.Runtime.InteropServices.Marshal]::SizeOf([type]'Job5G+JOBOBJECT_EXTENDED_LIMIT_INFORMATION')
$ptr = [System.Runtime.InteropServices.Marshal]::AllocHGlobal($sz)
[System.Runtime.InteropServices.Marshal]::StructureToPtr($info, $ptr, $false)
$ok = [Job5G]::SetInformationJobObject($job, 9, $ptr, $sz)
[System.Runtime.InteropServices.Marshal]::FreeHGlobal($ptr)
if (-not $ok) { W 'SetInformationJobObject FAILED'; exit 1 }
W "job created ok (size=$sz)"

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $wamrc
$psi.Arguments = "--enable-multi-thread --opt-level=1 --size-level=1 -o `"$aot`" `"$wasm`""
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.CreateNoWindow = $true
$p = New-Object System.Diagnostics.Process
$p.StartInfo = $psi
if (-not $p.Start()) { W 'wamrc start FAILED'; exit 1 }
if (-not [Job5G]::AssignProcessToJobObject($job, $p.Handle)) { W 'AssignProcessToJobObject FAILED'; $p.Kill(); exit 1 }
W "wamrc started pid=$($p.Id) assigned to 5GB job"

$outTask = $p.StandardOutput.ReadToEndAsync()
$errTask = $p.StandardError.ReadToEndAsync()
$peak = 0
while (-not $p.HasExited) {
  $p.Refresh()
  $ws = $p.WorkingSet64
  if ($ws -gt $peak) { $peak = $ws }
  W ("ALIVE mem={0:N2}GB peak={1:N2}GB cpu={2:N1}s aot={3}B" -f ($ws/1GB), ($peak/1GB), $p.TotalProcessorTime.TotalSeconds, ((Get-Item $aot -ErrorAction SilentlyContinue).Length))
  Start-Sleep -Seconds 30
}
$p.WaitForExit()
$so = $outTask.Result
$se = $errTask.Result
W "EXIT rc=$($p.ExitCode) peak={0:N2}GB aot={1}B" -f ($peak/1GB), ((Get-Item $aot -ErrorAction SilentlyContinue).Length)
if ($so) { W ("stdout: " + $so.Substring(0, [Math]::Min(500, $so.Length))) }
if ($se) { W ("stderr: " + $se.Substring(0, [Math]::Min(1000, $se.Length))) }
[void][Job5G]::CloseHandle($job)
W '=== done ==='
