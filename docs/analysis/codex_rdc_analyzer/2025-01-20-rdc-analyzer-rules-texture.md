# RDC Analyzer 规则详解：Texture（6 条）

> 范围：`scripts/rdc_analyzer/rules/texture.py`  
> 更新时间：2025-01-20

---

## 0) 先说清楚：这些规则依赖什么“事实数据”？

这些规则主要依赖 `AnalysisContext.textures`（类型 `TextureInfo` 列表）。  

- WHAT：规则并不是直接扫 `main.py` 的 `resources['textures']` 字典，而是扫 `context.textures` 这种“结构化对象”。  
- WHY：这意味着如果你的主分析链路没有构建/填充 `context.textures`，这些规则要么跑不起来，要么跑出来全是空结果。  
- HOW：未来最稳的做法是：把 `ReplayWrapper/ResourceInspector` 的结果统一写入 canonical schema（P0-1），再由“规则执行层”从 canonical schema 反序列化出 `AnalysisContext`。

---

## RD_TEX_001：Large Texture（超大纹理）

### WHAT
- 找出 width/height 任一维度超过阈值的纹理，最多报告前 5 个。

### WHY
- 大纹理的核心代价通常不是“内存占用”本身，而是：
  - 采样带宽与 cache miss；
  - mipmap 缺失时的严重带宽浪费与闪烁；
  - 移动端（TBDR）尤其敏感。
- 这是“资产层面”的最通用优化点之一，且建议动作明确（降分辨率、拆分、流式、压缩）。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/texture.py`（`TextureSizeRule`）
- 阈值读取：`self.get_threshold("max_texture_size", 2048)`
- 数据来源：遍历 `self.context.textures`，判断 `tex.width/tex.height`
- 输出：对每个大纹理输出 1 条 Issue（最多 5 条）

### 与当前项目现状的差距 / 风险点
- **阈值 key 漂移**：规则读 `max_texture_size`，但 `config/thresholds.py` 里并没有同名 key（存在 `mipmap_required_min_size/large_texture_threshold_mb` 等）。  
  - 结果：除非你在构建 `AnalysisContext.thresholds` 时人为塞 `max_texture_size`，否则会用默认 2048。

---

## RD_TEX_002：Texture Memory（单纹理内存过大）

### WHAT
- 检测 `tex.memory_size`（字节）是否超过阈值（默认 16MB）。

### WHY
- 单纹理“过大”通常意味着：
  - 压缩格式未用（BC/ASTC/ETC2 等）；
  - 资源复用不足（同内容多份）；
  - 对移动端/低端设备直接触发 OOM 或频繁换页。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/texture.py`（`TextureMemoryRule`）
- 阈值读取：`self.get_threshold("max_texture_memory_mb", 16) * 1024 * 1024`
- 数据来源：`self.context.textures` 的 `tex.memory_size`
- 输出：每个超阈纹理 1 条 Issue

### 与当前项目现状的差距 / 风险点
- **字段依赖**：`TextureInfo.memory_size` 必须被正确估算/填充（不同 API 对 row pitch / mip chain 的计算要谨慎）。  
- **阈值 key 漂移**：`max_texture_memory_mb` 在 `config/thresholds.py` 中也没有同名 key。

---

## RD_TEX_003：Missing Mipmap（大纹理缺 mipmap）

### WHAT
- 找出尺寸 >= 阈值（默认 256）且 `mip_levels <= 1` 的纹理（排除 RT/Depth）。

### WHY
- mipmap 缺失会带来：
  - 远处采样严重闪烁/锯齿；
  - GPU 带宽浪费（采样更高分辨率的 texel）；
  - 移动端带宽/功耗显著上升。
- 这是“可操作性极强”的建议：基本属于“改资源导入设置”即可。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/texture.py`（`MipmapMissingRule`）
- 阈值读取：`self.get_threshold("mipmap_required_size", 256)`
- 触发条件：
  - `(tex.width >= size_threshold or tex.height >= size_threshold)`
  - `tex.mip_levels <= 1`
  - `not tex.is_render_target and not tex.is_depth_stencil`
- 输出：1 条聚合 Issue（只报数量）

### 与当前项目现状的差距 / 风险点
- `RULES.md` 里写的是“256+ 尺寸缺 mipmap”，和默认值一致，但是否能正确判断依赖 `mip_levels` 与 `is_render_target/is_depth_stencil` 的填充质量。

---

## RD_TEX_004：Uncompressed Texture（大纹理未压缩）

### WHAT
- 找出尺寸 >= 阈值（默认 512）且纹理格式不在压缩格式白名单的纹理（排除 RT）。

### WHY
- 未压缩大纹理通常是“内存 + 带宽双杀”：
  - 内存占用更高，cache 命中更差；
  - 带宽压力上升，尤其在移动端是致命项；
  - 资产层面改动成本低（改格式/重新导入）。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/texture.py`（`TextureFormatRule`）
- 阈值读取：`self.get_threshold("compression_required_size", 512)`
- 判定逻辑：`tex.format.upper()` 是否包含 `BC* / DXT* / ASTC / ETC2 / PVRTC`
- 输出：1 条聚合 Issue（只报数量）

### 与当前项目现状的差距 / 风险点
- **格式字符串匹配的鲁棒性**：不同 API/驱动可能输出不同 format string（例如 DXGI_FORMAT_*），需要确保 `tex.format` 的口径一致。  
- **阈值 key 漂移**：`compression_required_size` 在 `config/thresholds.py` 中不存在同名项。

---

## RD_TEX_005：NPOT Texture（非 2 次幂纹理，移动端）

### WHAT
- 仅在 `platforms=["mobile"]` 下启用：检测非 2 次幂纹理（排除 RT）。

### WHY
- 现代移动 GPU 对 NPOT 纹理支持通常没问题，但仍可能出现：
  - 某些压缩格式/采样模式限制；
  - cache 行为/对齐不佳；
  - 以及“资产不规范”的信号（NPOT 经常与 UI/atlas 管理问题相关）。
- 这条更偏“资产规范/风险提示”，不一定总是要改。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/texture.py`（`NPOT_TextureRule`）
- POT 判断：`n > 0 and (n & (n - 1)) == 0`
- 输出：1 条聚合 Issue（只报数量）

### 与当前项目现状的差距 / 风险点
- 这条规则依赖 `AnalysisContext.platform` 的正确设置；但目前阈值体系/平台选择在多个管线间存在口径漂移。

---

## RD_TEX_006：Texture Array Candidate（建议使用 Texture2DArray）

### WHAT
- 按 `(width, height, format)` 分组统计纹理（排除 RT/Depth），若某组数量 >= 阈值则输出建议。

### WHY
- 纹理数组能带来：
  - 绑定切换减少（尤其在需要频繁切换贴图的材质集合里）；
  - shader 分支更稳定；
  - 对“同规格多贴图（例如角色换装/地表 splat）”场景效果显著。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/rules/texture.py`（`TextureArrayRule`）
- 阈值读取：`self.get_threshold("texture_array_threshold", 8)`
- 输出：每个超阈分组输出 1 条 Issue

### 与当前项目现状的差距 / 风险点
- **只看规格，不看使用方式**：同规格纹理未必在同一 draw/pipeline 使用；要“极致”需要结合绑定分析（这属于 `CallAnalyzer` 的强项）。  
- **阈值 key 漂移**：`texture_array_threshold` 在 `config/thresholds.py` 中不存在同名项。

---

## 结尾：Texture 规则对你的路线图意味着什么？

- Texture 规则的“建议动作”天然可执行（压缩、mipmap、尺寸、流式），非常适合 A（规则+建议）路线。  
- 但要把建议做“可信”和“能对比”，你需要：
  - 统一 schema（texture 的 width/height/format/mips/flags 的口径）；
  - 统一阈值 key（不然默认值会悄悄生效，导致你以为用了 pc/mobile 差异阈值，实际上没有）。

