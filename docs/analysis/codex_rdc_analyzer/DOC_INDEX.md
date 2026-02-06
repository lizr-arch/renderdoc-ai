# DOC_INDEX — 文档阅读入口（必读）

- WHAT: 提供 RDC Analyzer 文档的统一阅读入口与快速索引。
- WHY: 避免“找不到/记不住文档”，提升检索效率。
- HOW: 每个文档给出简介、关键词与适用链路（A/B/C）。

---

## 阅读顺序（建议）

1. `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md`（阅读总览）
2. `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROUTES.md`（A/B/C 路线）
3. `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_SCHEMA.md`（Schema/Bridge）
4. `docs/analysis/codex_rdc_analyzer/2025-01-31-rdc-analyzer-data-richness-baseline.md`（数据丰富度基线）
5. `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_VERIFICATION.md`（验证流程）
6. `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROADMAP.md`（优先级/计划）
7. `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_BUILD.md`（环境/编译）

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

### 2025-01-31-rdc-analyzer-data-richness-baseline（数据丰富度基线）
- 简介：对标 RenderDoc 源码字段，给出 A+C 覆盖/缺口与是否需 replay 的边界。
- 关键词：data richness, coverage, RenderDoc baseline, replay
- 适用路线：A/B/C
- 路径：`docs/analysis/codex_rdc_analyzer/2025-01-31-rdc-analyzer-data-richness-baseline.md`

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

### 2025-02-01-ui-refactor-summary（UI 重构升级总结）
- 简介：按计划逐条对照，解释 v2 UI 架构、流程与调用链。
- 关键词：ui refactor, contract, manifest, shell
- 适用链路：A/C
- 路径：`docs/analysis/codex_rdc_analyzer/2025-02-01-ui-refactor-summary.md`

### DATA_SOURCES_INDEX（数据来源方式总表）
- 简介：统一记录数据来源分类、可用性与限制（可持续补充）。
- 关键词：data sources, xml, json, replay, mali
- 适用链路：A/B/C
- 路径：`docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`

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

### scripts/rdc_analyzer/docs/INDEX（工具文档索引）
- 简介：rdc_analyzer 工具的本地文档索引，含纹理提取、Unity 导出、Mali 集成等。
- 关键词：texture, unity, mali, rdc format
- 适用链路：A/B/C
- 路径：`scripts/rdc_analyzer/docs/INDEX.md`

### TEXTURE_EXTRACTION（纹理提取速查）
- 简介：三种纹理提取方案（CLI/Python/元数据）对比与用法。
- 关键词：texture, export, SaveTexture, renderdoccmd
- 适用链路：C
- 路径：`scripts/rdc_analyzer/docs/TEXTURE_EXTRACTION.md`

### WHY_XML_ZIP_VK_UNREADABLE（Vulkan XML+ZIP 缩略图不可读原因）
- 简介：解释 Vulkan XML+ZIP 缩略图不可读的根因与为何必须走 GPU replay/export。
- 关键词：vulkan, xml+zip, tiling, rowPitch, replay
- 适用链路：B/C
- 路径：`docs/analysis/codex_rdc_analyzer/WHY_XML_ZIP_VK_UNREADABLE.md`

### rdc_format_spec（RDC 格式规范）
- 简介：RDC 文件二进制结构、Section 布局、Chunk 格式。
- 关键词：rdc, binary, section, chunk
- 适用链路：A/B/C
- 路径：`scripts/rdc_analyzer/docs/rdc_format_spec.md`

---

## 🆕 RDC 格式入门系列（新人友好）

> 以下文档专为新人程序员设计，使用类比和具体示例解释 RDC 文件结构。

### 01_RDC_INTRO（RDC 入门指南）
- 简介：用"游戏录像"和"书籍"类比解释 RDC 是什么、整体结构是什么。
- 关键词：intro, analogy, beginner, movie, book
- 适用链路：A/B/C（入门必读）
- 路径：`docs/analysis/codex_rdc_analyzer/rdc_format/01_RDC_INTRO.md`

### 02_RDC_STRUCTURE（二进制结构详解）
- 简介：逐字节解释 FileHeader、Thumbnail、Metadata、Section、Chunk 的二进制布局。
- 关键词：binary, bytes, header, section, chunk, hex
- 适用链路：A/B/C
- 路径：`docs/analysis/codex_rdc_analyzer/rdc_format/02_RDC_STRUCTURE.md`

### 03_RDC_EXAMPLE（数据示例）
- 简介：用一个 3D 游戏场景展示 RDC 中的真实数据：GPU 命令序列、Chunk 参数、XML、JSON 报告。
- 关键词：example, scene, draw call, xml, json, triangle
- 适用链路：A/B/C
- 路径：`docs/analysis/codex_rdc_analyzer/rdc_format/03_RDC_EXAMPLE.md`

---

## 维护约定
- 新文档必须补充到本索引（简介 + 关键词 + 适用链路）。
- 索引条目保持简短，单条不超过 4 行。
### 2025-01-19-rdc-analyzer-capability-scorecard（RDC Analyzer 能力盘点 / 冲突点 / 路线图（Codex 专属笔记））
- 简介：未标注（原因：源文档无 WHAT 段）
- 关键词：未标注（原因：源文档无关键词段）
- 适用路线：未标注（原因：源文档无适用路线段）
- 路径：`docs/analysis/codex_rdc_analyzer/2025-01-19-rdc-analyzer-capability-scorecard.md`

### 2025-01-19-rdc-analyzer-feature-details（RDC Analyzer 功能明细（WHAT / WHY / HOW））
- 简介：未标注（原因：源文档无 WHAT 段）
- 关键词：未标注（原因：源文档无关键词段）
- 适用路线：未标注（原因：源文档无适用路线段）
- 路径：`docs/analysis/codex_rdc_analyzer/2025-01-19-rdc-analyzer-feature-details.md`

### 2025-01-19-rdc-analyzer-key-deep-dive（RDC Analyzer 深度下钻（WHAT / WHY / HOW））
- 简介：未标注（原因：源文档无 WHAT 段）
- 关键词：未标注（原因：源文档无关键词段）
- 适用路线：未标注（原因：源文档无适用路线段）
- 路径：`docs/analysis/codex_rdc_analyzer/2025-01-19-rdc-analyzer-key-deep-dive.md`

### 2025-01-20-a-first-dod-repo-checklist（A-first DoD → Repo 执行清单（逐项勾选版））
- 简介：`py -3 -m rdc_analyzer analyze <capture.rdc> -o <out_dir> --format html,json` 能跑通
- 关键词：未标注（原因：源文档无关键词段）
- 适用路线：未标注（原因：源文档无适用路线段）
- 路径：`docs/analysis/codex_rdc_analyzer/2025-01-20-a-first-dod-repo-checklist.md`

### 2025-01-20-abc-modes-market-and-a-first-loop（RDC Analyzer：A/B/C 产品形态、使用场景与成熟方案调研（A 为第一闭环））
- 简介：同一份 capture，所有输出都围绕一套统一 schema（事件/资源/draw/pass/state/统计/issues/suggestions）。
- 关键词：未标注（原因：源文档无关键词段）
- 适用路线：未标注（原因：源文档无适用路线段）
- 路径：`docs/analysis/codex_rdc_analyzer/2025-01-20-abc-modes-market-and-a-first-loop.md`

### 2025-01-20-rdc-analyzer-rules-buffer（RDC Analyzer 规则详解：Buffer（6 条））
- 简介：未标注（原因：源文档无 WHAT 段）
- 关键词：未标注（原因：源文档无关键词段）
- 适用路线：未标注（原因：源文档无适用路线段）
- 路径：`docs/analysis/codex_rdc_analyzer/2025-01-20-rdc-analyzer-rules-buffer.md`

### 2025-01-20-rdc-analyzer-rules-draw-call（RDC Analyzer 规则详解：Draw Call（5 条））
- 简介：你现在“规则文档（RULES.md）里写的 36 条规则”，在 CLI 的 `rules --list` 里能看到，但在 `analyze` 的输出里不一定会出现。
- 关键词：未标注（原因：源文档无关键词段）
- 适用路线：未标注（原因：源文档无适用路线段）
- 路径：`docs/analysis/codex_rdc_analyzer/2025-01-20-rdc-analyzer-rules-draw-call.md`

### 2025-01-20-rdc-analyzer-rules-mobile（RDC Analyzer 规则详解：Mobile（6 条））
- 简介：移动端的关键不是“draw call 多一点”，而是**tile flush / 带宽 / overdraw / load-store 行为**。
- 关键词：未标注（原因：源文档无关键词段）
- 适用路线：未标注（原因：源文档无适用路线段）
- 路径：`docs/analysis/codex_rdc_analyzer/2025-01-20-rdc-analyzer-rules-mobile.md`

### 2025-01-20-rdc-analyzer-rules-pass（RDC Analyzer 规则详解：Pass（7 条））
- 简介：未标注（原因：源文档无 WHAT 段）
- 关键词：未标注（原因：源文档无关键词段）
- 适用路线：未标注（原因：源文档无适用路线段）
- 路径：`docs/analysis/codex_rdc_analyzer/2025-01-20-rdc-analyzer-rules-pass.md`

### 2025-01-20-rdc-analyzer-rules-state（RDC Analyzer 规则详解：State（6 条））
- 简介：未标注（原因：源文档无 WHAT 段）
- 关键词：未标注（原因：源文档无关键词段）
- 适用路线：未标注（原因：源文档无适用路线段）
- 路径：`docs/analysis/codex_rdc_analyzer/2025-01-20-rdc-analyzer-rules-state.md`

### 2025-01-20-rdc-analyzer-rules-texture（RDC Analyzer 规则详解：Texture（6 条））
- 简介：规则并不是直接扫 `main.py` 的 `resources['textures']` 字典，而是扫 `context.textures` 这种“结构化对象”。
- 关键词：未标注（原因：源文档无关键词段）
- 适用路线：未标注（原因：源文档无适用路线段）
- 路径：`docs/analysis/codex_rdc_analyzer/2025-01-20-rdc-analyzer-rules-texture.md`

### 2025-01-20-rdc-analyzer-schema-compare（RDC Analyzer 输出口径：对比两个 RDC（输入/输出 Schema 说明））
- 简介：输出顶层结构是什么？
- 关键词：未标注（原因：源文档无关键词段）
- 适用路线：未标注（原因：源文档无适用路线段）
- 路径：`docs/analysis/codex_rdc_analyzer/2025-01-20-rdc-analyzer-schema-compare.md`

### 2025-01-20-rdc-analyzer-schema-single-analysis（RDC Analyzer 输出口径：单个 RDC（JSON/HTML）Schema 说明）
- 简介：Schema 不是“导出 JSON 的字段列表”，而是“工具对外契约”。
- 关键词：未标注（原因：源文档无关键词段）
- 适用路线：未标注（原因：源文档无适用路线段）
- 路径：`docs/analysis/codex_rdc_analyzer/2025-01-20-rdc-analyzer-schema-single-analysis.md`

### 2025-01-21-a-first-plan-audit（A-first Execution Plan Audit (Reviewer Report)）
- 简介：** 顶层块必须稳定 + 文档/输出一致。
- 关键词：未标注（原因：源文档无关键词段）
- 适用路线：未标注（原因：源文档无适用路线段）
- 路径：`docs/analysis/codex_rdc_analyzer/2025-01-21-a-first-plan-audit.md`

### 2025-01-23-rdc-analyzer-architecture-review（RDC Analyzer 架构复审 & A-first 缺口清单（2025-01-23））
- 简介：CLI 入口在 `scripts/rdc_analyzer/__main__.py:23`，`analyze` **默认已走** `main.py` 的 AnalysisPipeline（仅在 ImportError 时回退旧管线）。
- 关键词：未标注（原因：源文档无关键词段）
- 适用路线：未标注（原因：源文档无适用路线段）
- 路径：`docs/analysis/codex_rdc_analyzer/2025-01-23-rdc-analyzer-architecture-review.md`

### 2025-01-23-rdc-analyzer-continue2-report（2025-01-23 Continue2 综合报告（A/B/C 全覆盖））
- 简介：定义唯一 `analysis.json` / `diff.json` 结构，作为所有入口输出。
- 关键词：未标注（原因：源文档无关键词段）
- 适用路线：未标注（原因：源文档无适用路线段）
- 路径：`docs/analysis/codex_rdc_analyzer/2025-01-23-rdc-analyzer-continue2-report.md`

### P2_MOBILE_GPU_ANALYSIS_DESIGN（P2 设计文档：移动 GPU 专项分析扩展）
- 简介：未标注（原因：源文档无 WHAT 段）
- 关键词：未标注（原因：源文档无关键词段）
- 适用路线：未标注（原因：源文档无适用路线段）
- 路径：`docs/analysis/codex_rdc_analyzer/P2_MOBILE_GPU_ANALYSIS_DESIGN.md`

### README（Codex：RDC Analyzer 文档索引（长期保留））
- 简介：继续2综合报告（A/B/C 全覆盖）：源码级核对、重复/冗余清单、下一阶段最小闭环任务。
- 关键词：未标注（原因：源文档无关键词段）
- 适用路线：未标注（原因：源文档无适用路线段）
- 路径：`docs/analysis/codex_rdc_analyzer/README.md`
