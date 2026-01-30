# RDC Analyzer 规则详解：Draw Call（5 条）

> 范围：`scripts/rdc_analyzer/rules/draw_call.py`  
> 目标：把每条规则写成**可执行的规格说明**（WHAT / WHY / HOW），并明确“对当前项目现状是否真的生效”。  
> 更新时间：2026-01-20

---

## 0) 重要前提：这些 RD_* 规则目前是否会出现在主报告里？

**结论（对当前仓库真实状态）**：默认情况下，`python -m rdc_analyzer analyze ...` 走的是 `scripts/rdc_analyzer/main.py` 的 `AnalysisPipeline`，它当前主要产出的是 `BIND* / PERF*` 类问题，并不会自动运行 `RuleRunner` 执行这批 `RD_*` 规则。  

- WHAT：你现在“规则文档（RULES.md）里写的 36 条规则”，在 CLI 的 `rules --list` 里能看到，但在 `analyze` 的输出里不一定会出现。  
  - 入口证据：`scripts/rdc_analyzer/__main__.py` 的 `cmd_analyze()` 默认使用 `from .main import AnalysisPipeline`。  
- WHY：这会直接伤害“极致/全方位”的可信度——**用户以为规则在跑，实际上可能没跑**。  
- HOW：P0 的方向是“统一事实来源 + 统一规则输出口径 + 把规则跑进主链路”，详见主路线图文档中的 P0-1/P0-3。

本文件仍然有价值：它把 RD_* 规则的**意图与实现细节**写清楚，方便你决定：
1) 继续走 A（规则+建议）路线时，保留并升级这些规则；或  
2) 直接把它们迁移/融合进 `PerformanceAnalyzer/OptimizationAdvisor` 的口径里。

---

## RD_DC_001：Draw Call Count（Draw Call 数量过多）

### WHAT
- 检测“单帧 draw call 总数”是否超过阈值；超过则输出 1 条 Issue（code=`RD_DC_001`）。

### WHY
- Draw call 过多会造成：
  - CPU 侧提交开销（驱动/命令录制/状态切换）飙升；
  - GPU 侧 state 变化与绑定频率上升，间接放大 cache miss / pipeline bubbles；
  - 对 Unity/Unreal/自研引擎都属于最通用的“先看指标”之一。
- 这条规则是目标 1（单帧极致分析）里最基础的“报警器”，也是目标 2（对比）里最常见的“回归结论来源”。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/draw_call.py`（`DrawCallCountRule`）
- 读取数据：`self.context.frame_summary.draw_call_count`
- 阈值读取：`self.get_threshold("draw_call_count", 2000)`
- 触发条件：`draw_count > threshold`
- 输出：
  - `Issue.code = "RD_DC_001"`
  - 默认严重程度：`WARNING`
  - `location_path = "Frame Summary"`

### 与当前项目现状的差距 / 风险点（你现在为什么需要在意）
- **阈值 key 漂移**：规则读取的是 `draw_call_count`，但 `scripts/rdc_analyzer/config/thresholds.py` 里对应的是 `max_draw_calls`（两个 key 不一致）。  
  - 结果：如果 `AnalysisContext.thresholds` 没人为塞入 `draw_call_count`，这里永远用默认值 2000，与你在 `RULES.md` 里宣称的 PC=3000/Mobile=500 不一致。
- **数据来源依赖**：必须保证 `frame_summary.draw_call_count` 在解析阶段正确统计，否则规则“看起来跑了”，但数据是 0 或缺失。

---

## RD_DC_002：Low Poly Draw Call（低多边形 Draw Call，建议合批）

### WHAT
- 统计“顶点数很少”的 draw call 数量，若超过一定数量则输出 1 条 Issue（code=`RD_DC_002`）。

### WHY
- “大量小 draw”通常意味着：
  - 不必要的 draw call 开销（同 RD_DC_001），但更偏向“可合批/可 instancing”的场景；
  - 对 Unity（Static/Dynamic Batching、SRP Batcher、GPU Instancing）、Unreal（Mesh Merge、HISM/ISM、Material merge）都有明确优化路径。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/draw_call.py`（`LowPolyDrawCallRule`）
- 数据来源：遍历 `self.context.parsed.draws`（每项是 dict）
  - `vertex_count = draw.get("vertex_count", 0)`
- 阈值读取：`self.get_threshold("min_vertices_per_draw", 100)`
- 触发条件：
  - 统计 `0 < vertex_count < threshold` 的 draw 数量 `low_poly_count`
  - 若 `low_poly_count > 10` 则触发（注意：这里 “10” 是写死的，不可配置）
- 输出：
  - `Issue.code = "RD_DC_002"`
  - `location_path = "Draw Calls"`

### 与当前项目现状的差距 / 风险点
- **阈值 key 漂移**：读取 `min_vertices_per_draw`，但 `config/thresholds.py` 的对应项更像 `small_draw_vertex_threshold`。  
- **依赖字段存在**：要求 `parsed.draws` 里必须有 `vertex_count`；而你的新管线 `main.py` 的 `draw_calls` 结构使用的是 RenderDoc event 的字段（如 `numIndices/numInstances`），并不等价于这里的 schema。
- **缺“定位能力”**：只输出“数量”，没有输出“哪些 draw（event_id/name/mesh）”，会削弱“极致建议”的可执行性。

---

## RD_DC_003：Non-Instanced Draw（重复绘制建议 Instancing）

### WHAT
- 通过“相同顶点配置的重复出现次数”来猜测“可能可以 instancing”的 draw call 集合。

### WHY
- Instancing 是 Unity/Unreal/自研引擎里最常用的 draw call 降维打击方案之一：  
  - 典型收益：降低 CPU 提交、降低 state/binding 切换，提升批处理效率。
- 对你的 analyzer 来说：这条规则更像“建议触发器”，属于 A（规则+建议）口径的核心之一。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/draw_call.py`（`InstancedDrawRule`）
- 数据来源：遍历 `self.context.parsed.draws`
- “相同配置”的 key：`(vertex_count, index_count)`
- 阈值读取：`self.get_threshold("instancing_threshold", 5)`
- 触发：
  - 若某个 key 的 count >= threshold，则输出 Issue
  - 严重程度动态调整：`count > 10 => WARNING`，否则 `INFO`

### 与当前项目现状的差距 / 风险点
- **判定过于粗糙**：只用 `(vertex_count, index_count)` 作为“同网格”代理，会出现大量误判（不同 mesh 也可能同顶点数）。  
  - 真正想“极致”：需要 mesh id / vertex buffer hash / pipeline signature（这正是你 `CallAnalyzer/PipelineSnapshot` 类模块的价值）。
- **阈值 key 漂移**：读取 `instancing_threshold`，但 `config/thresholds.py` 更像 `instancing_suggestion_threshold`。

---

## RD_DC_004：Empty Draw Call（空 Draw Call / 0 顶点绘制）

### WHAT
- 检测 `vertex_count == 0` 且 `index_count == 0` 的 draw call 数量，只要 >0 就报 Issue。

### WHY
- “空 draw”通常表示：
  - 引擎剔除/裁剪逻辑不一致（提交了无意义 draw）；
  - 渲染队列构建 bug（数据为空仍提交）；
  - 对 CPU/GPU 都是纯浪费，属于“必杀型”优化项（收益明确，风险低）。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/draw_call.py`（`EmptyDrawCallRule`）
- 数据来源：`self.context.parsed.draws`
- 触发条件：存在任何 draw 满足 `(vertex_count == 0 and index_count == 0)`
- 输出：1 条 Issue，message 包含空 draw 的数量

### 与当前项目现状的差距 / 风险点
- **依赖字段存在**：同样依赖 `parsed.draws` 的 schema。新管线的 `draw_calls` 结构未必提供 `vertex_count/index_count` 这套字段名。
- **缺少 event_id 列表**：只报数量，不报具体 event_id，定位成本仍高。

---

## RD_DC_005：High Vertex Count（单次 Draw 顶点数过多）

### WHAT
- 找出 “vertex_count > 阈值” 的 draw call，输出 1 条 Issue（目前只报数量）。

### WHY
- 超高顶点数 draw 可能意味着：
  - LOD 缺失/失效；
  - 网格未拆分导致剔除粗糙；
  - 在移动端尤其危险（顶点变换与带宽压力）。
- 对对比而言：这类问题常作为“内容回归”（模型变复杂）的证据链。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/draw_call.py`（`VertexCountRule`）
- 数据来源：`self.context.parsed.draws`
- 阈值读取：`self.get_threshold("max_vertices_per_draw", 100000)`
- 输出：如果存在超阈 draw，则输出 1 条 Issue（message 只包含数量）

### 与当前项目现状的差距 / 风险点
- **和 RULES.md 有出入**：RULES.md 写的是阈值 “顶点数 > 100,000”，这条一致；但是否真的能读到 `vertex_count` 取决于你的解析口径。  
- **缺少“TopN 列表”**：建议补充输出前 N 个 draw 的 `(event_id, vertex_count, name/pipeline)`，否则“极致建议”不好落地。

---

## 结尾：这 5 条规则对你的两大目标意味着什么？

- 对目标 1（单帧极致分析）：这 5 条是“批次/几何复杂度”的最小闭环，但**要变成极致**必须接入真实的 draw/state/pipeline 身份信息（避免启发式误判）。  
- 对目标 2（双帧全方位对比）：这 5 条里的阈值与输出格式如果不统一，会直接导致 compare 结论不可信（同一条规则在两次 capture 用不同阈值/不同字段）。  
- 对当前项目的 P0：这些规则最缺的不是“更多规则”，而是 **统一 schema + 统一阈值 key + 让规则真的跑在主链路**。

