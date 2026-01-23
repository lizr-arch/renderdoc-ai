# RDC Analyzer 规则详解：Pass（7 条）

> 范围：`scripts/rdc_analyzer/rules/render_pass.py`  
> 更新时间：2026-01-20

---

## 0) Pass 规则为什么对“极致/全方位”都关键？

Pass 层面的结构（RT 切换、clear、fullscreen、shadow、prepass 等）是：
- 目标 1（单帧极致分析）里“**带宽与结构性开销**”的主要来源；
- 目标 2（双帧对比）里“**渲染路径回归**”（新增后处理、阴影策略改变、RT 分辨率变化）的最直接证据链。

但 Pass 规则能否可信，取决于你是否能构建 `AnalysisContext.passes` + 正确的 `frame_summary.rt_switches` 等统计。

---

## RD_PASS_001：Pass Count（Pass 数量过多）

### WHAT
- 检测 `context.passes` 的数量是否超过阈值。

### WHY
- Pass 过多通常意味着：
  - 过多的 RT/FB 切换（额外带宽/同步）；
  - 重复后处理/重复渲染路径；
  - CPU/GPU 都可能被拖慢。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/render_pass.py`（`PassCountRule`）
- 阈值读取：`self.get_threshold("max_pass_count", 20)`
- 数据来源：`len(self.context.passes)`
- 输出：1 条 Issue（code=`RD_PASS_001`）

### 与当前项目现状的差距 / 风险点
- `config/thresholds.py` 里也有 `max_pass_count`，但值/平台差异与你 RULES.md 宣称的阈值可能不同（需要统一阈值来源）。

---

## RD_PASS_002：RT Switch（Render Target 切换过多）

### WHAT
- 检测 `frame_summary.rt_switches` 是否超过阈值。

### WHY
- RT 切换通常带来：
  - 带宽压力（store/load）；
  - pipeline flush/同步风险；
  - 在移动 TBDR 上会导致 tile flush（更糟）。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/render_pass.py`（`RTSwitchRule`）
- 阈值读取：`self.get_threshold("max_rt_switches", 30)`
- 数据来源：`self.context.frame_summary.rt_switches`
- 输出：1 条 Issue（code=`RD_PASS_002`）

### 与当前项目现状的差距 / 风险点
- `config/thresholds.py` 的类似项是 `max_rt_changes`（key 不一致）。  
- 新管线 `main.py` 是否会统计 rt_switches 取决于你的解析逻辑；如果没有，结果会恒为 0。

---

## RD_PASS_003：Empty Pass（空 Pass）

### WHAT
- 找出 `pass_info.draw_count == 0` 的 pass；存在则报 Issue（聚合）。

### WHY
- 空 pass 往往是：
  - 条件分支残留（某些 feature toggle 关闭后 pass 还在）；
  - render graph 编排 bug；
  - “带宽/切换纯浪费”的低风险优化点。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/render_pass.py`（`EmptyPassRule`）
- 数据来源：遍历 `self.context.passes`
- 输出：1 条聚合 Issue（message 包含前 3 个 pass 名）

### 与当前项目现状的差距 / 风险点
- 依赖 pass 构建的准确性（如何分 pass？marker？RT 切换？renderpass begin/end？）  
  - 这也是为什么你的“事实来源（ReplayWrapper + markers）”很重要。

---

## RD_PASS_004：Fullscreen Pass（全屏 Pass 过多）

### WHAT
- 统计 `pass_info.is_fullscreen == True` 的 pass 数量，超过阈值则报 Issue。

### WHY
- 全屏 pass 是典型的带宽杀手：
  - 每个 pass 都要读写大量像素；
  - 后处理堆叠很容易成为帧瓶颈；
  - 对移动端尤甚。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/render_pass.py`（`FullscreenPassRule`）
- 阈值读取：`self.get_threshold("max_fullscreen_passes", 10)`
- 数据来源：遍历 `self.context.passes`，筛选 `is_fullscreen`
- 输出：1 条 Issue

### 与当前项目现状的差距 / 风险点
- 如何判断 fullscreen？依赖 pass 构建逻辑。如果只是“heuristic”，容易误判 UI pass 或某些 fullscreen resolve。

---

## RD_PASS_005：Clear Optimization（Clear 冗余）

### WHAT
- 检测对同一 target 的“连续 clear”次数，超过 5 则报 Issue。

### WHY
- Clear 冗余代表：
  - 带宽浪费（尤其大 RT）；
  - render graph 编排不合理；
  - 或“clear + full overwrite”的可移除优化点（低风险高收益）。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/render_pass.py`（`ClearOptimizationRule`）
- 数据来源：`self.context.parsed.clears`（list[dict]，含 `target`）
- 逻辑：连续相同 target 则 `consecutive_clears += 1`
- 触发：`consecutive_clears > 5`（写死）
- 输出：1 条聚合 Issue

### 与当前项目现状的差距 / 风险点
- 依赖 `parsed.clears` 的真实填充；如果解析没有抽取 clear 操作，这条规则永远没结果。  
- 连续 clear 的定义很粗；更“极致”的版本应该关联到 pass、RT、load/store 行为。

---

## RD_PASS_006：Depth PrePass（复杂场景未用 Depth PrePass）

### WHAT
- 当 draw call 数量超过阈值（默认 500）且未检测到“深度预通道”，则输出建议。

### WHY
- Depth prepass 的意义：
  - 降低 overdraw（尤其复杂几何与大量透明/alpha-test 的场景）；
  - 提升 early-z 命中；
  - 但也有成本（多一次绘制）——需要结合场景判断。
- 因此这条规则很适合做成“建议 + 前提条件 + 解释”的形式，而不是硬性 warning。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/render_pass.py`（`DepthPrepassRule`）
- depth prepass 检测（启发式）：
  - `pass_info.is_depth_only` 或 name 包含 `prepass/depth`
- 阈值读取：`self.get_threshold("depth_prepass_threshold", 500)`
- 触发：`draw_count > threshold and not has_depth_prepass`
- 输出：1 条 Issue（INFO）

### 与当前项目现状的差距 / 风险点
- `depth_prepass_threshold` 在 `config/thresholds.py` 中不存在同名项。  
- “是否有 prepass”的判断是启发式：在自研引擎/Unreal/Unity SRP 下可能误判，需要用 markers 或实际 pipeline state 进一步增强。

---

## RD_PASS_007：Shadow Map（阴影图尺寸风险）

### WHAT
- 扫描名称包含 `shadow` 的 pass，检查其中 RT 尺寸是否超过阈值（默认 4096）。

### WHY
- 阴影图尺寸/更新频率是典型的大开销来源：
  - 阴影 pass 往往 draw call 很高；
  - 阴影贴图越大，写入带宽越大；
  - 多次更新会把成本直接拉满。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/render_pass.py`（`ShadowMapRule`）
- 数据来源：`self.context.passes`，筛选 name 包含 `shadow`
- 阈值读取：`self.get_threshold("max_shadowmap_size", 4096)`
- 输出：每个超阈 shadow RT 1 条 Issue

### 与当前项目现状的差距 / 风险点
- `max_shadowmap_size` 在 `config/thresholds.py` 中不存在同名项。  
- 只看 pass 名称会漏检（例如引擎用 “CSM” “SunDepth” “DirLight” 命名）；更稳的做法是结合资源用途/marker。

---

## 结尾：Pass 规则的“极致化”方向

Pass 规则的上限很高，但需要更强事实输入：
- 真实的 load/store/clear/resolve 行为（而不是只靠 `parsed.clears`）；  
- RT 生命周期与读写关系（这与你 `ResourceTracker` 目标一致）；  
- marker 分组（把 draw/calls 正确归到 pass）。

因此对路线图而言：P0 仍然是“统一事实来源 + schema + compare”，Pass 规则作为其自然增益项。

