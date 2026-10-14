param(
    [int]$Port = 18088
)

$ErrorActionPreference = "Continue"

function Section([string]$Title) {
    Write-Host ""
    Write-Host "===== $Title ====="
}

Section "ZEROTIER ADAPTERS"
$ztAdapters = Get-NetAdapter -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -match "ZeroTier" -or
        $_.InterfaceDescription -match "ZeroTier"
    }

if (-not $ztAdapters) {
    Write-Host "No ZeroTier adapter found."
} else {
    $ztAdapters | Format-Table ifIndex, Name, Status, MacAddress, InterfaceDescription
    foreach ($adapter in $ztAdapters) {
        Get-NetIPAddress -AddressFamily IPv4 -InterfaceIndex $adapter.ifIndex -ErrorAction SilentlyContinue |
            Format-Table InterfaceAlias, IPAddress, PrefixLength
    }
}

Section "PORTPROXY"
netsh interface portproxy show v4tov4

Section "LOCAL LISTENER"
$listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
if ($listener) {
    $listener | Format-Table LocalAddress, LocalPort, OwningProcess
} else {
    Write-Host "No TCP listener detected on port $Port."
}

Section "PORT TEST"
$zeroTierIps = @()
if ($ztAdapters) {
    foreach ($adapter in $ztAdapters) {
        $zeroTierIps += Get-NetIPAddress -AddressFamily IPv4 -InterfaceIndex $adapter.ifIndex -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty IPAddress
    }
}

if (-not $zeroTierIps) {
    Write-Host "No ZeroTier IPv4 address available for Test-NetConnection."
} else {
    foreach ($ip in $zeroTierIps) {
        Write-Host ("Testing {0}:{1}" -f $ip, $Port)
        Test-NetConnection -ComputerName $ip -Port $Port -InformationLevel Detailed
    }
}

Section "RESULT"
if ($listener) {
    Write-Host "DIAGNOSIS=windows_port_listener_present"
    Write-Host "Compare the portproxy connectaddress with the current WSL IPv4 printed by diagnose-wsl-proxy-bridge.sh."
} else {
    Write-Host "DIAGNOSIS=windows_port_listener_missing"
    Write-Host "The production proxy endpoint will refuse connections until the Windows bridge/listener is restored."
}
