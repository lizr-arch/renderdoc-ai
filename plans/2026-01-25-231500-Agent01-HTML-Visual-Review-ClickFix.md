## Scope
- In: 修改 `scripts/_tmp_html_ui_review_cdp.ps1`，在点击事件节点前自动打开 Event Browser 并等待事件树渲染。
- Out: 不改 HTML 页面、不改 RenderDoc 功能、不改数据生成逻辑。

## Assumptions
- HTML 提供 `showEventBrowser()` 与 `renderEventTree()`（由报告模板输出）。
- `eventBrowserBtn` 可能存在，作为可点击入口。
- 允许在 review.json 中记录更多步骤日志字段（step_log）。

## Build / Test / Lint Quick Guide (命令仅记录不执行)
- 执行 UI 验收（含步骤日志）：
  - `powershell -ExecutionPolicy Bypass -File scripts/_tmp_html_ui_review_cdp.ps1 -Html <html_path> -OutDir docs/analysis/codex_rdc_analyzer/html_review -LogFile edge_log`
  - 预期输出: `RunDir: ...`、`Saved screenshots: 7`，`review.json` 含 `step_log` 字段。
- 读取 step_log：
  - `py -3 -c "import json;print(json.load(open(r'docs/analysis/codex_rdc_analyzer/html_review/<run>/review.json','r',encoding='utf-8-sig'))['step_log'])"`

## Repo / File List (精确到行号范围)
- `scripts/_tmp_html_ui_review_cdp.ps1:140-190`（截图/点击逻辑）
- `scripts/_tmp_html_ui_review_cdp.ps1:200-220`（review.json 输出）

## Approach (Pseudo-code)
1) 在 jsClick 前注入“步骤日志”数组（stepLog）。
2) JS 顺序执行：
   - 尝试 `showEventBrowser()`；若不可用，点击 `#eventBrowserBtn`。
   - 等待 `.event-tree-list` 或 `.event-node` 出现（轮询最多 N 次）。
   - 调用 `renderEventTree()` 作为兜底。
   - 在命中元素后点击并高亮。
3) 将 stepLog 返回到 PowerShell，写入 review.json。

## Action Items (2–5 分钟粒度，含 WHAT/WHY/HOW)
- [x] **Step 1 — 扩展 jsClick 流程，先打开 Event Browser**
  - WHAT: 在 jsClick 中新增 open + wait 步骤。
  - WHY: 保证事件树已渲染，提高 `click_found=true` 概率。
  - HOW (完整片段，替换 `$jsClick`):
    ```
    (() => {
      const stepLog = [];
      const log = (s) => stepLog.push(s);
      const tryClick = (sel) => {
        const el = document.querySelector(sel);
        if (el) { el.click(); log("clicked:" + sel); return true; }
        log("missing:" + sel); return false;
      };
      if (typeof showEventBrowser === 'function') { showEventBrowser(); log("showEventBrowser()"); }
      else { tryClick('#eventBrowserBtn'); }
      if (typeof renderEventTree === 'function') { renderEventTree(); log("renderEventTree()"); }
      const maxTries = 20;
      let found = null;
      for (let i=0; i<maxTries; i++) {
        found = document.querySelector('.event-node') || document.querySelector('.event-tree-list .event-node');
        if (found) break;
      }
      // 原选择器/高亮逻辑继续执行
      ...
      return {found: ..., strategy: ..., text: ..., step_log: stepLog};
    })()
    ```

- [x] **Step 2 — 将 step_log 写入 review.json**
  - WHAT: PowerShell 侧读取 step_log 并持久化。
  - WHY: 满足“步骤说明写入 log”要求。
  - HOW (完整片段，加入 review 结构):
    ```
    $stepLog = @()
    $stepVal = Get-PropValue $clickInfo "step_log"
    if ($stepVal) { $stepLog = $stepVal }
    ...
    $review = @{
      ...
      step_log = $stepLog
    } | ConvertTo-Json -Depth 6
    ```

- [x] **Step 3 — 运行验收并验证 click_found**
  - WHAT: 用真实 HTML 运行脚本。
  - WHY: 确认改动有效。
  - HOW:
    ```
    powershell -ExecutionPolicy Bypass -File scripts/_tmp_html_ui_review_cdp.ps1 -Html scripts/rdc_analyzer/test_output/g145_report.html -OutDir docs/analysis/codex_rdc_analyzer/html_review -LogFile edge_log
    ```

## Impact Analysis
- 风险: HTML 若无 Event Browser 入口，click 仍可能 fallback。
- 影响: 仅调整验收脚本，产物结构新增字段 `step_log`。
- 兼容: 不影响旧 review.json 解析（新增字段可忽略）。

## Verification / Acceptance (DoD)
- `review.json` 包含 `step_log` 字段且有步骤内容。
- `click_found` 尽量为 `true`；若为 `false`，`step_log` 能解释原因。
- 产物目录仍包含 7 张截图。

### Verification Results (2026-01-25)
- Code change: `_tmp_html_ui_review_cdp.ps1` 注入 `step_log` 并加入 `showEventBrowser()` 打开逻辑。
- Run #1 (相对路径):
  - Command: `powershell -ExecutionPolicy Bypass -File scripts/_tmp_html_ui_review_cdp.ps1 -Html scripts/rdc_analyzer/test_output/g145_report.html -OutDir docs/analysis/codex_rdc_analyzer/html_review -LogFile edge_log`
  - Result: `click_found=false` / `step_log=['inject-style','missing:#eventBrowserBtn']`（疑似相对路径导致页面未命中）
- Run #2 (绝对路径):
  - Command: `powershell -ExecutionPolicy Bypass -File scripts/_tmp_html_ui_review_cdp.ps1 -Html D:\Code\git\renderdoc\scripts\rdc_analyzer\test_output\g145_report.html -OutDir docs/analysis/codex_rdc_analyzer/html_review -LogFile edge_log`
  - Result: `click_found=true` / `click_strategy=event-node`
  - step_log: `['inject-style','showEventBrowser()','renderEventTree()','event-node-ready']`

## Risks & Blockers
- PowerShell 仍可能提示 `System.Net.WebSockets` 缺失；记录为已知告警。

## Next Steps
- /do 执行修改，更新 `WORK_SUMMARY_VERIFICATION.md` 写入新的 run 记录。
