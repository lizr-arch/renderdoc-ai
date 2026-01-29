# 2026-01-29 RDC Analyzer 全量文档审阅：进度与展望（深度总结）

> 更新日期: 2026-01-29
> 目标: 基于“已阅读全部相关 .md”的证据，给出当前进度、冲突点、未来展望与 P0 优先级清单。

## 0) 结论摘要（只说事实）
- 当前状态: A-first 框架成型，但“真实数据链 + 验收闭环”未完成，无法宣称完全闭环。
- B-mode/C-mode: 核心能力已实现，但可信度依赖 Canonical Schema 统一与 Replay 数据源恢复。
- 最大阻塞: Replay 环境缺失、完整性比率对齐不足、HTML 视觉验收未覆盖关键空列表。

## 1) 覆盖范围与证据说明（不遗漏任何 .md）
本次审阅覆盖全仓库 .md 文件，共 203 份，分类统计如下：
- core（核心业务/研发文档）: 51
- plan（计划/验收/执行文档）: 36
- support（分析/架构/规则/规范支持文档）: 13
- project（项目级说明/贡献/设计）: 18
- artifact（工具产物/缓存/浏览器扩展）: 27
- other（其他）: 58

## 2) 当前进度（按核心能力拆解，全部提供 WHAT / WHY / HOW）

### 2.1 A-first 单帧闭环
- WHAT: 单个 RDC 生成可读 HTML + 结构化 JSON + 建议/验证计划（证据链）。
- WHY: 这是整个产品闭环的“第一个可落地价值点”，对外展示必须可信。
- HOW: 现有流程包含 XML 导出/解析、分析管线与 HTML 生成；但 Replay 数据源缺失，导致核心资源（纹理/Shader/管线）完整性未闭合。

### 2.2 B-mode 双帧对比（Diff/Regression）
- WHAT: 基于两份分析结果进行全维度对比与回归检测，输出差异与回归建议。
- WHY: 用于验证优化是否真正生效，避免“优化后反而更差”。
- HOW: DiffEngine + RegressionDetector 已形成；但对比输入与单帧输出的 Canonical Schema 尚未完全一致。

### 2.3 C-mode 资产审计
- WHAT: 无需基线的资源审计（纹理大小、重复、缺 mipmap 等），输出可执行建议。
- WHY: 快速找到“资源浪费型问题”，对美术/资产管线有直接价值。
- HOW: 审计规则库已形成，但依赖 A-first 的真实数据源完整性，否则结果易失真。

### 2.4 数据源路线（XML / RenderDoc API / renderdoccmd export）
- WHAT: 三条数据获取路线，分别对应“无依赖/高精度/资源导出”。
- WHY: 解决不同环境下可用性问题，降低对 GPU/replay 的硬依赖。
- HOW: XML 路线最易跑通；Python API 最高精度但依赖 replay；renderdoccmd export 适合资源外导。

### 2.5 规则引擎（Buffer/Texture/Draw/State/Pass/Mobile）
- WHAT: 规则库检测常见性能/资源问题，输出建议与证据。
- WHY: 规则是“建议产生器”，是分析价值的核心载体。
- HOW: 已实现多类规则，但阈值键名与配置存在漂移，导致默认值可能被错误使用。

### 2.6 HTML 验收与可视化审阅
- WHAT: 自动/半自动 UI 验收，确保 HTML 页面关键模块不为空。
- WHY: 你已经遇到“shader details / textures 列表为空”的缺陷，必须用验收发现。
- HOW: Headless + CDP 方案已形成，但关键数据完整性校验尚未覆盖“空列表”缺陷。

### 2.7 Mali 离线分析（移动端 Shader 性能）
- WHAT: 集成 malioc，对 shader 做瓶颈分类和性能估算。
- WHY: 移动端性能是游戏瓶颈高发区，价值显著。
- HOW: 接入已完成框架，但未与真实 RDC 数据流彻底贯通。

### 2.8 Canonical Schema（单帧/对比统一数据契约）
- WHAT: 定义统一 schema 作为 analyze/compare 的唯一数据结构。
- WHY: 不统一就需要兼容分支，导致对比结果不可控、难验证。
- HOW: 已在多份计划中列为 P0，但尚未完成端到端一致性验证。

## 3) 证据矩阵（结论 ↔ 文档证据）

| 结论 | 证据来源（文件） | 备注 |
|---|---|---|
| A-first 仍未完成真实数据链闭环 | `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_VERIFICATION.md` | replay 环境缺失、纹理比率未达标 |
| “已完成”口径与“未闭环”口径冲突 | `docs/analysis/codex_rdc_analyzer/TASK_TRACKER.md` vs `WORK_SUMMARY_VERIFICATION.md` | 必须统一对外口径 |
| Diff/Regression 机制已实现 | `scripts/rdc_analyzer/.ai/CHANGELOG.md`, `.ai/reviews/PENDING.md` | 仍需 schema 统一 |
| Routes A/B/C 可用性差异 | `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROUTES.md` | Python API 依赖 replay |
| Pipeline 数据源优先级 | `scripts/rdc_analyzer/.ai/docs/pipeline-state-data-sources.md` | XML 仅推断，API 才准确 |
| 规则阈值存在 key 漂移风险 | `docs/analysis/codex_rdc_analyzer/2026-01-20-rdc-analyzer-rules-*.md` | 多规则默认值可能失效 |

## 4) 主要冲突与不确定性（必须正面披露）
1. “A-first 完成” vs “Replay 缺失与验收未闭环”存在冲突口径。
2. “测试 453/501 通过” vs “关键空列表缺陷未被发现”存在冲突口径。
3. “C-mode 完成” vs “数据源完整性缺口”存在可信度风险。

## 5) P0 必做清单（每条提供 WHAT / WHY / HOW + 与现状差距）

### P0-1 Replay 环境与真实数据链恢复
- WHAT: 打通 RenderDoc Python API / replay 环境，获取权威资源与管线数据。
- WHY: 没有真实数据链，A/B/C 全部结论只能算“估计”，不能验收。
- HOW: 按文档中的 replay 方案落地；在报告中标注数据源来源字段。
- 与现状差距: 目前处于“无 replay 环境”状态，导致纹理/Shader列表不完整。

### P0-2 Canonical Schema 统一
- WHAT: analyze 与 compare 只输出/读取同一结构，不再兼容旧 schema。
- WHY: 统一后才能可信对比与复用测试。
- HOW: 以 `main.py` 为唯一输出链路，compare 读取 canonical JSON。
- 与现状差距: 目前存在多套 schema/兼容逻辑。

### P0-3 完整性比率与 UI 对齐
- WHAT: 建立纹理/Shader 数量与 UI/官方 API 的一致性校验。
- WHY: 解决“列表为空但未被发现”的验收漏洞。
- HOW: 对齐 RenderDoc UI 数量或 replay API 计数，低于阈值即 FAIL。
- 与现状差距: g145-battle-2 纹理比率 < 0.9，未闭环。

### P0-4 HTML 视觉验收覆盖“空列表”
- WHAT: 增加 HTML 验收规则：关键列表为空即失败。
- WHY: 防止“UI 看起来正常但核心数据为空”。
- HOW: 在 headless 验收脚本中增加 DOM 断言（列表 count > 0）。
- 与现状差距: 当前验收只关注页面结构，不判断内容完整性。

### P0-5 标准可追溯 + WHAT/WHY/HOW 元数据闭环
- WHAT: 所有规则/建议都必须带来源、阈值、证据链字段。
- WHY: 让“建议可解释、可复查”，避免“黑盒式结论”。
- HOW: canonical issues 增加 evidence/threshold/source 字段。
- 与现状差距: 规则阈值键名漂移、来源未统一记录。

## 6) P1 / P2 展望（同样给 WHAT / WHY / HOW）

### P1-1 规则阈值键名对齐
- WHAT: 统一规则读取的 threshold key。
- WHY: 避免规则默认为不正确的阈值。
- HOW: 建立阈值别名映射 + 校验测试。

### P1-2 对比入口统一 CLI
- WHAT: analyze/compare 命令统一入口与输出规范。
- WHY: 降低团队使用门槛。
- HOW: CLI 共享 argparse 结构，统一输出目录规范。

### P2-1 移动端 GPU（malioc）深度闭环
- WHAT: 将 malioc 分析接入真实 RDC pipeline。
- WHY: 移动端性能价值高。
- HOW: 复用 shader 提取链路 + 强制记录数据来源字段。

## 7) 建议的团队阅读顺序（功能性引导）
- WHAT: 建立“最短阅读路径”供新人快速理解现状。
- WHY: 降低理解成本，避免重复口径冲突。
- HOW: 先读总索引 -> 进度总结 -> 架构/路线/验证/Schema 文档。

## 8) 附录：MD 全量清单（带分类标签）
（标签: core / plan / support / project / artifact / other）

- [plan] D:\Code\git\renderdoc\plans\2025-01-16-143300-Agent01-ABCD-Roadmap.md
- [plan] D:\Code\git\renderdoc\plans\2025-01-17-143000-RDC-Report-V3-Design.md
- [plan] D:\Code\git\renderdoc\plans\2025-01-18-203500-Agent01-Milestone4-UX-Enhancements.md
- [plan] D:\Code\git\renderdoc\scripts\rdc_analyzer\plans\2025-01-20-140000-Agent01-RefactorRDCParser.md
- [plan] D:\Code\git\renderdoc\plans\2025-01-20-152300-Codex-A-first-execution-plan.md
- [plan] D:\Code\git\renderdoc\plans\2025-01-20-162030-Agent01-ExportCommand.md
- [plan] D:\Code\git\renderdoc\plans\2025-01-20-180000-Agent01-PreExportPipeline.md
- [plan] D:\Code\git\renderdoc\plans\2025-01-20-phase1-performance-integration.md
- [plan] D:\Code\git\renderdoc\plans\2025-01-21-AgentB-AuditFix-3-4.md
- [core] D:\Code\git\renderdoc\scripts\rdc_analyzer\.ai\archive\2025-01.md
- [plan] D:\Code\git\renderdoc\plans\2025-07-24-174500-Agent01-PipelineStateExtension.md
- [plan] D:\Code\git\renderdoc\scripts\rdc_analyzer\.ai\plans\2026-01-19-193500-Flux0119-TASK-007-XMLToContextBridge.md
- [core] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\2026-01-19-rdc-analyzer-capability-scorecard.md
- [core] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\2026-01-19-rdc-analyzer-feature-details.md
- [core] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\2026-01-19-rdc-analyzer-key-deep-dive.md
- [core] D:\Code\git\renderdoc\scripts\rdc_analyzer\.ai\reviews\2026-01-19.md
- [core] D:\Code\git\renderdoc\scripts\rdc_analyzer\.ai\tasks\2026-01-19.md
- [core] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\2026-01-20-a-first-dod-repo-checklist.md
- [core] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\2026-01-20-abc-modes-market-and-a-first-loop.md
- [plan] D:\Code\git\renderdoc\scripts\rdc_analyzer\.ai\plans\2026-01-20-Phase2-DiffEngine.md
- [core] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\2026-01-20-rdc-analyzer-rules-buffer.md
- [core] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\2026-01-20-rdc-analyzer-rules-draw-call.md
- [core] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\2026-01-20-rdc-analyzer-rules-mobile.md
- [core] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\2026-01-20-rdc-analyzer-rules-pass.md
- [core] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\2026-01-20-rdc-analyzer-rules-state.md
- [core] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\2026-01-20-rdc-analyzer-rules-texture.md
- [core] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\2026-01-20-rdc-analyzer-schema-compare.md
- [core] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\2026-01-20-rdc-analyzer-schema-single-analysis.md
- [core] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\2026-01-21-a-first-plan-audit.md
- [plan] D:\Code\git\renderdoc\plans\2026-01-23-194855-Codex-RDC-Analyzer-Review-Plan.md
- [plan] D:\Code\git\renderdoc\plans\2026-01-23-224804-Codex-Continue2-P0-Implementation-Plan.md
- [core] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\2026-01-23-rdc-analyzer-architecture-review.md
- [core] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\2026-01-23-rdc-analyzer-continue2-report.md
- [plan] D:\Code\git\renderdoc\plans\2026-01-24-120000-Agent01-QuickCapture.md
- [plan] D:\Code\git\renderdoc\plans\2026-01-24-165506-Agent01-StandardsTraceability.md
- [plan] D:\Code\git\renderdoc\plans\2026-01-24-185241-Agent01-BuildAndPythonCheck.md
- [plan] D:\Code\git\renderdoc\plans\2026-01-24-192949-Agent01-PythonInProcessCaptureDX11.md
- [plan] D:\Code\git\renderdoc\plans\2026-01-24-193124-Agent01-ExportCompile-Codemap.md
- [plan] D:\Code\git\renderdoc\plans\2026-01-24-205449-Agent01-WorkSummarySplit.md
- [plan] D:\Code\git\renderdoc\plans\2026-01-25-143824-Agent01-HTML-UI-Review.md
- [plan] D:\Code\git\renderdoc\plans\2026-01-25-144902-Codex-P2-Mobile-GPU-Analysis.md
- [plan] D:\Code\git\renderdoc\plans\2026-01-25-145750-Agent01-HTML-UI-Review-Headless.md
- [plan] D:\Code\git\renderdoc\plans\2026-01-25-203050-Codex-GitCleanup.md
- [plan] D:\Code\git\renderdoc\plans\2026-01-25-211506-Codex-RemainingChangesTriage.md
- [plan] D:\Code\git\renderdoc\plans\2026-01-25-213500-Agent01-HTML-Metrics-Alignment.md
- [plan] D:\Code\git\renderdoc\plans\2026-01-25-221000-Agent01-HTML-Visual-Review.md
- [plan] D:\Code\git\renderdoc\plans\2026-01-25-231500-Agent01-HTML-Visual-Review-ClickFix.md
- [plan] D:\Code\git\renderdoc\plans\2026-01-25-234500-Agent01-HTML-Visual-Review-PathAndLog.md
- [plan] D:\Code\git\renderdoc\plans\2026-01-25-235500-Agent01-ConsoleStepLog-And-NewRDC.md
- [plan] D:\Code\git\renderdoc\plans\2026-01-26-105505-Codex01-RDC-Html-Validation-Plan.md
- [plan] D:\Code\git\renderdoc\plans\2026-01-26-115829-Codex01-G145-Shader-Texture-Fix.md
- [plan] D:\Code\git\renderdoc\plans\2026-01-26-142143-Codex01-Completeness-Reconciliation.md
- [plan] D:\Code\git\renderdoc\plans\2026-01-26-183459-Codex01-Texture-Completeness-API-Path.md
- [plan] D:\Code\git\renderdoc\plans\2026-01-29-141922-Codex01-DocsReview-Progress-Outlook.md
- [other] D:\Code\git\renderdoc\Agents.md
- [support] D:\Code\git\renderdoc\docs\analysis\ARCHITECTURE.md
- [core] D:\Code\git\renderdoc\scripts\rdc_analyzer\docs\ARCHITECTURE_V1.md
- [other] D:\Code\git\renderdoc\.github\ISSUE_TEMPLATE\bug_report.md
- [core] D:\Code\git\renderdoc\scripts\rdc_analyzer\.ai\CHANGELOG.md
- [project] D:\Code\git\renderdoc\docs\CONTRIBUTING\Code-Explanation.md
- [other] D:\Code\git\renderdoc\.github\CODE_OF_CONDUCT.md
- [project] D:\Code\git\renderdoc\docs\CODE_OF_CONDUCT.md
- [project] D:\Code\git\renderdoc\docs\CONTRIBUTING\Compiling.md
- [project] D:\Code\git\renderdoc\docs\CONTRIBUTING.md
- [core] D:\Code\git\renderdoc\scripts\rdc_analyzer\.ai\CONVENTIONS.md
- [other] D:\Code\git\renderdoc\renderdoc\driver\ihv\nv\official\PerfSDK\redist\NvPerfUtility\CREDITS.md
- [project] D:\Code\git\renderdoc\docs\CONTRIBUTING\Dependencies.md
- [project] D:\Code\git\renderdoc\docs\CONTRIBUTING\Developing-Change.md
- [other] D:\Code\git\renderdoc\renderdoc\driver\shaders\spirv\extension_support.md
- [other] D:\Code\git\renderdoc\renderdoc\driver\vulkan\extension_support.md
- [core] D:\Code\git\renderdoc\scripts\rdc_analyzer\.ai\FEATURE_INDEX.md
- [other] D:\Code\git\renderdoc\.github\ISSUE_TEMPLATE\feature_request.md
- [project] D:\Code\git\renderdoc\docs\CONTRIBUTING\Filing-Issues-Bugs.md
- [project] D:\Code\git\renderdoc\docs\CONTRIBUTING\Filing-Issues-Features.md
- [project] D:\Code\git\renderdoc\docs\CONTRIBUTING\Filing-Issues.md
- [other] D:\Code\git\renderdoc\Resource\Game_x64h_2026.01.07_05.35.50_frame3996_analysis.md
- [support] D:\Code\git\renderdoc\docs\analysis\gpu-dependency-solutions.md
- [support] D:\Code\git\renderdoc\docs\analysis\gpu-replay-architecture.md
- [core] D:\Code\git\renderdoc\scripts\rdc_analyzer\.ai\INDEX.md
- [other] D:\Code\git\renderdoc\LICENSE.md
- [artifact] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\html_review\_cdp_profile\Default\Extensions\iikmkjmpaadaobahmlepeloendndfphd\5.4.1_0\vendor\saveas\LICENSE.md
- [artifact] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\html_review\run_20260125-192134\_cdp_profile\Default\Extensions\iikmkjmpaadaobahmlepeloendndfphd\5.4.1_0\vendor\saveas\LICENSE.md
- [artifact] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\html_review\run_20260125-192309\_cdp_profile\Default\Extensions\iikmkjmpaadaobahmlepeloendndfphd\5.4.1_0\vendor\saveas\LICENSE.md
- [artifact] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\html_review\run_20260125-202852\_cdp_profile\Default\Extensions\iikmkjmpaadaobahmlepeloendndfphd\5.4.1_0\vendor\saveas\LICENSE.md
- [artifact] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\html_review\run_20260125-204152\_cdp_profile\Default\Extensions\iikmkjmpaadaobahmlepeloendndfphd\5.4.1_0\vendor\saveas\LICENSE.md
- [artifact] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\html_review\run_20260125-204426\_cdp_profile\Default\Extensions\iikmkjmpaadaobahmlepeloendndfphd\5.4.1_0\vendor\saveas\LICENSE.md
- [artifact] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\html_review\run_20260125-204759\_cdp_profile\Default\Extensions\iikmkjmpaadaobahmlepeloendndfphd\5.4.1_0\vendor\saveas\LICENSE.md
- [other] D:\Code\git\renderdoc\renderdoc\3rdparty\pugixml\LICENSE.md
- [other] D:\Code\git\renderdoc\renderdoc\driver\ihv\amd\official\RGA\elf\LICENSE.md
- [core] D:\Code\git\renderdoc\scripts\rdc_analyzer\docs\MALI_INTEGRATION_SUMMARY.md
- [support] D:\Code\git\renderdoc\docs\analysis\md_scan_summary.md
- [project] D:\Code\git\renderdoc\docs\milestones\milestone-1-report.md
- [core] D:\Code\git\renderdoc\scripts\rdc_analyzer\docs\MILESTONE_SUMMARY.md
- [core] D:\Code\git\renderdoc\scripts\rdc_analyzer\.ai\ONBOARDING.md
- [core] D:\Code\git\renderdoc\scripts\rdc_analyzer\optimization_recommendations.md
- [core] D:\Code\git\renderdoc\scripts\rdc_analyzer\optimization_report_145.md
- [core] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\P2_MOBILE_GPU_ANALYSIS_DESIGN.md
- [core] D:\Code\git\renderdoc\scripts\rdc_analyzer\docs\P4_ENVIRONMENT_VERIFICATION.md
- [core] D:\Code\git\renderdoc\scripts\rdc_analyzer\.ai\reviews\PENDING.md
- [support] D:\Code\git\renderdoc\docs\analysis\phase1_requirements_for_phase2.md
- [core] D:\Code\git\renderdoc\scripts\rdc_analyzer\.ai\docs\pipeline-state-data-sources.md
- [project] D:\Code\git\renderdoc\docs\research\pipeline_state_research_report.md
- [project] D:\Code\git\renderdoc\docs\CONTRIBUTING\Preparing-Commits.md
- [core] D:\Code\git\renderdoc\scripts\rdc_analyzer\docs\PROGRESS_REPORT.md
- [support] D:\Code\git\renderdoc\docs\analysis\PROJECT_INDEX.md
- [other] D:\Code\git\renderdoc\.serena\memories\project_overview.md
- [plan] D:\Code\git\renderdoc\plans\PROJECT_SUMMARY.md
- [other] D:\Code\git\renderdoc\.github\pull_request_template.md
- [project] D:\Code\git\renderdoc\docs\CONTRIBUTING\Questions.md
- [support] D:\Code\git\renderdoc\docs\analysis\RDC_ANALYSIS_SPEC.md
- [support] D:\Code\git\renderdoc\docs\analysis\RDC_ANALYZER_DESIGN.md
- [other] D:\Code\git\renderdoc\.serena\memories\rdc_analyzer_overview.md
- [core] D:\Code\git\renderdoc\scripts\rdc_analyzer\docs\rdc_format_spec.md
- [support] D:\Code\git\renderdoc\docs\analysis\RDC_PARSING_INDEX.md
- [support] D:\Code\git\renderdoc\docs\analysis\rdoc_quick_capture.md
- [support] D:\Code\git\renderdoc\docs\analysis\rdoc_quick_capture_python.md
- [other] D:\Code\git\renderdoc\README.md
- [other] D:\Code\git\renderdoc\.pytest_cache\README.md
- [project] D:\Code\git\renderdoc\docs\README.md
- [core] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\README.md
- [artifact] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\html_review\_cdp_profile\Default\Extensions\ndcileolkflehcjpmjnfbnaibdcgglog\6.33.5_0\README.md
- [artifact] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\html_review\_cdp_profile\Edge Wallet\128.18367.18366.1\json\wallet\README.md
- [artifact] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\html_review\run_20260125-192134\_cdp_profile\Default\Extensions\ndcileolkflehcjpmjnfbnaibdcgglog\6.33.5_0\README.md
- [artifact] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\html_review\run_20260125-192309\_cdp_profile\Default\Extensions\ndcileolkflehcjpmjnfbnaibdcgglog\6.33.5_0\README.md
- [artifact] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\html_review\run_20260125-192309\_cdp_profile\Edge Wallet\128.18367.18366.1\json\wallet\README.md
- [artifact] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\html_review\run_20260125-202852\_cdp_profile\Default\Extensions\ndcileolkflehcjpmjnfbnaibdcgglog\6.33.5_0\README.md
- [artifact] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\html_review\run_20260125-204152\_cdp_profile\Default\Extensions\ndcileolkflehcjpmjnfbnaibdcgglog\6.33.5_0\README.md
- [artifact] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\html_review\run_20260125-204152\_cdp_profile\Edge Wallet\128.18367.18366.1\json\wallet\README.md
- [artifact] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\html_review\run_20260125-204426\_cdp_profile\Default\Extensions\ndcileolkflehcjpmjnfbnaibdcgglog\6.33.5_0\README.md
- [artifact] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\html_review\run_20260125-204426\_cdp_profile\Edge Wallet\128.18367.18366.1\json\wallet\README.md
- [artifact] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\html_review\run_20260125-204759\_cdp_profile\Default\Extensions\ndcileolkflehcjpmjnfbnaibdcgglog\6.33.5_0\README.md
- [artifact] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\html_review\run_20260125-204759\_cdp_profile\Edge Wallet\128.18367.18366.1\json\wallet\README.md
- [project] D:\Code\git\renderdoc\docs\pycharm_helpers\README.md
- [project] D:\Code\git\renderdoc\docs\stubs_generation\README.md
- [other] D:\Code\git\renderdoc\qrenderdoc\README.md
- [other] D:\Code\git\renderdoc\qrenderdoc\3rdparty\qt\README.md
- [other] D:\Code\git\renderdoc\qrenderdoc\3rdparty\swig\README.md
- [other] D:\Code\git\renderdoc\qrenderdoc\3rdparty\toolwindowmanager\README.md
- [other] D:\Code\git\renderdoc\qrenderdoc\Resources\README.md
- [other] D:\Code\git\renderdoc\renderdoc\3rdparty\glslang\README.md
- [other] D:\Code\git\renderdoc\renderdoc\3rdparty\include-bin\README.md
- [other] D:\Code\git\renderdoc\renderdoc\3rdparty\interceptor-lib\README.md
- [other] D:\Code\git\renderdoc\renderdoc\3rdparty\lz4\README.md
- [other] D:\Code\git\renderdoc\renderdoc\3rdparty\md5\README.md
- [other] D:\Code\git\renderdoc\renderdoc\3rdparty\plthook\README.md
- [other] D:\Code\git\renderdoc\renderdoc\3rdparty\superluminal\README.md
- [other] D:\Code\git\renderdoc\renderdoc\3rdparty\tinyexr\README.md
- [other] D:\Code\git\renderdoc\renderdoc\api\README.md
- [other] D:\Code\git\renderdoc\renderdoc\driver\ihv\amd\official\RGA\Common\README.md
- [other] D:\Code\git\renderdoc\renderdoc\driver\ihv\amd\official\RGA\elf\README.md
- [other] D:\Code\git\renderdoc\renderdoc\driver\ihv\amd\official\RGP\README.md
- [other] D:\Code\git\renderdoc\renderdoc\driver\ihv\arm\official\lizard\README.md
- [other] D:\Code\git\renderdoc\renderdoc\driver\ihv\arm\official\lizard\thirdparty\hwcpipe\README.md
- [other] D:\Code\git\renderdoc\renderdoc\driver\ihv\nv\official\nvapi\README.md
- [other] D:\Code\git\renderdoc\scripts\.pytest_cache\README.md
- [core] D:\Code\git\renderdoc\scripts\rdc_analyzer\README.md
- [artifact] D:\Code\git\renderdoc\scripts\rdc_analyzer\.pytest_cache\README.md
- [other] D:\Code\git\renderdoc\util\buildscripts\README.md
- [other] D:\Code\git\renderdoc\util\buildscripts\scripts\docker\README.md
- [other] D:\Code\git\renderdoc\util\buildscripts\support\README.md
- [other] D:\Code\git\renderdoc\util\clangformat\README.md
- [other] D:\Code\git\renderdoc\util\spirv-plugins\README.md
- [other] D:\Code\git\renderdoc\util\spirv-plugins\docker\README.md
- [other] D:\Code\git\renderdoc\util\test\README.md
- [other] D:\Code\git\renderdoc\util\test\data\demos\README.md
- [other] D:\Code\git\renderdoc\util\test\demos\3rdparty\ags\README.md
- [other] D:\Code\git\renderdoc\util\test\demos\3rdparty\fmt\README.md
- [other] D:\Code\git\renderdoc\util\test\demos\3rdparty\glad\README.md
- [other] D:\Code\git\renderdoc\util\test\demos\3rdparty\lz4\README.md
- [other] D:\Code\git\renderdoc\util\test\demos\3rdparty\md5\README.md
- [other] D:\Code\git\renderdoc\util\test\demos\3rdparty\nuklear\README.md
- [other] D:\Code\git\renderdoc\util\test\demos\3rdparty\shaderc\README.md
- [other] D:\Code\git\renderdoc\util\test\demos\3rdparty\volk\README.md
- [other] D:\Code\git\renderdoc\util\test\demos\3rdparty\VulkanMemoryAllocator\README.md
- [core] D:\Code\git\renderdoc\scripts\rdc_analyzer\docs\REFACTOR_ANALYSIS.md
- [artifact] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\html_review\_cdp_profile\Default\Extensions\ndcileolkflehcjpmjnfbnaibdcgglog\6.33.5_0\RELEASE_NOTES.md
- [artifact] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\html_review\run_20260125-192134\_cdp_profile\Default\Extensions\ndcileolkflehcjpmjnfbnaibdcgglog\6.33.5_0\RELEASE_NOTES.md
- [artifact] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\html_review\run_20260125-192309\_cdp_profile\Default\Extensions\ndcileolkflehcjpmjnfbnaibdcgglog\6.33.5_0\RELEASE_NOTES.md
- [artifact] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\html_review\run_20260125-202852\_cdp_profile\Default\Extensions\ndcileolkflehcjpmjnfbnaibdcgglog\6.33.5_0\RELEASE_NOTES.md
- [artifact] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\html_review\run_20260125-204152\_cdp_profile\Default\Extensions\ndcileolkflehcjpmjnfbnaibdcgglog\6.33.5_0\RELEASE_NOTES.md
- [artifact] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\html_review\run_20260125-204426\_cdp_profile\Default\Extensions\ndcileolkflehcjpmjnfbnaibdcgglog\6.33.5_0\RELEASE_NOTES.md
- [artifact] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\html_review\run_20260125-204759\_cdp_profile\Default\Extensions\ndcileolkflehcjpmjnfbnaibdcgglog\6.33.5_0\RELEASE_NOTES.md
- [project] D:\Code\git\renderdoc\docs\offline_reference\RENDERDOC_DOCS_INDEX.md
- [core] D:\Code\git\renderdoc\scripts\rdc_analyzer\RULES.md
- [support] D:\Code\git\renderdoc\docs\analysis\RULES_EXTERNAL.md
- [support] D:\Code\git\renderdoc\docs\analysis\RULES_RENDERDOC.md
- [other] D:\Code\git\renderdoc\renderdoc\driver\shaders\spirv\spirv_registry.md
- [other] D:\Code\git\renderdoc\.serena\memories\style_conventions.md
- [other] D:\Code\git\renderdoc\.serena\memories\suggested_commands.md
- [other] D:\Code\git\renderdoc\.serena\memories\task_completion_checklist.md
- [core] D:\Code\git\renderdoc\scripts\rdc_analyzer\.ai\TASK_INDEX.md
- [core] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\TASK_TRACKER.md
- [core] D:\Code\git\renderdoc\scripts\rdc_analyzer\.ai\tasks\TEMPLATE.md
- [project] D:\Code\git\renderdoc\docs\CONTRIBUTING\Testing.md
- [core] D:\Code\git\renderdoc\scripts\rdc_analyzer\docs\TODO.md
- [core] D:\Code\git\renderdoc\scripts\rdc_analyzer\USAGE_MALI_ANALYZER.md
- [core] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\WORK_SUMMARY_2025-01-21.md
- [core] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\WORK_SUMMARY_ARCH.md
- [core] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\WORK_SUMMARY_BUILD.md
- [core] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\WORK_SUMMARY_ROADMAP.md
- [core] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\WORK_SUMMARY_ROUTES.md
- [core] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\WORK_SUMMARY_SCHEMA.md
- [core] D:\Code\git\renderdoc\docs\analysis\codex_rdc_analyzer\WORK_SUMMARY_VERIFICATION.md
