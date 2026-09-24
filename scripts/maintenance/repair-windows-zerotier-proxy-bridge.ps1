param(
    [int]$Port = 18088,
    [string]$ListenAddress = "",
    [string]$ApiTestUrl = "https://api.planets.nu/time?version=1"
)

$ErrorActionPreference = "Stop"

function Section([string]$Title) {
    Write-Host ""
    Write-Host "===== $Title ====="
}

function Fail([string]$Diagnosis, [string]$Message, [int]$Code) {
    Section "RESULT"
    Write-Host ("DIAGNOSIS={0}" -f $Diagnosis)
    Write-Host $Message
    exit $Code
}

function Test-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
}

if (-not (Test-Admin)) {
    Fail "repair_requires_admin" "Run this script from an elevated Windows PowerShell." 2
}

Section "DISCOVER ZEROTIER ADDRESS"
$ztAdapters = Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match "ZeroTier" -or $_.InterfaceDescription -match "ZeroTier"
}

$ztAddresses = @()
foreach ($adapter in $ztAdapters) {
    $ztAddresses += Get-NetIPAddress `
        -AddressFamily IPv4 `
        -InterfaceIndex $adapter.ifIndex `
        -ErrorAction SilentlyContinue |
        Select-Object InterfaceAlias, IPAddress, PrefixLength
}

$ztAddresses | Format-Table InterfaceAlias, IPAddress, PrefixLength

if (-not $ListenAddress) {
    $preferred = $ztAddresses |
        Where-Object { $_.IPAddress -like "10.147.17.*" } |
        Select-Object -First 1

    if ($preferred) {
        $ListenAddress = $preferred.IPAddress
    } elseif ($ztAddresses.Count -eq 1) {
        $ListenAddress = $ztAddresses[0].IPAddress
    } else {
        Fail `
            "zerotier_listen_address_ambiguous" `
            "Could not choose the Planets Intel ZeroTier address automatically. Re-run with -ListenAddress <ip>." `
            3
    }
}

$listenRecord = $ztAddresses |
    Where-Object { $_.IPAddress -eq $ListenAddress } |
    Select-Object -First 1

if (-not $listenRecord) {
    Fail `
        "zerotier_listen_address_missing" `
        ("Requested listen address {0} is not assigned to a ZeroTier adapter." -f $ListenAddress) `
        4
}

Write-Host ("selected_listen_address={0}" -f $ListenAddress)
Write-Host ("selected_prefix_length={0}" -f $listenRecord.PrefixLength)

Section "VERIFY WSL TINYPROXY BEFORE MUTATION"
if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    Fail "wsl_unavailable" "wsl.exe is unavailable." 5
}

$wslCommand = 'set +e; curl -sS --connect-timeout 8 --max-time 20 --proxy http://127.0.0.1:{0} ''{1}'' -o /tmp/planets-intel-repair-preflight.out; rc=$?; echo WSL_PROXY_RC=$rc; if [ -s /tmp/planets-intel-repair-preflight.out ]; then cat /tmp/planets-intel-repair-preflight.out; echo; fi; exit $rc' -f $Port, $ApiTestUrl
& wsl.exe -e bash -lc $wslCommand
$wslProxyRc = $LASTEXITCODE

if ($wslProxyRc -ne 0) {
    Fail `
        "wsl_proxy_local_failed" `
        "Tinyproxy is not usable through 127.0.0.1 inside WSL; refusing to change Windows portproxy." `
        6
}

Section "BACKUP CURRENT WINDOWS STATE"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = Join-Path $env:TEMP ("planets-intel-proxy-repair-" + $stamp)
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

$portproxyBackup = Join-Path $backupDir "portproxy.txt"
$firewallBackup = Join-Path $backupDir "firewall.txt"

netsh interface portproxy dump | Out-File -Encoding utf8 $portproxyBackup
Get-NetFirewallRule -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName -like "Planets Intel*" } |
    Format-List * |
    Out-File -Encoding utf8 $firewallBackup

Write-Host ("backup_dir={0}" -f $backupDir)

Section "RECREATE PORTPROXY RULE"
$deleteOutput = netsh interface portproxy delete v4tov4 `
    listenaddress=$ListenAddress `
    listenport=$Port 2>&1
$deleteOutput

$addOutput = netsh interface portproxy add v4tov4 `
    listenaddress=$ListenAddress `
    listenport=$Port `
    connectaddress=127.0.0.1 `
    connectport=$Port 2>&1
$addOutput

if ($LASTEXITCODE -ne 0) {
    Fail `
        "portproxy_add_failed" `
        ("Failed to add v4tov4 rule. Backup: {0}" -f $backupDir) `
        7
}

Section "ENSURE FIREWALL RULE"
$firewallName = "Planets Intel ZeroTier Proxy $Port"
Get-NetFirewallRule -DisplayName $firewallName -ErrorAction SilentlyContinue |
    Remove-NetFirewallRule -ErrorAction SilentlyContinue

New-NetFirewallRule `
    -DisplayName $firewallName `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalAddress $ListenAddress `
    -LocalPort $Port `
    -Profile Any |
    Out-Null

Get-NetFirewallRule -DisplayName $firewallName |
    Format-Table DisplayName, Enabled, Direction, Action, Profile

Section "RESTART IP HELPER"
$ipHelper = Get-Service -Name iphlpsvc -ErrorAction Stop
if ($ipHelper.Status -eq "Running") {
    Restart-Service -Name iphlpsvc -Force
} else {
    Start-Service -Name iphlpsvc
}
Start-Sleep -Seconds 2
Get-Service -Name iphlpsvc | Format-Table Name, Status, StartType

Section "VERIFY PORTPROXY"
netsh interface portproxy show v4tov4

Write-Host ""
Write-Host "--- listeners on bridge port ---"
$listeners = Get-NetTCPConnection `
    -State Listen `
    -LocalPort $Port `
    -ErrorAction SilentlyContinue
$listeners | Format-Table LocalAddress, LocalPort, OwningProcess

$targetListener = $listeners |
    Where-Object {
        $_.LocalAddress -eq $ListenAddress -or $_.LocalAddress -eq "0.0.0.0"
    } |
    Select-Object -First 1

if (-not $targetListener) {
    Fail `
        "portproxy_listener_not_created" `
        ("The explicit rule exists but Windows still has no listener on {0}:{1}. Backup: {2}" -f $ListenAddress, $Port, $backupDir) `
        8
}

Section "VERIFY LOCAL ZEROTIER ENDPOI^T"
$tcp = Test-NetConnection `
    -ComputerName $ListenAddress `
    -Port $Port `
    -InformationLevel Detailed `
    -WarningAction SilentlyContinue
$tcp
if (-not $tcp.TcpTestSucceeded) {
    Fail `
        "zerotier_port_still_unreachable" `
        ("Windows now has a listener, but Test-NetConnection to {0}:{1} still fails. Backup: {2}" -f $ListenAddress, $Port, $backupDir) `
        9
}

Section "VERIFY HTTP PROXY THROUGH ZEROTIER ADDRESS"
$curlCommand = Get-Command curl.exe -ErrorAction SilentlyContinue
if (-not $curlCommand) {
    Write-Host "curl.exe unavailable; TCP verification passed."
    Section "RESULT"
    Write-Host "DIAGNOSIS=windows_zerotier_bridge_repaired_tcp_only"
    Write-Host ("listen_address={0}" -f $ListenAddress)
    Write-Host ("port={0}" -f $Port)
    Write-Host ("backup_dir={0}" -f $backupDir)
    exit 0
}

$bodyFile = Join-Path $backupDir "proxy-test-body.txt"
& $curlCommand.Source `
    -sS `
    --connect-timeout 8 `
    --max-time 20 `
    --proxy ("http://{0}:{1}" -f $ListenAddress, $Port) `
    $ApiTestUrl `
    -o $bodyFile
$curlRc = $LASTEXITCODE
Write-Host ("windows_proxy_curl_rc={0}" -f $curlRc)
if (Test-Path $bodyFile) {
    Get-Content $bodyFile
}

if ($curlRc -ne 0) {
    Fail `
        "windows_zerotier_bridge_tcp_ok_proxy_failed" `
        ("TCP listener works, but HTTP proxy traversal failed. Backup: {0}" -f $backupDir) `
        10
}

Section "RESULT"
Write-Host "DIAGNOSIS=windows_zerotier_bridge_repaired"
Write-Host ("listen_address={0}" -f $ListenAddress)
Write-Host ("port={0}" -f $Port)
Write-Host ("connect_address=127.0.0.1")
Write-Host ("backup_dir={0}" -f $backupDir)
Write-Host "Run the production-side diagnose-private-refresh-bridge.sh next."
exit 0
