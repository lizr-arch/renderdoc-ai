# RDC Analyzer 规则详解：Mobile（6 条）

> 范围：`scripts/rdc_analyzer/rules/mobile.py`  
> 适用：`platform=mobile`（这些规则都声明了 `platforms=["mobile"]`）  
> 更新时间：2026-01-20

---

## 0) 先说清楚：移动端规则的“上限”取决于你是否真的理解 TBDR

移动端（尤其 Arm Mali / Qualcomm Adreno / Apple GPU）很多是 TBDR（Tile-Based Deferred Rendering）或类似架构。  

- WHAT：移动端的关键不是“draw call 多一点”，而是**tile flush / 带宽 / overdraw / load-store 行为**。  
- WHY：你要做“极致分析 + 建议”，移动端如果只用 PC 的规则，会给出大量误导建议。  
- HOW：这 6 条规则是一个起点，但当前实现多数是启发式估算；要把它们做成“可信标准”，需要接入更真实的数据源（AGI/Perfetto/Mali counters，或 RenderDoc 更细粒度状态与资源读写）。

---

## RD_MOBILE_001：TBDR Flush（中途读取 RT 导致 tile flush）

### WHAT
- 检测 draw 中是否“读取当前 render target”（RT read-after-write），这种模式在 TBDR 下很容易触发 tile flush。

### WHY
- TBDR 的核心优势是“tile 内缓存 + 延迟写回”。  
  一旦你在同一 pass 中读取当前 RT，就可能迫使 GPU 提前写回（flush）并重新加载，带宽/功耗暴涨。
- 这条规则属于移动端“高价值/高收益”的结构性报警器。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/mobile.py`（`TBDRFlushRule`）
- 数据来源：遍历 `self.context.parsed.draws`
  - `current_rts`：从 `draw['render_targets']` 收集
  - 检测：`draw['bound_textures']` 是否包含 `current_rts` 中的纹理 id
- 输出：1 条聚合 Issue（只报次数）

### 与当前项目现状的差距 / 风险点
- 依赖字段存在：`render_targets`/`bound_textures` 必须在 draw schema 里有且可信。  
- 真正的 RT read 行为还需要考虑：subresource、read-only depth、input attachment 等；当前实现是简化版。

---

## RD_MOBILE_002：Mobile Overdraw（移动端过度绘制）

### WHAT
- 估算 overdraw 倍数（启发式），超过阈值则报 Issue。

### WHY
- overdraw 是移动端最常见的 GPU 瓶颈之一（带宽 + fragment 执行浪费）。  
- 透明/粒子/UI 堆叠会使 overdraw 成倍增加。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/mobile.py`（`MobileOverdrawRule`）
- screen_pixels：`viewport_width * viewport_height`
- 估算逻辑（非常简化）：
  - blend draw：假设覆盖全屏（+1x）
  - opaque draw：假设覆盖 0.3 屏幕
- 阈值读取：`self.get_threshold("mobile_max_overdraw", 3.0)`
- 输出：1 条 Issue（包含估算 overdraw 倍数）

### 与当前项目现状的差距 / 风险点
- **这是启发式，不是“真实 overdraw”**：没有深度复杂度/coverage 信息时，结论只能作为“风险提示”。  
- 阈值 key 漂移：`mobile_max_overdraw` 在 `config/thresholds.py` 中不存在同名项。

---

## RD_MOBILE_003：Mobile Precision（移动端精度/RT 格式）

### WHAT
- 检测是否存在过多 float32 的 render target（RT），并建议改用 float16。

### WHY
- float32 RT 会显著增加：
  - 带宽；
  - tile memory 压力；
  - 以及功耗。
- 在移动端，大多数后处理/中间 RT 用 float16 足够。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/mobile.py`（`MobilePrecisionRule`）
- 数据来源：`self.context.textures`，筛选 `tex.is_render_target`
- float32 判定：`tex.format.upper()` 在 `FLOAT32_FORMATS` 集合中
- 触发：`len(float32_rts) > 3`（写死）
- 输出：1 条 Issue

### 与当前项目现状的差距 / 风险点
- 依赖 `TextureInfo.is_render_target` 与 format 口径一致。  
- 更“极致”的版本应该区分：HDR 必要性、写入频率、分辨率、是否可降采样等。

---

## RD_MOBILE_004：Mobile Bandwidth（大纹理过多导致带宽压力）

### WHAT
- 统计“超过阈值尺寸的大纹理”数量，过多则报 Issue。

### WHY
- 移动端带宽通常是第一约束；大量大纹理会导致：
  - cache miss 上升；
  - 带宽占用上升；
  - 进而掉帧/发热。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/mobile.py`（`MobileBandwidthRule`）
- 阈值读取：`self.get_threshold("mobile_texture_size", 1024)`
- 数据来源：遍历 `self.context.textures`，排除 RT
- 触发：`large_texture_samples > 20`（写死）
- 输出：1 条 Issue

### 与当前项目现状的差距 / 风险点
- 这条规则目前只看“数量”，没有结合：mipmap、压缩格式、采样次数、屏幕覆盖度。  
- 阈值 key 漂移：`mobile_texture_size` 在 `config/thresholds.py` 中不存在同名项。

---

## RD_MOBILE_005：Alpha Test Usage（alpha test/discard 影响 early-z）

### WHAT
- 统计 draw 中使用 discard/alpha test 的次数，超过阈值则提示风险。

### WHY
- Alpha test（discard/clip）常常破坏 early-z / TBDR 优化，导致：
  - fragment 执行浪费；
  - tile 内合并/压缩效果变差；
  - 粒子/植被等场景尤其明显。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/mobile.py`（`MobileAlphaTestRule`）
- 数据来源：遍历 `self.context.parsed.draws`
  - `draw.get("uses_discard") or draw.get("uses_alpha_test")`
- 阈值读取：`self.get_threshold("mobile_max_alpha_test", 50)`
- 输出：1 条 Issue

### 与当前项目现状的差距 / 风险点
- 依赖解析阶段能判断 shader 是否使用 discard（需要 shader reflection / DXIL/SPIR-V 分析）。  
- 阈值 key 漂移：`mobile_max_alpha_test` 在 `config/thresholds.py` 中不存在同名项。

---

## RD_MOBILE_006：Load Store Action（Load/Store 行为风险）

### WHAT
- 找出“未 clear 直接绘制”的 pass，提示确认 LoadAction/StoreAction 是否正确。

### WHY
- 在移动 TBDR 上，错误的 load/store 会造成：
  - 不必要的 tile load/store（带宽暴涨）；
  - 帧内中间 RT 成本被放大；
  - 有时甚至造成 tile flush。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/mobile.py`（`MobileLoadStoreRule`）
- 数据来源：遍历 `self.context.passes`
  - 触发条件：`pass_info.draw_count > 0 and not pass_info.has_clear`
- 输出：1 条聚合 Issue（只报 pass 数量）

### 与当前项目现状的差距 / 风险点
- “未 clear”并不一定等价于“load/store 错误”；更严谨需要知道 RT 的首次使用、前一帧内容是否需要保留、load/store action 真实值。  
- 要把这条做成“极致建议”，需要接入更真实的 renderpass/load-store 语义。

---

## 结尾：移动端规则的路线图建议（和你当前项目最相关的 WHY）

- 你已经有 `mali_analyzer.py` / Mali 报告的雏形，说明你在往“移动端更真实指标”走。  
- 这 6 条规则建议作为“可解释的入口”，但不要把它们当成最终标准：  
  - 先把 canonical schema + compare pipeline 做稳（P0），  
  - 然后再把移动端的“带宽/flush/overdraw”从启发式升级成证据链（P1/P2）。

