param(
    [int]$Port = 18088,
    [string]$TaskName = "Planets Intel Proxy Bridge Watchdog"
)

$ErrorActionPreference = "Continue"

function Section([string]$Title) {
    Write-Host ""
    Write-Host "===== $Title ====="
}

Section "IDENTITY"
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
Write-Host ("user={0}" -f $identity.Name)
Write-Host ("is_admin={0}" -f $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))

Section "WATCHDOG TASK"
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $task) {
    Write-Host "watchdog_task=missing"
} else {
    $info = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue
    Write-Host ("state={0}" -f $task.State)
    if ($info) {
        Write-Host ("last_run_time={0}" -f $info.LastRunTime)
        Write-Host ("last_task_result={0}" -f $info.LastTaskResult)
        Write-Host ("next_run_time={0}" -f $info.NextRunTime)
    }
    Write-Host ("principal_user={0}" -f $task.Principal.UserId)
    Write-Host ("principal_logon_type={0}" -f $task.Principal.LogonType)
    Write-Host ("principal_run_level={0}" -f $task.Principal.RunLevel)
    foreach ($action in $task.Actions) {
        Write-Host ("action_execute={0}" -f $action.Execute)
        Write-Host ("action_arguments={0}" -f $action.Arguments)
        Write-Host ("action_working_directory={0}" -f $action.WorkingDirectory)
    }
    foreach ($trigger in $task.Triggers) {
        Write-Host ("trigger={0}" -f ($trigger | Out-String).Trim())
    }
}

Section "RELEVANT SERVICES"
$servicePatterns = "ZeroTier|IP Helper|Lxss|WSL|Host Network|Hyper-V Host Compute|vmcompute|hns"
Get-CimInstance Win32_Service |
    Where-Object {
        $_.Name -match $servicePatterns -or $_.DisplayName -match $servicePatterns
    } |
    Sort-Object Name |
    Select-Object Name, DisplayName, State, StartMode, StartName, ProcessId |
    Format-Table -AutoSize

Section "RELEVANT PROCESSES"
Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -match "^(powershell|pwsh|wscript|cscript|wsl|wslhost|conhost|vmcompute|zerotier-one).*"
    } |
    Sort-Object Name, ProcessId |
    Select-Object Name, ProcessId, ParentProcessId, CommandLine |
    Format-Table -Wrap -AutoSize

Section "PORTPROXY"
netsh interface portproxy show v4tov4

Section "PORT LISTENERS"
$listeners = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
if ($listeners) {
    $listeners | Select-Object LocalAddress, LocalPort, OwningProcess | Format-Table -AutoSize
} else {
    Write-Host ("listener_port_{0}=missing" -f $Port)
}

Section "INSTALLED WATCHDOG FILES"
$root = Join-Path $env:ProgramData "PlanetsIntel"
foreach ($name in @("proxy-bridge-watchdog.ps1", "proxy-bridge-watchdog.vbs")) {
    $path = Join-Path $root $name
    if (Test-Path $path) {
        $item = Get-Item $path
        Write-Host ("file={0} length={1} modified={2}" -f $item.FullName, $item.Length, $item.LastWriteTime)
    } else {
        Write-Host ("file_missing={0}" -f $path)
    }
}

Section "WATCHDOG LOG TAIL"
$log = Join-Path $root "logs\proxy-bridge-watchdog.log"
if (Test-Path $log) {
    Get-Content $log -Tail 40
} else {
    Write-Host "watchdog_log=missing"
}

Section "RESULT"
if (-not $task) {
    Write-Host "DIAGNOSIS=watchdog_task_missing"
} elseif ($task.Actions.Execute -match "powershell.exe") {
    Write-Host "DIAGNOSIS=watchdog_task_still_direct_powershell"
} elseif ($task.Actions.Execute -match "wscript.exe") {
    Write-Host "DIAGNOSIS=watchdog_task_uses_hidden_launcher"
} else {
    Write-Host "DIAGNOSIS=watchdog_task_action_unexpected"
}
