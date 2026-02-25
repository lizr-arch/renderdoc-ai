# Report Issue Jump Export Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-02-24  
**Owner:** Agent01  
**Last Updated:** 2026-02-24  
**Plan File:** plans/2026-02-24-224419-Agent01-Report-Issue-Jump-Export.md

**Goal:** 形成“完整分析报告体系”：报告页可查看数据、问题可导出，并可一键跳转到 RenderDoc GUI 定位。

**Architecture:** 以 `analysis.json` 为 SSOT，通过 `report_from_analysis.py` 生成报告包；在报告包内新增问题导出文件（JSON/CSV），各页面问题列表与 EID/资源绑定，并通过 `/api/jump?eid=` 触发 GUI 定位（无内嵌 WebUI server 时禁用/提示）。

**Tech Stack:** Python 3.x、rdc_analyzer 报告模板（HTML/JS/CSS）、RenderDoc GUI 扩展 / WebUI server。

**Success Criteria (measurable):**
- 使用样本 `D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc` 生成报告后，`index/events/textures/shaders` 页面可访问且显示**非空**数据（events/shaders/textures/passes 至少各 ≥1 条；pipeline_state/uniforms 不可用则显示空态提示）。
- “问题导出”文件在输出目录生成：`issues_export.json` 与 `issues_export.csv`（至少包含 level/message/eid/resource_id）。
- 在 issues 列表中点击 “Jump to GUI” 能定位到对应 EID（内嵌 WebUI server 可用时）；外部 WebUI server 场景按钮禁用并提示原因。

**Acceptance Criteria:**
- “什么有问题”在报告中可见，并提供“导出 + 跳转”入口。
- “问题 → EID → GUI”定位链路可验证（至少 3 个问题样本）。
- WebUI 与离线报告使用同一数据口径（analysis.json）。

**Verification Commands:**
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_report_issue_export.py -v` (Expected: PASS)
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_report_issue_jump_links.py -v` (Expected: PASS)

**Evidence:**
- 输出目录包含：`issues_export.json` / `issues_export.csv`
- 报告页面截图（issues 列表 + Jump 按钮）
- GUI 跳转日志：`%APPDATA%\\qrenderdoc\\extensions\\rdc_analyzer_ext\\rdc_analyzer_latest.log`

**Estimation:**
- Effort: 1–2 天
- Story Points: 3
- Original Estimate: 1 天

**Risk Register (impact/likelihood/mitigation):**
- Issue 缺少 EID → 无法跳转 | High | Medium | 允许用相关事件列表回退，或提示“缺少 EID”
- analysis.json 未输出 issues → 页面空态 | Medium | Medium | 增加空态提示 + 输出导出文件为空
- 大量 issues 导出性能风险 | Medium | Low | 生成 CSV/JSON 时流式写入或按需导出

## Game Dev: Memory & Resource Budget (Leak Checks)
- 报告导出阶段新增 issues 文件，确认不会额外加载全量纹理/RT。
- 若新增缩略图 Top‑N，限制总大小并在报告里标注缓存策略。

## Game Dev: Asset Pipeline
- issues 导出文件与报告包同目录，避免改变现有资源路径。
- 若后续加入缩略图/纹理导出，必须标注“离线分享专用”开关。

## Game Dev: Crash Repro + Dumps/Symbols
- Repro: 生成报告 → 打开 issues 列表 → 点击 Jump → GUI 定位
- Dump/Core: 记录日志路径与版本（PDB/Build ID）
- Symbols: 确保 RenderDoc 使用带符号的开发版本

---

## Scope
- In scope: issues 导出、issues 列表展示、Jump to GUI 与跳转禁用提示、最小单测。
- Out of scope: 多帧对比、HLSL 反编译、P1/P2 外部硬件分析展示。

## Assumptions
- `analysis.json` 按 `analysis_report_schema_v1.md` 生成（包含 `issues/suggestions`）。
- 用户仅做视觉验收，跳转逻辑由扩展内部验证。

## Build/Test/Lint Quick Guide
- Tests: `py -3 -m pytest scripts/rdc_analyzer/tests/test_report_issue_export.py -v`
- Tests: `py -3 -m pytest scripts/rdc_analyzer/tests/test_report_issue_jump_links.py -v`

## Navigation Evidence (codemap-first + fallback)
**Codemap queries used (no matches in this repo):**
1. `codemap "templates/index.html" -Num 20` → 命中 client_s1，非本仓库
2. `codemap "rdc_analyzer/templates/index.html" -Num 20` → No matches
3. `codemap "rdc_analyzer/webui" -Num 20` → No matches

**Serena fallback attempt:**
- `serena.find_file` / `serena.search_for_pattern` 在 `scripts/rdc_analyzer` 路径被策略忽略（无法访问）。

**Equivalent local evidence (rg):**
- `[renderdoc] scripts/rdc_analyzer/generate_offline_report.py:18` — “CSS/JS/HTML 模板存放在 assets/ 和 templates/ 目录”
- `[renderdoc] scripts/rdc_analyzer/report_from_analysis.py:9` — `def generate_report_from_analysis(...)`
- `[renderdoc] scripts/rdc_analyzer/webui/server.py:132` — `if parsed.path == "/api/jump":`

**Follow-up targets:**
- `scripts/rdc_analyzer/report_from_analysis.py`：新增 issues 导出文件
- `scripts/rdc_analyzer/templates/*.html`：issues 列表 + 导出 + Jump 按钮

## File List (with line refs)
- `scripts/rdc_analyzer/report_from_analysis.py:9`（生成报告入口，新增 issues 导出）
- `scripts/rdc_analyzer/webui/server.py:132`（Jump API 路径）
- `scripts/rdc_analyzer/templates/index.html:454`（issues 区块）
- `scripts/rdc_analyzer/templates/events.html:2108`（issues 标记 / Jump 按钮）
- `scripts/rdc_analyzer/templates/shaders.html:1228`（issues 筛选 / 导出）
- `scripts/rdc_analyzer/templates/textures.html:753`（issues 筛选 / Jump）
- `scripts/rdc_analyzer/tests/`（新增 issue 导出/跳转相关测试）

## Approach (Pseudo-code)
```python
# report_from_analysis.py
def generate_report_from_analysis(...):
    data = load(analysis.json)
    bundle = analysis_to_bundle(data)
    generator = ReportBundleGenerator(...)
    generator.set_events(...)
    generator.set_textures(...)
    generator.set_shaders(...)
    generator.stats.update(...)
    generator.generate_all()
    export_issues(data, output_dir)  # issues_export.json + issues_export.csv

def export_issues(data, output_dir):
    issues = data.get("issues", [])
    rows = [
        {"level": i.level, "message": i.message, "eid": i.eid, "resource_id": i.resource_id}
        for i in issues
    ]
    write_json(rows)
    write_csv(rows)
```

```js
// templates/<page>.html
function renderIssueList(items){
  // 显示 level/message/eid/resource，并提供 Jump 按钮
  // Jump → /api/jump?eid=xxx (若不可用则禁用按钮)
}
```

## Impact Analysis
- 新增 issues 导出文件与 Jump 入口，不影响现有数据生成路径。
- 离线报告与 WebUI 一致性提升，便于性能团队快速定位问题。
- 风险集中在 issues 是否包含 EID / 资源引用完整性。

---

## Task Checklist

### Task 1: Add failing tests for issues export + jump links
- [x] Step 1: 新增 `test_report_issue_export.py`（断言 issues_export.json/csv 生成）
- [x] Step 2: 运行测试确认失败
- [x] Step 3: 新增 `test_report_issue_jump_links.py`（断言页面包含 Jump/导出入口）
- [x] Step 4: 运行测试确认失败
- [x] Step 5: 提交  
  `git commit -m "test(rdc-analyzer): add issue export/jump checks"`

### Task 2: Implement issues export in report generation
- [x] Step 1: 在 `report_from_analysis.py` 增加 `export_issues(...)`
- [x] Step 2: 运行测试确认通过
- [x] Step 3: 提交  
  `git commit -m "feat(rdc-analyzer): export issues for reports"`

### Task 3: Add issues panel + export links in report templates
- [x] Step 1: `templates/index.html` 增加 issues 汇总卡 + 导出入口
- [x] Step 2: `templates/events.html` 增加 issues 过滤 + Jump 可用性提示
- [x] Step 3: `templates/shaders.html` / `textures.html` 增加 issues 导出入口
- [x] Step 4: 运行测试确认通过
- [x] Step 5: 提交  
  `git commit -m "feat(rdc-analyzer): add issues UI + jump in reports"`

### Task 4: Update docs & verification notes
- [ ] Step 1: 更新 `report_ui_optimization_v1.md`（补充 issues 导出/跳转）
- [ ] Step 2: 更新 `WEBUI_AND_UI_EXTENSION.md`（补充 Jump 说明）
- [ ] Step 3: 运行测试确认通过
- [ ] Step 4: 提交  
  `git commit -m "docs(rdc-analyzer): document issue export + jump"`

## Verification / Acceptance (Definition of Done)
- issues_export.json/csv 生成并包含必要字段
- 报告页能查看 issues 列表 + 导出入口
- Jump to GUI 在内嵌 WebUI server 场景可用
- 测试通过

## Open Questions
- issues 是否需要区分来源（rules vs suggestions）？
- issues 与 shader/texture 的资源映射是否强制要求？

## Next Steps
- 用户确认 /do 后执行；每完成 3 个任务汇报一次。
