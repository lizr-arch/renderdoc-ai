# DOC_INDEX — 文档阅读入口（必读）

- WHAT: 提供 RDC Analyzer 文档的统一阅读入口与快速索引。
- WHY: 避免“找不到/记不住文档”，提升检索效率。
- HOW: 每个文档给出简介、关键词与适用链路（A/B/C）。

---

## 阅读顺序（建议）
1. `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md`（总索引）
2. `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROUTES.md`（A/B/C 路线）
3. `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_SCHEMA.md`（Schema/Bridge）
4. `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_VERIFICATION.md`（验证流程）
5. `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROADMAP.md`（优先级/计划）
6. `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_BUILD.md`（环境/编译）

---

## 索引条目（简介 + 关键词 + 适用链路）

### WORK_SUMMARY_2025-01-21（总索引）
- 简介：项目主入口索引，列出核心主题文档与阅读顺序。
- 关键词：index, overview, reading order
- 适用链路：A/B/C
- 路径：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md`

### WORK_SUMMARY_ROUTES（A/B/C 路线）
- 简介：三条输入路线与验证状态，含 A+C 主路径定位与 B 依赖边界。
- 关键词：routes, A/B/C, XML, Python API, export
- 适用链路：A/B/C
- 路径：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROUTES.md`

### WORK_SUMMARY_SCHEMA（Schema / Bridge）
- 简介：Canonical Schema v1、Bridge、DiffEngine 关键字段映射。
- 关键词：schema, bridge, canonical, diff
- 适用链路：A/B
- 路径：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_SCHEMA.md`

### WORK_SUMMARY_VERIFICATION（验证流程）
- 简介：CLI 验证命令、通过记录、证据链要求。
- 关键词：verification, pytest, evidence
- 适用链路：A/B/C
- 路径：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_VERIFICATION.md`

### WORK_SUMMARY_ROADMAP（路线图）
- 简介：任务优先级、决策记录、后续规划。
- 关键词：roadmap, priority, decisions
- 适用链路：A/B/C
- 路径：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROADMAP.md`

### WORK_SUMMARY_BUILD（环境与编译）
- 简介：Python 3.6 + renderdoc.pyd 依赖、编译产物与验证。
- 关键词：build, py36, renderdoc.pyd, renderdoccmd
- 适用链路：B/C
- 路径：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_BUILD.md`

### TASK_TRACKER（任务追踪）
- 简介：A-first/B-mode 任务状态、DoD 完成度、P0 列表。
- 关键词：task tracker, DoD, status
- 适用链路：A/B/C
- 路径：`docs/analysis/codex_rdc_analyzer/TASK_TRACKER.md`

### scripts/rdc_analyzer/README（工具入口）
- 简介：rdc_analyzer CLI 用法与模块入口。
- 关键词：cli, analyze, compare, usage
- 适用链路：A/B/C
- 路径：`scripts/rdc_analyzer/README.md`

### scripts/rdc_analyzer/RULES（规则库）
- 简介：性能规则与阈值说明。
- 关键词：rules, thresholds, issues
- 适用链路：A/B
- 路径：`scripts/rdc_analyzer/RULES.md`

### pipeline-state-data-sources（数据来源）
- 简介：PipelineState 数据来源优先级与字段来源说明。
- 关键词：dataSource, pipeline, priority
- 适用链路：A/B/C
- 路径：`scripts/rdc_analyzer/.ai/docs/pipeline-state-data-sources.md`

### WORK_SUMMARY_ARCH（架构速查）
- 简介：模块结构与关键入口速查表。
- 关键词：architecture, modules, entrypoints
- 适用链路：A/B/C
- 路径：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ARCH.md`

---

## 维护约定
- 新文档必须补充到本索引（简介 + 关键词 + 适用链路）。
- 索引条目保持简短，单条不超过 4 行。
