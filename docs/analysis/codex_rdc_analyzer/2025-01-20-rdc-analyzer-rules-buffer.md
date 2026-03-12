# RDC Analyzer 规则详解：Buffer（6 条）

> 范围：`scripts/rdc_analyzer/rules/buffer.py`  
> 更新时间：2025-01-20

---

## 0) 规则依赖的数据面：Buffers + Draws + Buffer Updates

Buffer 类规则依赖三类数据：
- `AnalysisContext.buffers`（结构化 `BufferInfo` 列表）
- `AnalysisContext.parsed.draws`（draw 里的 bound buffer/vertex stride/index format 等字段）
- `AnalysisContext.parsed.buffer_updates`（动态更新记录）

这三者在“新端到端管线（main.py）”里并不是同一套 schema，这也是你当前需要做 P0-1（canonical schema）的原因之一。

---

## RD_BUF_001：Large Buffer（单 Buffer 过大）

### WHAT
- 逐个检查 buffer 的字节大小，超过阈值则报 Issue。

### WHY
- 超大 buffer 往往意味着：
  - 资源打包/分块策略不合理（一次性上传/常驻了过大的数据）；
  - streaming/分段加载不足；
  - 在显存压力下会导致抖动或 OOM（尤其在移动/低端）。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/buffer.py`（`BufferSizeRule`）
- 阈值读取：`self.get_threshold("max_buffer_size_mb", 64) * 1024 * 1024`
- 数据来源：`self.context.buffers` 的 `buf.size`
- 输出：每个超阈 buffer 1 条 Issue

### 与当前项目现状的差距 / 风险点
- **阈值 key 漂移**：规则读 `max_buffer_size_mb`，而 `config/thresholds.py` 中存在的是 `large_buffer_threshold_mb`。  
- 依赖 `BufferInfo.size` 的准确性（不同 API 的对齐/压缩/视图可能导致“看起来大小不合理”）。

---

## RD_BUF_002：Dynamic Buffer Update（动态 Buffer 更新过频）

### WHAT
- 统计 `parsed.buffer_updates` 里每个 buffer 的更新次数，超过阈值则报 Issue（聚合）。

### WHY
- 高频更新通常意味着：
  - 每帧大量 Map/Unmap 或 UpdateSubresource；
  - 资源管理策略未采用 ring buffer / persistent mapping；
  - CPU 开销显著，且容易触发同步/阻塞。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/buffer.py`（`DynamicBufferRule`）
- 数据来源：`self.context.parsed.buffer_updates`（每项 dict，含 `buffer_id`）
- 阈值读取：`self.get_threshold("max_buffer_updates", 10)`
- 输出：1 条聚合 Issue（只报“有多少个 buffer 更新频繁”）

### 与当前项目现状的差距 / 风险点
- 你必须在解析阶段真实填充 `parsed.buffer_updates`；否则这条规则永远空结果。  
- 阈值 key 漂移：`max_buffer_updates` 在 `config/thresholds.py` 里没有同名项。

---

## RD_BUF_003：Constant Buffer Packing（常量缓冲过碎）

### WHAT
- 检测 `is_constant_buffer=True` 且 size < 64B 的 buffer 数量；过多则提示合并。

### WHY
- 过碎的常量缓冲意味着：
  - 绑定频繁（尤其 D3D11/D3D12 descriptor 管理场景）；
  - 对驱动/命令录制造成额外开销；
  - 对 shader 侧也可能导致 layout 不稳定。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/buffer.py`（`ConstantBufferRule`）
- 数据来源：`self.context.buffers`
  - 统计 `buf.is_constant_buffer` 且 `buf.size < 64`
- 触发条件：`small_cb_count > 20`（写死，不可配置）
- 输出：1 条聚合 Issue

### 与当前项目现状的差距 / 风险点
- 依赖 `BufferInfo.is_constant_buffer` 的准确分类；如果解析阶段没有区分 CB/VB/IB，这条规则会失效或误判。

---

## RD_BUF_004：Index Buffer Format（索引格式浪费）

### WHAT
- 检测 draw 使用 32-bit index（`R32_UINT`），但 vertex_count < 65535 的情况；若出现很多次则提示用 16-bit。

### WHY
- 32-bit index 的成本：
  - index buffer 占用翻倍（相对 16-bit）；
  - 带宽/缓存压力上升；
  - 移动端更敏感。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/buffer.py`（`IndexBufferFormatRule`）
- 数据来源：`self.context.parsed.draws`
  - `draw.get("index_format") == "R32_UINT"`
  - `vertex_count = draw.get("vertex_count", 0)`
- 触发：`wasteful_count > 10`（写死）
- 输出：1 条聚合 Issue

### 与当前项目现状的差距 / 风险点
- 依赖 `parsed.draws` 中存在 `index_format` 与 `vertex_count` 字段；新管线的 `draw_calls` schema 未必一致。

---

## RD_BUF_005：Vertex Buffer Layout（顶点 stride 过大）

### WHAT
- 检测 draw 的 `vertex_stride` 是否超过阈值；超过则报 Issue（聚合）。

### WHY
- 顶点 stride 过大通常意味着：
  - 顶点属性过度（太多 UV/颜色/骨骼权重，或精度不合理）；
  - vertex fetch 带宽压力上升；
  - 缓存命中率下降。
- 对“极致分析”来说，这是能直接转化成“资产/布局建议”的典型规则。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/buffer.py`（`VertexBufferLayoutRule`）
- 阈值读取：`self.get_threshold("max_vertex_stride", 64)`
- 数据来源：`self.context.parsed.draws` 的 `vertex_stride`
- 输出：1 条聚合 Issue（只报数量）

### 与当前项目现状的差距 / 风险点
- 依赖解析阶段提供 `vertex_stride`；否则永远是 0。  
- 阈值 key 漂移：`max_vertex_stride` 在 `config/thresholds.py` 里没有同名项。

---

## RD_BUF_006：Unused Buffer（创建但未使用）

### WHAT
- 找出“存在于 buffers 列表，但从未出现在任何 draw 的 bound_buffers 里”的 buffer；数量/总大小过大则报 Issue。

### WHY
- 未使用资源意味着：
  - 资产冗余、初始化浪费；
  - 内存常驻但无收益；
  - 对移动端/低端属于“直接可回收的预算”。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/buffer.py`（`UnusedBufferRule`）
- used_buffers：遍历 `parsed.draws` 的 `bound_buffers` 收集
- unused：遍历 `context.buffers`，resource_id 不在 used_buffers
- 触发：`len(unused) > 10`（写死）
- 输出：1 条聚合 Issue（包含数量与总 MB）

### 与当前项目现状的差距 / 风险点
- 依赖 draw 的 `bound_buffers` 列表；而你的新管线目前更多是“事件级信息 + 简化 draw_calls”，绑定级信息在 HTML 导出时甚至是占位。

---

## 结尾：Buffer 规则与 P0 的关系

Buffer 规则的“可信度”高度依赖事实数据：
- 必须能从 capture 中拿到：buffer 类型、大小、更新次数、绑定情况、vertex stride/index format。  
- 当前仓库里最强的数据来源其实是 `ReplayWrapper/ResourceInspector` 路线，但它还没有被统一喂给主报告。  

所以对你而言：**继续加规则不是优先项**；先把 schema/事实来源打通，规则自然就会更准、更“极致”、更适合做对比结论。

