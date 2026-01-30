## Scope
- In: `_tmp_html_ui_review_cdp.ps1` 控制台输出 step_log；对新 RDC `g145-battle-2.rdc` 运行一次 HTML 生成。
- Out: 不修改 HTML 模板、不调整分析算法、不新增外部依赖。

## Assumptions
- `g145-battle-2.rdc` 可被本机 Python 分析脚本读取。
- `analyze_rdc.py` 可直接生成 HTML（如需要 Mali Offline Compiler 则记录失败原因）。
- 允许输出 HTML 到 RDC 同目录。

## Build / Test / Lint Quick Guide (命令仅记录不执行)
- UI 验收脚本（带 console step_log）：
  - `powershell -ExecutionPolicy Bypass -File scripts/_tmp_html_ui_review_cdp.ps1 -Html scripts/rdc_analyzer/test_output/g145_report.html -OutDir docs/analysis/codex_rdc_analyzer/html_review -LogFile edge_log`
  - 预期输出：`StepLog:` 行 + `RunDir:` 行
- 新 RDC 报告生成：
  - `py -3 scripts/rdc_analyzer/analyze_rdc.py "D:\renderdoc\goog pixel-9\g145-battle-2.rdc" --output "D:\renderdoc\goog pixel-9\g145-battle-2_report.html"`
  - 预期输出：`[OK] Report saved to: ...`

## Repo / File List (精确到行号范围)
- `scripts/_tmp_html_ui_review_cdp.ps1:185-210`（review.json 输出与 Write-Host）
- `scripts/rdc_analyzer/analyze_rdc.py:2499-2545`（CLI 入口与 --output 参数）

## Approach (Pseudo-code)
1) 在 PowerShell 侧将 `step_log` 合并 `html_input/html_abs/file_url` 并输出到 console。
2) 跑脚本验证 console 日志出现。
3) 使用 `analyze_rdc.py` 处理新 RDC 并生成 HTML。

## Action Items (2–5 分钟粒度，含 WHAT/WHY/HOW)
- [x] **Step 1 — 控制台输出 step_log**
  - WHAT: 写一行 `Write-Host` 输出 step_log。
  - WHY: 方便快速定位，无需打开 review.json。
  - HOW (完整片段，插入 review.json 写入前后):
    ```
    $stepLog = @("html_input:$htmlInput","html_abs:$Html","file_url:$fileUrl") + $stepLog
    Write-Host ("StepLog: " + ($stepLog -join "; "))
    ```

- [x] **Step 2 — 执行 UI 验收脚本**
  - WHAT: 跑一遍以验证 console 输出。
  - WHY: 证明 step_log 已可读。
  - HOW:
    ```
    powershell -ExecutionPolicy Bypass -File scripts/_tmp_html_ui_review_cdp.ps1 -Html scripts/rdc_analyzer/test_output/g145_report.html -OutDir docs/analysis/codex_rdc_analyzer/html_review -LogFile edge_log
    ```

- [x] **Step 3 — 新 RDC 生成 HTML**
  - WHAT: 对 `g145-battle-2.rdc` 生成 HTML。
  - WHY: 满足“用新的 rdc 跑一遍”的要求。
  - HOW:
    ```
    py -3 scripts/rdc_analyzer/analyze_rdc.py "D:\renderdoc\goog pixel-9\g145-battle-2.rdc" --output "D:\renderdoc\goog pixel-9\g145-battle-2_report.html"
    ```

## Impact Analysis
- 风险: analyze_rdc.py 依赖 Mali Offline Compiler；如缺失会报错。
- 影响: 仅脚本输出增强，不影响核心分析链路。

## Verification / Acceptance (DoD)
- console 输出包含 `StepLog:` 且含 html_input/html_abs/file_url。
- 新 RDC 输出 HTML 成功生成；若失败，记录错误原因与日志。

### Verification Results (2026-01-26)
- Command: `powershell -ExecutionPolicy Bypass -File scripts/_tmp_html_ui_review_cdp.ps1 -Html scripts/rdc_analyzer/test_output/g145_report.html -OutDir docs/analysis/codex_rdc_analyzer/html_review -LogFile edge_log`
  - Output: console 出现 `StepLog:`，包含 html_input/html_abs/file_url/doc_ready/doc_url。
- Command: `py -3 scripts/rdc_analyzer/analyze_rdc.py "D:\renderdoc\goog pixel-9\g145-battle-2.rdc" --output "D:\renderdoc\goog pixel-9\g145-battle-2_report.html"`
  - Output: `[OK] Report saved to: D:\renderdoc\goog pixel-9\g145-battle-2_report.html`
  - Note: `[INFO] No texture manifest found for g145-battle-2.rdc`（纹理导出未提供）。

## Risks & Blockers
- 若 `g145-battle-2.rdc` 需要 RenderDoc Python API 环境，可能报错；记录并回报。

## Next Steps
- 如 analyze_rdc.py 失败，则切换到 `renderdoccmd export` + `generate_real_report.py` 备选链路。
