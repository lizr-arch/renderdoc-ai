# RDC Analyzer 功能明细（WHAT / WHY / HOW）

> 从主文档拆分：`docs/analysis/codex_rdc_analyzer/2025-01-19-rdc-analyzer-capability-scorecard.md`
> 目的：控制单文件大小（<= 800 行）并降低维护成本。
> 更新时间：2025-01-20

---

### 1.5 功能明细：WHAT / WHY / HOW（对照当前项目现状，解释“为什么重要”）

> 说明：你要求“每个功能都要 WHAT/WHY/HOW，而且要能说服你”。  
> 所以我这里把 `scripts/rdc_analyzer/` 里**已经出现的主要能力**逐项拆开：  
> - **WHAT**：用户/系统拿到的交付物与能力边界  
> - **WHY**：对你的两大核心目标（单帧极致分析 + 双帧全方位对比）的价值；并明确“对比当前项目”缺口在哪里  
> - **HOW**：当前代码怎么实现（入口/关键文件/数据流）；以及扩展点与当前限制  
>
> 注：这部分的“对照现状”不是空泛口号，而是直接引用你当前工程里“并存的多条链路/占位数据/测试红灯”等客观事实（见第 3 节冲突点与第 2 节打分表）。

#### 1.5.1 CLI：`python -m rdc_analyzer analyze ...`（单帧分析入口）

**WHAT**
- 给用户一个稳定的命令入口，把“打开 rdc → 分析 → 导出报告（JSON/HTML）”串起来。
- 交付物通常应包含：
  - `analysis.json`（机器可消费，后续 compare 的输入）
  - `report.html`（人可阅读，面向“建议/证据”）

**WHY**
- 这是把“能力”变成“产品”的第一步：你再强的 analyzer，如果没有一个稳定入口，团队/流水线就很难用起来。
- 对比当前项目现状：
  - 你已经有 CLI 入口（见 `scripts/rdc_analyzer/__main__.py:26`），这很好；
  - 但目前 compare 不是一等命令（第 3.3 节已指出），导致你的“目标 2”在产品形态上弱于“目标 1”；
  - 另外，analyze 的输出里仍混入占位/模拟字段（第 3.1 节），这会让“建议”看起来像“泛泛而谈”，降低信任。

**HOW**
- 入口文件：`scripts/rdc_analyzer/__main__.py:26`
- 主调用链：CLI → `AnalysisPipeline`（`scripts/rdc_analyzer/main.py:147`）→ `_export_reports`（`scripts/rdc_analyzer/main.py:941`）。
- 扩展点：
  - 新增子命令（例如 compare）应该复用 CLI 的 argparse 结构（保持一等入口一致性）。
  - analyze 的最终结果应收敛为“唯一权威 JSON”（P0-1），否则后续任何 compare/回归都会对不上口径。

#### 1.5.2 新端到端主分析管线：`scripts/rdc_analyzer/main.py`（AnalysisPipeline）

**WHAT**
- 提供一条“端到端”的主干分析链路，包含：
  - 打开 capture（`_open_capture`）
  - 解析事件/DrawCall（`_parse_events`）
  - 抽取状态与资源（`_extract_states`）
  - 跑规则/性能分析（`_analyze_rules`）
  - 导出 JSON/HTML（`_export_reports`）
- 这是你当前最接近“产品主路径”的实现。

**WHY**
- 你要的“极致”必须依赖一条可控的主干流程：否则深度模块（replay/call/resource）永远只是“能用但用不上”。
- 对比当前项目现状：
  - 这条主干已经存在、也能导出报告（第 2 节给它打了 6.5/10），说明方向正确；
  - 但它在导出阶段使用了“模拟 DrawCallDetail/占位资源生命周期”，导致主干与最强能力脱节（第 3.1 节证据：`main.py:1005`/`main.py:1041`/`main.py:1043`）。
  - 这就是为什么它“看起来能跑通”，但离“极致可信”差一口气：输出证据链不够硬。

**HOW**
- 关键入口与步骤（证据点）：
  - `scripts/rdc_analyzer/main.py:147`：`class AnalysisPipeline`
  - `scripts/rdc_analyzer/main.py:282`：`_open_capture`
  - `scripts/rdc_analyzer/main.py:316`：`_parse_events`
  - `scripts/rdc_analyzer/main.py:350`：`_extract_states`
  - `scripts/rdc_analyzer/main.py:403`：`_analyze_rules`
  - `scripts/rdc_analyzer/main.py:941`：`_export_reports`
- 扩展点与限制（现状对照）：
  - 扩展点：主 pipeline 是“编排器”，应把“事实采集”（ReplayWrapper/pipeline snapshot）和“判断/建议”（rules/advisor）解耦。
  - 当前限制：主 pipeline 为了适配 exporter 引入动态 type/占位字段（第 3.1 节），需要在 P0-2 里替换为真实 snapshot。

#### 1.5.3 旧模块化管线：`scripts/rdc_analyzer/pipeline.py`

**WHAT**
- 提供另一套 `AnalysisPipeline` + `analyze_rdc(...)` 的模块化入口，便于脚本化调用或在不同场景下复用分析步骤。

**WHY**
- 模块化管线本身不是坏事：它能让你更容易把分析拆成组件、做单元测试、做组合分析。
- 但对比当前项目现状，“并存两套 pipeline”会显著增加维护成本：
  - 字段口径/输出结构分裂（第 3.2 节）；
  - 规则阈值/建议格式漂移（第 3.2 节）。
- 所以它的重要性不在于“继续扩大它”，而在于：要么收敛进 SSOT（P0-1），要么明确它只是内部库入口，不再产出另一套 JSON 口径。

**HOW**
- 关键文件与入口：
  - `scripts/rdc_analyzer/pipeline.py:23`：`AnalysisPipeline`
  - `scripts/rdc_analyzer/pipeline.py:107`：`analyze_rdc(...)`
- 推荐的工程治理方式（对照现状）：
  - 只允许它返回 `AnalysisResult`（与 `main.py` 同模型），禁止它产生“第二套 report schema”。
  - 用它做“可单测的内部库入口”，把 CLI 入口保持在 `__main__.py`。

#### 1.5.4 报告导出：JSON/HTML（主 pipeline 的 `_export_reports`）

**WHAT**
- 将分析结果导出成“可读 + 可机器消费”的两种报告：
  - JSON：用于 compare、归档、CI、回归检测
  - HTML：用于面向人类的结论/建议阅读

**WHY**
- 对你的目标来说，导出不是“最后一步的美化”，而是“可复查性”的载体：
  - 没有结构化 JSON → compare/diff 只能靠临时脚本拼装，结论不可复用；
  - 没有可读 HTML → 建议无法被引擎/TA/程序快速采纳。
- 对比当前项目现状：
  - 你已经具备 HTML/JSON 的导出路径（这是加分项）；
  - 但导出阶段为了适配 HTMLExporter 引入“模拟模型/占位字段”，让导出变成“污染源”（第 3.1 节），这会反向降低信任。

**HOW**
- 导出入口在：`scripts/rdc_analyzer/main.py:941`（`_export_reports`）
- 关键原则（对照现状最重要的一条）：
  - `_export_reports` 只能做“序列化与模板渲染”，不能做“补事实/造事实”。
  - 事实应由 ReplayWrapper/深度模块产生（P0-2），结构应由 SSOT schema 决定（P0-1）。

#### 1.5.5 纹理导出：`TextureExporter`（export_textures.py）

**WHAT**
- 从 capture 中导出纹理（图像），用于离线分析、回归对比、质量审查（分辨率/格式/mips/内容是否变化）。

**WHY**
- 游戏引擎（Unity/Unreal/自研）里，“纹理”通常是 GPU 性能与内存的第一大户之一：
  - 尺寸/格式/mips/采样与过滤设置会直接影响带宽与缓存命中；
  - 内容变化在回归场景里也很关键（例如某材质贴图错了/变黑/压缩坏了）。
- 对比当前项目现状：
  - 你的建议系统目前更强的是“纹理维度”（第 1.2 节/第 2 节），说明你已经在最重要的资产项上取得了成果；
  - 但它与主 pipeline 的 SSOT 还没有统一：导出的纹理信息如果不进入 canonical `resources`，compare 就很难做“全方位”结论。

**HOW**
- 入口类：`scripts/rdc_analyzer/export_textures.py:40`（`TextureExporter`）
- 运行方式通常应由主 pipeline 编排（而不是让用户手写脚本），并把导出的纹理清单/统计写入 `analysis.json.resources.textures[*]`。
- 扩展点：
  - 增加纹理 fingerprint（例如格式+尺寸+mips+hash）用于 compare 稳定匹配（这与 P1-2 的“稳定匹配策略”直接相关）。

#### 1.5.6 离线报告：`generate_offline_html`（generate_offline_report.py）

**WHAT**
- 生成“完全离线”的 HTML 报告（不依赖网络，PIL 可选），适合：
  - 内网/保密环境
  - 产线归档
  - 把结果发给没装 RenderDoc 的同学

**WHY**
- 对比当前项目现状：
  - 你已经有“离线产品线”（第 1.1 节），这很有价值：真实团队里经常不能要求每个人都装同样环境；
  - 但如果离线报告的数据源不是 SSOT，而是某个脚本的私有结构，那么它越好用，就越会加剧“多口径并存”的冲突（第 3.2 节）。
- 所以它的重要性在于：它是你“报告产品化”的关键能力，但必须绑定 SSOT，才能不引入技术债。

**HOW**
- 入口函数：`scripts/rdc_analyzer/generate_offline_report.py:133`（`generate_offline_html`）
- 推荐用法：把它视为“HTML 输出后端之一”，输入固定为 canonical `analysis.json`（或 canonical 的 in-memory 模型）。

#### 1.5.7 规则系统（A 口径的第一核心）：BaseRule / RuleRunner / RULES.md

**WHAT**
- 把“经验/最佳实践/硬性红线”固化成可执行规则：
  - 输出 issue（问题）与 evidence（证据）
  - 可选输出 suggestion（建议步骤）
- 并提供规则注册、运行器与规则清单文档（RULES.md）。

**WHY**
- 你选的 A 就是“规则 + 建议”。规则系统是你让工具“可规模化复用”的关键：
  - 任何一个新人/项目，只要同样跑规则，就能得到同样口径的问题清单；
  - 能把“极致分析”的深度结果转成“可被执行的结论”（这一步是很多分析工具缺失的）。
- 对比当前项目现状：
  - 规则数量与结构已经不错（第 1.2 节 36 条；第 2 节也给出完成度），说明基础很好；
  - 最大风险来自“输入数据口径不统一”（第 3.2 节）和“主 pipeline 用占位 state”（第 3.1 节）：
    - 规则如果吃到占位/缺失字段，就会退化成“启发式猜测”，这会直接破坏用户信任。

**HOW**
- 关键文件：
  - `scripts/rdc_analyzer/rules/base.py:15`：`BaseRule` / `RuleRegistry`
  - `scripts/rdc_analyzer/rules/runner.py:14`：`RuleRunner`
  - `scripts/rdc_analyzer/RULES.md:1`：规则清单文档
- 正确的数据流（对照现状的“应然”）：
  - ReplayWrapper/主 pipeline 产出事实（events/resources/pipeline snapshots）
  - RuleRunner 消费事实 → 产出统一 Issue（P0-3）→ 进入 SSOT JSON（P0-1）
  - OptimizationAdvisor 消费 Issue → 产出建议（见下）

#### 1.5.8 性能分析器（PERF001~PERF007）：PerformanceAnalyzer

**WHAT**
- 专注“性能维度”的规则化分析（例如 drawcall 数量、资源压力、可能的冗余绑定等），输出结构化结果。

**WHY**
- 你要“极致性能分析”，性能分析器是把大量指标固化为可执行规则/诊断的地方：
  - 它能把“采样/统计”升级为“结论与建议”；
  - 也是你做对比结论（目标 2）最需要复用的能力（baseline/target 的指标对比）。
- 对比当前项目现状：
  - 模块已存在（第 1.2 节），但在第 2 节被指出“需要更强的数据来源来避免启发式估计”；
  - 这说明它的重要性非常高，但它的可信度依赖 P0-2（真实 snapshot）与 P0-1（统一 schema）。

**HOW**
- 文件：`scripts/rdc_analyzer/analyzers/performance_analyzer.py:1`
- 推荐改造方向（对照现状）：
  - 让它只消费 canonical `analysis` 事实（events/resources/snapshots），并把产出写入统一 `issues`/`stats`。
  - 需要“阈值/标准”的部分，应该走 profile/平台化（P1-1），否则容易在 PC/移动端/不同目标 FPS 下误报。

#### 1.5.9 建议生成器（OptimizationAdvisor）：把“问题”变成“可执行改进步骤”

**WHAT**
- 将检测到的问题（issues）转化为建议（suggestions），典型应包含：
  - 可执行步骤（怎么改）
  - 预估收益（为什么值得改）
  - 优先级（先做哪个）

**WHY**
- 很多分析工具的“死亡点”在这里：只会报问题，不会给可执行建议；或建议过于泛泛。
- 对比当前项目现状：
  - 你已经做到了“可执行步骤 + 估算收益 + 优先级”（第 2 节认可），这是非常强的产品特征；
  - 但覆盖面目前偏纹理维度（第 1.2 节/第 2 节），并且建议格式未与全局统一模型绑定（P0-3）。
- 所以它的重要性是：它决定了你工具能不能真正推动项目性能变好，而不只是生成报告。

**HOW**
- 文件：`scripts/rdc_analyzer/core/optimization_advisor.py:1`
- 推荐的数据依赖（对照现状）：
  - 输入只接受统一 Issue（P0-3），不要接受“某模块私有结构”；
  - 建议应引用 issue 的 id/fingerprint，确保 compare 时能追踪“同一个问题在 target 是否改善/变坏”。

#### 1.5.10 ReplayWrapper：深度分析的“事实采集器/唯一真实来源”候选

**WHAT**
- 对 RenderDoc Replay API 的封装，负责安全地：
  - 打开 capture、创建/关闭 controller
  - 遍历 action/drawcall
  - 在指定 event 上读取状态（pipeline state、资源绑定等）

**WHY**
- 你想要的“极致分析”，一定需要“事实采集层”：
  - 规则/建议再聪明，也不能从缺失的 state 推断出真实 GPU 行为；
  - 真实 state 是“证据链”的根。
- 对比当前项目现状：
  - 这个模块能力很强（第 2 节给出 8.5/10 的“能力分”），但“未产品化集成”导致它没成为主 pipeline 的权威数据源；
  - 这正是第 3.1 节所说的“主链路与最强能力脱节”。

**HOW**
- 文件：`scripts/rdc_analyzer/extractors/replay_wrapper.py:1`
- 正确落位方式（对照现状）：
  - ReplayWrapper 应成为 P0-2 的核心：为每个关键 event 生成 snapshot；
  - 主 pipeline 只做编排（选事件、缓存、写入 canonical result），不再造占位 state。

#### 1.5.11 Pipeline State 抽取脚本：extract_pipeline_state.py

**WHAT**
- 从 capture 抽取真实 pipeline state 的脚本化工具，通常用于：
  - 调试与验证（验证某 event 的 state 是否如预期）
  - 为后续规则/建议扩展字段提供“探针”

**WHY**
- 对比当前项目现状：
  - 你已经有这个脚本，说明你在“获取真实 state”上走在正确路线上；
  - 但只要它停留在“脚本探针”，主 pipeline 仍可能继续使用占位字段（第 3.1 节），团队最终还是拿不到可信结论。
- 重要性在于：它是 P0-2 的直接基础资产，应当从“工具脚本”升级为“主 pipeline 的事实来源实现”。

**HOW**
- 文件：`scripts/rdc_analyzer/extract_pipeline_state.py:1`
- 推荐演进路径：
  - 把脚本中的“state 抽取逻辑”沉淀成可复用函数/类，被主 pipeline 调用；
  - 保留脚本作为 debug 工具（验证某条规则/某个 state 字段）。

#### 1.5.12 CallAnalyzer：调用级绑定/冗余分析（极致分析的关键抓手）

**WHAT**
- 面向 draw/dispatch 的“绑定层面”分析，典型能回答：
  - 这个 draw 绑定了什么资源？
  - 有哪些冗余绑定/无效绑定？
  - 哪些资源被绑定却未使用（或使用模式异常）？

**WHY**
- 在引擎里，很多性能问题不是“一个数值太大”，而是“绑定/状态管理策略错误”：
  - 例如多余的资源绑定、频繁切换 state、无效更新等。
- 对比当前项目现状：
  - 该模块结构清晰、很适合 A 口径输出建议（第 2 节认可）；
  - 但它依赖真实 PipelineSnapshot 才能达到“极致准确度”（第 2 节短板），而当前主 pipeline 还没喂它真实数据（第 3.1 节）。
- 因此它的重要性是：它是你从“统计型分析”升级到“根因定位”的关键能力，但前提是 P0-2 打通。

**HOW**
- 文件：`scripts/rdc_analyzer/analysis/call_analyzer.py:1`
- 建议的数据链路（对照现状）：
  - 输入：来自 ReplayWrapper 的 snapshot（绑定表/状态）
  - 输出：统一 Issue（P0-3），写入 canonical `analysis.json`（P0-1）

#### 1.5.13 ResourceTracker：资源生命周期/依赖图追踪（RAW/WAR/WAW 与 unused writes）

**WHAT**
- 追踪资源访问序列与依赖，输出：
  - RAW/WAR/WAW hazard
  - unused writes
  - 生命周期与首次/最后访问

**WHY**
- 这类信息非常“硬”，且能直接支撑“极致分析”的结论：
  - 许多性能/正确性问题来自资源访问顺序与同步/依赖管理不当；
  - unused writes 在移动端/带宽敏感场景特别重要。
- 对比当前项目现状：
  - 该模块已经能产出很强的深度信息（第 2 节优点），但同样没被主链路喂上真实数据（第 3.1 节）；
  - 主 pipeline 目前甚至用“假设整帧活跃 + read_count=1”的占位（`main.py:1041`/`main.py:1043`），会直接让 ResourceTracker 类结论失真。
- 重要性总结：这是你“极致分析”的王牌之一，但必须进入主路径并基于真实访问数据，否则会反噬可信度。

**HOW**
- 文件：`scripts/rdc_analyzer/analysis/resource_tracker.py:1`
- 推荐落地方式：
  - 作为 P0-2 的消费方：由 snapshot/访问记录驱动，而不是由占位字段驱动；
  - 输出统一 Issue，并在 HTML/JSON 中展示证据锚点（event_id/marker_path/资源 id）。

#### 1.5.14 DiffEngine：结构化差异对比（目标 2 的基础设施）

**WHAT**
- 对两份分析结果做结构化 diff：
  - draw/事件差异（支持顺序匹配与签名匹配）
  - texture/shader/buffer 差异
  - summary 差异
  - state diff（目前为简化实现）

**WHY**
- 对比能力不是“跑两次 analyze 再打印两个数字”，而是要解释“哪里变了、为什么变了、影响什么”：
  - 结构化 diff 是“结论”生成的底座。
- 对比当前项目现状：
  - DiffEngine 已有可用版本（第 2 节 7/10），说明你离目标 2 不远；
  - 但 state diff 较浅、匹配策略偏弱（第 2 节短板），而“稳定匹配”又是全方位对比的关键（P1-2）。
- 重要性在于：它决定了 compare 的“覆盖面”和“解释力”，没有它就无法做到全方位。

**HOW**
- 文件：`scripts/rdc_analyzer/diff/diff_engine.py:1`
- 关键点：
  - drawcall 匹配策略：`scripts/rdc_analyzer/diff/diff_engine.py:373`
  - state diff（简化）：`scripts/rdc_analyzer/diff/diff_engine.py:570`
- 推荐与 SSOT 的绑定方式：
  - diff 的输入应是 canonical `analysis.json`（P0-1），避免直接读多条 pipeline 的私有结构。

#### 1.5.15 RegressionDetector + regression_types：从 diff 里生成“结论”

**WHAT**
- 在 diff 的基础上做“阈值化判断”，输出：
  - 是否回归（is_regression_detected）
  - 回归项列表（REG001~REG007）
  - 结论摘要（summary）

**WHY**
- “对比”最后要给结论：让人一眼知道是否变坏、坏在哪里、优先排查什么。
- 对比当前项目现状：
  - 你已具备 v1 结论能力（第 2 节 7/10），这是很好的起点；
  - 但缺少“根因定位”（第 2 节短板）：也就是“到底是哪一批 draw/资源/状态变化导致回归”。
- 重要性在于：RegressionDetector 是你对外说服力的核心。没有根因锚点，它的结论会被质疑为“黑盒判定”。

**HOW**
- 文件：
  - `scripts/rdc_analyzer/diff/regression_detector.py:1`
  - `scripts/rdc_analyzer/diff/regression_types.py:1`
- 推荐增强方向（对照现状）：
  - 把每条回归结论绑定到证据锚点：marker_path + event_id + 关键数值变化（与 P0-4 的 compare 输出要求一致）。

#### 1.5.16 compare_rdc.py（现有对比脚本入口：偏“脚本型”，非一等 CLI）

**WHAT**
- 提供一个“脚本入口”执行两份数据的对比，当前更偏向 JSON 导出结果对比。

**WHY**
- 对比当前项目现状：
  - 它证明你已经把 compare 能力做出来了（并非从零开始）；
  - 但它不是 `python -m rdc_analyzer` 的一等子命令（第 3.3 节），会导致团队使用路径分裂、参数/输出不统一。
- 重要性：它是“现有实现资产”，但下一步应该被 P0-4 的 compare 子命令吸收，统一入口与数据源，而不是继续扩散脚本分支。

**HOW**
- 文件：`scripts/rdc_analyzer/compare_rdc.py:1`
- 建议演进：
  - 保留其内部实现为库函数（可复用），但将入口迁移到主 CLI compare。
  - 输入/输出改为 canonical schema（P0-1）与 compare schema（P0-4）。

#### 1.5.17 Tests（pytest 基座）：端到端可信的最后底座

**WHAT**
- 用单元测试保证规则/建议/diff/导出等逻辑在重构中不回归。

**WHY**
- 对比当前项目现状：
  - 你的测试覆盖面整体不错（第 2 节 8/10），但当前存在 4 fail + 1 error（第 3.4 节），且 integration 边界不清晰。
  - 在你要推进 P0（大量收敛/改造）之前，不把测试修到“可依赖”，你会不敢动手，也无法证明改动收益。
- 重要性：这是“让你敢重构、敢极致”的底座。没有它，你的项目会卡在“能跑但不敢改”。

**HOW**
- pytest 配置：`scripts/rdc_analyzer/pytest.ini:1`
- 当前已知问题证据：
  - `scripts/rdc_analyzer/tests/test_shader_extractor.py:243`（HTML_TEMPLATE 相关）
  - `scripts/rdc_analyzer/tests/test_resource_inspector.py:99`（controller fixture 缺失）
- 修复策略已在 P0-5 给出：明确 integration，保证 `-m 'not integration'` 全绿。

