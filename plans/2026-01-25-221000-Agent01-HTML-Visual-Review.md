## Scope
- In: 基于现有 HTML 报告进行自动化 UI 视觉验收（Headless Edge + CDP 截图），并形成可追溯记录。
- Out: 不新增 UI 功能、不调整 HTML 样式、不改 RenderDoc 核心。

## Assumptions
- 目标 HTML 已生成（优先使用你指定的路径；否则使用最新 `g145_report.html`）。
- 可执行 PowerShell 脚本（`scripts/_tmp_html_ui_review_cdp.ps1` 已存在）。
- 视觉验收以“页面可打开 + 关键模块可见 + 事件点击可高亮”为通过标准。

## Build / Test / Lint Quick Guide (命令仅记录不执行)
- 运行 Headless 视觉验收：
  - `powershell -ExecutionPolicy Bypass -File scripts/_tmp_html_ui_review_cdp.ps1 -Html <html_path> -OutDir docs/analysis/codex_rdc_analyzer/html_review -LogFile edge_log`
  - 预期输出: `RunDir: ...`、`Saved screenshots: 7`，并生成 `review.json` + `01..07.png`。
- 校验 review.json：
  - `py -3 -c "import json;print(json.load(open(r'docs/analysis/codex_rdc_analyzer/html_review/<run>/review.json','r',encoding='utf-8'))['click_found'])"`

## Repo / File List (精确到行号范围)
- `scripts/_tmp_html_ui_review_cdp.ps1:1-150`（CDP 启动、截图、点击逻辑）
- `scripts/_tmp_html_ui_review_cdp.ps1:160-230`（review.json 输出）
- `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_VERIFICATION.md:167-234`（已有 headless 说明/约束）

## Approach (Pseudo-code)
1) 运行 headless 脚本生成截图与 review.json。
2) 读取 review.json，确认 click_found=true 且 run_dir 正确。
3) 用 rg 验证 HTML 中关键节点是否存在（Events/Performance 等）。
4) 在 `WORK_SUMMARY_VERIFICATION.md` 追加本次 run 记录（路径+结果）。

## Action Items (2–5 分钟粒度，含 WHAT/WHY/HOW)
- [x] **Step 1 — 选定 HTML 路径**
  - WHAT: 确认验收目标 HTML。
  - WHY: 视觉验收必须有确定输入，否则结果不可追溯。
  - HOW: 若用户未指定，使用 `scripts/rdc_analyzer/test_output/g145_report.html`。

- [x] **Step 2 — 执行 Headless 视觉验收**
  - WHAT: 运行 CDP 脚本生成 7 张截图 + review.json。
  - WHY: 用截图与 click 高亮验证 UI 的基本可用性。
  - HOW (完整命令片段):
    ```
    powershell -ExecutionPolicy Bypass -File scripts/_tmp_html_ui_review_cdp.ps1 -Html <html_path> -OutDir docs/analysis/codex_rdc_analyzer/html_review -LogFile edge_log
    ```

- [x] **Step 3 — 校验 review.json 与关键 DOM**
  - WHAT: 确认 click_found=true，DOM 关键节点存在。
  - WHY: click 高亮证明 Event Browser 可交互；DOM 校验证明面板存在。
  - HOW (完整命令片段):
    ```
    py -3 -c "import json;print(json.load(open(r'docs/analysis/codex_rdc_analyzer/html_review/<run>/review.json','r',encoding='utf-8')))"
    rg -n "eventTotalCount|eventListCount|performancePanel" <html_path>
    ```

- [x] **Step 4 — 记录验收结果**
  - WHAT: 将 run 目录与关键结果写入 `WORK_SUMMARY_VERIFICATION.md`。
  - WHY: 保留证据链，便于后续复查。
  - HOW: 追加“本次 run 路径/截图列表/click_found 状态”。

## Impact Analysis
- 风险: headless 渲染与实际浏览器存在差异（字体/缩放）。
- 影响: 仅生成审阅产物，不改业务逻辑。
- 兼容: 不影响已有 HTML 导出流程。

## Verification / Acceptance (DoD)
- 输出目录包含 `review.json` 与 `01..07.png`。
- `review.json` 中 `click_found = true` 或明确记录失败原因。
- `WORK_SUMMARY_VERIFICATION.md` 增加本次 run 记录。

### Verification Results (2026-01-25)
- Command: `powershell -ExecutionPolicy Bypass -File scripts/_tmp_html_ui_review_cdp.ps1 -Html scripts/rdc_analyzer/test_output/g145_report.html -OutDir docs/analysis/codex_rdc_analyzer/html_review -LogFile edge_log`
  - Output: `RunDir: docs/analysis/codex_rdc_analyzer/html_review/run_20260125-223218` / `Saved screenshots: 7`
  - Note: `System.Net.WebSockets` assembly missing warning from PowerShell, but screenshots still saved.
- review.json:
  - `click_found=false`, `click_strategy=fallback` (记录为未命中事件节点)
- DOM checks:
  - `eventTotalCount` / `eventListCount` / `performancePanel` 存在（rg 已验证）。

## Risks & Blockers
- 若出现 Chromium `fallback_task_provider` 报错：记录为非阻塞告警（已有历史证明不影响截图）。
- 若 CDP 无法连接：记录错误并停止，等待用户指示。

## Decisions
- 继续复用现有 `_tmp_html_ui_review_cdp.ps1`，不新增依赖。

## Open Questions
- 目标 HTML 路径是否需要换成你指定的“真实导出 HTML”？

## Next Steps
- 等你确认 `/do`，我将执行上述流程并更新验收记录。
