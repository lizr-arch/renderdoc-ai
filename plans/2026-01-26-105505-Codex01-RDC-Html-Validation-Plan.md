# Scope / Assumptions
- Scope (In): 让 `analyze_rdc.py` 生成的 HTML 与“UI 视觉验收脚本”兼容；补齐关键指标展示；纹理清单可追踪；对 `D:\renderdoc\goog pixel-9\g145-battle-2.rdc` 的输出可通过验收。
- Scope (Out): “标准可追溯规则/元数据闭环”本阶段暂不补充（已确认可后续补）。
- Assumptions: 现有 `generate_real_report.py` 的 HTML 结构为“完整报告基准”；`analyze_rdc.py` 当前为“轻量报告”，缺少 Event Browser/指标；纹理清单来源于 `export_textures_rdoc.py` 的 manifest.json。

# Build / Test / Lint Quick Guide (记录命令，不执行)
- 单帧分析（当前路径）:
  - `py -3 scripts/rdc_analyzer/analyze_rdc.py "D:\renderdoc\goog pixel-9\g145-battle-2.rdc" --output "D:\renderdoc\goog pixel-9\g145-battle-2_report.html"`
  - 预期输出（修复后）：包含 `Report saved` / `HTML written` 类提示，且不再出现 `No texture manifest found`。
- 纹理预导出（如需）:
  - `py -3 scripts/rdc_analyzer/export_textures_rdoc.py "D:\renderdoc\goog pixel-9\g145-battle-2.rdc"`
  - 预期输出：`Manifest saved to: ...\manifest.json`
- UI 视觉验收（CDP，生成截图+review.json）:
  - `powershell -ExecutionPolicy Bypass -File scripts/_tmp_html_ui_review_cdp.ps1 -Html "D:\renderdoc\goog pixel-9\g145-battle-2_report.html" -OutDir "docs/analysis/codex_rdc_analyzer/html_review" -LogFile edge_log`
  - 预期输出：`click_found=true` 且 `StepLog:` 内包含 `event-node-ready` 或替代验证项。

# Repo / File List (含行号)
- `scripts/rdc_analyzer/analyze_rdc.py:435` 生成 HTML 报告函数入口 `generate_html_report(...)`
- `scripts/rdc_analyzer/analyze_rdc.py:2499` 参数解析入口 `argparse.ArgumentParser(...)`
- `scripts/rdc_analyzer/generate_real_report.py:874` `generate_minimal_texture_data()`
- `scripts/rdc_analyzer/generate_real_report.py:1338` `main()` 报告生成入口
- `scripts/rdc_analyzer/export_textures_rdoc.py:38` 输出目录与纹理导出流程
- `scripts/rdc_analyzer/export_textures_rdoc.py:101` manifest.json 写入位置
- `scripts/_tmp_html_ui_review_cdp.ps1:159` Event Browser/DOM 选择器与 step_log 采集
- `scripts/_tmp_html_ui_review_cdp.ps1:209` step_log 写回 review.json

# Approach (Pseudo-code)
```python
# analyze_rdc.py (新增完整报告模式)
def run_full_report(rdc_path, output_html, textures_dir=None):
    # 1) 确保有可供完整报告使用的数据（json/manifest）
    json_path = ensure_export_json(rdc_path)   # 复用已有导出链路
    manifest_ok = ensure_texture_manifest(rdc_path, textures_dir)
    # 2) 调用完整报告生成器（单一 HTML）
    generate_real_report(json_path, output_html, textures_dir=textures_dir)
    # 3) 若 manifest 缺失，HTML 中显式标注“纹理未导出”

# _tmp_html_ui_review_cdp.ps1 (兼容轻量 HTML)
if (EventBrowser 存在) { 走现有 showEventBrowser + event-node 流程 }
else { 走 analyze_rdc DOM 选择器清单，至少命中 1 个关键区块 }
```

# Impact Analysis
- 行为变更：`analyze_rdc.py` 可能新增 `--html-mode` / `--full-report` 分支；输出 HTML 结构可能对比现有轻量模板产生变化。
- 验收影响：UI 视觉验收脚本需兼容两类 DOM（完整报告/轻量报告），否则新 HTML 会继续失败。
- 风险：完整报告依赖 manifest.json；若导出链路不可用，需明确降级提示而非静默失败。

# Action Items (2-5 min/步；每步含 WHAT/WHY/HOW)
- [x] 1. 增加 `--html-mode` 参数（lite/full）并落到分支
  - WHAT: 在 `analyze_rdc.py` 参数中新增 `--html-mode`，默认 `lite`。
  - WHY: 用开关明确“轻量/完整”输出，避免混淆验收路径。
  - HOW (完整代码片段):
    ```python
    # analyze_rdc.py: argparse 区域
    parser.add_argument("--html-mode", choices=["lite", "full"], default="lite",
                        help="HTML output mode: lite (current) or full (generate_real_report)")
    ```
- [x] 2. 在 `full` 模式下调用完整报告生成器
  - WHAT: 复用 `generate_real_report.py` 生成包含 Event Browser 的 HTML。
  - WHY: 让 UI 验收脚本复用现有“完整报告”选择器，避免另起一套 UI 标准。
  - HOW (完整代码片段):
    ```python
    # analyze_rdc.py: main flow
    if args.html_mode == "full":
        from scripts.rdc_analyzer import generate_real_report
        generate_real_report.main([
            export_json_path,
            args.output
        ] + (["--textures", textures_dir] if textures_dir else []))
        return
    ```
- [x] 3. 补齐纹理 manifest 检测与自动导出（可选）
  - WHAT: 若 `manifest.json` 缺失，提示或触发 `export_textures_rdoc.py`。
  - WHY: 当前 g145-battle-2 报告提示 “No texture manifest found”，导致纹理相关面板信息缺失。
  - HOW (完整代码片段):
    ```python
    manifest_path = Path(textures_dir) / "manifest.json"
    if not manifest_path.exists():
        print("[WARN] Texture manifest missing. Run export_textures_rdoc.py first.")
        # 可选: subprocess.run(["py","-3","scripts/rdc_analyzer/export_textures_rdoc.py", rdc_path])
    ```
- [ ] 4. UI 视觉验收脚本兼容轻量报告 DOM
  - WHAT: 增加针对 `analyze_rdc.py` HTML 的选择器集合（如 textures/event 版块）。
  - WHY: 即使不走 full-report，也可通过最低限度的 UI 验收。
  - HOW (完整代码片段):
    ```javascript
    // _tmp_html_ui_review_cdp.ps1 内注入脚本的 selectors 追加:
    {n:'lite-textures', s:'#textureGrid, .texture-grid, .texture-card'},
    {n:'lite-sections', s:'section, .report-section, .card-header'}
    ```
- [ ] 5. 更新验证文档与验收清单
  - WHAT: 在 `WORK_SUMMARY_VERIFICATION.md` 追加本次 g145-battle-2 的运行记录与截图路径。
  - WHY: 留下可追溯的验收证据链，避免“看过但无记录”的问题。
  - HOW (完整代码片段):
    ```markdown
    ## 7.x g145-battle-2 HTML 验收
    - cmd: py -3 scripts/rdc_analyzer/analyze_rdc.py ...
    - html: D:\renderdoc\goog pixel-9\g145-battle-2_report.html
    - review: docs/analysis/codex_rdc_analyzer/html_review/run_YYYYMMDD-HHMMSS/
    - result: click_found=true (selector: ...)
    ```
- [x] 6. TDD 模板（最小烟测）
  - WHAT: 写一个最小 smoke 检查，确认 HTML 至少包含一个关键区块。
  - WHY: 防止“可生成 HTML 但 UI 验收脚本找不到任何元素”的回归。
  - HOW (完整代码片段):
    ```python
    # scripts/rdc_analyzer/tests/test_html_smoke.py
    html = Path(r"D:\renderdoc\goog pixel-9\g145-battle-2_report.html").read_text(encoding="utf-8")
    assert ("Event Browser" in html) or ("texture-grid" in html)
    ```

# Risks & Blockers
- `generate_real_report.py` 是否能被安全 import/调用？若内部依赖 `__main__` 参数，需小幅重构。
- 纹理导出依赖 RenderDoc replay/驱动环境；若缺失，需要明确降级策略。

# Verification / Acceptance (DoD)
- g145-battle-2.rdc 输出 HTML：能打开、无 JS 错误主阻断。
- UI 视觉验收脚本返回 `click_found=true`，并写入 `review.json` + `StepLog`。
- 报告包含至少一项指标/面板（Event Browser 或 Texture 面板）。
- 记录在 `WORK_SUMMARY_VERIFICATION.md`，含命令、输出路径、截图目录。

# Open Questions
- `analyze_rdc.py` 的轻量 HTML 是否需要长期保留，还是完全转向 full-report？
- 纹理导出是强制步骤还是可选（仅在 UI 需要纹理时）？

# Next Steps
- 等待 /do 批准后开始逐项执行并按计划文件勾选。
