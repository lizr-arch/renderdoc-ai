## Scope
- In: `_tmp_html_ui_review_cdp.ps1` 增强路径解析（相对→绝对）与 step_log 细化。
- Out: 不改 HTML、不改 RenderDoc 功能、不改生成链路。

## Assumptions
- HTML 报告可用 `file:///` 方式打开。
- headless Edge 可访问本地文件。
- step_log 允许新增字段，不影响现有解析。

## Build / Test / Lint Quick Guide (命令仅记录不执行)
- 运行 UI 验收（使用相对路径验证自动归一化）：
  - `powershell -ExecutionPolicy Bypass -File scripts/_tmp_html_ui_review_cdp.ps1 -Html scripts/rdc_analyzer/test_output/g145_report.html -OutDir docs/analysis/codex_rdc_analyzer/html_review -LogFile edge_log`
  - 预期：`review.json.step_log` 包含 `html_abs` / `file_url` / `doc_ready`。
- 读取 step_log：
  - `py -3 -c "import json;print(json.load(open(r'docs/analysis/codex_rdc_analyzer/html_review/<run>/review.json','r',encoding='utf-8-sig'))['step_log'])"`

## Repo / File List (精确到行号范围)
- `scripts/_tmp_html_ui_review_cdp.ps1:1-40`（参数与 To-FileUrl）
- `scripts/_tmp_html_ui_review_cdp.ps1:140-190`（jsClick 与 step_log）
- `scripts/_tmp_html_ui_review_cdp.ps1:200-220`（review.json 输出）

## Approach (Pseudo-code)
1) 进入脚本后立即将 `$Html` 解析为绝对路径（`[IO.Path]::GetFullPath`）。
2) 将 `html_input/html_abs/file_url` 写入 step_log。
3) 在 JS 中记录 `document.readyState` 与 `location.href`。

## Action Items (2–5 分钟粒度，含 WHAT/WHY/HOW)
- [x] **Step 1 — 绝对路径归一化**
  - WHAT: 将 `$Html` 转绝对路径并替换后续使用。
  - WHY: 避免相对路径导致 DOM 不可访问。
  - HOW (完整片段，插入在 `Test-Path` 后):
    ```
    $htmlInput = $Html
    $Html = [IO.Path]::GetFullPath($Html)
    ```

- [x] **Step 2 — step_log 增强**
  - WHAT: 记录输入路径、绝对路径、file_url、doc.readyState、location.href。
  - WHY: 让验收流程“可追溯”。
  - HOW (完整片段，插入 jsClick 头部与 review.json):
    ```
    log('html_input:' + htmlInput)
    log('html_abs:' + htmlAbs)
    log('file_url:' + fileUrl)
    ...
    log('doc_ready:' + document.readyState)
    log('doc_url:' + document.location.href)
    ```
    PowerShell 侧新增 `html_input/html_abs/file_url` 写入 review.json。

- [x] **Step 3 — 跑一轮验证**
  - WHAT: 用相对路径执行脚本。
  - WHY: 验证自动归一化是否生效。
  - HOW:
    ```
    powershell -ExecutionPolicy Bypass -File scripts/_tmp_html_ui_review_cdp.ps1 -Html scripts/rdc_analyzer/test_output/g145_report.html -OutDir docs/analysis/codex_rdc_analyzer/html_review -LogFile edge_log
    ```

## Impact Analysis
- 风险: 无（仅脚本增强，改动极小）。
- 兼容: 旧 review.json 解析不受影响。
- 回滚: 删除新增字段即可。

## Verification / Acceptance (DoD)
- `step_log` 包含 `html_abs` / `file_url` / `doc_ready` / `doc_url`。
- 使用相对路径运行时 `click_found=true`。

### Verification Results (2026-01-25)
- Command: `powershell -ExecutionPolicy Bypass -File scripts/_tmp_html_ui_review_cdp.ps1 -Html scripts/rdc_analyzer/test_output/g145_report.html -OutDir docs/analysis/codex_rdc_analyzer/html_review -LogFile edge_log`
  - Output: `RunDir: docs/analysis/codex_rdc_analyzer/html_review/run_20260125-232313` / `Saved screenshots: 7`
  - Note: `System.Net.WebSockets` 警告仍出现（已知非阻塞）。
- review.json:
  - `click_found=true`, `click_strategy=event-node`
  - `html_input=scripts/rdc_analyzer/test_output/g145_report.html`
  - `html_abs=D:\Code\git\renderdoc\scripts\rdc_analyzer\test_output\g145_report.html`
  - `file_url=file:///D:/Code/git/renderdoc/scripts/rdc_analyzer/test_output/g145_report.html`
  - `step_log=['doc_ready:complete','doc_url:file:///D:/Code/git/renderdoc/scripts/rdc_analyzer/test_output/g145_report.html','inject-style','showEventBrowser()','renderEventTree()','event-node-ready']`

## Risks & Blockers
- PowerShell WebSockets 警告仍可能出现；记录为已知告警。

## Next Steps
- /do 执行改动并写入新的验收记录。
