# Codex：RDC Analyzer 文档索引（长期保留）

> 位置：`docs/analysis/codex_rdc_analyzer/`  
> 目标：把对 `scripts/rdc_analyzer` 的盘点、评分、冲突点、路线图沉淀成**可长期维护**的文档。  
> 约束：单文件控制在 **<= 800 行**（避免阅读/维护成本爆炸）。  
> 更新时间：2026-01-23

---

## 1) 建议阅读顺序（按你关心的问题）

1. **我现在做到了什么？值不值？下一步先做什么？**  
   - 读：`docs/analysis/codex_rdc_analyzer/2026-01-19-rdc-analyzer-capability-scorecard.md`

2. **每个模块到底是干什么的？为什么重要？现在项目里真实状态是什么？**  
   - 读：`docs/analysis/codex_rdc_analyzer/2026-01-19-rdc-analyzer-feature-details.md`

3. **想把“极致/全方位”做成可信工具，最关键的 5–10 个点到底缺什么？**  
   - 读：`docs/analysis/codex_rdc_analyzer/2026-01-19-rdc-analyzer-key-deep-dive.md`

4. **你列的 36 条规则，逐条是什么、为什么、怎么做、当前项目能不能跑起来？**  
   - 读：本目录后续新增的 `*-rules-*.md`（按分类拆分，保证每份可读）

5. **JSON/HTML/对比输出的“口径/字段”到底是什么？为什么 compare 会不可信？怎么统一？**  
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
