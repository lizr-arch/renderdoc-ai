# RDC Analyzer：A/B/C 产品形态、使用场景与成熟方案调研（A 为第一闭环）

> 位置：`docs/analysis/codex_rdc_analyzer/`  
> 背景：你希望工具同时覆盖三类价值：  
> - A：单帧排查（极致性能分析 + 可执行建议）  
> - B：CI/回归门禁（baseline vs target 的可信结论）  
> - C：资产/内容审计（预算/规范/整改清单）  
> 决策：**先把 A 做成第一个闭环**，B/C 作为后续演进方向。  
> 更新时间：2025-01-20

---

## 0) 先立一个“总原则”（这决定你 A/B/C 能不能共存）

**原则：A/B/C 必须共享同一份事实来源（SSOT / Canonical Schema），否则会演变成三套互不兼容的产品线。**

- WHAT：同一份 capture，所有输出都围绕一套统一 schema（事件/资源/draw/pass/state/统计/issues/suggestions）。  
- WHY：  
  - A 需要“证据链”才能说服人；  
  - B 需要“稳定契约”才能当门禁；  
  - C 需要“可聚合的数据面”才能做清单与归因。  
- HOW：先把“对外契约”当成产品的地基（schema_version + 字段含义/单位/统计口径），再让 A/B/C 只是不同视角的报告与聚合。

---

## 1) A / B / C 的具体区别是什么？分别在什么使用环境？

为了避免“把 A 的逻辑硬塞到 B/C 导致误报/不可用”，这里用 WHAT/WHY/HOW + 典型失败模式 来划边界。

### A：单帧排查模式（Interactive Triage）

**WHAT（交付物）**
- 输入：一个 `.rdc`  
- 输出：Top 问题 + 证据链（event/draw/pass/resource）+ 可执行建议（步骤/风险/预期收益/验证方法）

**WHY（价值）**
- 解决“现在卡在哪、为什么卡、我该怎么改”的日常工程问题。  
- 价值核心：**定位深度 + 建议可执行**（不是“报表好看”）。

**HOW（使用环境/工作流）**
- 环境：本地开发机 / 性能实验机；人机交互为主。  
- 工作流：抓帧 → 分析 → 钻取证据（marker/pass/draw）→ 输出修复 playbook → 再抓帧验证。

**典型失败模式（必须主动防）**
- capture 信息不全（无 markers / 无真实 pipeline state / 无资源读写）导致建议“像玄学”；  
  → A 必须输出 `Confidence/DataQuality`（见第 3 章灵感）。

---

### B：CI/回归门禁模式（Regression Gate）

**WHAT（交付物）**
- 输入：baseline vs target（通常是一组 capture 或统计窗口，不建议只 1 帧）  
- 输出：pass/fail（exit code）+ 回归摘要 + 回归证据链 + 可追溯 artifacts（json/html）

**WHY（价值）**
- 解决“性能回退没人发现/发现太晚”的团队级痛点。  
- 价值核心：**稳定、可重复、低误报**。

**HOW（使用环境/工作流）**
- 环境：CI/夜间构建/专用性能机；无人值守。  
- 工作流：自动跑场景 → 自动抓帧/采样 → 与基线对比 → 输出 fail 原因。

**典型失败模式**
- 非确定性导致误报：单点差值不可靠 → B 需要“统计比较/分布比较”。  
- 输入 schema 漂移导致“猜字段/补 0” → 门禁会变得不可信，最终被关掉。

---

### C：资产/内容审计模式（Asset Budget & Hygiene）

**WHAT（交付物）**
- 输出：整改清单（超预算纹理/网格/材质/LOD/包体/疑似冗余资源）+ 预算归因（目录/模块/负责人）

**WHY（价值）**
- 解决“预算被内容吃爆、渲染团队背锅”的体系化问题。  
- 价值核心：**批量 + 清单化 + 可归因**（面向内容团队/TA，不是 event_id）。

**HOW（使用环境/工作流）**
- 环境：编辑器工具 + 夜间全量扫描。  
- 工作流：扫描资产/构建报告/运行时快照 → 聚合 → 输出整改清单（CSV/HTML/Treemap）。

**典型失败模式**
- 只基于某一帧 capture 判定“未使用资源”会误报（动态加载/Addressables）。  
  → C 必须把“疑似”与“验证建议”写清楚。

---

## 2) 市面上针对 A/B/C 是否已有成熟方案？他们怎么做？

> 目标不是“我们要复制一个 RenderDoc/PIX”，而是把成熟工具的核心设计抄到你的 analyzer 里：  
> 可信度、证据链、统计比较、对齐、可视化、自动化闭环。

### 2.1 A 类（单帧排查）成熟方案

1) RenderDoc（帧调试/事件级检查）  
   - WHAT：单帧捕获 + API/事件级查看与调试。  
   - HOW：UE 官方文档直接给出“在 Unreal 内启用 RenderDoc 插件并捕获”的闭环路径，且强调 capture 选项会影响信息量/体积。  
   - WHY（对你启发）：**“捕获选项 = 分析上限”**，你的工具应该内建 capture preflight（缺信息就降级/提示）。  
   - 参考：https://dev.epicgames.com/documentation/en-us/unreal-engine/using-renderdoc-with-unreal-engine

2) Unity RenderDoc Integration（抓帧闭环）  
   - WHAT：Unity Editor 与 RenderDoc 集成，让用户在编辑器里抓到可分析的 capture。  
   - WHY：A 模式最常见失败不是算法，而是“用户没抓到可分析数据”。  
   - 参考：https://docs.unity.cn/6000.2/Documentation/Manual/RenderDocIntegration.html

3) NVIDIA Nsight Graphics（帧分析 + 钻取 + marker）  
   - WHAT：按 draw/marker 展示并钻取 GPU 事件与性能信息；可保存会话供后续复用。  
   - WHY：你可以借鉴它的“分组/钻取方式”，让 issue 能跳转到证据（marker/pass/draw）。  
   - 参考：https://docs.nvidia.com/nsight-graphics/UserGuide/index.html

4) AMD RGP（更低层计数器，但要显式声明 replay 偏差）  
   - WHAT：更硬的 GPU 计数器视角；并提供 RenderDoc interop（BETA）。  
   - WHY：引入硬计数器前必须先解决“replay vs native”的可信度问题，否则会误导 A/B。  
   - 参考：https://gpuopen.com/manuals/rgp_manual/rgp_manual-renderdoc_and_rgp_interop/

---

### 2.2 B 类（对比与回归门禁）成熟方案

1) Microsoft PIX：Timing Capture Comparison Layout（统计比较）  
   - WHAT：为 timing captures 提供专用 compare layout，把比较做成“统计意义上的比较”，而不是单点差值。  
   - WHY（对你启发）：B 的核心不是 diff，而是**噪声控制 + 显著性**。  
   - 参考：https://devblogs.microsoft.com/pix/the-timing-capture-comparison-layout/

2) Nsight Graphics：Trace Compare（对齐 + delta）  
   - WHAT：双 trace 对齐，按事件/marker 关联，输出 side-by-side 与 delta。  
   - WHY：对齐到 marker 能显著降低噪声；delta table 提升可读性与可解释性。  
   - 参考：https://docs.nvidia.com/nsight-graphics/UserGuide/index.html

3) Unity Profile Analyzer（多帧统计 + 两数据集对比）  
   - WHAT：聚合多帧 marker 数据，并支持两数据集并排 compare（mean/median/percentile/histogram）。  
   - WHY：B 最怕误报，统计比较是最成熟的降噪路径之一。  
   - 参考：https://docs.unity.cn/Packages/com.unity.performance.profile-analyzer%401.2/manual/index.html

4) Unity Performance Testing（CI 友好的性能采样体系）  
   - WHAT：把性能测量纳入测试框架，记录运行配置 metadata，适配 CI。  
   - WHY：B 要能追溯“硬件/配置/版本”，否则 compare 结果不可复现。  
   - 参考：https://docs.unity.cn/Packages/com.unity.test-framework.performance%403.0/manual/index.html

5) Unreal Gauntlet（自动跑场景/会话编排）  
   - WHAT：自动化运行 UE session 的测试框架。  
   - WHY：B 最大成本往往在“稳定复现与自动跑场景”，而不是分析逻辑本身。  
   - 参考：https://dev.epicgames.com/documentation/en-us/unreal-engine/gauntlet-automation-framework-in-unreal-engine

---

### 2.3 C 类（资产/内容审计）成熟方案

1) Unreal Size Map（Treemap + 引用嵌套）  
   - WHAT：用 treemap 展示资产大小，嵌套结构表达引用关系。  
   - WHY（对你启发）：C 最强的展示形式之一就是 treemap：最大头一眼可见，并能解释“为什么被带进构建”。  
   - 参考：https://dev.epicgames.com/documentation/ja-jp/unreal-engine/cooking-content-and-creating-chunks-in-unreal-engine

2) Unity Build Report Inspector（构建输出占用归因）  
   - WHAT：基于 BuildReport 展示构建中包含的资源与占用。  
   - WHY：C 里“以构建为准”的资产清单比“单帧 capture 为准”更可靠。  
   - 参考：https://docs.unity3d.com/es/2019.3/Manual/com.unity.build-report-inspector.html

3) Unity Memory Profiler：snapshot compare（两快照对比）  
   - WHAT：对比两份内存快照，聚焦变化项，帮助定位增长来源。  
   - WHY：C 的“内存预算”必须能做 compare，否则无法闭环。  
   - 参考：https://docs.unity.cn/Packages/com.unity.memoryprofiler%401.1/manual/snapshots-comparison.html

4) AssetScope（Unity 资产扫描工具，含“疑似未引用”提示）  
   - WHAT：扫描项目列出最大资产、疑似未引用资源，并明确误判来源。  
   - WHY：C 的“疑似未引用”必须带风险提示与验证路径。  
   - 参考：https://assetscope.dev/

5) Asset Auditor Pro（UE 资产诊断类产品）  
   - WHAT：宣称扫描项目并报告 LOD/纹理/材质等问题，并给出使用情况报告。  
   - WHY：这类产品卖点是“清单可执行 + 可归因 + 扫描速度”，不是规则数量。  
   - 参考：https://www.fab.com/listings/7e245ff3-a7d0-4f02-82ef-ada094de3727

---

## 3) 我认为你最值得“直接抄”的 6 个设计灵感（同时服务 A→B→C）

### 灵感 1：把“数据可信度/覆盖率（Confidence）”作为一等输出
- WHAT：每个结论旁边输出 High/Medium/Low + 原因（缺 markers？缺真实 pipeline state？缺资源读写？）。  
- WHY：A 避免玄学建议；B 降误报；C 降误删风险。  
- HOW：定义 `DataQualityReport`，并在低可信时降级输出（只报能保证正确的结论）。

### 灵感 2：把“证据链（Evidence Chain）”结构化（不是一句话结论）
- WHAT：每条 issue/regression 都输出 top contributors（Top-K draws/resources/passes）+ event_id 列表。  
- WHY：说服力来自“可定位、可复现、可验证”；否则 A 不可执行、B 不可审计、C 不可整改。  
- HOW：统一 issue 模型：`issue + evidence + suggested_actions + verification_plan`。

### 灵感 3：B 模式必须做“统计比较”，不要只做单点差值
- WHAT：输出均值/中位数/分位数/直方图差异（至少给出采样数与置信度）。  
- WHY：CI 最怕误报，统计对比是成熟工业方案（PIX/Unity Profile Analyzer 的路线）。  
- HOW：先从最简单的：多次采样/多帧窗口 → 比较分位数 → 输出显著性提示。

### 灵感 4：双帧对齐（marker/pass）比“更复杂 diff”更重要
- WHAT：尽可能对齐到 marker/pass/pipeline signature，再做 diff。  
- WHY：对齐降低噪声，提高可读性。  
- HOW：引入稳定 identity（pipeline signature / resource signature / draw signature）。

### 灵感 5：C 的最佳 UI 形态是 treemap + 引用解释
- WHAT：按 size 的 treemap + 嵌套引用关系。  
- WHY：内容团队一眼就能看到“最大头”，并知道“为什么带进来”。  
- HOW：输出 `assets.json`（size + ref graph），HTML 用 treemap 展示。

### 灵感 6：把“抓帧标准化”纳入产品（Capture Preflight）
- WHAT：报告里自动提示“为了保证分析可信，需要开启哪些捕获选项/如何在 Unity/UE 做”。  
- WHY：A 的上限来自 capture 信息量；B 的稳定性来自标准化采集；C 的准确性也受数据完整性影响。  
- HOW：输出 preflight checklist（自动检测 + 文案建议），缺项就降级。

---

## 4) 决策：A 作为第一个闭环（B/C 以后做）

**WHY**
- A 最能直接变现价值：工程师拿到一个卡顿帧，马上能用。  
- A 做稳后，B/C 的难点会明显下降：  
  - A 迫使你把“证据链、可信度、schema”做扎实；  
  - 这些正是 B/C 的地基。

---

## 5) A-first：第一个闭环建议怎么做（每项 WHAT/WHY/HOW）

> 这里不讨论“更多规则/更多分析器”，而是讨论把 A 做成“能说服人、能闭环验证”的产品形态。

### A-1：输出 DataQuality/Confidence（第一天就能救命）
- WHAT：在报告头部输出数据覆盖率：markers/state/bindings/pass/resource RW 等是否存在。  
- WHY：避免“占位/启发式”结论被当成事实；提升信任。  
- HOW：定义 `coverage` 字段；每个 issue 也带 `confidence`。

### A-2：Issue 必须带 Evidence Chain（Top-K + event_id）
- WHAT：每个 issue 输出 top contributors（Top-K draws/resources/passes）与 event_id 列表。  
- WHY：没有证据链就无法行动，工具会被认为“空话”。  
- HOW：在采集阶段就把 draw/pass/resource 做稳定 id，并在 issue 中引用。

### A-3：建议输出 Playbook（Unity / UE / 自研三套 HOW）
- WHAT：同一问题输出不同引擎的落地步骤模板（可先只覆盖 2-3 个最常见问题）。  
- WHY：建议的价值不是“告诉你减少 draw call”，而是“怎么做”。  
- HOW：建议结构：`steps + expected_impact + risk + verification`。

### A-4：把“验证方法”写进建议（形成 A 的自闭环）
- WHAT：每条建议带 `verification_plan`（改完后再抓一帧应看到哪些指标下降）。  
- WHY：你要求 WHAT/HOW/WHY 说服你，最强说服来自“可验证”。  
- HOW：输出 `before/after` 对比提示，哪怕先是粗粒度指标。

### A-5：Capture Preflight（把抓帧标准化）
- WHAT：当关键数据缺失时，报告里提示用户如何在 Unity/UE 抓到“可分析 capture”。  
- WHY：减少“分析不准”的根因（不是算法问题，是输入不足）。  
- HOW：输出 checklist + 链接到官方抓帧指南。

---

## 6) 下一步（你已经决定：A 先做）

你已经安排其他 AI 做“单帧深度分析”和“双帧深度分析”。对你而言最值得补齐的是：

- 把 A 做成可说服人的产品闭环：**可信度 + 证据链 + 可执行建议 + 验证方法**  
- 让这一套输出成为未来 B/C 的地基（共享 schema / identity / evidence）

---

## 7) A-first Definition of Done（DoD / 验收标准，带 WHAT/WHY/HOW）

> 目标：明确“做到什么算 A 闭环完成”。否则 A 很容易变成“功能很多，但说服力不足、落不到改动、无法验证”。  
> 这些 DoD 的设计刻意对齐你当前仓库的真实风险点：多套 schema/多入口、占位 state、阈值 key 漂移、issue 模型不统一等。

### 7.1 一条命令跑通（端到端可用性）

**WHAT（验收条件）**
- 用户可以用**一条命令**完成单帧分析并得到可读报告（HTML）+ 机器可读输出（JSON）。

**WHY（为什么这是 DoD）**
- A 的第一价值是“拿到一帧就能用”；如果需要串脚本/改代码/手工拷文件，团队很难每天用。  
- 这也是你后续做 B/C（自动化/批量）的必备基础。

**HOW（怎么验收）**
- 运行命令（示例）：
  - `py -3 -m rdc_analyzer analyze <capture.rdc> -o <out_dir> --format html,json --platform pc`
- Pass 标准：
  - 命令返回码为 0
  - `<out_dir>` 下产出 1 个 HTML + 1 个 JSON（命名可带 timestamp）
  - 控制台输出至少包含：总耗时、drawcall/纹理/buffer 等摘要 + 问题数量

---

### 7.2 输出契约稳定（Canonical Schema v1）

**WHAT**
- 输出 JSON 明确包含 `schema_version`（例如 `"schema_version": "1.0"`）。
- JSON 至少包含这些顶层块（名称可调整，但必须有等价结构）：
  - `meta`（输入文件、时间、工具版本、平台、API、运行配置）
  - `summary`（关键指标与单位）
  - `issues`（问题列表）
  - `suggestions`（建议列表）
  - `coverage` / `data_quality`（数据质量/可信度）
  - `evidence_index`（可选，但推荐：把 event_id/draw/pass/resource 的引用结构化）

**WHY**
- A 要“说服人”必须可追溯；B/C 要复用必须稳定。  
- 你当前仓库曾出现“多 schema 并存 + compare 兼容补 0”，这会直接摧毁可信度。A-first 必须先断掉这种风险。

**HOW**
- 验收方式：对同一个 capture 连续跑 2 次，JSON 除了 `timestamp` 外，其余字段在语义上应一致（排序/稳定性可以通过规范化输出保证）。
- 文档要求：在 `docs/analysis/codex_rdc_analyzer/` 里维护 `schema` 文档（字段含义/单位/统计口径）。

---

### 7.3 DataQuality/Confidence 成为一等输出（防玄学）

**WHAT**
- 报告头部必须输出 `coverage/data_quality`：对关键数据面给出 `present/missing/estimated` 三态（或类似），并给出理由。
- 每条 `issue/suggestion` 必须携带 `confidence`（High/Medium/Low）与 `confidence_reasons`。

**WHY**
- 你当前仓库里存在“占位 state/占位资源生命周期”的现实风险。没有 confidence，用户会把启发式当事实，从而不信任工具。  
- A 模式要敢给建议，必须敢在数据不足时说“我不确定”。

**HOW**
- 验收方式：造一个“缺 markers/缺 state”的 capture（或在选项里关闭对应采集），报告仍能输出，但关键结论会降级（例如只输出粗统计与低置信度建议）。

---

### 7.4 Issue 必须有证据链（Evidence Chain）

**WHAT**
- 每条 issue 至少包含：
  - `rule_id/code`、`severity`、`category`
  - `message`（人类可读）
  - `evidence`：至少提供以下之一（越多越好）：
    - `event_ids`（Top-K）
    - `draw_signatures` / `pipeline_signatures`（可选）
    - `resource_ids`（纹理/Buffer/RT 等）
    - `pass/marker path`（例如 `"pass_path": "Main/Transparent/UI"`）

**WHY**
- A 的“可执行性”来自证据链：你告诉我哪里有问题，我才能改；否则 A 只是统计报表。  
- 证据链也是你未来 B（门禁）里“解释回归”的关键材料。

**HOW**
- 验收方式：从 HTML 报告中随机点 1 条 issue，必须能回溯到具体 event/draw/resource（哪怕是 Top3）。

---

### 7.5 建议必须是 Playbook（不是一句话）

**WHAT**
- 每条 suggestion 至少包含结构化字段：
  - `steps`（分步骤，能执行）
  - `expected_impact`（至少包含一个：drawcall/vertex/bandwidth/ms 的方向性或粗估）
  - `risk`（例如可能的画质风险/内存风险）
  - `engine_howto`（可选但推荐）：Unity/Unreal/自研引擎各自的落地提示（先覆盖最常见 2-3 类即可）

**WHY**
- 你要求 WHAT/HOW/WHY 说服你：建议如果不能落成步骤，就无法说服，也无法形成团队实践。  
- 成熟工具链（Unity/UE 的最佳实践）本质上就是一套 playbook。

**HOW**
- 验收方式：选择至少 3 类常见问题（例如：小批次、未压缩纹理、过多全屏 pass），每类至少输出 1 条带 steps 的 suggestion。

---

### 7.6 每条建议必须带验证方法（A 闭环的闭环）

**WHAT**
- 每条 suggestion 必须带 `verification_plan`：告诉用户“改完后再抓一帧，哪些指标应该下降/变化”。

**WHY**
- A 的终极闭环不是“给建议”，而是“建议可验证”。  
- 有了 verification_plan，A 自然能升级成 B（回归门禁）——因为你已经定义了“什么算变好/变坏”。

**HOW**
- 验收方式：对 1 条建议，报告里必须明确列出：
  - 关注指标（例如 draw calls、texture memory、fullscreen passes）
  - 预期变化方向（下降/上升/不变）
  - 推荐对比方式（baseline vs target 的同场景 capture）

---

### 7.7 Capture Preflight（把“如何抓到可分析数据”纳入产品）

**WHAT**
- 报告必须包含 “Preflight” 区块：当关键数据缺失时，提示用户如何在 Unity/UE/自研引擎抓到更完整的 capture。

**WHY**
- A 的上限来自输入信息量；如果不教用户怎么抓帧，工具会因为“输入不足”被误判为“不准”。

**HOW**
- 验收方式：当发现缺少关键数据（例如 markers/pipeline state），Preflight 必须出现，并给出可操作的链接/步骤。

---

### 7.8 工程质量底线（让 A 变成“可长期用的工具”）

**WHAT**
- 测试：`py -3 -m pytest -m 'not integration' scripts/rdc_analyzer/tests` 通过（或等价规则：单测全绿；integration 明确标记）。
- 输出可重复：同一输入多次运行，除时间戳外输出稳定（至少排序稳定）。
- 性能：对典型 capture（你选的内部样例）在可接受时间内完成（你可以自定义门槛，例如 30s/3min/10min 三档）。

**WHY**
- 没有测试与稳定性，A 的每次改动都会引入“看不见的回归”，最终没人敢用。  
- A 做稳后才有资格推进 B/C。

**HOW**
- 在 repo 里保留一组“基准样例 capture”（可以是脱敏/小样），并把它作为回归验证集（不一定提交大文件，可用内部路径或 CI artifact）。

