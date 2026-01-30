# RDC Analyzer 深度下钻（WHAT / WHY / HOW）

> 从主文档拆分：`docs/analysis/codex_rdc_analyzer/2026-01-19-rdc-analyzer-capability-scorecard.md`
> 目的：控制单文件大小（<= 800 行）并降低维护成本。
> 更新时间：2026-01-20

---

### 1.6 深度下钻（你选择的 3：优先把 5–10 个“最关键功能”讲透）

> 你选了 “3”，所以我不在这里把 36 条规则逐条展开（那会非常长），而是先把**最影响可信度/可落地性**的关键功能讲透：  
> - 每个条目都包含：WHAT / WHY / HOW  
> - 且包含“**对比当前项目现状**：现在有什么、缺什么、为什么重要”  
> - 同时尽量给到“字段级别”的输入/输出说明，避免只停留在概念。

#### 1.6.1 数据模型（AnalysisContext / AnalysisResult / core.types）——“SSOT 的地基”

**WHAT**
- 提供一套“结构化的内存数据模型”，用于承载：
  - 解析结果（ParsedData）
  - 分析产物（FrameSummary、资源列表、Pass、DrawCall、Shader 等）
  - 规则输出（Issue 列表）
  - 最终输出（AnalysisResult）
- 这套模型如果成为“唯一口径”，后续 compare/diff、报表、建议才有一致数据源。

**WHY（对比当前项目现状，为什么重要）**
- 你当前项目里**至少并存 2 套数据模型**：
  1) 旧 pipeline（`scripts/rdc_analyzer/pipeline.py`）走 `AnalysisContext`/`AnalysisResult` 这套 dataclass 模型；
  2) 新 pipeline（`scripts/rdc_analyzer/main.py`）导出的是 `analysis_data` dict（字段与 dataclass 不一致），并且为了 HTML 导出还会动态造对象（见第 3.1 节证据）。
- 结果是：同一个“概念字段”（例如 draw call 数、纹理内存、事件列表、issues）在不同链路里名字/类型都不一致，导致：
  - 对比（compare）不得不写“兼容转换/猜字段”（见 `scripts/rdc_analyzer/compare_rdc.py:118` 的 Phase1->Phase2 兼容逻辑），结论可信度下降；
  - 规则系统（RD_*）与新 pipeline（BIND*/PERF*）事实上不是同一套 issue 口径（见 1.6.3），你以为有 36 条规则，但 analyze 不一定跑到。
- 所以它的重要性是：这是一切“可信分析/可复查/可对比”的地基。没有统一模型，任何“极致”都会被口径分裂抵消。

**HOW（当前实现怎么做 + 字段级说明）**
- 数据模型定义位置：
  - `scripts/rdc_analyzer/core/types.py:12`（TextureInfo/BufferInfo/ShaderInfo/PassInfo/DrawCallInfo/Issue/FrameSummary/ParsedData…）
  - `scripts/rdc_analyzer/core/context.py:26`（AnalysisContext：贯穿 pipeline 的共享状态容器）
  - `scripts/rdc_analyzer/core/result.py:16`（AnalysisResult：最终输出）
- 关键字段（节选，与你两大目标直接相关）：
  - `AnalysisContext.parsed`：原始解析数据（draws/resources/shaders/markers…）
  - `AnalysisContext.frame_summary`：帧级统计（draw_call_count/texture_count/rt_switches/shader_changes…）
  - `AnalysisContext.textures/buffers/shaders/passes/draw_calls`：结构化列表，供 rules/compare/report 消费
  - `Issue`：`severity/category/code/message/event_id/resource_id/location_path`（这是“证据链”的落点）
- 现状差异点（非常关键）：
  - BaseParser 能创建带阈值的 context（`scripts/rdc_analyzer/parsers/base.py:49`），但旧 pipeline 并未使用它（见 1.6.2）。

#### 1.6.2 阈值体系（config/thresholds.py vs 规则 key）——“标准/阈值是否真的生效”

**WHAT**
- 提供按平台（pc/mobile/low_end）切换的阈值字典（thresholds），用于让规则输出“可解释的标准”：
  - 同一条规则在 PC 与 Mobile 的阈值不同（例如 draw call 上限、纹理尺寸/内存等）。

**WHY（对比当前项目现状，为什么重要）**
- 你想做“极致性能分析 + 建议”，阈值是建议系统的“标准尺”：
  - 没有阈值（或阈值不生效），工具输出就会变成“个人感觉”，团队无法对齐。
- 当前项目存在两个会直接破坏阈值生效的客观问题：
  1) **旧 pipeline 没把 thresholds 注入 AnalysisContext**：`scripts/rdc_analyzer/pipeline.py:66` 创建 context 时只传了 `parsed/platform`，没传 `thresholds`，导致 rules 的 `get_threshold()` 只会拿到默认值。  
  2) **规则里用的阈值 key 与 config/thresholds.py 的 key 存在漂移**：例如 DrawCallCountRule 用 `draw_call_count`（默认 2000），而 config 里是 `max_draw_calls`（PC=3000, Mobile=500）。这会造成“文档阈值 vs 实际生效阈值”不一致，输出可信度直接下降。

**HOW**
- 阈值定义：`scripts/rdc_analyzer/config/thresholds.py:12`
  - `DEFAULT_THRESHOLDS`（PC）
  - `MOBILE_THRESHOLDS`（移动端更严格）
  - `LOW_END_THRESHOLDS`（低端设备更严格）
  - `get_thresholds(platform)`（按平台返回 dict）
- 正确注入阈值的方式（当前项目只有部分链路做到）：
  - BaseParser 提供 `create_context(platform)`，会注入 thresholds：`scripts/rdc_analyzer/parsers/base.py:49`
  - 但旧 pipeline 直接 new 了 AnalysisContext，绕开了 create_context：`scripts/rdc_analyzer/pipeline.py:66`
- 字段级建议（用于你阅读时判断“是不是在胡说”）：
  - 任何 Rule/Analyzer 输出里如果出现“阈值 XXX”，你都应该能追溯到：
    - `context.thresholds[key]`（来自 config）
    - 或明确是 fallback default（且文档要承认这是 default）

#### 1.6.3 规则系统（RD_*） vs 新 pipeline（BIND*/PERF*）——“你以为的 36 条规则，用户是否真的看得到”

**WHAT**
- RD_* 规则系统（`scripts/rdc_analyzer/rules/*`）提供 36 条规则，统一输出 `core.types.Issue`：
  - 注册机制：`scripts/rdc_analyzer/rules/__init__.py:14`（`register_all_rules()`）
  - 执行器：`scripts/rdc_analyzer/rules/runner.py:14`（RuleRunner）
- 新 pipeline（`scripts/rdc_analyzer/main.py`）另有一套“内置规则/性能分析”的 issue 输出（BIND001/BIND002 + PERF001~007），字段与 Issue dataclass 不同（dict）。

**WHY（对比当前项目现状，为什么重要）**
- 你选择的 A 路径是“规则 + 建议”。如果 analyze 主路径不跑 RD_* 规则，那么：
  - 你在工程里写的 36 条规则会变成“存在但不生效”的资产；
  - 用户看到的 issue 只剩 BIND* 和 PERF*，你对外宣称的能力与实际输出不一致，信任会被打穿。
- 当前项目的客观证据：
  - 新 pipeline 的 `_analyze_rules()` 并没有调用 RuleRunner，而是直接 append dict（BIND001/BIND002），再跑 `_run_performance_analysis()`：`scripts/rdc_analyzer/main.py:403`
  - 旧 pipeline 才会调用 RuleRunner：`scripts/rdc_analyzer/pipeline.py:101`

**HOW**
- RD_* 规则实际执行路径（旧 pipeline）：
  - `scripts/rdc_analyzer/pipeline.py:52` 调用 `register_all_rules()`
  - `scripts/rdc_analyzer/pipeline.py:103` 使用 `RuleRunner(context).run()`
  - 输出类型：`core.types.Issue`
- 新 pipeline 当前执行路径（main.py）：
  - `_analyze_rules()` 内部直接写 `self._issues = [{code/severity/message/eventId}]`：`scripts/rdc_analyzer/main.py:409`
  - 输出类型：dict（不是 `core.types.Issue`）
- “为什么这事要写进文档”：
  - 因为它解释了：为什么你看代码“规则系统很完整”，但实际跑 analyze 可能看不到这些规则的输出。

#### 1.6.4 当前 JSON 输出口径 vs compare 输入口径——“为什么 compare 现在只能做兼容猜字段”

**WHAT**
- 单帧 analyze 的 JSON 输出，应当成为 compare 的输入（否则 compare 只能做脚本拼装）。

**WHY（对比当前项目现状，为什么重要）**
- 当前至少存在两种 JSON 口径：
  1) 新 pipeline 导出的 `analysis_data`（meta/summary/events/draw_calls/resources/resource_samples/issues）：`scripts/rdc_analyzer/main.py:948`
  2) compare_rdc.py 期望的输入是 “Phase2 dict 结构”（summary/textures/shaders/buffers/draw_calls…），并且还要兼容 “Phase1 list 结构”，兼容时会把 vertices/triangles/events 等关键字段置 0 或置空：`scripts/rdc_analyzer/compare_rdc.py:118`
- 这会直接影响“对比结论可信度”：
  - 如果 compare 的输入在兼容阶段就被填 0/空，那么 RegressionDetector 的结论可能是“对着空数据做回归判定”。

**HOW（字段级证据）**
- 新 pipeline JSON（analysis_data）字段（节选）：
  - `meta.rdc_path/api/timestamp/version`
  - `summary.total_events/draw_call_count/texture_count/buffer_count`
  - `events`（最多 1000 条）
  - `draw_calls`（列表）
  - `resources.textures/buffers`（dict）
  - `issues`（list[dict]）
  - 见：`scripts/rdc_analyzer/main.py:948`
- compare_rdc 输入兼容转换（Phase1 list → Phase2 dict）：
  - 强制填 `totalVertices=0/totalTriangles=0/events=[]`：`scripts/rdc_analyzer/compare_rdc.py:154`
  - 纹理内存通过“估算 bytes-per-pixel + mip 乘系数”推断：`scripts/rdc_analyzer/compare_rdc.py:48`
- 结论：当你发现 compare 输出里某些指标不可信（例如 triangles=0），不是算法问题，是输入 schema 口径问题。

#### 1.6.5 HTML 导出适配层的“造假风险”——为什么它会伤害可信度（但也说明你缺的是什么）

**WHAT**
- HTML 导出应该把“事实 + 证据 + 建议”可视化。

**WHY（对比当前项目现状，为什么重要）**
- 当前新 pipeline 在 HTML 导出前会：
  - 动态造一个“简化 DrawCallDetail”对象，关键字段全部空（shader/RT/资源绑定等都是 None/空数组）：`scripts/rdc_analyzer/main.py:1005`
  - 构造资源生命周期时把 first_access_event/last_access_event/read_count 写成占位（假设整帧活跃、至少读一次）：`scripts/rdc_analyzer/main.py:1041`
- 这会造成一种“很危险的假象”：
  - 报表看起来信息很全，但其实关键证据字段是空/假设出来的；
  - 用户会质疑：你给的建议是不是“猜的”。一旦信任破裂，后续再补真实数据也很难挽回。

**HOW**
- 当前实现路径：
  - `_export_reports()` 构建 analysis_data：`scripts/rdc_analyzer/main.py:941`
  - `_export_html()` 做数据适配并调用 HTMLExporter：`scripts/rdc_analyzer/main.py:987`
  - 动态造 DrawCallDetail：`scripts/rdc_analyzer/main.py:1005`
  - 资源生命周期占位：`scripts/rdc_analyzer/main.py:1041`
- 正确的演进方向（为什么 P0-2 必须做）：
  - DrawCallDetail/PipelineSnapshot 必须来自 Replay 真 state（例如 ReplayWrapper），而不是 exporter 阶段“补出来”。

#### 1.6.6 DiffEngine 的匹配策略与 state diff 深度——“全方位对比的技术核心”

**WHAT**
- DiffEngine 负责把两份数据对齐并计算差异：
  - draw/资源/统计等 diff
  - 支持 drawcall 的顺序匹配与签名匹配
  - 提供（简化）state diff

**WHY（对比当前项目现状，为什么重要）**
- 你要的目标 2 是“全方位对比 + 给结论”。全方位的关键是：
  - **匹配对不对**（baseline 的某个 draw 对应 target 的哪个 draw）
  - **state diff 够不够深**（仅数量变化 vs 绑定/渲染目标/Shader 变化）
- 当前项目现状（从证据点看）：
  - 匹配策略已存在：`scripts/rdc_analyzer/diff/diff_engine.py:373`
  - state diff 仍是简化实现：`scripts/rdc_analyzer/diff/diff_engine.py:570`
  - 而输入 JSON 口径还不统一（见 1.6.4），会进一步削弱 diff 的可靠性。

**HOW**
- DiffEngine 文件：`scripts/rdc_analyzer/diff/diff_engine.py:1`
- “字段级需求”（如果你要判断 diff 可信不可信，看它有没有这些字段）：
  - 事件：`event_id` + `marker_path`（用于稳定定位）
  - shader：hash/资源 id（用于判断“是不是同一个 pipeline”）
  - 资源：纹理/缓冲的尺寸/格式/usage/fingerprint（用于稳定匹配与解释差异）

#### 1.6.7 RegressionDetector 的“结论证据链”——为什么只有阈值还不够

**WHAT**
- RegressionDetector 把 diff 转成“结论”：是否回归、哪些回归、严重程度。

**WHY（对比当前项目现状，为什么重要）**
- 游戏/引擎团队要的不是“delta_percent=+20%”，而是：
  - **发生在哪一段 marker / 哪一批 draw**
  - **为什么变坏**（资源变大？pass 变多？shader 更慢？）
- 当前项目里 compare 的 JSON 导出结构能输出 baseline/target/delta_percent（这是必要但不充分）：
  - `scripts/rdc_analyzer/compare_rdc.py:331` 会写 regressions.issues[*].baseline_value/target_value/delta_percent
  - 但缺少“事件锚点/marker 路径/关键资源”会让结论说服力不足。

**HOW**
- compare_rdc 的 JSON 导出：`scripts/rdc_analyzer/compare_rdc.py:312`
- 你阅读 compare 输出时的判断标准：
  - 如果只有 summary 数字，没有 event/marker/resource 的 evidence，那么它只能算“报警器”，还不是“诊断器”。

#### 1.6.8 规则系统本身的“真值输入”——为什么 ReplayWrapper/CallAnalyzer/ResourceTracker 是极致分析的护城河

**WHAT**
- ReplayWrapper：读取 RenderDoc Replay 真 state（绑定、pipeline、资源信息等）。
- CallAnalyzer：调用级绑定/冗余分析（根因定位）。
- ResourceTracker：资源生命周期/依赖（RAW/WAR/WAW、unused writes 等）。

**WHY（对比当前项目现状，为什么重要）**
- 你要的“极致”最终拼的是“证据链硬不硬”：
  - 统计只能告诉你“可能慢”，state/绑定/依赖才能告诉你“为什么慢、怎么改”。
- 当前项目现状：
  - 这些深度模块都存在（第 1.3 节列出），但主 pipeline 没喂真实数据，反而在 exporter 阶段用占位生命周期（1.6.5）。
  - 所以它们的重要性不仅是“未来增强”，而是“把你已经有的最强能力接到主链路上”，让 output 可信。

**HOW（字段级）**
- ReplayWrapper：`scripts/rdc_analyzer/extractors/replay_wrapper.py:1`
- CallAnalyzer：`scripts/rdc_analyzer/analysis/call_analyzer.py:1`
- ResourceTracker：`scripts/rdc_analyzer/analysis/resource_tracker.py:1`
- 如果你看到分析输出里缺少：
  - 资源绑定细节（哪些 SRV/UAV/CBV 被绑定、是否冗余）
  - 生命周期访问统计（first/last access、read/write counts）
  - 那就意味着还没接上这条“极致链路”。

