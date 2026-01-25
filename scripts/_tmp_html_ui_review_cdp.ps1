param(
  [string]$Html,
  [string]$OutDir,
  [int]$Port = 9222,
  [string]$LogFile = ""
)

if (-not (Test-Path $Html)) { throw "HTML not found: $Html" }
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }

$runStamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runDir = Join-Path $OutDir ("run_" + $runStamp)
if (-not (Test-Path $runDir)) { New-Item -ItemType Directory -Path $runDir | Out-Null }

$logOut = $null
$logErr = $null
if ($LogFile -and $LogFile.Trim().Length -gt 0) {
  $logBase = $LogFile
  if (-not [IO.Path]::IsPathRooted($logBase)) {
    $logBase = Join-Path $runDir $logBase
  }
  $logDir = Split-Path $logBase -Parent
  if ($logDir -and -not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
  $logOut = $logBase + ".out"
  $logErr = $logBase + ".err"
}

function To-FileUrl([string]$path) {
  $p = $path.Replace('\','/')
  if ($p -match '^[A-Za-z]:/') { return "file:///$p" }
  return "file:///$p"
}

$fileUrl = To-FileUrl $Html

function Resolve-EdgePath() {
  $regPaths = @(
    "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\msedge.exe",
    "HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\msedge.exe"
  )
  foreach ($rp in $regPaths) {
    try {
      $val = (Get-ItemProperty -Path $rp -ErrorAction Stop)."(default)"
      if ($val -and (Test-Path $val)) { return $val }
    } catch { }
  }
  $candidates = @(
    "$env:ProgramFiles\\Microsoft\\Edge\\Application\\msedge.exe",
    "$env:ProgramFiles(x86)\\Microsoft\\Edge\\Application\\msedge.exe"
  )
  foreach ($c in $candidates) {
    if ($c -and (Test-Path $c)) { return $c }
  }
  throw "msedge.exe not found via App Paths or Program Files"
}

$edgePath = Resolve-EdgePath
$edgeVersion = (Get-Item $edgePath).VersionInfo.FileVersion

$args = @(
  "--headless=new",
  "--disable-gpu",
  "--remote-debugging-port=$Port",
  "--user-data-dir=$runDir\\_cdp_profile",
  "--allow-file-access-from-files",
  "--disable-web-security",
  "about:blank"
)
if ($logErr) {
  $args += @("--enable-logging=stderr", "--v=1")
  New-Item -ItemType File -Path $logOut -Force | Out-Null
  New-Item -ItemType File -Path $logErr -Force | Out-Null
  Start-Process $edgePath -ArgumentList $args -RedirectStandardOutput $logOut -RedirectStandardError $logErr | Out-Null
} else {
  Start-Process $edgePath -ArgumentList $args | Out-Null
}
Start-Sleep -Seconds 2

function Get-Json([string]$url) {
  for ($i=0; $i -lt 20; $i++) {
    try { return Invoke-RestMethod $url } catch { Start-Sleep -Milliseconds 300 }
  }
  throw "CDP endpoint not reachable: $url"
}

$targets = Get-Json "http://127.0.0.1:$Port/json/list"
$page = $targets | Where-Object { $_.type -eq "page" } | Select-Object -First 1
if (-not $page) { throw "No page target found" }
$wsUrl = $page.webSocketDebuggerUrl

Add-Type -AssemblyName System.Net.WebSockets
$ws = [System.Net.WebSockets.ClientWebSocket]::new()
$ws.ConnectAsync([Uri]$wsUrl, [Threading.CancellationToken]::None).Wait()

$msgId = 0
function Receive-Json() {
  $buffer = New-Object byte[] 65536
  $sb = New-Object System.Text.StringBuilder
  do {
    $seg = [System.ArraySegment[byte]]::new($buffer, 0, $buffer.Length)
    $result = $ws.ReceiveAsync($seg, [Threading.CancellationToken]::None).Result
    if ($result.Count -gt 0) {
      $null = $sb.Append([Text.Encoding]::UTF8.GetString($buffer, 0, $result.Count))
    }
  } while (-not $result.EndOfMessage)
  $text = $sb.ToString()
  return ($text | ConvertFrom-Json)
}

function Send-Cdp([string]$method, [hashtable]$params=@{}) {
  $script:msgId++
  $obj = @{ id = $script:msgId; method = $method; params = $params }
  $json = ($obj | ConvertTo-Json -Depth 20 -Compress)
  $bytes = [Text.Encoding]::UTF8.GetBytes($json)
  $seg = [System.ArraySegment[byte]]::new($bytes, 0, $bytes.Length)
  $ws.SendAsync($seg, [Net.WebSockets.WebSocketMessageType]::Text, $true, [Threading.CancellationToken]::None).Wait()
  while ($true) {
    $msg = Receive-Json
    if ($msg.id -eq $script:msgId) { return $msg }
  }
}

function Wait-Load() {
  $deadline = (Get-Date).AddSeconds(20)
  while ((Get-Date) -lt $deadline) {
    $msg = Receive-Json
    if ($msg.method -eq "Page.loadEventFired") { return }
  }
}

$null = Send-Cdp "Page.enable"
$null = Send-Cdp "Runtime.enable"
$null = Send-Cdp "Input.enable"
$null = Send-Cdp "Page.navigate" @{ url = $fileUrl }
Wait-Load

$null = Send-Cdp "Emulation.setDeviceMetricsOverride" @{ width = 1280; height = 720; deviceScaleFactor = 1; mobile = $false }

function Capture([string]$name) {
  $res = Send-Cdp "Page.captureScreenshot" @{ format = "png" }
  $b64 = $res.result.data
  $bytes = [Convert]::FromBase64String($b64)
  $path = Join-Path $runDir $name
  [IO.File]::WriteAllBytes($path, $bytes)
}

Capture "01_baseline.png"
Send-Cdp "Runtime.evaluate" @{ expression = "window.scrollBy(0,1200);" }
Capture "02_scroll.png"
Send-Cdp "Runtime.evaluate" @{ expression = "document.body.style.zoom='110%';" }
Capture "03_zoom_in.png"
Send-Cdp "Runtime.evaluate" @{ expression = "document.body.style.zoom='90%';" }
Capture "04_zoom_out.png"
Send-Cdp "Runtime.evaluate" @{ expression = "window.scrollBy(0,1200);" }
Capture "05_scroll2.png"
$clickRes = Send-Cdp "Runtime.evaluate" @{
  expression = "(()=>{const sels=['.event-row','.event-item','[data-event-id]'];for(const s of sels){const el=document.querySelector(s);if(el){el.scrollIntoView({block:'center'});el.click();el.style.outline='3px solid #ff3b30';el.style.background='rgba(255,59,48,0.18)';el.setAttribute('data-cdp-highlight','1');return s;}}return null;})()"
  returnByValue = $true
}
Send-Cdp "Runtime.evaluate" @{
  expression = "(()=>{let badge=document.getElementById('cdp-badge');if(!badge){badge=document.createElement('div');badge.id='cdp-badge';badge.textContent='CDP CLICK';badge.style.position='fixed';badge.style.top='12px';badge.style.right='12px';badge.style.zIndex='999999';badge.style.padding='6px 10px';badge.style.background='rgba(255,59,48,0.9)';badge.style.color='#fff';badge.style.font='bold 12px sans-serif';badge.style.borderRadius='4px';}document.body.appendChild(badge);})()"
}
Capture "06_event_click.png"
Send-Cdp "Runtime.evaluate" @{ expression = "document.body.style.zoom='100%';" }
Capture "07_final.png"

$review = @{
  html = $Html
  run_dir = $runDir
  edge_path = $edgePath
  edge_version = $edgeVersion
  click_selector = $clickRes.result.result.value
  log_stdout = $logOut
  log_stderr = $logErr
  screenshots = @("01_baseline.png","02_scroll.png","03_zoom_in.png","04_zoom_out.png","05_scroll2.png","06_event_click.png","07_final.png")
} | ConvertTo-Json -Depth 5
$review | Set-Content -Path (Join-Path $runDir "review.json") -Encoding UTF8
Write-Host "RunDir: $runDir"
Write-Host "Saved screenshots: 7"
