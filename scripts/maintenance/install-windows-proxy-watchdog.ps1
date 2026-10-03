param(
    [int]$Port = 18088,
    [string]$PreferredNetworkPrefix = "10.147.17.",
    [string]$ApiTestUrl = "https://api.planets.nu/time?version=1",
    [switch]$RunOnce,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$TaskName = "Planets Intel Proxy Bridge Watchdog"
$InstallRoot = Join-Path $env:ProgramData "PlanetsIntel"
$InstalledScript = Join-Path $InstallRoot "proxy-bridge-watchdog.ps1"
$LogRoot = Join-Path $InstallRoot "logs"
$LogPath = Join-Path $LogRoot "proxy-bridge-watchdog.log"

function Ensure-Dirs {
    New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null
}

function Rotate-Log {
    if (-not (Test-Path $LogPath)) { return }
    $file = Get-Item $LogPath
    if ($file.Length -lt 2MB) { return }
    $backup = $LogPath + ".1"
    Remove-Item $backup -Force -ErrorAction SilentlyContinue
    Move-Item $LogPath $backup -Force
}

function Log([string]$Message) {
    Ensure-Dirs
    Rotate-Log
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"), $Message
    Add-Content -Path $LogPath -Value $line -Encoding UTF8
    Write-Host $line
}

function Is-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Fail([string]$Diagnosis, [string]$Message, [int]$Code) {
    Log ("DIAGNOSIS={0} {1}" -f $Diagnosis, $Message)
    exit $Code
}

function Get-ZeroTierListenAddress {
    $adapters = Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object {
        ($_.Name -match "ZeroTier" -or $_.InterfaceDescription -match "ZeroTier") -and $_.Status -eq "Up"
    }
    $addresses = @()
    foreach ($adapter in $adapters) {
        $addresses += Get-NetIPAddress -AddressFamily IPv4 -InterfaceIndex $adapter.ifIndex -ErrorAction SilentlyContinue | Select-Object InterfaceAlias, IPAddress, PrefixLength
    }
    $preferred = @($addresses | Where-Object { $_.IPAddress.StartsWith($PreferredNetworkPrefix) })
    if ($preferred.Count -eq 1) { return $preferred[0].IPAddress }
    if ($preferred.Count -gt 1) { Fail "zerotier_address_ambiguous" ("More than one ZeroTier address matches {0}" -f $PreferredNetworkPrefix) 20 }
    if ($addresses.Count -eq 1) { return $addresses[0].IPAddress }
    Fail "zerotier_address_missing" ("No unique active ZeroTier IPv4 address found; expected prefix {0}" -f $PreferredNetworkPrefix) 21
}

function Invoke-WslProxyTest {
    $command = 'set +e; curl -sS --connect-timeout 6 --max-time 15 --proxy http://127.0.0.1:{0} \'{1}\' -o /dev/null; exit $?' -f $Port, $ApiTestUrl
    & wsl.exe -u root -e bash -lc $command *> $null
    return ($LASTEXITCODE -eq 0)
}

function Restart-WslTinyproxy {
    Log "tinyproxy local probe failed; restarting WSL tinyproxy"
    $command = "if command -v systemctl >/dev/null 2>&1; then systemctl restart tinyproxy; else service tinyproxy restart; fi"
    & wsl.exe -u root -e bash -lc $command *> $null
    if ($LASTEXITCODE -ne 0) { return $false }
    Start-Sleep -Seconds 2
    return (Invoke-WslProxyTest)
}

function Get-PortProxyRule([string]$ListenAddress) {
    $lines = netsh interface portproxy dump
    return $lines | Where-Object {
        $_ -match "add v4tov4" -and
        $_ -match ("listenport={0}\\b" -f $Port) -and
        $_ -match ("listenaddress={0}(\\s|$)" -f [regex]::Escape($ListenAddress))
    } | Select-Object -First 1
}

function Test-BridgeTcp([string]$ListenAddress) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Where-Object {
        $_.LocalAddress -eq $ListenAddress -or $_.LocalAddress -eq "0.0.0.0"
    } | Select-Object -First 1
    if (-not $listener) { return $false }
    $result = Test-NetConnection -ComputerName $ListenAddress -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue
    return [bool]$result
}

function Test-BridgeHttp([string]$ListenAddress) {
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if (-not $curl) { return $true }
    & $curl.Source -sS --connect-timeout 6 --max-time 15 --proxy ("http://{0}:{1}" -f $ListenAddress, $Port) $ApiTestUrl -o NUL
    return ($LASTEXITCODE -eq 0)
}

function Backup-BridgeState {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backup = Join-Path $InstallRoot ("backup-" + $stamp)
    New-Item -ItemType Directory -Path $backup -Force | Out-Null
    netsh interface portproxy dump | Out-File -Encoding utf8 (Join-Path $backup "portproxy.txt")
    Get-NetFirewallRule -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -like "Planets Intel*" } | Format-List * | Out-File -Encoding utf8 (Join-Path $backup "firewall.txt")
    Log ("bridge_state_backup={0}" -f $backup)
}

function Repair-Bridge([string]$ListenAddress) {
    Backup-BridgeState
    Log ("repairing Windows bridge listen={0}:{1}" -f $ListenAddress, $Port)
    netsh interface portproxy delete v4tov4 listenaddress=$ListenAddress listenport=$Port *> $null
    netsh interface portproxy add v4tov4 listenaddress=$ListenAddress listenport=$Port connectaddress=127.0.0.1 connectport=$Port *> $null
    if ($LASTEXITCODE -ne 0) { return $false }
    $firewallName = "Planets Intel ZeroTier Proxy $Port"
    Get-NetFirewallRule -DisplayName $firewallName -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
    New-NetFirewallRule -DisplayName $firewallName -Direction Inbound -Action Allow -Protocol TCP -LocalAddress $ListenAddress -LocalPort $Port -Profile Any | Out-Null
    $ipHelper = Get-Service -Name iphlpsvc -ErrorAction Stop
    if ($ipHelper.Status -eq "Running") { Restart-Service -Name iphlpsvc -Force } else { Start-Service -Name iphlpsvc }
    Start-Sleep -Seconds 2
    return (Test-BridgeTcp $ListenAddress)
}

function Run-WatchdogOnce {
    if (-not (Is-Admin)) { Fail "watchdog_requires_admin" "The watchdog must run elevated." 2 }
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { Fail "wsl_unavailable" "wsl.exe is unavailable." 3 }
    $listenAddress = Get-ZeroTierListenAddress
    Log ("check listen_address={0} port={1}" -f $listenAddress, $Port)
    if (-not (Invoke-WslProxyTest)) {
        if (-not (Restart-WslTinyproxy)) { Fail "wsl_proxy_repair_failed" "Tinyproxy is still unusable after restart." 4 }
        Log "tinyproxy_repaired=true"
    }
    $rule = Get-PortProxyRule $listenAddress
    $tcpOk = Test-BridgeTcp $listenAddress
    $httpOk = $false
    if ($tcpOk) { $httpOk = Test-BridgeHttp $listenAddress }
    if ($rule -and $tcpOk -and $httpOk) { Log "DIAGNOSIS=windows_proxy_bridge_healthy"; exit 0 }
    Log ("bridge unhealthy rule={0} tcp={1} http={2}; attempting repair" -f [bool]$rule, $tcpOk, $httpOk)
    if (-not (Repair-Bridge $listenAddress)) { Fail "windows_bridge_repair_failed" "Portproxy listener did not recover." 5 }
    if (-not (Test-BridgeHttp $listenAddress)) { Fail "windows_bridge_http_still_failed" "TCP bridge recovered but HTTP proxy traversal still fails." 6 }
    Log "DIAGNOSIS=windows_proxy_bridge_repaired"
    exit 0
}

function Install-Watchdog {
    if (-not (Is-Admin)) { Fail "install_requires_admin" "Run installer from elevated PowerShell." 10 }
    Ensure-Dirs
    if (-not $PSCommandPath) { Fail "installer_path_unknown" "Cannot determine script source path." 11 }
    Copy-Item -LiteralPath $PSCommandPath -Destination $InstalledScript -Force
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $actionArgs = ('-NoProfile -ExecutionPolicy Bypass -File "{0}" -RunOnce -Port {1} -PreferredNetworkPrefix "{2}" -ApiTestUrl "{3}"' -f $InstalledScript, $Port, $PreferredNetworkPrefix, $ApiTestUrl)
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $actionArgs
    $logon = New-ScheduledTaskTrigger -AtLogOn -User $identity
    $repeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 2) -RepetitionDuration (New-TimeSpan -Days 3650)
    $principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($logon, $repeat) -Principal $principal -Settings $settings -Force | Out-Null
    Log ("watchdog_installed task={0} user={1}" -f $TaskName, $identity)
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $InstalledScript -RunOnce -Port $Port -PreferredNetworkPrefix $PreferredNetworkPrefix -ApiTestUrl $ApiTestUrl
    $initialRc = $LASTEXITCODE
    if ($initialRc -ne 0) { Fail "watchdog_installed_initial_repair_failed" ("Task installed, but initial health/repair run failed rc={0}. See {1}" -f $initialRc, $LogPath) 12 }
    Log ("DIAGNOSIS=windows_proxy_watchdog_installed log={0}" -f $LogPath)
    exit 0
}

function Uninstall-Watchdog {
    if (-not (Is-Admin)) { Fail "uninstall_requires_admin" "Run uninstall from elevated PowerShell." 30 }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Remove-Item $InstalledScript -Force -ErrorAction SilentlyContinue
    Log "DIAGNOSIS=windows_proxy_watchdog_uninstalled"
    exit 0
}

if ($Uninstall) { Uninstall-Watchdog }
if ($RunOnce) { Run-WatchdogOnce }
Install-Watchdog
