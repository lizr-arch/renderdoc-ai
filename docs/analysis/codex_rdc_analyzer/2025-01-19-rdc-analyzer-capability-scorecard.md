# RDC Analyzer 能力盘点 / 冲突点 / 路线图（Codex 专属笔记）

> 目的：把当前 `scripts/rdc_analyzer/` 的实现现状、冲突点、优缺点、以及“必须要做的事”的优先级固化在仓库里，避免以后丢失。  
> 适用范围：仅覆盖二次开发目录 `scripts/rdc_analyzer/`（不评价 RenderDoc 主工程 C++ 代码本身）。  
> 更新日期：2025-01-19  
> 作者：Codex（本仓库内的辅助分析记录）

---

## 快速索引（避免单文件过长）

- 总索引：`docs/analysis/codex_rdc_analyzer/README.md`
- 功能明细（WHAT/WHY/HOW）：`docs/analysis/codex_rdc_analyzer/2025-01-19-rdc-analyzer-feature-details.md`
- 深度下钻（WHAT/WHY/HOW）：`docs/analysis/codex_rdc_analyzer/2025-01-19-rdc-analyzer-key-deep-dive.md`
- 规则逐条（36 条 RD_*）：`docs/analysis/codex_rdc_analyzer/2025-01-20-rdc-analyzer-rules-*.md`
- Schema/对外契约：`docs/analysis/codex_rdc_analyzer/2025-01-20-rdc-analyzer-schema-*.md`

---

## 0. 你的核心目标（SSOT）

你明确的两大核心能力：

1. **单个 RDC 的性能分析（极致）+ 建议**
2. **两个 RDC 的对比（全方位）+ 结论**

你选择的验收口径：**A（规则与建议驱动）**  
也就是：规则覆盖要足够、建议要可执行、并且尽量能定位到事件/资源（B/C 未来再做）。

---

## 0.1 2025-01-23 复审增补（A-first 验证链闭合）

> 结论：默认验证路径已统一，测试归属/覆盖缺口已补齐。

1) **关键集成测试已纳入默认验证**  
   - 证据：`scripts/rdc_analyzer/pytest.ini:2` 包含 `../../tests`，默认 `py -3 -m pytest -q -rs` 覆盖根 tests。  
   - 结果：`501 passed, 8 skipped`（2025-01-23）。

2) **`scripts/rdc_analyzer/tests` 已可追踪**  
   - 证据：`.gitignore` 已放开 `scripts/rdc_analyzer/tests/**/*.py`。  
   - 结果：测试可复现。

> 这些问题已同步为新的 P0 任务（P0-NEW-5/6/7），需要先补齐再宣称 A-first “完成”。

---

## 1. 我看到你“已经实现了什么”（按目标归类）

> 注意：这里的“实现”是从代码路径 + 单测覆盖面判断的现状，不代表所有链路已经端到端贯通。

### 1.1 单个 RDC：分析入口与输出

**新端到端管线（主入口之一）**

- CLI 入口：`scripts/rdc_analyzer/__main__.py:26`（`python -m rdc_analyzer analyze ...`）
- 新管线：`scripts/rdc_analyzer/main.py:147`（`class AnalysisPipeline`）
  - 打开 capture：`scripts/rdc_analyzer/main.py:282`（`_open_capture`）
  - 解析事件/DrawCall：`scripts/rdc_analyzer/main.py:316`（`_parse_events`）
  - 拉取资源（textures/buffers）：`scripts/rdc_analyzer/main.py:350`（`_extract_states`）
  - 规则/性能/Mali 分析：`scripts/rdc_analyzer/main.py:403`（`_analyze_rules`）
  - 导出报告（JSON/HTML）：`scripts/rdc_analyzer/main.py:941`（`_export_reports`）

**旧模块化管线（与新管线并存）**

- `scripts/rdc_analyzer/pipeline.py:23`（`AnalysisPipeline`）
- 便捷函数：`scripts/rdc_analyzer/pipeline.py:107`（`analyze_rdc(...)`）

**纹理导出 + 100% 离线纹理报告（另一个“产品线”）**

- 导出纹理（需要 RenderDoc API 可用）：`scripts/rdc_analyzer/export_textures.py:40`（`TextureExporter`）
- 离线 HTML（不需要网络；依赖 PIL 可选）：`scripts/rdc_analyzer/generate_offline_report.py:133`（`generate_offline_html`）

### 1.2 单个 RDC：规则与建议（A 口径）

**规则系统（36 条）**

- 规则注册/基类：`scripts/rdc_analyzer/rules/base.py:15`（`BaseRule` / `RuleRegistry`）
- 规则执行：`scripts/rdc_analyzer/rules/runner.py:14`（`RuleRunner`）
- 规则清单（自动生成的文档）：`scripts/rdc_analyzer/RULES.md:1`

**性能分析器（PERF001-PERF007）**

- `scripts/rdc_analyzer/analyzers/performance_analyzer.py:1`

**“建议”能力（目前更强的是纹理维度）**

- 纹理优化建议生成器：`scripts/rdc_analyzer/core/optimization_advisor.py:1`

### 1.3 单个 RDC：更“极致”的深度分析模块（能力存在，但集成不足）

这些模块具备做“极致分析”的潜质（真实 state、依赖、冗余绑定），但目前没有成为“主干输出”的唯一事实来源：

- RenderDoc 回放封装（生命周期、安全 API、遍历 drawcall 等）：`scripts/rdc_analyzer/extractors/replay_wrapper.py:1`
- 真实 pipeline state 抽取脚本：`scripts/rdc_analyzer/extract_pipeline_state.py:1`
- 调用级绑定/冗余分析器：`scripts/rdc_analyzer/analysis/call_analyzer.py:1`
- 资源生命周期/依赖图追踪器：`scripts/rdc_analyzer/analysis/resource_tracker.py:1`

### 1.4 两个 RDC：对比与结论

**差异对比引擎（DiffEngine）**

- `scripts/rdc_analyzer/diff/diff_engine.py:1`
- DrawCall 对比支持两种策略（顺序 vs 签名匹配）：`scripts/rdc_analyzer/diff/diff_engine.py:373`
- State 对比目前是“简化实现”：`scripts/rdc_analyzer/diff/diff_engine.py:570`

**回归检测（RegressionDetector + REG001~REG007）**

- `scripts/rdc_analyzer/diff/regression_detector.py:1`
- 规则定义与阈值：`scripts/rdc_analyzer/diff/regression_types.py:1`

**对比脚本入口（目前更多面向 JSON 导出对比）**

- `scripts/rdc_analyzer/compare_rdc.py:1`

---

### 1.5 功能明细：WHAT / WHY / HOW（对照当前项目现状，解释“为什么重要”）

> 章节已拆分到单独文档（避免单文件 > 800 行）：
> - `D:/Code/git/renderdoc/docs/analysis/codex_rdc_analyzer/2025-01-19-rdc-analyzer-feature-details.md`

### 1.6 深度下钻（你选择的 3：优先把 5–10 个“最关键功能”讲透）

> 章节已拆分到单独文档（避免单文件 > 800 行）：
> - `D:/Code/git/renderdoc/docs/analysis/codex_rdc_analyzer/2025-01-19-rdc-analyzer-key-deep-dive.md`

## 2. 打分表（已完成 / 部分完成 / 冲突功能）

评分维度（0-10）：
- 深度/“极致程度”
- 端到端可用性（是否一条命令跑通）
- 一致性与可维护性（是否只有一条权威链路）

| 模块/能力 | 状态 | 分数 | 证据（关键文件） | 优点 | 主要短板 |
|---|---|---:|---|---|---|
| 单个 RDC：新端到端分析（`main.py`） | 部分完成 | 6.5 | `scripts/rdc_analyzer/main.py:147` | CLI 形态清晰；能导出 HTML/JSON | HTML 导出阶段用“模拟 DrawCallDetail”而不是真实 state（见下文冲突点）；shader_count 未实现 |
| 单个 RDC：深度回放与 state 读取（ReplayWrapper） | 能力已完成，未产品化 | 8.5（能力）/6（集成） | `scripts/rdc_analyzer/extractors/replay_wrapper.py:1` | 抽象扎实，适合作为唯一事实来源 | 未成为 main pipeline 的权威数据源 |
| 单个 RDC：调用级绑定/冗余分析（CallAnalyzer） | 已完成（模块） | 8 | `scripts/rdc_analyzer/analysis/call_analyzer.py:1` | 规则结构清晰，适合 A 口径输出建议 | 需要真实 PipelineSnapshot 才能达到“极致”准确度 |
| 单个 RDC：资源依赖/生命周期（ResourceTracker） | 已完成（模块） | 8 | `scripts/rdc_analyzer/analysis/resource_tracker.py:1` | 能产出 RAW/WAR/WAW 与 unused writes，这类信息很“极致” | 同样依赖真实资源访问数据；目前主流程未喂它 |
| 单个 RDC：规则系统（36条） | 已完成，但口径不统一风险较高 | 7（覆盖）/5（口径） | `scripts/rdc_analyzer/rules/base.py:15` | 易扩展、可配置 | 与新管线/旧管线的数据结构不一致风险（见冲突点） |
| 单个 RDC：性能分析器（PERF001~007） | 已完成（模块） | 7 | `scripts/rdc_analyzer/analyzers/performance_analyzer.py:1` | 已具备规则化输出结构 | 需要更强的数据来源（pass/state/绑定）来避免“启发式估计” |
| 单个 RDC：建议生成（OptimizationAdvisor） | 已完成（纹理维度强） | 7.5 | `scripts/rdc_analyzer/core/optimization_advisor.py:1` | 可执行步骤 + 估算收益 + 优先级排序 | 建议覆盖面偏纹理；全局性能建议未统一格式 |
| 两个 RDC：DiffEngine | 已完成“可用版” | 7 | `scripts/rdc_analyzer/diff/diff_engine.py:1` | summary/texture/shader/buffer/draw 都能产出 diff | state diff 目前很浅；匹配策略偏弱 |
| 两个 RDC：回归结论（RegressionDetector） | 已完成“v1 结论” | 7 | `scripts/rdc_analyzer/diff/regression_detector.py:1` | 阈值化规则 + is_regression_detected | 缺“根因定位”（是哪一批 draw/资源导致） |
| 端到端验证（tests） | 部分完成 | 6 | `scripts/rdc_analyzer/pytest.ini:1` | 单测覆盖量大 | **测试分散且未统一入口**：关键测试在 repo 根 `tests/`，且 `scripts/rdc_analyzer/tests` 有未纳入 Git 的测试，导致结果不可复现 |

---

## 3. 已发现的冲突/技术债（影响“极致”和“全方位”的关键问题）

### 3.1 “主分析链路”与“最强分析能力”脱节（P0）

新端到端管线在导出 HTML 时，为了适配 HTMLExporter，**用动态 type 造了“简化 DrawCallDetail 模型”**，而不是用真实的 pipeline snapshot：

- `scripts/rdc_analyzer/main.py:1005`（`detail = type('DrawCallDetail', (), { ... })()`）

同时资源生命周期也是“假设整帧活跃 + read_count=1”的占位实现：

- `scripts/rdc_analyzer/main.py:1041`（`first_access_event = 1`）
- `scripts/rdc_analyzer/main.py:1043`（`read_count = 1  # 假设至少被读取一次`）

这会直接导致：
- CallAnalyzer / ResourceTracker 这类“极致分析模块”无法被真正喂上真实数据
- 规则与建议很难做到“可定位、可复现、可解释”（即 A 口径也会变成“泛泛建议”）

### 3.2 三套“分析入口/数据模型”并存（P0）

至少三条并行链路：
- 新端到端 `main.py`：`scripts/rdc_analyzer/main.py:147`
- 旧模块化 `pipeline.py`：`scripts/rdc_analyzer/pipeline.py:23`
- 深度分析模块：`ReplayWrapper` + `call_analyzer/resource_tracker`

风险：
- 输出 JSON 字段口径不同，compare/diff 很难保证“同口径对比”
- 规则阈值与建议格式会漂移

### 3.3 对比是“核心目标”，但当前入口不是一级命令（P0）

对比脚本目前是 `scripts/rdc_analyzer/compare_rdc.py:1`，而 `python -m rdc_analyzer` 的主 CLI 子命令只有 analyze/rules（见 `scripts/rdc_analyzer/__main__.py:26`）。  
这会让“目标 2”在产品形态上弱于“目标 1”。

### 3.4 当前测试集存在“冲突/缺失 fixture”（P0）

我在 Windows 上执行：`py -3 -m pytest -q scripts/rdc_analyzer/tests -m 'not integration'`  
结果：261 items 中 **4 failed + 1 error**（其余通过）。

主要问题：

1) HTML 模板常量缺失：测试期待 `HTML_TEMPLATE`，但实现已转向 `TemplateLoader`  
   - `scripts/rdc_analyzer/tests/test_shader_extractor.py:243`（以及 251/259/267）

2) Replay 环境 fixture 缺失：`controller` fixture 不存在，但 test 没有标记为 integration 或 skip  
   - `scripts/rdc_analyzer/tests/test_resource_inspector.py:99`

---

## 4. 网上资料：游戏/引擎侧最关心什么指标？有什么“标准/阈值”？

你要求“各 5 篇”，我按 **两类**整理，并把可抽取的指标/阈值映射到 A 口径（规则与建议）。

> 注：这些资料里给的数值多带有前提（平台/画面/引擎版本/目标帧率）。本节的价值是：把它们沉淀成“规则阈值的默认 seed”，并明确出处与适用范围。

### 4.1 优化/性能最佳实践（5 篇）

1) Unity Manual: Optimizing graphics performance  
   - 链接：https://docs.unity3d.com/Manual/OptimizingGraphicsPerformance.html  
   - 关注点：batches/draw call、顶点/三角形规模、材质/纹理、shader 与带宽  
   - 可抽取阈值（Unity 文档给出建议范围）：  
     - **PC：每帧顶点数建议控制在 ~200K 到 ~3M（取决于 GPU/场景）**  
     - **Mobile：一般建议不超过 ~100K 顶点/帧（经验值，具体取决于设备与 shader）**  
   - 映射到你的规则/建议：`draw_call_count`、`total_vertices/triangles`、纹理压缩/mipmap/材质合并

2) Unreal Engine Docs: Introduction to Performance Profiling and Configuration in Unreal Engine  
   - 链接：https://dev.epicgames.com/documentation/en-us/unreal-engine/introduction-to-performance-profiling-and-configuration-in-unreal-engine  
   - 关注点：frame time（ms） vs FPS、性能预算、UE 的 profiling 工具链与定位路径  
   - 可抽取标准：**常见目标 FPS：30/60/120（对应预算 ~33.33/16.66/8.33ms）**  
   - 映射：把所有“阈值”绑定到 target FPS（移动端默认 30/60，PC 默认 60/120）

3) AMD GPUOpen: Unreal Engine Performance Guide  
   - 链接：https://gpuopen.com/learn/unreal-engine-performance-guide/  
   - 关注点：Unreal Insights、stat 命令、RGP（低层 GPU 捕获）与 case study（ms 级收益）  
   - 可抽取标准：把“优化收益”落到 **ms 与帧预算百分比**（例如 0.3ms ≈ 60FPS 预算的 2%）  
   - 映射：你的建议系统可以输出 `estimated_ms_saved`（哪怕先是粗估）提升说服力

4) Android Developers (AGI): Analyze texture memory bandwidth usage  
   - 链接：https://developer.android.com/agi/sys-trace/texture-memory-bw  
   - 关注点：纹理带宽（平均/峰值）、纹理 L1 cache miss、mipmap/压缩/AF 的成本权衡  
   - 可抽取阈值（AGI 文档给出推荐值，尤其针对 Adreno）：  
     - **平均 texture read bandwidth ≤ 1 GB/s**  
     - **峰值 ≤ 3 GB/s**  
     - **Texture L1 cache miss ≤ 10%**  
   - 映射：移动端规则不应只看“尺寸/格式”，还应引入“带宽风险”解释（P1+）

5) NVIDIA GPU Gems 1: Chapter 28 — Graphics Pipeline Performance  
   - 链接：https://developer.nvidia.com/gpugems/gpugems/part-v-performance-and-practicalities/chapter-28-graphics-pipeline-performance  
   - 关注点：通用 GPU pipeline 瓶颈分类（batch/state/bandwidth/shader）与定位方法  
   - 可抽取标准：把你的报告组织成“瓶颈分类 + 证据链 + 建议动作”，适配自研引擎

> 备注：这 5 篇刻意覆盖 Unity + Unreal + 移动端 GPU（AGI）+ 通用 GPU 原理（自研引擎可直接套用）。

### 4.2 RenderDoc 使用教学/教程（5 篇）

1) Unreal Engine Docs: Using RenderDoc with Unreal Engine  
   - 链接：https://dev.epicgames.com/documentation/en-us/unreal-engine/using-renderdoc-with-unreal-engine  
   - 重点：UE 内置 RenderDoc 插件的开启方式、capture 流程、以及 capture 配置项（会显著影响 capture 体积/信息量）  
   - 对你的工具价值：你可以把这些“捕获设置”写成 analyzer 的 **前置检查/建议**，避免“数据缺失导致分析不准”

2) Unity Manual: RenderDoc integration  
   - 链接：https://docs.unity.cn/6000.2/Documentation/Manual/RenderDocIntegration.html  
   - 重点：Unity Editor 里加载 RenderDoc、捕获流程、以及 D3D11 shader debug symbols 提示  
   - 对你的工具价值：把“如何抓到可分析的 capture”写进报告，形成闭环（尤其是 shader/debug info）

3) Arm Learning Path: Use RenderDoc to debug and analyze workloads  
   - 链接：https://learn.arm.com/learning-paths/mobile-graphics-and-gaming/vulkan-ml-sample/5-renderdoc/  
   - 重点：移动端 Vulkan 抓帧、查看 API calls、资源状态与内存使用  
   - 对你的工具价值：帮助你把 mobile 规则与“真实抓帧路径”对齐（减少用户环境差异）

4) baldurk/renderdoc Wiki: Vulkan  
   - 链接：https://github.com/baldurk/renderdoc/wiki/Vulkan  
   - 重点：Vulkan 捕获的使用方式、implicit layer 机制、以及注意事项（RenderDoc 不是 validation debugger）  
   - 对你的工具价值：对于自研引擎（Vulkan/D3D12）用户，这是“最低成本的正确使用说明”

5) Debian Sources: RenderDoc Python API Getting Started（文档镜像）  
   - 链接：https://sources.debian.org/src/renderdoc/1.11%2Bdfsg-5/docs/python_api/examples/renderdoc_intro.rst/  
   - 重点：Python API 的使用方式与注意事项（版本匹配、模块加载、示例路径）  
   - 对你的工具价值：你要做自动化分析（单帧/批量/对比），Python API 是事实采集的最强杠杆；Debian 镜像在很多环境更稳定可访问

---

## 5. A（规则+建议）口径下：你现在“最缺什么”？

一句话：**缺一个“统一、可信、可复用”的事实来源**，让规则与建议建立在同一份真实数据之上，而不是在导出时用占位对象拼装。

对应到仓库现状，有三个关键缺口：

1) **真实 PipelineSnapshot / 资源访问数据没有进入主报告**  
   - `main.py` 在导出阶段做了大量“模拟/假设”，见 `scripts/rdc_analyzer/main.py:1005`、`scripts/rdc_analyzer/main.py:1043`。

2) **三套管线并存导致规则/建议口径漂移**  
   - `main.py`、`pipeline.py`、以及 `analysis/*` 的深度模块未统一成一条权威链路。

3) **测试红灯点正好落在“对外 API/集成边界”**  
   - HTML exporter 的模板 API 重构未同步测试：`scripts/rdc_analyzer/tests/test_shader_extractor.py:243`  
   - replay fixture 缺失说明 integration boundary 没定清：`scripts/rdc_analyzer/tests/test_resource_inspector.py:99`

---

## 6. 【必须要做】优先级列表（P0→P2）

> 这是你要求的“单独标题 + 优先级”，并且只围绕 A（规则与建议驱动）+ 目标 2（对比结论）展开。  
> 不做 B/C（可复现诊断/UI 跳转等）级别的扩展。

### P0（必须先做，否则“极致/全方位”不可信）

1) **统一单帧输出的 Canonical Schema（唯一权威 JSON 结构）**  
   - 理由：目前多条链路输出字段口径不一致（`main.py` vs `pipeline.py` vs xml/json），compare/diff 很难做到“同口径对比”。  
   - 目标：单帧分析产出 `analysis.json`（事件、draw、资源、统计、issues、suggestions）成为唯一事实来源。

2) **让主分析链路产出真实的 DrawCallDetail/PipelineSnapshot（移除 main.py 的占位实现）**  
   - 理由：`scripts/rdc_analyzer/main.py:1005` 的模拟对象会直接把分析深度锁死在“启发式”。  
   - 目标：主链路直接使用 `ReplayWrapper`（`scripts/rdc_analyzer/extractors/replay_wrapper.py:1`）生成真实 state，再喂给 CallAnalyzer/ResourceTracker。

3) **统一 Issue/Rule/Suggestion 的数据结构（跨模块）**  
   - 理由：目前存在 `Issue`（core/types）、`BindingIssue`（analysis/call_analyzer）、以及 rules 的 Issue，多套模型会导致 exporter/compare 无法统一展示与排序。  
   - 目标：统一字段：`code/rule_id`、`severity`、`category`、`message`、`event_id`、`resource_ids`、`suggestion_steps`。

4) **把 compare 做成一级 CLI 子命令，并明确输入源**  
   - 理由：对比是核心目标 2，但目前不是 `python -m rdc_analyzer` 的一级命令。  
   - 目标：`python -m rdc_analyzer compare baseline.rdc target.rdc ...`（内部可先导出 canonical JSON 再 diff）。

5) **修复当前测试红灯（或正确标记 integration）**  
   - 理由：验证系统必须可信，尤其你要做“极致/全方位”。  
   - 目标：至少保证 `py -3 -m pytest -m 'not integration'` 全绿；把需要 RenderDoc 环境的用例标为 integration/skip。

#### P0-1：统一单帧分析 Canonical Schema（唯一权威 JSON）——WHAT / WHY / HOW

**WHAT（交付物是什么）**
- 定义并落地一个**唯一权威**的单帧分析输出结构：`analysis.json`（带 `schema_version`）。
- 约束：所有下游（HTML exporter、compare/diff、regression detector、二次开发脚本）都**只**消费这份 JSON，不再直接读 `main.py` 的内部对象/临时 dict。

**WHY（为什么必须做）**
- 你目前存在多条分析路径与多种输出口径（例如 `scripts/rdc_analyzer/main.py` vs `scripts/rdc_analyzer/pipeline.py` vs 各类脚本输出），字段不一致会直接导致：
  - 对比（目标 2）做不出“同口径”结论，结论不可信。
  - 导出（JSON/HTML）与测试出现 API 漂移，一次小改就引发连锁回归。
- 你选定的 A（规则 + 建议）要求“可复查”：别人只拿到 `analysis.json` 就能复现你的问题与证据链（event/资源/数值），没有 SSOT 做不到。

**HOW（怎么做）**
- 先落地“最小可闭环 schema”（先保证工程闭环，再迭代字段深度），建议至少包含：
  - `meta`：capture 信息（路径/hash）、API、平台、工具版本、时间戳
  - `stats`：draw/dispatch 数量、marker 树摘要、资源总量摘要
  - `events`：关键事件列表（`event_id` + `marker_path` + `action_type`）
  - `resources`：textures/buffers 的稳定描述（name/format/dim/usage…）
  - `issues`：统一 issue 列表（见 P0-3）
  - `suggestions`：统一建议列表（可引用 issue）
- 收敛入口/数据流（减少“隐式魔法”）：
  - `scripts/rdc_analyzer/main.py` 与 `scripts/rdc_analyzer/pipeline.py` 都返回同一种 `AnalysisResult`（对象或 dict），再统一序列化为 `analysis.json`。
  - `scripts/rdc_analyzer/main.py` 的 `_export_reports` 只负责输出（序列化），不再补字段/猜字段。
- 验收口径（Done when）：
  - 同一份 `analysis.json` 能被 HTML exporter、compare/diff、regression detector 共同消费，不需要任何“适配层/特判拼装”。
  - schema 有版本号；新增字段不破坏旧字段；缺失字段有明确默认策略（或显式 `null`）。

#### P0-2：打通真实 DrawCallDetail / PipelineSnapshot（移除占位 state）——WHAT / WHY / HOW

**WHAT（交付物是什么）**
- 单帧分析中，对关键 draw/dispatch event 能抓到**真实 Replay**的 `PipelineSnapshot` / `DrawCallDetail`（最小字段也可以，但必须真实）。
- 移除/绕开 `scripts/rdc_analyzer/main.py` 的“占位 state/模拟拼装”路径，避免污染下游规则与 compare。

**WHY（为什么必须做）**
- “极致性能分析 + 建议”必须基于真实 pipeline state，否则建议不可执行、对比结论不可信（本质是“对着假数据开药方”）。
- 目前主 pipeline 已存在占位/模拟 state 的写入点（见文档前文对 `scripts/rdc_analyzer/main.py:1005` / `scripts/rdc_analyzer/main.py:1043` 的定位），这会污染任何规则系统与对比结论。
- 你其实已经有更贴近真实数据源的模块（例如 `scripts/rdc_analyzer/extractors/replay_wrapper.py`、`scripts/rdc_analyzer/extract_pipeline_state.py`、`scripts/rdc_analyzer/analysis/*`），但它们尚未成为“主路径的唯一真实来源”。

**HOW（怎么做）**
- 事件选择策略（避免 P0 直接变成性能黑洞）：
  - 先只对 draw/dispatch + marker 叶子节点抓 snapshot（不要对每个 event 全量抓取）。
- Replay 抓取落地策略：
  - 对每个选中 event：通过 `ReplayWrapper` set event → 读取 pipeline state → 写入 `PipelineSnapshot`（挂到 canonical `events[*]` 上）。
  - 将 `CallAnalyzer/ResourceTracker` 的分析结果与 `event_id` 串联，让 issue evidence 能引用 snapshot 字段。
- 性能控制：
  - 做 cache（例如 `(event_id + state_fingerprint)`），避免重复读取 state。
  - 先覆盖规则需要的关键字段（shader/RT/DS/viewport/resource bindings…），再逐步加深（不要一口气“全 API 全字段”）。
- 验收口径（Done when）：
  - 同一 capture 多次运行得到一致 snapshot（字段稳定、可复现）。
  - rules/建议能引用真实字段（例如“某 draw 的 RT 格式/尺寸/绑定情况/资源引用”）。

#### P0-3：统一 Issue / Rule / Suggestion 数据结构（单一模型）——WHAT / WHY / HOW

**WHAT（交付物是什么）**
- 定义一个统一的 `Issue`（以及可选 `Suggestion`）数据结构；rules、analyzers、diff/regression 全部输出同样字段。
- exporter/compare 只消费统一模型，不再并存多套 issue 形态。

**WHY（为什么必须做）**
- 目前 issue 形态分裂（rules 输出 vs analysis 模块输出 vs 其他类型），会导致：
  - HTML/JSON exporter 只能做大量特判拼装，维护成本高且极易回归。
  - compare 无法对 issues 做稳定 diff（甚至无法判断“同一个问题”是否同一个）。
- A（规则 + 建议）要求建议能落到“哪里/什么问题/证据是什么”，统一模型是“建议可执行”的前提。

**HOW（怎么做）**
- 建议统一字段（最小集合，先闭环）：
  - `code`（或 `rule_id`）、`severity`、`category`、`title`、`message`
  - `event_id`（可空）、`marker_path`（可空）
  - `resource_ids`（可空）、`evidence`（关键数值/状态字段快照）
  - `suggestion_steps`（可选，多条、可执行）
- 对齐 rules：
  - `RuleRunner` 统一把 rule 输出包装成 `Issue`（rule 只负责判定与证据填充，不负责导出格式）。
- 对齐 compare：
  - 增加 `issue_fingerprint`（例如 `code + marker_path/event_id + resource fingerprint`），用于跨模块/跨 capture 的匹配。
- 验收口径（Done when）：
  - 所有 issues 都能在同一份 JSON/HTML 中以统一格式展示；compare 能输出 issues 的新增/消失/严重度变化，并带证据锚点。

#### P0-4：把 compare 做成一等 CLI（明确数据源）——WHAT / WHY / HOW

**WHAT（交付物是什么）**
- 新增/完善 CLI：`python -m rdc_analyzer compare baseline.rdc target.rdc ...`（带 `--help`、明确输出路径/格式）。
- 输出 `compare.json`（summary、top regressions、diff stats、evidence anchors），可选输出 `compare.html`。

**WHY（为什么必须做）**
- 目标 2（双 RDC 全方位对比 + 结论）需要“稳定入口 + 稳定数据源”，否则会退化为脚本拼装，无法复用，也无法持续扩展。
- 你已有 diff/regression 核心实现（`scripts/rdc_analyzer/diff/diff_engine.py`、`scripts/rdc_analyzer/diff/regression_detector.py`），但缺少“挂到 canonical schema + CLI”的产品化闭环。

**HOW（怎么做）**
- compare 的角色是 orchestrator（编排器），不重复造分析轮子：
  - baseline/target 各跑一次 analyze → 得到两份 canonical `analysis.json`（或直接 load 已有 JSON）。
  - 将两份 JSON 交给 DiffEngine 做结构化 diff（events/resources/issues）。
  - RegressionDetector 输出“结论 + 证据锚点”（marker_path + event_id + 数值变化）。
- 验收口径（Done when）：
  - compare 输出中的每条回归都能追溯到证据字段（不是空泛“变慢了”）。
  - compare 支持“无 RenderDoc 环境”对两份 `analysis.json` 做 diff（便于 CI 与快速验证）。

#### P0-5：修复测试 + 明确 integration 边界——WHAT / WHY / HOW

**WHAT（交付物是什么）**
- `not integration` 测试全绿；明确标记哪些用例需要 RenderDoc runtime/驱动/GPU（integration），并默认跳过。
- 修复当前已知失败点（exporter API 漂移、replay controller fixture 缺失）。

**WHY（为什么必须做）**
- P0-1..P0-4 会涉及字段收敛与编排重构；没有测试兜底，你无法安全迭代，也无法证明“真的更好”。
- 当前测试失败点已经体现出“API/边界漂移”的客观风险：这类风险如果不先治理，后续任何重构都会放大不确定性。

**HOW（怎么做）**
- 定义 integration 判定：
  - 只要 import/use `renderdoc` 或需要 replay controller → `@pytest.mark.integration`
  - 纯逻辑（schema、diff、report 组装、规则判断）→ `not integration`
- 修复两类已知问题：
  - exporter：让模板入口稳定（避免测试硬依赖易漂移的常量名；或补齐并固定常量名）。
  - fixture：提供 fake controller/stub 数据支撑单测；若天然依赖真实 replay，则标 integration。
- 验收口径（Done when）：
  - `py -3 -m pytest -q scripts/rdc_analyzer/tests -m 'not integration'` 0 failed / 0 error。

### P1（增强可信度与建议可执行性）

1) **把阈值体系做成“可配置 + 平台化”**（pc/mobile + 目标 FPS）  
   - 理由：Unity/Unreal/移动端对阈值预期不同；需要在报告里明确“本次判断依据哪个 profile”。  
   - 可参考：Unity 的顶点量级范围、Intel 的帧预算、AGI 的带宽阈值（见第 4 节资料）。

2) **对比侧的“稳定匹配策略”升级**（跨 capture 的资源/事件对齐）  
   - 理由：resourceId / eventId 跨 capture 天生不稳定；要做“全方位对比”必须靠更稳定签名（name/format/dim/hash/shader hash/marker path 等）。

### P2（未来可做：B/C 的前置基础）

1) CPU/GPU 分离（真正的 bottleneck 判断）  
2) UI 回链（点击结论跳转到 RenderDoc 事件/marker）  
3) 自动生成“捕获设置建议”（Unity/Unreal/Android）并做缺数据诊断

---

## 7. 附：本次验证记录（可复查）

本地执行（Windows, Python 3.11）：

- `py -3 -m pytest -q scripts/rdc_analyzer/tests -m 'not integration'`
- 结果摘要：261 items 中 254 passed / 4 failed / 1 error / 2 skipped

失败/错误点：

- HTML_TEMPLATE import 失败（测试与实现不一致）：`scripts/rdc_analyzer/tests/test_shader_extractor.py:243`
- controller fixture 缺失：`scripts/rdc_analyzer/tests/test_resource_inspector.py:99`
