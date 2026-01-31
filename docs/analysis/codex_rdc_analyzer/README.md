# Codex：RDC Analyzer 文档索引（长期保留）

> 位置：`docs/analysis/codex_rdc_analyzer/`  
> 目标：把对 `scripts/rdc_analyzer` 的盘点、评分、冲突点、路线图沉淀成**可长期维护**的文档。  
> 约束：单文件控制在 **<= 800 行**（避免阅读/维护成本爆炸）。  
> 更新时间：2026-01-23

---

## 0) WORK_SUMMARY 索引（新）

> 说明：`WORK_SUMMARY_2025-01-21.md` 已改为**索引页**，用于汇总 5 份主题文档。

- 文档阅读入口（必读）：`docs/analysis/codex_rdc_analyzer/DOC_INDEX.md`
- 索引入口：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md`
- 主题文档：
  1) `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ARCH.md`
  2) `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROUTES.md`
  3) `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_SCHEMA.md`
  4) `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_VERIFICATION.md`
  5) `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROADMAP.md`

---

## 1) 建议阅读顺序（按你关心的问题）

1. **我只想先搞清楚“总览/入口/阅读顺序”**  
   - 读：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md`（索引页）

2. **我现在做到了什么？值不值？下一步先做什么？**  
   - 读：`docs/analysis/codex_rdc_analyzer/2026-01-19-rdc-analyzer-capability-scorecard.md`

3. **每个模块到底是干什么的？为什么重要？现在项目里真实状态是什么？**  
   - 读：`docs/analysis/codex_rdc_analyzer/2026-01-19-rdc-analyzer-feature-details.md`

4. **想把“极致/全方位”做成可信工具，最关键的 5–10 个点到底缺什么？**  
   - 读：`docs/analysis/codex_rdc_analyzer/2026-01-19-rdc-analyzer-key-deep-dive.md`

5. **你列的 36 条规则，逐条是什么、为什么、怎么做、当前项目能不能跑起来？**  
   - 读：本目录后续新增的 `*-rules-*.md`（按分类拆分，保证每份可读）

6. **JSON/HTML/对比输出的“口径/字段”到底是什么？为什么 compare 会不可信？怎么统一？**  
   - 读：本目录后续新增的 `*-schema-*.md`

---

## 2) 已存在的核心文档

- `docs/analysis/codex_rdc_analyzer/2026-01-23-rdc-analyzer-continue2-report.md`  
  WHAT：继续2综合报告（A/B/C 全覆盖）：源码级核对、重复/冗余清单、下一阶段最小闭环任务。  
  WHY：在不写代码的前提下，把“现状/冲突/下一步”压缩为可执行清单，避免继续发散。  
  HOW：基于 `rg -n` 小片段证据，逐条给出 WHAT/WHY/HOW，并按 P0/P1 排序。  

- `docs/analysis/codex_rdc_analyzer/2026-01-23-rdc-analyzer-architecture-review.md`  
  WHAT：架构复审 + 目标功能横向对比 + A-first 缺口清单（含 P0 任务与测试点）。  
  WHY：把“功能已实现但入口/验证链断裂”的问题显性化，避免误判完成度。  
  HOW：基于代码入口与测试路径的真实结构，列出可执行收敛方案。

- `docs/analysis/codex_rdc_analyzer/2026-01-19-rdc-analyzer-capability-scorecard.md`  
  WHAT：能力盘点 + 打分 + 冲突点/技术债 + 外部资料（5+5）+ P0/P1/P2 路线图（含 P0 的 WHAT/WHY/HOW）。  
  WHY：这是你问的“我现在实现了什么/优缺点/冲突功能/必须实现什么”的总答案。  
  HOW：以代码证据为主（具体文件/关键行号），并把结论落到可执行的 P0 任务。

- `docs/analysis/codex_rdc_analyzer/2026-01-19-rdc-analyzer-feature-details.md`  
  WHAT：按模块列出 WHAT/WHY/HOW，强调“对照当前项目现状”。  
  WHY：让你能判断每个模块是否真正支撑 2 个核心目标（单帧极致分析 + 双帧全方位对比）。  
  HOW：用现有入口/数据结构/导出路径解释“该模块现在能被用户看见吗？可信度如何？”

- `docs/analysis/codex_rdc_analyzer/2026-01-19-rdc-analyzer-key-deep-dive.md`  
  WHAT：挑最关键的点深入讲清楚（SSOT、阈值体系、规则口径漂移、compare 输入口径等）。  
  WHY：这些点不解决，“建议/结论”会变成不可验证的主观判断。  
  HOW：直接对照 `main.py`/`pipeline.py`/rules/thresholds/diff 等实现，指出具体“断链”位置。

---

## 2.1) 规则细化文档（36 条 RD_* 规则的 WHAT / WHY / HOW）

> 这些文档的重点不是“再写一遍 RULES.md”，而是：  
> 逐条解释规则的输入依赖/阈值 key/当前项目能否真正跑起来（现实对照）。

- `docs/analysis/codex_rdc_analyzer/2026-01-20-rdc-analyzer-rules-draw-call.md`（RD_DC_001~005）
- `docs/analysis/codex_rdc_analyzer/2026-01-20-rdc-analyzer-rules-texture.md`（RD_TEX_001~006）
- `docs/analysis/codex_rdc_analyzer/2026-01-20-rdc-analyzer-rules-buffer.md`（RD_BUF_001~006）
- `docs/analysis/codex_rdc_analyzer/2026-01-20-rdc-analyzer-rules-pass.md`（RD_PASS_001~007）
- `docs/analysis/codex_rdc_analyzer/2026-01-20-rdc-analyzer-rules-state.md`（RD_STATE_001~006）
- `docs/analysis/codex_rdc_analyzer/2026-01-20-rdc-analyzer-rules-mobile.md`（RD_MOBILE_001~006）

---

## 2.2) Schema / 对外契约文档（为什么 compare 现在会不可信）

- `docs/analysis/codex_rdc_analyzer/2026-01-20-rdc-analyzer-schema-single-analysis.md`  
  WHAT：单个 RDC 的 JSON/HTML 输出结构（新旧两套）  
  WHY：多套 schema 并存会直接导致结论不可对比/不可验证  
  HOW：给出 as-is 结构骨架 + 字段来源 + 风险点

- `docs/analysis/codex_rdc_analyzer/2026-01-20-rdc-analyzer-schema-compare.md`  
  WHAT：对比输入（load_json_data）+ 对比输出（export_json_diff）的结构  
  WHY：Phase1->Phase2 兼容层会补 0/空列表，结论可能失真  
  HOW：指出根因并给出“唯一输入契约”的建议（与 P0-4 对齐）

---

## 2.3) 产品形态与竞品调研（A/B/C + A-first 闭环）

- `docs/analysis/codex_rdc_analyzer/2026-01-20-abc-modes-market-and-a-first-loop.md`  
  WHAT：解释 A/B/C 的边界与使用环境；整理市面成熟方案“怎么做”；提炼可抄的设计灵感；明确 A-first 的闭环落地项。  
  WHY：避免功能发散；让后续实现围绕“可信度/证据链/闭环验证”收敛。  
  HOW：从 RenderDoc/PIX/Nsight/Unity/UE 工具链中抽取可复用的产品设计模式。

---

## 2.4) A-first DoD → Repo 执行清单（逐项勾选落地）

- `docs/analysis/codex_rdc_analyzer/2026-01-20-a-first-dod-repo-checklist.md`  
  WHAT：把 A-first DoD（7.1~7.8）映射到 `scripts/rdc_analyzer/` 的具体文件/模块，并提供可勾选的落地清单。  
  WHY：避免“DoD 很对但落不到代码”，让执行的人按文件/模块推进，不跑偏。  
  HOW：对每项 DoD 给出：涉及文件 + 勾选任务 + 验证方式（命令仅记录）。

---

## 3) 约定（避免未来再次失控）

- 每新增一个“功能文档”，必须含 **WHAT / WHY / HOW**，并且要写清楚“对当前项目的真实状态有什么要求/依赖”。  
- 单文件超过 800 行：必须拆分，并在原文处留下链接 stub。  
- 结论必须能落到：  
  - 目标 1：单个 RDC 的“极致性能分析 + 建议”  
  - 目标 2：两个 RDC 的“全方位对比 + 结论”
---

## 4) 补充功能清单（来自 MD/源码扫描）

> 每个功能 **WHAT / WHY / HOW**，写在本节内。

### 4.1 RDC -> HTML 一键转换

- WHAT：提供 `rdc_to_html.py` 将 .rdc 直接转换为 HTML 报告（含 RenderDoc Shell 用法）。
- WHY：这是“单个 RDC 快速可视化”的最短路径，直接支撑核心目标 1。
- HOW：
  - CLI：`py -3 scripts/rdc_analyzer/rdc_to_html.py <rdc> -o <report.html>`
  - RenderDoc Shell：`rdc_to_html_from_context(pyrenderdoc)`

### 4.2 Mali Shader 性能分析

- WHAT：使用 Mali Offline Compiler 对 .rdc 中 shader 做性能估算。
- WHY：移动端 GPU 是你的核心场景，Shader 瓶颈是高频问题源。
- HOW：`analyze_rdc.py` + `mali_analyzer.py` + `USAGE_MALI_ANALYZER.md`。

### 4.3 XML -> HTML 离线路径

- WHAT：用 RenderDoc 导出的 XML 生成 HTML 报告。
- WHY：缺少 renderdoc Python 模块时，XML 路径可作为离线替代方案。
- HOW：`py -3 analyze_xml_report.py capture.xml -o report.html`。

### 4.4 Diff / Regression + HTML 对比

- WHAT：diff 引擎 + regression detector + 对比 HTML 导出。
- WHY：直接支撑核心目标 2（双 RDC 全方位对比 + 结论）。
- HOW：`generate_diff_report.py` + `diff/diff_engine.py` + `diff/regression_detector.py`。

### 4.5 HTML 导出层与离线报告

- WHAT：HTML exporter / offline report 生成链路。
- WHY：报告模板与渲染逻辑是交付可视化结果的基础资产。
- HOW：`exporters/html_exporter.py` / `generate_offline_report.py`。

### 4.6 纹理浏览 UI：搜索 / 筛选 / 排序

- WHAT：纹理搜索、筛选、排序能力。
- WHY：缩短“定位异常纹理”的时间，是单帧分析效率提升的核心体验点。
- HOW：见 `docs/MILESTONE_SUMMARY.md` 的 UI 功能条目与说明。

---

## 5) RDC -> HTML 实测（g145.rdc）

- WHAT：将 `D:\renderdoc\goog pixel-9\g145.rdc` 生成 HTML 报告。
- WHY：验证真实 RDC 的“快速查看 + HTML 展示”能力。
- HOW：
  - 已尝试：`py -3 scripts/rdc_analyzer/rdc_to_html.py g145.rdc -o g145_report.html`
  - 结果：本机 Python 环境缺少 `renderdoc` 模块，无法直接运行 CLI 模式。
  - 追加尝试：设置 `PYTHONPATH=D:\Code\git\renderdoc\x64\Development\pymodules` 且 PATH 指向 `x64\Development` 后仍提示缺少 `renderdoc` 模块。
  - 推荐：在 RenderDoc UI 的 Python Shell 中执行：
    - `exec(open(r"D:\Code\git\renderdoc\scripts\rdc_analyzer\rdc_to_html.py").read())`
    - `rdc_to_html_from_context(pyrenderdoc)`
  - 离线路径（已执行）：使用已导出的 `g145_capture.xml` 生成 HTML 成功。
    - 命令：`py -3 scripts/rdc_analyzer/analyze_xml_report.py g145_capture.xml -o D:\renderdoc\goog pixel-9\g145_report.html`
    - 输出：`D:\renderdoc\goog pixel-9\g145_report.html`（已生成）
    - 关键结果：180 events / 136 draw calls / 100 textures / Score 41.0/100
    - 重新导出（XML→HTML，2026-01-24）：`D:\renderdoc\goog pixel-9\g145_report_reexport.html`
    - 重新导出命令：`py -3 scripts/rdc_analyzer/analyze_xml_report.py g145_capture.xml -o D:\renderdoc\goog pixel-9\g145_report_reexport.html`
    - 验证点（已通过）：
      - HTML 文件存在且 > 0 字节
      - HTML 包含 `<!DOCTYPE html>`
      - 输出统计与脚本日志一致（events/draw calls/textures/score）

---

## 6) 结构图：主链路 / 辅助链路

```
RDC (.rdc)
  ├─ rdc_to_html.py ───────────────> HTML report
  ├─ analyze_rdc.py ───────────────> JSON + HTML (Mali Shader)
  ├─ export_textures.py ─┐
  │                     └─ generate_offline_report.py ─> HTML
  └─ (RenderDoc XML) -> analyze_xml_report.py ────────> HTML

Compare (A/B)
  JSON A + JSON B ──> diff_engine / regression_detector ──> diff.html
```

- 主链路（核心目标直达）：`rdc_to_html.py` / `analyze_rdc.py` / `generate_diff_report.py`
- 辅助链路（兜底 / 离线 / 批量）：XML->HTML / offline export / batch analyze


---

## 5.1 首次拿到 RDC 的流程（按“export / compile”两条路）

- WHAT：第一次拿到 .rdc 时的标准处理流程（两条路径可选）。
- WHY：保证“首次拿到就能出 HTML 报告”，并与文档里写的“export/编译”保持一致。
- HOW：
  - 路线 A（export 路线，当前已验证可用）
    1) 获取 XML（来自 RenderDoc UI 导出或你们现有的导出脚本/流程）
    2) 运行 `analyze_xml_report.py` 生成 HTML
    3) 产物就是 HTML 报告（本次 g145 已通过该路线生成）
  - 路线 B（compile 路线，直接 .rdc → HTML）
    1) 编译 RenderDoc，产出 `renderdoc.pyd` 及其依赖 DLL
    2) 设置 `PYTHONPATH` 指向 `pymodules`
    3) 运行 `rdc_to_html.py` 直接从 .rdc 生成 HTML
    4) 该路线目前在本机尚未可用（renderdoc 模块导入失败，原因是 DLL 依赖/版本匹配问题）


---

## 7) 导出阻塞说明（export/compile）

- WHAT：当前“程序化导出”链路的阻塞点说明
- WHY：解释为何无法直接从 .rdc 进行 export（路线 C / compile 路线）
- HOW：
  - 系统安装版 `renderdoccmd.exe` 不包含 `export` 命令（无法程序化导出）
  - 源码版编译 `renderdoccmd` 失败：缺少 `D:\util\WindowsSDKTarget.props`


---

## 7.1 renderdoccmd --export-xml 线索说明

- WHAT：说明 `renderdoccmd --export-xml` 的实现线索与缺失情况
- WHY：解释 XML 产出为何无法在当前源码中复现
- HOW：
  - `scripts/rdc_analyzer/analyze_xml_report.py` 文档提示 `renderdoccmd capture.rdc --export-xml capture.xml`
  - 当前源码 `renderdoccmd/renderdoccmd.cpp` 中未发现 `--export-xml` 选项实现（仅支持纹理/metadata/bindings 导出）
  - 结论：XML 可能来自历史分支或外部定制版 renderdoccmd 的程序化导出
