# 2025-01-31 数据丰富度基线（对标 RenderDoc 源码）

## 0) 文档目的（WHAT / WHY / HOW）
- WHAT：建立 RenderDoc 官方可读数据面的“字段基线”，并与 A+C 当前输出做对齐与缺口标注。
- WHY：明确“缺失=功能缺口”与“缺失=必须 replay 才能拿到”的边界，避免误判。
- HOW：以 RenderDoc 源码结构体/ReplayController API 为证据，结合现有 A/C 输出 schema 与实际代码输出做对照。

证据入口（RenderDoc 源码）
- ActionDescription：`renderdoc/api/replay/data_types.h:1983`
- TextureDescription：`renderdoc/api/replay/data_types.h:789`
- PipeState：`renderdoc/api/replay/pipestate.h:32`
- ReplayController API：`renderdoc/replay/replay_controller.h:146`

证据入口（A/C 输出）
- A 路线 EventPassData（schema）：`docs/analysis/codex_rdc_analyzer/2025-01-20-rdc-analyzer-schema-single-analysis.md:129`
- A 路线 HTML 事件合并实现：`scripts/rdc_analyzer/analyze_xml_report.py:313`
- A 路线纹理元数据加载：`scripts/rdc_analyzer/analyze_xml_report.py:427`
- C 路线 compare 输入结构：`docs/analysis/codex_rdc_analyzer/2025-01-20-rdc-analyzer-schema-compare.md:21`
- Canonical Schema v1 示例：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_SCHEMA.md:1`

---

## 1) 官方数据面基线（RenderDoc 源码）

### 1.1 ActionDescription（事件/动作）
- WHAT：RenderDoc 对“动作/事件”的权威结构；含 draw/dispatch/copy 信息、事件层级、输出资源。
- WHY：Event Browser 的核心数据面；对标时应以此为“动作字段全集”。
- HOW（证据）：
  - 基础事件字段（id/name/flags/draw/dispatch 等）：`renderdoc/api/replay/data_types.h:2036`
  - 拷贝/输出/事件树字段（copySource/dest、outputs、children）：`renderdoc/api/replay/data_types.h:2141`
- 关键字段样本（节选）：
  - `eventId, actionId, customName, flags, markerColor`  
  - `numIndices, numInstances, baseVertex, indexOffset, vertexOffset, instanceOffset`  
  - `dispatchDimension, dispatchThreadsDimension, dispatchBase`  
  - `copySource, copyDestination, outputs, depthOut, events, children`  

### 1.2 TextureDescription（纹理元数据）
- WHAT：RenderDoc 对纹理资源的权威元数据结构。
- WHY：纹理列表/显存占用/格式判断的基线字段集。
- HOW（证据）：`renderdoc/api/replay/data_types.h:837`
- 关键字段样本（节选）：
  - `format, dimension, type`
  - `width, height, depth`
  - `resourceId, cubemap`
  - `mips, arraysize, creationFlags`
  - `msQual, msSamp, byteSize`

### 1.3 PipeState（通用管线状态）
- WHAT：跨 API 的 Pipeline State 入口（D3D11/D3D12/GL/Vulkan）。
- WHY：资源绑定/输入布局/渲染状态的“官方快照”。
- HOW（证据）：`renderdoc/api/replay/pipestate.h:32`
- 说明：PipeState 通过不同 API 的具体 State 提供完整细节；这是“绑定与状态完整性”的官方来源。

### 1.4 ReplayController（数据获取入口）
- WHAT：ReplayController 暴露“官方可读数据面”API。
- WHY：决定哪些数据必须通过 replay 才能获取。
- HOW（证据）：`renderdoc/replay/replay_controller.h:146`
- 关键 API（节选）：
  - `GetRootActions()` / `GetPipelineState()` / `GetTextures()` / `GetBuffers()`
  - `GetResources()` / `GetDescriptorStores()` / `GetDebugMessages()`
  - `GetShaderEntryPoints()` / `GetShader()`

---

## 2) A 路线（XML → HTML）当前数据面

### 2.1 EventPassData（Event Browser 核心）
- WHAT：A 路线 HTML Event Browser 的最小契约结构（eventPassData）。
- WHY：Event Browser 的“Shader/Bindings/Mesh/API Call”都直接依赖这些字段。
- HOW（证据）：
  - Schema 说明：`docs/analysis/codex_rdc_analyzer/2025-01-20-rdc-analyzer-schema-single-analysis.md:129`
  - 实现合并逻辑：`scripts/rdc_analyzer/analyze_xml_report.py:313`

当前 A 路线事件字段（基于实现）：
- WHAT：每个事件包含 draw 基础 + XML 合并字段。
- WHY：决定是否能“像 RenderDoc 一样”展示事件详情。
- HOW（证据）：`scripts/rdc_analyzer/analyze_xml_report.py:373`
  - 基础 draw 字段：`eid, name, index_count, vertex_count, instance_count, shader_vs/ps, render_targets, depth_target`
  - XML 合并字段：`type, flags, duration, params, meshInfo, pipelineState, resourceBindings`
  - `pipelineState.bindings` 合并：`scripts/rdc_analyzer/analyze_xml_report.py:261`

### 2.2 纹理元数据（A 路线）
- WHAT：A 路线仅从 XML 或 textures.json 读取纹理元数据。
- WHY：决定“Textures 列表”是否有基础尺寸/格式信息。
- HOW（证据）：`scripts/rdc_analyzer/analyze_xml_report.py:427`
- 当前字段：`id, name, width, height, depth, format, mips, arrayLayers, thumbnail(空)`

结论（A 路线与官方对标）：
- ActionDescription：**部分覆盖**（缺失 outputs/copySource/copyDest/事件树等字段）→ 需要 replay 才能完整。  
  证据：官方字段见 `renderdoc/api/replay/data_types.h:2141`；A 路线字段见 `scripts/rdc_analyzer/analyze_xml_report.py:373`
- TextureDescription：**部分覆盖**（缺失 resourceId/cubemap/creationFlags/msQual/msSamp/byteSize）→ 需要 replay 或 XML 扩展。  
  证据：官方字段见 `renderdoc/api/replay/data_types.h:837`；A 路线字段见 `scripts/rdc_analyzer/analyze_xml_report.py:468`
- PipeState：**部分覆盖**（XML pipelineState + bindings 仅是快照）→ 完整状态需 replay。  
  证据：PipeState 官方入口 `renderdoc/api/replay/pipestate.h:32`

---

## 3) C 路线（Compare）当前数据面

### 3.1 compare 输入结构（Phase2 dict）
- WHAT：compare 需要“字典结构的 canonical JSON”，而非 Phase1 list。
- WHY：对比引擎依赖统一 schema；否则关键字段会被清零。
- HOW（证据）：`docs/analysis/codex_rdc_analyzer/2025-01-20-rdc-analyzer-schema-compare.md:21`
- 要求字段（节选）：`summary, textures, shaders, buffers, draw_calls, events, statistics`

### 3.2 compare 输出结构（diff/report）
- WHAT：输出 summary/regressions/resource_changes 等差异视图。
- WHY：支撑“全方位对比+结论”的自动化出口。
- HOW（证据）：`docs/analysis/codex_rdc_analyzer/2025-01-20-rdc-analyzer-schema-compare.md:43`

### 3.3 Canonical Schema v1（目标结构）
- WHAT：统一的 single/compare 输入输出 schema。
- WHY：避免 A/C/B 产生多 schema 分裂。
- HOW（证据）：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_SCHEMA.md:1`

结论（C 路线与官方对标）：
- C 路线强调 **差异视角**（summary/regression/resource_changes），不等于官方“字段全集”。  
  因此对标 RenderDoc“数据丰富度”时，C 只能覆盖“统计/结论层”，而非细节字段。

---

## 4) 字段对齐与缺口（A+C vs 官方）

### 4.1 对齐表（高层）
| 数据面 | 官方基线（RenderDoc） | A 路线覆盖 | C 路线覆盖 | 是否必须 Replay |
|---|---|---|---|---|
| Actions / Events | ActionDescription 全字段 | 部分（基础 draw + XML params/meshInfo/pipelineState） | 统计/对比（非字段全集） | 是（完整事件树/输出/拷贝字段） |
| Pipeline State | PipeState + API-specific State | 部分（XML snapshot + bindings 合并） | 统计层 | 是（完整 state/bindings/descriptor） |
| Textures | TextureDescription 全字段 | 部分（尺寸/格式/层级，缺 byteSize 等） | 统计/对比层 | 部分（完整元数据需 replay） |
| Buffers / Resources | BufferDescription / ResourceDescription | 缺失（A 未导出） | 统计/对比层 | 是 |
| Descriptors | DescriptorStore/Access | 缺失 | 缺失 | 是 |
| Shaders | ShaderEntryPoints / ShaderReflection | 缺失 | 部分（统计） | 是 |
| Debug Messages | DebugMessage | 缺失 | 缺失 | 是 |
| Counters | Enumerate/FetchCounters | 缺失 | 缺失 | 是 |

### 4.2 缺口说明（WHAT / WHY / HOW）

#### 缺口 A：事件树/输出/拷贝字段
- WHAT：`outputs, depthOut, copySource, copyDestination, children` 等字段未在 A 路线事件中体现。
- WHY：Event Browser 无法做“输出/拷贝通路”与“事件树层级”完整展示。
- HOW（证据）：官方字段见 `renderdoc/api/replay/data_types.h:2141`；A 路线字段见 `scripts/rdc_analyzer/analyze_xml_report.py:373`
- 结论：需 replay 才能完整对齐（B 路线能力）。

#### 缺口 B：纹理完整元数据
- WHAT：A 路线缺少 `resourceId/cubemap/creationFlags/msQual/msSamp/byteSize`。
- WHY：缺少这些字段无法与 RenderDoc 纹理视图一致（显存/格式/多采样完整性）。
- HOW（证据）：官方字段见 `renderdoc/api/replay/data_types.h:837`；A 路线字段见 `scripts/rdc_analyzer/analyze_xml_report.py:468`
- 结论：可在 XML 扩展或 replay 获取；现阶段 A 路线为“部分覆盖”。

#### 缺口 C：PipelineState 全量
- WHAT：A 路线仅有 XML snapshot + bindings 合并。
- WHY：无法覆盖 API-specific state 与完整 descriptor 访问。
- HOW（证据）：PipeState 入口 `renderdoc/api/replay/pipestate.h:32`；A 路线合并逻辑 `scripts/rdc_analyzer/analyze_xml_report.py:261`
- 结论：完整性依赖 replay（B 路线）。

---

## 5) 结论与下一步（不改代码，仅边界结论）
- A+C 可以形成“可用的 HTML + 统计/建议闭环”，但与 RenderDoc 官方数据丰富度仍有明确差距。
- “官方字段全集”大部分依赖 ReplayController API，因此 **必须承认 B 路线是完整对标的必要条件**。
- A 路线应被定义为“快速/无 replay 的部分覆盖”，并在报告中明确标注覆盖度与缺口原因。
