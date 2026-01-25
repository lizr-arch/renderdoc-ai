param(
  [string]$Html,
  [string]$OutDir,
  [int]$Port = 9222
)

if (-not (Test-Path $Html)) { throw "HTML not found: $Html" }
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }

function To-FileUrl([string]$path) {
  $p = $path.Replace('\','/')
  if ($p -match '^[A-Za-z]:/') { return "file:///$p" }
  return "file:///$p"
}

$fileUrl = To-FileUrl $Html

$args = @(
  "--headless=new",
  "--disable-gpu",
  "--remote-debugging-port=$Port",
  "--user-data-dir=$OutDir\\_cdp_profile",
  "--allow-file-access-from-files",
  "--disable-web-security",
  "about:blank"
)
Start-Process "msedge.exe" -ArgumentList $args | Out-Null
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
  $path = Join-Path $OutDir $name
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
Send-Cdp "Runtime.evaluate" @{ expression = "(()=>{const sels=['.event-row','.event-item','[data-event-id]'];for(const s of sels){const el=document.querySelector(s);if(el){el.scrollIntoView();el.click();return s;}}return null;})()" }
Capture "06_event_click.png"
Send-Cdp "Runtime.evaluate" @{ expression = "document.body.style.zoom='100%';" }
Capture "07_final.png"

$review = @{
  html = $Html
  screenshots = @("01_baseline.png","02_scroll.png","03_zoom_in.png","04_zoom_out.png","05_scroll2.png","06_event_click.png","07_final.png")
} | ConvertTo-Json -Depth 5
$review | Set-Content -Path (Join-Path $OutDir "review.json") -Encoding UTF8
Write-Host "Saved screenshots: 7"
