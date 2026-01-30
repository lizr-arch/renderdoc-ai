# 2026-01-23 Continue2 综合报告（A/B/C 全覆盖）

> 目的：在不新增代码的前提下，完成“继续2”的源码级核对、重复/冗余清单与下一阶段最小闭环任务清单（均含 WHAT/WHY/HOW）。
> 范围：仅覆盖 `scripts/rdc_analyzer/`（不评价 RenderDoc 主工程 C++ 代码本体）。
> 成功标准：A/B/C 三部分各给出 ≥8 个源码证据点；至少 5 组重复/冗余判断；下一阶段 6-10 个任务按 P0/P1 排序。

## 0. 导航证据与限制

### 0.1 codemap 查询（无命中）
1) `codemap 'AnalysisPipeline' -Num 20 -Ctx 1` → No matches  
2) `codemap 'analysis_pipeline' -Num 20 -Ctx 1` → No matches  
3) `codemap 'rdc_analyzer' -Num 20 -Ctx 1` → No matches  

**原因**：当前 codemap 未索引本仓库（或索引不可用）。  

### 0.2 Serena 兜底限制
Serena 对 `scripts/rdc_analyzer` 标记为 ignored，无法直接访问该目录；因此改用 `rg -n` 做最小化取证。  

### 0.3 证据候选（至少 3 个）
- `[renderdoc] scripts/rdc_analyzer/main.py:157` `class AnalysisPipeline:`  
- `[renderdoc] scripts/rdc_analyzer/pipeline.py:23` `class AnalysisPipeline:`  
- `[renderdoc] scripts/rdc_analyzer/compare_rdc.py:122` `Phase 2 期望的字典格式`  

### 0.4 跟进点与下一步
- 跟进点：`main.py:1115+` 与 `pipeline.py:23+`（核对主管线与导出逻辑）。  
- 下一步：用 `rg -n` 定位 + `Get-Content` 小片段核对（已完成最小读取）。  

## 1. 我对“文档很多”的想法（简短版）

### 1.1 WHAT
文档数量多是合理的，但必须“入口唯一 + 证据可追溯 + 单文档 < 800 行”。  

### 1.2 WHY
当前体系存在多条并行链路（新管线/旧管线/离线路径/对比路径）。没有清晰索引，团队会各自解读，导致口径分裂，直接冲击“极致分析 + 全方位对比”的目标可信度。  

### 1.3 HOW
唯一入口放在 `docs/analysis/codex_rdc_analyzer/README.md`，并将“证据驱动的结论”集中在一份主报告（本文件），其余文档只做分题扩展。  

## A. 源码级核对补充报告（≥8）

### A1. 存在两个 `AnalysisPipeline`（新/旧并行）
- **WHAT**：`main.py` 与 `pipeline.py` 都定义 `AnalysisPipeline`。  
- **WHY**：主分析入口不唯一，输出口径和数据源分裂风险高。  
- **HOW**：明确“唯一主管线”，其余管线只保留为实验/兼容。  
- **Evidence**：  
  - `scripts/rdc_analyzer/main.py:157` `class AnalysisPipeline:`  
  - `scripts/rdc_analyzer/pipeline.py:23` `class AnalysisPipeline:`  

### A2. 新管线规则逻辑是“内置简化版”，未接入 RuleRunner
- **WHAT**：`main.py` 使用 `_analyze_rules()` 直接拼接 BIND001/BIND002 与简化性能分析。  
- **WHY**：规则系统与旧管线的 `RuleRunner`/`RuleRegistry` 输出口径不一致。  
- **HOW**：统一改为 RuleRunner 或提供明确的兼容输出转换。  
- **Evidence**：  
  - `scripts/rdc_analyzer/main.py:485` `def _analyze_rules(self):`  
  - `scripts/rdc_analyzer/pipeline.py:53` `register_all_rules()`  
  - `scripts/rdc_analyzer/pipeline.py:103` `runner = RuleRunner(context)`  

### A3. 覆盖率/生命周期数据被标记为“estimated”
- **WHAT**：资源生命周期/管线状态缺少真实追踪时被标记为估算值。  
- **WHY**：这会降低“极致分析”可信度，影响建议/验证链路。  
- **HOW**：将 ReplayWrapper/ResourceTracker 等真实数据源接入主链路。  
- **Evidence**：  
  - `scripts/rdc_analyzer/main.py:1161` `访问信息标记为 "estimated"`  
  - `scripts/rdc_analyzer/main.py:1177-1193` `first_access_event/read_count = -1`  
  - `scripts/rdc_analyzer/main.py:1345-1351` `pipeline_state = 'estimated'`  
  - `scripts/rdc_analyzer/main.py:1364` `resource_lifecycle = 'estimated'`  

### A4. 新管线导出明确标记 `schema_version = 1.0`
- **WHAT**：输出为 `analysis_data` 且 schema_version 固定为 1.0。  
- **WHY**：对比链路仍兼容多种历史格式，存在“隐性兼容逻辑”。  
- **HOW**：确立 canonical schema 为唯一输入/输出协议。  
- **Evidence**：  
  - `scripts/rdc_analyzer/main.py:1059-1060` `analysis_data = { 'schema_version': '1.0', ... }`  

### A5. compare 仍在兼容 Phase1/Phase2 结构
- **WHAT**：compare 支持 Phase1 列表格式与 Phase2 字典格式。  
- **WHY**：这说明上游输出未统一，导致 diff 结果依赖“猜字段”。  
- **HOW**：统一分析输出为 Phase2/canonical，废弃 Phase1。  
- **Evidence**：  
  - `scripts/rdc_analyzer/compare_rdc.py:122-154` `Phase 1/Phase 2` 兼容处理  

### A6. compare CLI 已存在并支持多帧汇总
- **WHAT**：`python -m rdc_analyzer compare` 与 `cmd_compare_multi_frame` 已实现。  
- **WHY**：对比是目标 2 的核心能力，应该成为主入口而非旁路脚本。  
- **HOW**：让 compare 直接接入 canonical schema & 输出统一报告。  
- **Evidence**：  
  - `scripts/rdc_analyzer/__main__.py:35` `compare   对比两个 RDC/JSON 文件`  
  - `scripts/rdc_analyzer/__main__.py:527` `def cmd_compare(args):`  
  - `scripts/rdc_analyzer/__main__.py:700` `def cmd_compare_multi_frame(args):`  

### A7. XML 离线路径独立存在
- **WHAT**：XML 解析与桥接独立链路，不走主管线。  
- **WHY**：离线分析是重要补偿路径，但输出口径需要与主线对齐。  
- **HOW**：XML -> canonical schema 的标准化转换。  
- **Evidence**：  
  - `scripts/rdc_analyzer/core/bridge.py:28` `class XMLToContextBridge:`  
  - `scripts/rdc_analyzer/parse_rdc_xml.py:462` `def parse_rdc_xml(xml_path):`  

### A8. 纹理导出 + 离线报告是并行独立链路
- **WHAT**：TextureExporter 与 generate_offline_html 形成独立报告通路。  
- **WHY**：功能强但与主分析输出口径不一致，难以复用建议链路。  
- **HOW**：将离线纹理报告视为 canonical schema 的一个视图。  
- **Evidence**：  
  - `scripts/rdc_analyzer/export_textures.py:40` `class TextureExporter:`  
  - `scripts/rdc_analyzer/generate_offline_report.py:155` `def generate_offline_html(...)`  

### A9. 二进制/离线解析路径另起一套
- **WHAT**：BinaryParser 与 rdc_parser.py 形成独立离线解析路径。  
- **WHY**：这说明“离线能力”与“回放能力”并存，需要统一输出。  
- **HOW**：离线解析只负责数据采集，输出统一进入 canonical schema。  
- **Evidence**：  
  - `scripts/rdc_analyzer/parsers/binary_parser.py:270` `class BinaryParser(BaseParser):`  
  - `scripts/rdc_analyzer/rdc_parser.py:2870` `Usage: python rdc_parser.py ...`  

## B. 重复/冗余清单 + 去重决策（≥5）

### B1. 双 AnalysisPipeline（main.py vs pipeline.py）
- **WHAT**：两个管线并存且命名一致。  
- **WHY**：团队入口/输出分裂，导致“极致分析”口径无法统一。  
- **HOW**：保留 `main.py` 作为主入口；`pipeline.py` 仅保留兼容或迁移到内部组件。  
- **决策**：合并（保留 main 为唯一主入口）。  
- **Evidence**：`scripts/rdc_analyzer/main.py:157`、`scripts/rdc_analyzer/pipeline.py:23`  

### B2. 双报告体系（reporters vs exporters）
- **WHAT**：旧管线用 `reporters/*`，新管线用 `exporters/html_exporter.py`。  
- **WHY**：导出逻辑重复维护，输出格式分裂。  
- **HOW**：统一导出为 canonical schema + 单一 HTML/JSON exporter。  
- **决策**：合并（弃用 reporters 或仅作为 legacy）。  
- **Evidence**：  
  - `scripts/rdc_analyzer/pipeline.py:20` `JSONReporter/HTMLReporter`  
  - `scripts/rdc_analyzer/reporters/html_reporter.py:15` `class HTMLReporter`  
  - `scripts/rdc_analyzer/exporters/html_exporter.py:53` `class HTMLExporter`  
  - `scripts/rdc_analyzer/main.py:1117` `from .exporters.html_exporter import ...`  

### B3. 多个 CLI/脚本入口并行
- **WHAT**：`__main__.py`、`compare_rdc.py`、`parse_rdc_xml.py`、`rdc_parser.py` 都是入口。  
- **WHY**：使用路径分裂，导致“统一验收/统一输出”困难。  
- **HOW**：全部入口最终汇入 `python -m rdc_analyzer <subcommand>`。  
- **决策**：合并入口（脚本保留但降级为内部工具）。  
- **Evidence**：  
  - `scripts/rdc_analyzer/__main__.py:35` compare 子命令  
  - `scripts/rdc_analyzer/compare_rdc.py:10` `python compare_rdc.py ...`  
  - `scripts/rdc_analyzer/parse_rdc_xml.py:6` `py -3 parse_rdc_xml.py ...`  
  - `scripts/rdc_analyzer/rdc_parser.py:2870` `Usage: python rdc_parser.py ...`  

### B4. 双 schema 兼容（Phase1/Phase2 + schema_version 1.0）
- **WHAT**：compare 兼容 Phase1 列表格式；main 输出 schema_version 1.0。  
- **WHY**：schema 漂移让 diff 结果依赖“猜字段/估算”。  
- **HOW**：定义 canonical schema，并明确弃用 Phase1。  
- **决策**：收敛到 canonical schema。  
- **Evidence**：  
  - `scripts/rdc_analyzer/compare_rdc.py:122-154`  
  - `scripts/rdc_analyzer/main.py:1059-1060`  

### B5. 规则/性能分析两套实现
- **WHAT**：旧管线 RuleRunner + 规则体系；新管线自建 `_analyze_rules()`。  
- **WHY**：规则口径不一致，最终建议链条割裂。  
- **HOW**：统一为 RuleRunner 产出 canonical issue；保留 _analyze_rules 作为兼容适配器。  
- **决策**：合并规则出口。  
- **Evidence**：  
  - `scripts/rdc_analyzer/main.py:485` `_analyze_rules`  
  - `scripts/rdc_analyzer/pipeline.py:53` `register_all_rules()`  
  - `scripts/rdc_analyzer/pipeline.py:103` `RuleRunner(context)`  

## C. 下一阶段最小闭环 + 真实数据链验证清单（6-10 项）

### P0（必须做）
**P0-1 统一 Canonical Schema（单帧 + 对比）**  
- WHAT：定义唯一 `analysis.json` / `diff.json` 结构，作为所有入口输出。  
- WHY：对比核心价值依赖“统一字段”；否则结果只能做启发式估算。  
- HOW：将 `main.py` 输出与 `compare_rdc.py` 输入统一为同一 schema；逐步废弃 Phase1。  
- Evidence：`scripts/rdc_analyzer/main.py:1059-1060`、`scripts/rdc_analyzer/compare_rdc.py:122-154`  

**P0-2 接入真实数据链（ReplayWrapper/ResourceTracker）**  
- WHAT：将资源生命周期、pipeline_state 等从估算改为真实追踪。  
- WHY：这是“极致分析”的核心，否则建议链不可验证。  
- HOW：在主管线使用 ReplayWrapper 生成真实 pipeline snapshot，再喂给 ResourceTracker/CallAnalyzer。  
- Evidence：`scripts/rdc_analyzer/main.py:1161-1193`、`scripts/rdc_analyzer/extractors/replay_wrapper.py:109`  

**P0-3 规则系统统一出口**  
- WHAT：新旧管线统一由 RuleRunner 产出 canonical issues。  
- WHY：否则规则口径不同，建议与对比结论无法对齐。  
- HOW：`_analyze_rules()` 内部改为调用 RuleRunner 或转换 RuleRunner 输出到 canonical issue。  
- Evidence：`scripts/rdc_analyzer/main.py:485`、`scripts/rdc_analyzer/pipeline.py:103`  

**P0-4 Compare 入口闭环化**  
- WHAT：`python -m rdc_analyzer compare` 接受 `.rdc`，自动生成 canonical JSON 再 diff。  
- WHY：对比是目标 2，必须成为“默认路径”。  
- HOW：在 `cmd_compare` 内集成 analyze -> canonical -> diff 的流水线。  
- Evidence：`scripts/rdc_analyzer/__main__.py:35`、`scripts/rdc_analyzer/compare_rdc.py:122`  

**P0-5 证据链字段标准化（verification_plan）**  
- WHAT：保证建议/验证计划字段命名统一、可机器消费。  
- WHY：缺少统一字段会导致“建议→验证”链无法自动化落地。  
- HOW：固定 `verification_plan.expected_direction` 等字段并纳入 schema 文档。  
- Evidence：`scripts/rdc_analyzer/main.py:1562-1790`  

**P0-6 阈值注入一致性**  
- WHAT：确保 AnalysisContext 总是带 thresholds（平台阈值一致）。  
- WHY：规则阈值不一致会导致同一 capture 在不同管线结论冲突。  
- HOW：统一使用 `BaseParser.create_context()` 或显式传入 thresholds。  
- Evidence：`scripts/rdc_analyzer/parsers/base.py:59-65`、`scripts/rdc_analyzer/pipeline.py:66`  

### P1（重要但可后置）
**P1-1 入口统一与脚本降级**  
- WHAT：把 `compare_rdc.py` / `parse_rdc_xml.py` / `rdc_parser.py` 变成内部工具。  
- WHY：减少入口分裂，便于统一验收与用户路径。  
- HOW：保留脚本但在 README 强调统一入口为 `python -m rdc_analyzer`。  
- Evidence：`scripts/rdc_analyzer/compare_rdc.py:10`、`scripts/rdc_analyzer/parse_rdc_xml.py:6`、`scripts/rdc_analyzer/rdc_parser.py:2870`  

**P1-2 报告系统收敛**  
- WHAT：统一 HTML/JSON 输出逻辑，避免双体系维护。  
- WHY：当前 reporters 与 exporters 双套实现，长期维护成本高。  
- HOW：确定单一导出器并迁移旧 reporter 使用者。  
- Evidence：`scripts/rdc_analyzer/pipeline.py:20`、`scripts/rdc_analyzer/exporters/html_exporter.py:53`  

