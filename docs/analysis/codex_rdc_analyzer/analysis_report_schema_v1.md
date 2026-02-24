# Analysis Report Schema v1 (Single Frame)

> **目标**：为单帧分析报告定义统一字段契约（P0/P1/P2）、页面结构与数据采集路径，
> 覆盖 Vulkan + D3D11 + D3D12，并对 Mali Offline Compiler 形成 P1 扩展位。

## 1. 范围与分层

- **范围**：单帧分析（multi-frame diff 另立）。
- **P0**：基础可用分析字段（不依赖外部硬件工具）。
- **P1**：Mali Offline Compiler 指标。
- **P2**：RGP/Nsight/PIX 等外部硬件分析占位。

## 2. Top-level Contract (P0)

> `analysis.json` 为 SSOT，至少包含以下顶层键。

| Key | Type | 说明 |
| --- | --- | --- |
| `schema_version` | string | 版本号 |
| `summary` | object | 帧摘要 |
| `events` | array | 事件/Draw/Dispatch 列表 |
| `textures` | array | 纹理与 RT 资源 |
| `shaders` | array | Shader 列表 |
| `passes` | array | Render Pass / pass-like 分组 |
| `pipeline_state` | array | 事件级渲染状态快照 |
| `uniforms` | array | 常量/Uniform 绑定摘要 |
| `issues` | array | 规则/诊断输出（可为空） |
| `suggestions` | array | 诊断建议（可为空） |

## 3. Field Contract (P0)

### 3.1 Summary
基于 `FrameSummary`（`scripts/rdc_analyzer/core/types.py`）。

| Field | Type | 必填 | 说明 |
| --- | --- | --- | --- |
| `api` | string | Y | Vulkan / D3D11 / D3D12 |
| `frame` | int | Y | 帧号（若可用） |
| `draw_call_count` | int | Y | DrawCall 计数 |
| `dispatch_count` | int | Y | Dispatch 计数 |
| `texture_count` | int | Y | 纹理数量 |
| `buffer_count` | int | Y | Buffer 数量 |
| `pass_count` | int | Y | Pass 数量 |
| `viewport_width` | int | N | 视口宽 |
| `viewport_height` | int | N | 视口高 |
| `total_texture_memory` | int | N | 纹理内存估算 |
| `total_buffer_memory` | int | N | Buffer 内存估算 |

### 3.2 Events / Draws
基于 `ParsedData.draws/dispatches` 与 `DrawCallInfo`（`scripts/rdc_analyzer/core/types.py`）。

| Field | Type | 必填 | 说明 |
| --- | --- | --- | --- |
| `eid` | int | Y | 事件 ID |
| `name` | string | Y | Draw/Dispatch 名称 |
| `type` | string | Y | draw / dispatch / clear |
| `pass_id` | int | N | 所属 pass index |
| `vs_id` / `ps_id` | string | N | 关联 shader id |
| `rt_ids` | array | N | 绑定的 RT 列表 |
| `ds_id` | string | N | 深度模板 id |

### 3.3 Textures / Render Targets
基于 `TextureInfo`（`scripts/rdc_analyzer/core/types.py`）。

| Field | Type | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | string | Y | 资源 id |
| `name` | string | N | 资源名 |
| `width/height/depth` | int | Y | 尺寸 |
| `format` | string | Y | 格式 |
| `format_category` | string | N | compressed/uncompressed/depth |
| `mip_levels` | int | N | Mip 数 |
| `array_size` | int | N | 数组层 |
| `sample_count` | int | N | MSAA |
| `memory_size` | int | N | 内存估算 |
| `is_render_target` | bool | N | RT 标识 |
| `is_depth_stencil` | bool | N | DS 标识 |
| `bind_count` | int | N | 绑定次数 |

### 3.4 Shaders
基于 `ShaderInfo`（`scripts/rdc_analyzer/core/types.py`）。

| Field | Type | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | string | Y | 资源 id |
| `stage` | string | Y | VS/PS/CS/GS/HS/DS/AS/MS |
| `entry_point` | string | N | 入口函数 |
| `encoding` | string | N | HLSL/DXIL/SPIRV/GLSL |
| `hash` | string | N | 字节码 hash |
| `source_asm` | string | N | 反汇编文本 |
| `source_hlsl` | string | N | HLSL 源码（若可用） |
| `constant_blocks` | array | N | 常量缓冲信息 |
| `read_only_resources` | array | N | SRV |
| `read_write_resources` | array | N | UAV |
| `samplers` | array | N | 采样器 |

### 3.5 Passes
基于 `PassInfo`（`scripts/rdc_analyzer/core/types.py`）。

| Field | Type | 必填 | 说明 |
| --- | --- | --- | --- |
| `index` | int | Y | Pass 编号 |
| `name` | string | N | Pass 名称 |
| `start_event_id` | int | Y | 起始事件 |
| `end_event_id` | int | Y | 结束事件 |
| `draw_count` | int | N | Draw 数 |
| `dispatch_count` | int | N | Dispatch 数 |
| `render_targets` | array | N | RT 列表（若可用） |
| `depth_stencil` | object | N | DS 信息 |
| `marker_name` | string | N | Debug Marker |
| `color_attachments` | array | N | Vulkan render pass 附件 |
| `depth_attachment` | object | N | Vulkan depth 附件 |
| `has_resolve` | bool | N | 是否 resolve |

### 3.6 Pipeline State (per-event)
来自 `DrawCallInfo` 中的状态字段，或从 RenderDoc pipeline state 获取。

| Field | Type | 必填 | 说明 |
| --- | --- | --- | --- |
| `eid` | int | Y | 事件 ID |
| `blend_enabled` | bool | N | Blend |
| `depth_test` | bool | N | 深度测试 |
| `depth_write` | bool | N | 深度写 |
| `cull_mode` | string | N | Cull |
| `fill_mode` | string | N | Fill |

### 3.7 Uniforms / Constant Buffers
来自 `ShaderInfo.constant_blocks` + `ShaderConstantBlock`。

| Field | Type | 必填 | 说明 |
| --- | --- | --- | --- |
| `eid` | int | N | 关联事件 |
| `shader_id` | string | N | 关联 shader |
| `cbuffers` | array | N | 常量缓冲列表 |
| `push_constants` | array | N | Vulkan push constants（若可用） |

## 4. P1: Mali Offline Compiler

**字段位置建议：**
```
shaders[].mali = {
  "gpu": "Mali-G78",
  "cycles": ...,
  "registers": ...,
  "local_mem": ...,
  "warnings": [...]
}
```

数据来源：`scripts/rdc_analyzer/analyzers/mali_analyzer.py`

## 5. P2: External Profilers (占位)

- **RGP (AMD)**：wave occupancy / ISA / barrier cost
- **Nsight (NVIDIA)**：source mapping / shader profiler
- **PIX (Windows)**：GPU timing / counters

占位字段：`shaders[].external.<tool>`，`events[].external.<tool>`

## 6. Page Structure

- **Overview**：summary + top issues + 关键计数
- **Events / Passes**：时间线 / pass 分组 / 搜索过滤
- **Shaders**：列表 + 使用频率 + Mali 指标（P1）
- **Textures / RT**：格式/尺寸/内存/使用事件
- **Pipeline State**：状态变化与热点事件
- **Uniforms**：常量缓冲 + push constants 摘要

## 7. Extraction Map

| Field | Source (module:function) | Vulkan | D3D11 | D3D12 | Notes |
| --- | --- | --- | --- | --- | --- |
| `summary.*` | `scripts/rdc_analyzer/core/types.py:FrameSummary` | Y | Y | Y | 汇总由 analyzers 汇聚 |
| `textures[]` | `scripts/rdc_analyzer/analyzers/resource.py:_parse_texture_api` | Y | Y | Y | API 模式直接从 controller |
| `shaders[]` | `scripts/rdc_analyzer/analyzers/resource.py:_parse_shader_api` | Y | Y | Y | 依赖 RenderDoc 反射 |
| `passes[]` | `scripts/rdc_analyzer/analyzers/pass_analyzer.py:_analyze_from_draws` | Y | Y | Y | 无 renderPass 时退化 |
| `passes[].renderPassInfo` | `scripts/rdc_analyzer/analyzers/pass_analyzer.py:_analyze_from_render_passes` | Y | N | N | Vulkan XML renderPass |
| `pipeline_state[]` | `scripts/rdc_analyzer/core/types.py:DrawCallInfo` | Y | Y | Y | 取决于 draw 解析字段 |
| `uniforms[]` | `scripts/rdc_analyzer/core/types.py:ShaderConstantBlock` | ? | ? | ? | 依赖 shader 反射与绑定信息 |
| `issues[]` | `scripts/rdc_analyzer/core/types.py:Issue` | Y | Y | Y | 规则系统输出 |
| `mali metrics` | `scripts/rdc_analyzer/analyzers/mali_analyzer.py` | Y | N | N | P1 |

> **说明**：`uniforms[]` 及部分 pipeline_state 字段的 API 覆盖尚需校验，标记为 **?（待验证）**。

## 8. 已知缺口 / 待验证

- `uniforms` 的事件级实际值捕获是否可用（依赖 API 反射能力）。
- D3D11/D3D12 是否能提供 Vulkan 类似的 render pass 细节（当前按 draw 分组）。
- `analysis.json` 中是否已包含所有事件级 RT/DS 绑定细节（需和 pipeline 输出对齐）。
