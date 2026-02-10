# Typography System Plan (RDC Bundle Report)

- Plan ID: 2026-02-09-235254-Codex01-TypographySystem-RDCReport
- Date: 2026-02-09
- Owner: Codex01
- Stage: /do

## Scope

目标：把 Bundle 报告的字体“型号（font stack）+ 字阶（type scale）”收敛到专业中后台/仪表盘风格，重点解决：

- events.html 右侧属性栏（Pipeline State）阅读体验：字号更舒适、层级更清晰、对齐更稳定。
- 全站字体体系从“散点微调”升级为“可复用 token + 统一字阶”。

范围：

- ✅ 改动模板与通用 CSS（scripts/rdc_analyzer/templates/common.css + scripts/rdc_analyzer/templates/events.html 及必要的 textures.html/shaders.html/index.html 微调）
- ✅ 仅 UI/样式层，不改数据生成逻辑
- ✅ 保持现有结构与交互（避免大回归）
- ⚠️ 不涉及编译 RenderDoc / GPU replay

## Assumptions

- 用户的验收方式：只看本地 file:///D:/backup/.../*.html 的视觉效果（不希望任何手动流程）。
- 浏览器环境以 Windows 为主（Segoe UI 可用），但报告可能在不同机器打开，需要中文 fallback。

## Design Spec (Target)

### A) Font Stack (字体型号)

在 common.css 中把 --font-family 从当前的简化系统栈扩充为中文友好的专业栈：

- UI 字体：
  - Segoe UI（Win 主力）
  - Inter（可选，如系统无则 fallback）
  - -apple-system, BlinkMacSystemFont（macOS）
  - PingFang SC, Hiragino Sans GB, Microsoft YaHei, Noto Sans CJK SC（中文 fallback）
  - sans-serif

- 等宽字体（代码/ID/数值对齐）：
  - JetBrains Mono, Cascadia Mono（可选）
  - Consolas, SFMono-Regular, Monaco
  - monospace

### B) Type Scale (字号体系)

收敛到 4 档（减少 8/9/10/11/12/13/14/16/20 的碎片）：

- --font-micro: 10px  （极少数 chip/slot 标签）
- --font-xs: 11px     （辅助信息、badge、说明）
- --font-sm: 12px     （属性值/列表主文本）
- --font-md: 14px     （区块标题/重点标题）

基线：body 基线改为 14px（更接近中后台阅读舒适区），同时通过 xs/sm 控制密度。

### C) Events Right Panel Mapping

对 events.html 的 #panelRight 右侧属性栏强制使用：

- label = 11px（xs）
- value = 12px（sm）
- highlight = 12px（sm，颜色强调）

同时提升“专业工具对齐感”：

- 为数值/ID 使用 font-variant-numeric: tabular-nums（对齐更稳）
- 保持 line-height 在 1.25~1.35，避免拥挤

## File List (Planned Edits, with line ranges)

1) scripts/rdc_analyzer/templates/common.css
- 目标区间 A：69-76（字体变量定义区，当前 --font-family / --font-mono）
- 目标区间 B：91-97（body 基线字号与行高）
- 计划：新增 --font-micro/--font-xs/--font-sm/--font-md token；更新字体栈；评估 body 13→14

2) scripts/rdc_analyzer/templates/events.html
- 目标区间 A：708-763（stat-row / stat-label / stat-value / #panelRight 覆盖区）
- 目标区间 B：788-798（prop-section-title 字号层级）
- 目标区间 C：457-526（pipeline-title / pipeline-badge / pipeline-toggle 字阶一致性）
- 计划：右栏映射改为 11/12/12 + tabular-nums，必要时微调 section 标题字阶

3) （条件触发）scripts/rdc_analyzer/templates/textures.html
- 触发条件：body 基线提升后出现 chip/badge 拥挤或换行
- 预估区间：筛选条与摘要条样式区 + badge 样式区（按 smoke 截图定位后再精确改动）

4) （条件触发）scripts/rdc_analyzer/templates/shaders.html
- 触发条件：toolbar 按钮高度/文本基线错位
- 预估区间：toolbar button 规则区（#hlslBtn/#aiOptimizeBtn 附近）

## Impact Analysis

- 风险（中）：body 基线从 13→14 可能导致某些 panel/header 变高，引发布局溢出。
  - 缓解：用 headless smoke + 多分辨率截图（1366x768/1536x864/1920x1080）验证。
- 风险（低）：不同机器缺少 Inter/JetBrains Mono 时 fallback 变化。
  - 缓解：字体栈给出明确中文 fallback，且使用系统字体优先。

## TDD / Verification Plan

### Step 1 — Add/Update Tests (Fail First)
- 在 scripts/rdc_analyzer/tests/test_bundle_report_assets.py 增加最小契约断言：
  - common.css 中存在 --font-xs/--font-sm/--font-md token
  - events.html 中 #panelRight .stat-label 使用 var(--font-xs)（或 11px），#panelRight .stat-value 使用 var(--font-sm)（或 12px）

预期：
- 修改前测试失败（缺少 token / selector 不匹配）

### Step 2 — Minimal Implementation
- 落地 token 与样式覆盖

### Step 3 — Verify
- 单测：
  py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -q
- UI headless smoke（针对用户报告目录）：
  py -3 scripts/rdc_analyzer/tools/ui_headless_smoke.py --report-dir D:\backup\endfield_report --out-dir docs\analysis\codex_rdc_analyzer\ui_smoke_artifacts\r_typo_endfield --no-fail
- 生成一份最新报告供用户视觉验证（不需要手动）：
  py -3 scripts/rdc_analyzer/xml_to_bundle.py D:\backup\endfield_auto.zip.xml -o D:\backup\endfield_report_typo_r1

验收标准：
- headless smoke 通过（或在 shaders=0 场景下仍可产出 events/textures 截图）
- events 右栏 EID/类型/名称/耗时 字体不再像 KPI 巨字，也不至于 10px 难读
- 视觉清单（可读性）提升，目标 >= 90/100

## Task Checklist (2–5 min granularity)

- [x] 在 common.css 添加 font scale tokens（10/11/12/14）
- [x] 更新 --font-family/--font-mono 为中文友好栈
- [x] 将 body 基线从 13 调整为 14，并跑 smoke 截图核对
- [x] 将 events.html 右栏字号改为 token（label=xs=11, value=sm=12, highlight=sm=12）
- [x] 加入 tabular-nums 到右栏数值（stat-value）
- [x] 添加/更新最小测试契约（fail-first → pass）
- [x] 生成 D:\backup\endfield_report_typo_r1 供你直接打开
- [x] 跑 headless smoke + 截图产物落盘
- [ ] Git commit（Conventional Commits）

## Decisions

- 采用“舒适优先”的字阶：右栏不低于 11/12；避免 10px 作为主要阅读字号。
- token 化优先于散点硬编码，以便后续页面一致。

## Build/Test/Lint Quick Guide（命令仅记录）

1) 契约测试（快速）
py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -q
预期：全部通过（如 23 passed 或更高）

2) UI smoke（多分辨率）
py -3 scripts/rdc_analyzer/tools/ui_headless_smoke.py --report-dir D:\backup\endfield_report --out-dir docs\analysis\codex_rdc_analyzer\ui_smoke_artifacts\r_typo_endfield --no-fail
预期：输出 overall_pass: True（若 shader 数据为空，至少有 textures/events 截图产物）

3) 生成用户验收目录
py -3 scripts/rdc_analyzer/xml_to_bundle.py D:\backup\endfield_auto.zip.xml -o D:\backup\endfield_report_typo_r1
预期：生成 index/events/textures/shaders/recommendations + data json + common.css

## Definition of Done

- common.css 有统一字体栈与字号 token。
- events.html 右栏在 1920x1080 与 1366x768 下均清晰可读，且未出现溢出/遮挡。
- 自动化验证命令通过，截图可见字体层级改善。
- 变更已提交并可在本地报告目录直接打开验证。

## Risks / Blockers

- [已解决] shaders_data=0 场景下，ui_headless_smoke 已支持空态通过（跳过 shader 列表强制项）。
- [注意] 若后续新增 shader 页面结构变更，需同步更新 smoke 选择器契约（#shaderList/.shader-item/.shader-list-empty）。


## Execution Log (2026-02-10)

- 已执行：py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py scripts/rdc_analyzer/tests/test_ui_headless_smoke_unit.py -q，结果 29 passed。
- 已执行：py -3 scripts/rdc_analyzer/tools/ui_headless_smoke.py --report-dir D:\backup\endfield_report --out-dir docs\analysis\codex_rdc_analyzer\ui_smoke_artifacts\r4_typography_followup，结果 overall_pass=True。
- 已执行：py -3 scripts/rdc_analyzer/xml_to_bundle.py D:\backup\endfield_auto.zip.xml -o D:\backup\endfield_report，用于覆盖你当前 visual check 目录。
- 备注：shaders_data.json=0 场景已在 smoke 中按空态通过处理，不再误报失败。
