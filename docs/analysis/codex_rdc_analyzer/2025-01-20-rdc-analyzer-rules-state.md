# RDC Analyzer 规则详解：State（6 条）

> 范围：`scripts/rdc_analyzer/rules/state.py`  
> 更新时间：2025-01-20

---

## 0) State 规则的关键：它们需要“真实的状态历史”

State 类规则理论上是“极致分析”的核心（因为很多性能问题来自状态抖动/绑定冗余/排序问题），但它们对事实数据要求也最高：

- `frame_summary` 里要有 shader/blend/depth/rasterizer 的切换统计；
- `state_history` 里要有每次 draw 的关键状态快照（至少包含 shader 标识）；
- `passes` 里要能判断 UI pass、是否使用 scissor 等；
- `parsed.draws` 里要包含每个 draw 的 state（depth_test/blend 等）。

你当前仓库里最危险的点是：**主导出链路（main.py 的 HTML 导出适配）存在大量占位 state**，会让 State 规则看起来“跑了”，但结论无法可信。

---

## RD_STATE_001：Excessive State Changes（状态切换过多）

### WHAT
- 检测多个状态切换计数（shader/blend/depth/rasterizer）是否超过各自阈值。

### WHY
- 频繁状态切换会导致：
  - CPU 端设置状态/绑定的开销增加；
  - GPU pipeline 的 cache/PSO 复用下降；
  - 在 D3D12/Vulkan 这类 API 下，PSO 颗粒度变小会显著增大管理成本。
- 对目标 2（对比）而言：它非常适合作为“回归证据”（例如 shader_changes 从 200 -> 800）。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/state.py`（`StateChangeRule`）
- 阈值 key：
  - `max_shader_changes`（默认 500）
  - `max_blend_changes`（默认 200）
  - `max_depth_changes`（默认 200）
  - `max_rasterizer_changes`（默认 200）
- 数据来源：`stats = self.context.frame_summary`，读取属性：
  - `shader_changes/blend_state_changes/depth_state_changes/rasterizer_changes`
- 输出：每个超过阈值的项输出 1 条 Issue

### 与当前项目现状的差距 / 风险点
- **阈值 key 漂移**：`config/thresholds.py` 里有 `max_shader_changes`，但 blend 的 key 写的是 `max_blend_state_changes`（不是 `max_blend_changes`）。  
- **字段名不一致风险**：规则读取的是 `blend_state_changes` 等属性；但 `FrameSummary` 是否定义/是否填充这些字段需要核对，否则会默认 0。

---

## RD_STATE_002：Shader Thrashing（Shader 切换抖动）

### WHAT
- 检测 A->B->A 这种“来回切换”的模式次数（thrash_count），过多则报 Issue。

### WHY
- Shader thrashing 往往意味着：
  - draw 排序不合理（按材质/PSO 分组不足）；
  - 渲染队列混乱（UI/透明/特效穿插）；
  - 对 CPU（绑定频率）与 GPU（pipeline cache）都有坏处。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/state.py`（`ShaderSwitchRule`）
- 数据来源：`state_history = self.context.state_history`（list[dict]）
- 检测模式：`state_history[i]['shader'] == state_history[i-2]['shader'] != state_history[i-1]['shader']`
- 触发：`thrash_count > 50`（写死）
- 输出：1 条 Issue

### 与当前项目现状的差距 / 风险点
- **state_history 的 schema 未定义为 SSOT**：必须统一“shader 的标识是什么”（shader id? pipeline id? vs/ps hash?）。否则 A/B/A 判断没有意义。  
- 如果主链路不采集 state_history，这条规则永远空结果。

---

## RD_STATE_003：Redundant State（冗余状态设置）

### WHAT
- 检测 `frame_summary.redundant_state_sets` 是否过多（>100）。

### WHY
- 冗余状态设置说明：
  - 引擎缺少状态缓存（重复 set 相同值）；
  - state setting 与 draw 组织脱节；
  - CPU 提交有可回收空间。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/state.py`（`RedundantStateRule`）
- 数据来源：`self.context.frame_summary.redundant_state_sets`
- 触发：`redundant > 100`（写死）
- 输出：1 条 Issue

### 与当前项目现状的差距 / 风险点
- 是否能统计 redundant_state_sets，取决于你是否在解析/回放阶段做了“状态去重计数”。目前主链路并未明确这一点。

---

## RD_STATE_004：Scissor Test Usage（UI 未启用裁剪）

### WHAT
- 在 UI/GPU pass 中，如果未启用 scissor，则报 Issue（逐 pass）。

### WHY
- UI 往往有大量小矩形与透明叠加；没有 scissor 会造成：
  - UI overdraw；
  - 片段着色器浪费；
  - 移动端更明显。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/state.py`（`ScissorTestRule`）
- 数据来源：遍历 `self.context.passes`
  - UI pass 判定：pass 名包含 `ui/gui`
  - 若 `not pass_info.uses_scissor` 则报 Issue

### 与当前项目现状的差距 / 风险点
- 依赖 pass 的 `uses_scissor` 字段被正确填充；否则会大量误报。
- UI 识别只靠名字（ui/gui）可能漏检，需要 marker 或 renderpass tag。

---

## RD_STATE_005：Depth Test Issues（深度测试配置异常）

### WHAT
- 如果“非 UI/非后处理” draw 中，有过高比例禁用了 depth test，则报 Issue。

### WHY
- 大量禁用 depth test 可能意味着：
  - early-z 失效导致 overdraw；
  - 排序问题导致更多片段执行；
  - 或者错误把不透明物体走了透明管线。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/state.py`（`DepthTestRule`）
- 数据来源：遍历 `self.context.parsed.draws`
  - `state = draw.get("state", {})`
  - `if not state.get("depth_test_enabled", True): ...`
  - 排除：`draw.get("is_ui")`、`draw.get("is_postprocess")`
- 触发：禁用深度的比例 `ratio > 0.3`
- 输出：1 条 Issue

### 与当前项目现状的差距 / 风险点
- 依赖 draw 的 `state.depth_test_enabled` 与 `is_ui/is_postprocess` 字段存在且可信；这是“事实来源”的一部分。

---

## RD_STATE_006：Alpha Blend Overdraw（透明混合过多）

### WHAT
- 统计 `blend_enabled == True` 的 draw 数量，超过阈值则报 Issue。

### WHY
- 透明混合 draw 往往带来：
  - overdraw（尤其粒子/UI/半透明特效）；
  - bandwidth 压力；
  - 移动端（TBDR）更糟。
- 这条规则如果能结合“覆盖率/深度复杂度”会非常强，但当前实现是“数量级提示”。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/state.py`（`AlphaBlendRule`）
- 数据来源：`self.context.parsed.draws` 中 `draw['state']['blend_enabled']`
- 阈值读取：`self.get_threshold("max_blend_draws", 200)`
- 输出：1 条 Issue

### 与当前项目现状的差距 / 风险点
- 阈值 key 漂移：`max_blend_draws` 在 `config/thresholds.py` 中没有同名项。  
- 只靠数量不足以判断严重程度：需要像素覆盖率/overdraw（这与你的 Mobile Overdraw 方向有关，但当前也是启发式）。

---

## 结尾：State 规则为什么是“护城河”，但也最容易误伤？

- 它们是极致分析的“灵魂”（真正能指导你怎么排序/合批/减少状态抖动）。  
- 但如果 state 数据是占位/启发式，输出会非常不可信，反而会让用户对工具失去信任。  
- 所以对当前项目来说：State 规则的优先级不是“加更多”，而是“让主链路产出真实 state（P0-2）+ 统一 schema（P0-1）”。

