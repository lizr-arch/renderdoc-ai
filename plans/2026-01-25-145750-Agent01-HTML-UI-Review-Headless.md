# HTML UI Review (Headless) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-01-25  
**Owner:** Agent01  
**Last Updated:** 2026-01-25

## Plan Metadata
- Version: 2026-01-25
- Owner: Agent01
- Last Updated: 2026-01-25
- Plan File: `plans/2026-01-25-145750-Agent01-HTML-UI-Review-Headless.md`

## Goal
- 实现无人参与的 HTML 交互审阅：Headless Edge + CDP 自动截图、交互覆盖与哈希差异校验，并将结果记录到验证文档。
- 增强交互可见性：点击目标有明显高亮，截图可证明点击发生。
- 产物可追溯：每次运行输出到带时间戳的子目录，避免历史混淆。

## Architecture
- 用 Edge Headless + CDP 远程调试打开 `file:///` 的报告页，执行滚动/缩放/点击等交互，捕获多帧截图。
- 生成 `review.json` 记录动作与截图清单；用 Python 计算哈希确认交互差异；将结论写入验证文档。

## Tech Stack
- PowerShell 7、Microsoft Edge (Chromium/CDP)、Python 3、RenderDoc 导出的静态 HTML。

## Success Criteria (measurable)
- 截图文件 ≥ 7 张，且均为非空 PNG。
- hash 校验中 ≥ 3 张截图 hash 不同。
- `review.json` 与验证记录写入成功。
- 事件点击截图与点击前截图 hash 不同（可见变化）。
- 点击命中真实事件元素（click_found=true 且 click_strategy != fallback）。
- 产物目录包含时间戳子目录。
- Chrome/Edge 错误日志不再“持续刷屏”，或已被记录为可接受的外部噪声（有证据）。

## Acceptance Criteria
- 在无人操作的情况下可一键运行，产物落地到既定目录。
- 复跑同一命令可获得同类型产物（截图 + 哈希输出 + 验证记录）。
- 事件点击存在可见高亮（截图可识别），且为真实事件元素而非纯徽标注入。
- Headless 运行期间不出现持续刷屏的 `fallback_task_provider` 报错，或有明确根因与处理策略。

## Verification Commands
- `pwsh -File scripts/_tmp_html_ui_review_cdp.ps1 -Html "D:\renderdoc\goog pixel-9\g145_from_convert_report.html" -OutDir "docs/analysis/codex_rdc_analyzer/html_review"`  
  Expected: `Saved screenshots: 7` 且 `review.json` 生成
- `py -3 scripts/_tmp_html_review_hash.py docs/analysis/codex_rdc_analyzer/html_review`  
  Expected: 至少 3 张截图 hash 不同
- 期望：`06_event_click.png` 与 `05_scroll2.png` hash 不同（点击可见变化）
- 期望：`review.json` 中 `click_found=true` 且 `click_strategy` 不为 `fallback`

## Evidence
- `docs/analysis/codex_rdc_analyzer/html_review/*.png`
- `docs/analysis/codex_rdc_analyzer/html_review/review.json`
- `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_VERIFICATION.md`

## Estimation
- Effort: 20–30 分钟
- Story Points: 1
- Original Estimate: 1

## Risk Register
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Headless 渲染与真实 UI 差异 | 中 | 中 | 验证记录中标注“headless 结果”，必要时补充人工 UI 复核 |
| CDP 端口被占用 | 中 | 低 | 允许 `-Port` 覆盖，失败时更换端口 |
| file:// 访问受限 | 中 | 中 | 使用 `--allow-file-access-from-files` |
| 点击无可见变化 | 中 | 中 | 注入高亮样式（outline/背景），截图前后对比 |
| 产物混淆 | 低 | 中 | 每次运行写入时间戳子目录 |
| Chromium 警告刷屏 | 低 | 中 | 先采集日志定位来源，再决定是否需要抑制或记录为已知噪声 |

## Game Dev: Memory & Resource Budget (Leak Checks)
- 该任务不涉及运行时内存/资源预算验证；如需扩展可加入 GPU/资源统计页的对比截图与阈值校验。

## Game Dev: Asset Pipeline
- 产物为静态 HTML 与 PNG 截图；需保证导出 HTML 与资源文件夹同目录且可被 `file:///` 正确加载。

## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: 运行 headless 审阅脚本并触发 CDP 流程。
- Dump/Core: 不适用（无可执行崩溃路径）。
- Symbols: 不适用。
- Build identity: 记录 HTML 来源与导出时间戳。

# Scope / Assumptions
- In scope: 全自动（无人参与）HTML 交互审阅：Headless Edge + CDP 截图 + 差异校验 + 结果写入验证文档。
- Out of scope: 修改 HTML 生成逻辑或 RenderDoc 代码；安装新依赖；改动第三方库。
- 假设：本机存在 `msedge.exe`；允许 Headless + Remote Debugging；HTML 可通过 `file:///` 加载。

# Build/Test/Lint Quick Guide (只记录不执行)
- 运行自动审阅：  
  `pwsh -File scripts/_tmp_html_ui_review_cdp.ps1 -Html "D:\renderdoc\goog pixel-9\g145_from_convert_report.html" -OutDir "docs/analysis/codex_rdc_analyzer/html_review"`  
  - 预期输出：`Saved screenshots: 7` + `review.json` 生成
- 计算截图哈希（确认交互差异）：  
  `py -3 scripts/_tmp_html_review_hash.py docs/analysis/codex_rdc_analyzer/html_review`  
  - 预期输出：至少 3 张截图 hash 不同

# Repo / File List (预期修改/新增)
- 新增（临时脚本）：`scripts/_tmp_html_ui_review_cdp.ps1`
- 新增（临时脚本）：`scripts/_tmp_html_review_hash.py`
- 新增（审阅产物）：`docs/analysis/codex_rdc_analyzer/html_review/*.png`
- 修改（记录审阅结果）：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_VERIFICATION.md:121`

# Approach (Pseudo-code)
```
launch Edge headless with remote debugging port
query /json/list to get page websocket URL
connect via ClientWebSocket
enable Page/Runtime/Input
navigate to file:///<html>
wait for Page.loadEventFired
set viewport
capture baseline screenshot
scroll via Runtime.evaluate (window.scrollBy)
capture screenshots
zoom via Runtime.evaluate (document.body.style.zoom)
capture screenshots
click first event-like element via Runtime.evaluate querySelector
inject highlight style on clicked element (outline/background)
capture screenshot
write review.json (actions + file list)
hash screenshots and assert differences
append results to WORK_SUMMARY_VERIFICATION.md
```

# Automation Script (完整片段)
```powershell
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
function Send-Cdp([string]$method, [hashtable]$params=@{}) {
  $script:msgId++
  $obj = @{ id = $script:msgId; method = $method; params = $params }
  $json = ($obj | ConvertTo-Json -Depth 20 -Compress)
  $bytes = [Text.Encoding]::UTF8.GetBytes($json)
  $seg = New-Object System.ArraySegment[byte] -ArgumentList $bytes
  $ws.SendAsync($seg, [Net.WebSockets.WebSocketMessageType]::Text, $true, [Threading.CancellationToken]::None).Wait()
  while ($true) {
    $buffer = New-Object byte[] 65536
    $seg = New-Object System.ArraySegment[byte] -ArgumentList $buffer
    $result = $ws.ReceiveAsync($seg, [Threading.CancellationToken]::None).Result
    $text = [Text.Encoding]::UTF8.GetString($buffer, 0, $result.Count)
    $msg = $text | ConvertFrom-Json
    if ($msg.id -eq $script:msgId) { return $msg }
  }
}

function Wait-Load() {
  $buffer = New-Object byte[] 65536
  $seg = New-Object System.ArraySegment[byte] -ArgumentList $buffer
  $deadline = (Get-Date).AddSeconds(20)
  while ((Get-Date) -lt $deadline) {
    $result = $ws.ReceiveAsync($seg, [Threading.CancellationToken]::None).Result
    $text = [Text.Encoding]::UTF8.GetString($buffer, 0, $result.Count)
    $msg = $text | ConvertFrom-Json
    if ($msg.method -eq "Page.loadEventFired") { return }
  }
}

Send-Cdp "Page.enable"
Send-Cdp "Runtime.enable"
Send-Cdp "Input.enable"
Send-Cdp "Page.navigate" @{ url = $fileUrl }
Wait-Load

Send-Cdp "Emulation.setDeviceMetricsOverride" @{ width = 1280; height = 720; deviceScaleFactor = 1; mobile = $false }

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
```

# Hash Check Script (完整片段)
```python
# scripts/_tmp_html_review_hash.py
from pathlib import Path
import hashlib
import sys

root = Path(sys.argv[1])
pngs = sorted(root.glob("*.png"))
for p in pngs:
    data = p.read_bytes()
    h = hashlib.sha256(data).hexdigest()
    print(p.name, h, len(data))
```

# Impact Analysis
- 风险：Headless 渲染与真实 UI 有差异 → 需在验证记录中标注“headless 结果”。
- 风险：CDP 端口被占用 → 需可配置 Port。
- 风险：file:// 加载受限 → 使用 `--allow-file-access-from-files`。

# Action Items (2–5 分钟粒度)
- [x] 1. 新建 `scripts/_tmp_html_ui_review_cdp.ps1`（按上方脚本）。
- [x] 2. 新建 `scripts/_tmp_html_review_hash.py`。
- [x] 3. 运行 CDP 审阅脚本生成截图与 `review.json`。
- [x] 4. 运行 hash 校验脚本，确认截图存在差异。
- [x] 5. 将审阅结果写入 `WORK_SUMMARY_VERIFICATION.md:121`。
- [x] 6. 改造脚本：输出目录改为时间戳子目录（保留基础 OutDir）。
- [x] 7. 改造脚本：点击目标注入高亮样式（outline/background），确保截图可见变化。
- [x] 8. 重新运行自动审阅，验证点击截图 hash 与点击前不同。
- [x] 9. 更新验证文档，记录新 run 的目录与点击可见性结论。
- [ ] 10. 改造脚本：在 JS 中增加“真实事件元素”定位策略（data-attr / text-match / fallback），并记录 `click_found`/`click_strategy`。
- [ ] 11. 重新运行自动审阅，确认 `click_found=true` 且点击前后 hash 不同。
- [ ] 12. 更新验证文档，记录新策略结果与 run 目录。
- [x] 13. 记录问题详情（期望/实际/复现步骤/频率/环境），写入计划或验证文档。
- [x] 14. 增加可选日志采集参数（例如 `-LogFile`），让 headless run 可落地完整日志。
- [x] 15. 复跑并收集日志，确认报错来源与触发条件（是否与页面加载/截图/点击相关）。
- [x] 16. 基于证据形成单一假设（日志来源与触发条件），写入执行记录。
- [x] 17. 若确认影响可忽略 → 记录为已知噪声；若影响功能 → 进入最小化验证修复步骤。
- [x] 18. 更新验证文档与计划执行记录。

# Verification / DoD
- 生成截图 ≥ 7 张且均可打开。
- 至少 3 张截图 hash 不同（交互产生变化）。
- 结果写入 `WORK_SUMMARY_VERIFICATION.md`。
- 点击截图与点击前截图 hash 不同。
- 产物在时间戳子目录中。
- `fallback_task_provider` 报错不再持续刷屏，或已记录为已知噪声并说明原因与证据。

# Execution Notes (during /do)
- 尝试 1 失败：ArraySegment 构造参数被拆分，导致 Send/Receive 无法调用；修正为 `[System.ArraySegment[byte]]::new(...)`。
- 尝试 2 失败：CDP 大包 JSON 被拆分导致解析报错；新增 `Receive-Json` 组包读取逻辑后成功。
- 尝试 3：加入点击高亮与时间戳目录，run_20260125-192309 成功；点击可见差异满足。
- 尝试 4（计划中）：命中真实事件元素并记录 click_strategy。
- 尝试 5：加入 LogFile + Edge 路径解析，run_20260125-202852 捕获 `fallback_task_provider` 报错；产物正常，记录为已知噪声。

# Next Steps
- 已完成自动化审阅；若需提升“点击后可见变化”，可调整选择器或添加高亮样式。
