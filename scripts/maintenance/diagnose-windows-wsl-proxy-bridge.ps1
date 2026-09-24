param(
    [int]$Port = 18088,
    [string]$ApiTestUrl = "https://api.planets.nu/time?version=1"
)

$ErrorActionPreference = "Continue"

function Section([string]$Title) {
    Write-Host ""
    Write-Host "===== $Title ====="
}

function Get-WslValue([string]$Command) {
    $output = & wsl.exe -e bash -lc $Command 2>$null
    if ($LASTEXITCODE -ne 0) {
        return $null
    }
    return ($output | Select-Object -First 1)
}

Section "WINDOWS / ZEROTIER"
$ztAdapters = Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match "ZeroTier" -or $_.InterfaceDescription -match "ZeroTier"
}

$zeroTierIps = @()
if (-not $ztAdapters) {
    Write-Host "No ZeroTier adapter found."
} else {
    $ztAdapters | Format-Table ifIndex, Name, Status, MacAddress, InterfaceDescription
    foreach ($adapter in $ztAdapters) {
        $ips = Get-NetIPAddress -AddressFamily IPv4 -InterfaceIndex $adapter.ifIndex -ErrorAction SilentlyContinue
        $ips | Format-Table InterfaceAlias, IPAddress, PrefixLength
        $zeroTierIps += $ips | Select-Object -ExpandProperty IPAddress
    }
}

Section "WINDOWS IP HELPER / PORTPROXY"
$ipHelper = Get-Service -Name iphlpsvc -ErrorAction SilentlyContinue
if ($ipHelper) {
    $ipHelper | Format-Table Name, Status, StartType
} else {
    Write-Host "IP Helper service not found."
}

Write-Host ""
Write-Host "--- netsh portproxy v4tov4 ---"
netsh interface portproxy show v4tov4

Write-Host ""
Write-Host "--- netsh portproxy dump ---"
$portProxyDump = netsh interface portproxy dump
$portProxyDump

$portProxyRule = $portProxyDump | Where-Object { $_ -match "listenport=$Port\b" } | Select-Object -First 1

$connectAddress = $null
$connectPort = $null
$listenAddress = $null

if ($portProxyRule) {
    if ($portProxyRule -match "connectaddress=([^\s]+)") {
        $connectAddress = $Matches[1].Trim('"')
    }
    if ($portProxyRule -match "connectport=([^\s]+)") {
        $connectPort = $Matches[1].Trim('"')
    }
    if ($portProxyRule -match "listenaddress=([^\s]+)") {
        $listenAddress = $Matches[1].Trim('"')
    }
}

Section "WINDOWS LISTENER"
$listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
if ($listener) {
    $listener | Format-Table LocalAddress, LocalPort, OwningProcess
} else {
    Write-Host "No TCP listener detected on port $Port."
}

Section "WSL"
if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    Write-Host "wsl.exe is unavailable."
    Section "RESULT"
    Write-Host "DIAGNOSIS=wsl_unavailable"
    exit 2
}

& wsl.exe --status
Write-Host ""

$wslIpv4 = Get-WslValue "hostname -I | tr ' ' '\n' | grep -E '^[0-9]+(\\.[0-9]+){3}$' | grep -v '^127\\.' | head -1"
if ($wslIpv4) {
    Write-Host ("current_wsl_ipv4={0}" -f $wslIpv4)
} else {
    Write-Host "current_wsl_ipv4=<unknown>"
}

Write-Host ""
Write-Host "--- tinyproxy service ---"
& wsl.exe -e bash -lc "if command -v systemctl >/dev/null 2>&1; then systemctl status tinyproxy --no-pager -l || true; elif command -v service >/dev/null 2>&1; then service tinyproxy status || true; else echo 'No systemctl/service command available.'; fi"

Write-Host ""
Write-Host "--- WSL listener ---"
& wsl.exe -e bash -lc "if command -v ss >/dev/null 2>&1; then ss -lntp | grep -E '[:.]$Port[[:space:]]' || true; else echo 'ss unavailable'; fi"

Write-Host ""
Write-Host "--- WSL local proxy test ---"
$wslProxyCommand = 'set +e; curl -sS -v --connect-timeout 8 --max-time 20 --proxy http://127.0.0.1:{0} ''{1}'' -o /tmp/planets-intel-wsl-proxy-test.out; rc=$?; echo WSL_LOCAL_PROXY_RC=$rc; if [ -s /tmp/planets-intel-wsl-proxy-test.out ]; then cat /tmp/planets-intel-wsl-proxy-test.out; echo; fi; exit $rc' -f $Port, $ApiTestUrl
& wsl.exe -e bash -lc $wslProxyCommand
$wslProxyRc = $LASTEXITCODE

Section "WINDOWS ZEROTIER PORT TEST"
$zeroTierPortOk = $false
if (-not $zeroTierIps) {
    Write-Host "No ZeroTier IPv4 address available for Test-NetConnection."
} else {
    foreach ($ip in $zeroTierIps) {
        Write-Host ("Testing {0}:{1}" -f $ip, $Port)
        $result = Test-NetConnection -ComputerName $ip -Port $Port -InformationLevel Detailed -WarningAction SilentlyContinue
        $result
        if ($result.TcpTestSucceeded) {
            $zeroTierPortOk = $true
        }
    }
}

Section "COMPARISON"
Write-Host ("portproxy_rule_present={0}" -f [bool]$portProxyRule)
if ($listenAddress) {
    Write-Host ("portproxy_listenaddress={0}" -f $listenAddress)
} else {
    Write-Host "portproxy_listenaddress=<unknown>"
}
if ($connectAddress) {
    Write-Host ("portproxy_connectaddress={0}" -f $connectAddress)
} else {
    Write-Host "portproxy_connectaddress=<unknown>"
}
if ($connectPort) {
    Write-Host ("portproxy_connectport={0}" -f $connectPort)
} else {
    Write-Host "portproxy_connectport=<unknown>"
}
if ($wslIpv4) {
    Write-Host ("current_wsl_ipv4={0}" -f $wslIpv4)
} else {
    Write-Host "current_wsl_ipv4=<unknown>"
}
Write-Host ("windows_listener_present={0}" -f [bool]$listener)
Write-Host ("zerotier_port_reachable_locally={0}" -f $zeroTierPortOk)
Write-Host ("wsl_local_proxy_rc={0}" -f $wslProxyRc)

Section "RESULT"

if ($wslProxyRc -ne 0) {
    Write-Host "DIAGNOSIS=wsl_proxy_local_failed"
    Write-Host "Tinyproxy or its local listener/path is not working inside WSL."
    exit 3
}

if (-not $portProxyRule) {
    Write-Host "DIAGNOSIS=windows_portproxy_rule_missing"
    Write-Host "WSL proxy works locally, but Windows has no portproxy rule for the configured bridge port."
    exit 4
}

if ($wslIpv4 -and $connectAddress -and ($connectAddress -ne $wslIpv4)) {
    Write-Host "DIAGNOSIS=windows_portproxy_stale_wsl_ip"
    Write-Host ("portproxy points to {0}, current WSL IPv4 is {1}" -f $connectAddress, $wslIpv4)
    exit 5
}

if (-not $listener) {
    Write-Host "DIAGNOSIS=windows_port_listener_missing"
    Write-Host "The portproxy rule exists and WSL proxy works locally, but Windows is not listening on the bridge port."
    exit 6
}

if (-not $zeroTierPortOk) {
    Write-Host "DIAGNOSIS=windows_zerotier_port_unreachable"
    Write-Host "Windows has a listener and WSL proxy works, but the bridge port is not reachable through the local ZeroTier address."
    exit 7
}

Write-Host "DIAGNOSIS=windows_wsl_bridge_looks_healthy"
Write-Host "The local Windows/WSL bridge path is reachable. If production still fails, inspect firewall/ZeroTier routing between hosts."
exit 0
