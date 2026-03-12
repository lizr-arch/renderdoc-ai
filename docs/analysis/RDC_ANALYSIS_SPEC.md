# RDC 自动分析输出规格 v1.1

> **目标**: 定义 MCP/Skill 从 RDC 文件中提取的数据结构和输出格式
> 
> **状态**: 正式版 | **更新**: 2025-01-16
>
> **文档职责**: 本文档**只定义输出格式**，规则定义请参见 `RULES_RENDERDOC.md`

---

## 1. 设计原则

1. **分层输出**: 从粗到细，先给摘要，再给详情
2. **问题导向**: 不只输出数据，还要检测潜在问题
3. **LLM 友好**: 输出格式便于大模型理解和推理
4. **增量扩展**: 核心字段固定，允许 API 特定扩展

---

## 2. 输出结构总览

```
RDCAnalysisResult
├── meta                    # 文件元信息
├── frame_summary           # 帧级摘要统计
├── resources               # 资源清单
│   ├── textures[]
│   ├── buffers[]
│   └── shaders[]
├── render_passes[]         # 渲染 Pass 结构
├── draw_calls[]            # 绘制调用列表
├── state_changes           # 状态切换统计
├── issues[]                # 检测到的问题
└── raw_chunks[]            # (可选) 原始 Chunk 序列
```

---

## 3. 详细字段定义

### 3.1 meta - 文件元信息

```yaml
meta:
  file_name: "Game_x64h_2026.01.07_05.35.50_frame3996.rdc"
  file_size: 45678901                    # 字节
  capture_time: "2026-01-07T05:35:50"    # ISO 8601
  api: "D3D11"                           # D3D11 | D3D12 | Vulkan | OpenGL
  driver_version: "31.0.15.5123"         # 可选
  gpu_name: "NVIDIA GeForce RTX 4090"    # 可选
  frame_number: 3996                     # 帧号
  renderdoc_version: "1.32"              # RenderDoc 版本
```

### 3.2 frame_summary - 帧级摘要

```yaml
frame_summary:
  # === 绘制统计 ===
  total_draw_calls: 127
  total_dispatches: 5                    # Compute Shader 调度
  total_vertices: 2450000
  total_triangles: 816666
  total_indices: 2450000
  instanced_draws: 12                    # 使用 Instancing 的 Draw 数
  indirect_draws: 0                      # 使用 Indirect 的 Draw 数
  
  # === 资源统计 ===
  texture_count: 89
  buffer_count: 156
  shader_count: 23
  render_target_count: 8
  depth_stencil_count: 2
  
  # === 内存估算 ===
  estimated_texture_memory_mb: 512.5
  estimated_buffer_memory_mb: 128.3
  estimated_total_memory_mb: 640.8
  
  # === 状态切换 ===
  pso_changes: 45                        # Pipeline State 切换
  shader_changes: 67                     # VS/PS/CS 等切换
  render_target_changes: 12              # RT 切换
  viewport_changes: 8
  blend_state_changes: 23
  depth_state_changes: 18
  rasterizer_state_changes: 15
  
  # === 效率指标 ===
  redundant_state_sets: 34               # 冗余状态设置数
  redundant_state_ratio: 0.08            # 冗余比例 (0-1)
  avg_vertices_per_draw: 19291           # 平均每 Draw 顶点数
  small_draw_count: 15                   # 小 Draw (< 100 顶点)
  small_draw_ratio: 0.12                 # 小 Draw 占比
```

### 3.3 resources - 资源清单

#### 3.3.1 textures[]

```yaml
textures:
  - id: "0x00001234"
    name: "Albedo_Diffuse"               # 如有调试名
    width: 2048
    height: 2048
    depth: 1                             # 3D 纹理深度
    array_size: 1                        # 纹理数组大小
    mip_levels: 11
    format: "BC7_UNORM"                  # DXGI_FORMAT / VkFormat
    format_category: "compressed"        # compressed | uncompressed | depth
    sample_count: 1                      # MSAA
    usage: ["SRV"]                       # SRV | RTV | DSV | UAV
    memory_mb: 5.33
    is_render_target: false
    is_depth_stencil: false
    
    # 问题标记
    issues:
      - "LARGE_UNCOMPRESSED"             # 如果适用
```

#### 3.3.2 buffers[]

```yaml
buffers:
  - id: "0x00005678"
    name: "VertexBuffer_MainChar"
    size_bytes: 16777216                 # 16 MB
    size_mb: 16.0
    usage: ["VERTEX_BUFFER"]             # VERTEX | INDEX | CONSTANT | STRUCTURED | UAV
    cpu_access: "none"                   # none | read | write | read_write
    stride: 32                           # 结构化 Buffer 的 stride
    element_count: 524288                # 元素数量
```

#### 3.3.3 shaders[]

```yaml
shaders:
  - id: "0x0000ABCD"
    type: "PS"                           # VS | PS | GS | HS | DS | CS
    name: "GBuffer_PS"                   # 如有调试名
    bind_count: 45                       # 本帧绑定次数
    hash: "a1b2c3d4..."                  # Shader 字节码 hash
```

### 3.4 render_passes[] - Pass 结构

```yaml
render_passes:
  - index: 0
    name: "GBuffer Pass"                 # 推断或标注的名称
    start_event_id: 100
    end_event_id: 245
    draw_count: 45
    dispatch_count: 0
    
    render_targets:
      - slot: 0
        texture_id: "0x00001000"
        format: "R8G8B8A8_UNORM"
        clear: true                      # 是否 Clear
        load_op: "CLEAR"                 # CLEAR | LOAD | DONT_CARE
        store_op: "STORE"                # STORE | DONT_CARE
        
    depth_stencil:
      texture_id: "0x00002000"
      format: "D24_UNORM_S8_UINT"
      clear: true
      
    viewport:
      width: 1920
      height: 1080
      
    # Pass 级统计
    stats:
      total_vertices: 500000
      total_triangles: 166666
      avg_draw_size: 11111
```

### 3.5 draw_calls[] - 绘制调用详情

```yaml
draw_calls:
  - event_id: 150
    type: "DrawIndexed"                  # Draw | DrawIndexed | DrawInstanced | ...
    
    # 几何参数
    index_count: 3600
    vertex_count: 1200                   # 估算
    instance_count: 1
    start_index: 0
    base_vertex: 0
    start_instance: 0
    
    # 当前绑定状态 (快照)
    bound_state:
      vertex_shader: "0x0000A001"
      pixel_shader: "0x0000A002"
      render_targets: ["0x00001000", "0x00001001"]
      depth_stencil: "0x00002000"
      index_buffer: "0x00003000"
      vertex_buffers: ["0x00004000", "0x00004001"]
      
    # Pass 归属
    pass_index: 0
```

### 3.6 state_changes - 状态切换统计

```yaml
state_changes:
  by_type:
    OMSetRenderTargets: 12
    PSSetShader: 45
    VSSetShader: 38
    IASetVertexBuffers: 89
    IASetIndexBuffer: 67
    RSSetViewports: 8
    OMSetBlendState: 23
    OMSetDepthStencilState: 18
    RSSetState: 15
    
  redundant:                             # 冗余设置详情
    OMSetBlendState: 5
    RSSetState: 3
    
  hotspots:                              # 高频切换的资源
    - type: "PSSetShader"
      resource_id: "0x0000A002"
      count: 23                          # 被绑定 23 次
```

### 3.7 issues[] - 检测到的问题

```yaml
issues:
  - severity: "warning"                  # error | warning | info
    category: "performance"              # performance | correctness | memory
    code: "HIGH_DRAW_CALL_COUNT"
    message: "Draw Call 数量 (127) 较高，考虑批处理优化"
    threshold: 100
    actual: 127
    
  - severity: "warning"
    category: "memory"
    code: "LARGE_UNCOMPRESSED_TEXTURE"
    message: "纹理 0x00005678 (4096x4096 R8G8B8A8) 未使用压缩格式"
    resource_id: "0x00005678"
    suggestion: "考虑使用 BC7 压缩格式"
    
  - severity: "info"
    category: "performance"
    code: "SMALL_DRAW_CALLS"
    message: "15 个 Draw Call (12%) 绘制少于 100 顶点"
    count: 15
    ratio: 0.12
    suggestion: "考虑合批或剔除"
    
  - severity: "info"
    category: "performance"
    code: "REDUNDANT_STATE_SETS"
    message: "34 次冗余状态设置 (8%)"
    count: 34
    ratio: 0.08
```

---

## 4. 问题检测规则

> ⚠️ **注意**: 完整的规则定义、阈值和检测逻辑请参见 [`RULES_RENDERDOC.md`](./RULES_RENDERDOC.md)
>
> 本节仅列出 `issues[]` 字段中使用的规则 ID 映射。

### 4.1 规则 ID 映射表

| issues.code | RULES 文档 ID | 类别 |
|-------------|---------------|------|
| `HIGH_DRAW_CALL_COUNT` | `RD_DC_001` | Draw Call |
| `FREQUENT_STATE_SWITCH` | `RD_DC_002` | Draw Call |
| `UNBATCHED_SAME_MATERIAL` | `RD_DC_003` | Draw Call |
| `INSTANCING_CANDIDATE` | `RD_DC_004` | Draw Call |
| `EMPTY_DRAW_CALL` | `RD_DC_005` | Draw Call |
| `LARGE_UNCOMPRESSED_TEXTURE` | `RD_TEX_001` | 纹理 |
| `NON_POT_TEXTURE` | `RD_TEX_002` | 纹理 |
| `NO_MIPMAP` | `RD_TEX_003` | 纹理 |
| `HUGE_TEXTURE` | `RD_TEX_004` | 纹理 |
| `HIGH_TEXTURE_MEMORY` | `RD_TEX_005` | 纹理 |
| `HIGH_VERTEX_COUNT` | `RD_VERT_001` | 顶点 |
| `LARGE_SINGLE_DRAW` | `RD_VERT_002` | 顶点 |
| `FREQUENT_RT_SWITCH` | `RD_RT_001` | RT |
| `FREQUENT_SHADER_SWITCH` | `RD_SHADER_001` | Shader |
| `HIGH_BUFFER_MEMORY` | `RD_BUF_001` | Buffer |
| `DEPTH_WRITE_WITH_BLEND` | `RD_STATE_001` | 状态 |
| `HIGH_TRANSPARENT_RATIO` | `RD_OD_001` | Overdraw |

### 4.2 严重性级别

| 级别 | 说明 | 规则示例 |
|------|------|----------|
| `error` | 严重问题，必须修复 | `RD_STATE_004` (线框模式) |
| `warning` | 性能隐患，建议优化 | `RD_DC_001` (Draw Call 过多) |
| `info` | 优化建议 | `RD_DC_004` (Instancing 候选) |

---

## 5. 输出格式

### 5.1 JSON (完整数据)

```json
{
  "version": "1.0",
  "meta": { ... },
  "frame_summary": { ... },
  "resources": { ... },
  "render_passes": [ ... ],
  "draw_calls": [ ... ],
  "state_changes": { ... },
  "issues": [ ... ]
}
```

### 5.2 Markdown (人类可读摘要)

```markdown
# RDC Analysis Report

## Frame Summary
| Metric | Value |
|--------|-------|
| Draw Calls | 127 |
| Triangles | 816,666 |
| ...

## Issues Found (3)
- ⚠️ HIGH_DRAW_CALL_COUNT: Draw Call 数量较高...
- ⚠️ LARGE_UNCOMPRESSED_TEXTURE: ...

## Top Resources by Memory
1. Texture 0x1234 (512 MB) - Shadowmap
2. ...
```

### 5.3 LLM Prompt (用于 AI 分析)

```
以下是 RDC 文件 "xxx.rdc" 的分析结果：

帧统计：
- Draw Call: 127, 三角形: 816666, 纹理数: 89

检测到的问题：
1. [WARNING] Draw Call 数量 127 超过阈值 100
2. [WARNING] 纹理 0x5678 (4096x4096) 未压缩

请基于以上数据，给出性能优化建议。
```

---

## 6. 实现路线图

| Phase | 目标 | 输出 |
|-------|------|------|
| **Phase 1** | 帧摘要 | `frame_summary` + 基础 `issues` |
| **Phase 2** | 资源清单 | `resources.textures/buffers` |
| **Phase 3** | Pass 结构 | `render_passes` |
| **Phase 4** | 完整 Draw 详情 | `draw_calls` + 绑定状态 |
| **Phase 5** | 高级检测 | 扩展 `issues` 规则 |

---

## 7. API 特定扩展

### D3D11 扩展字段

```yaml
d3d11_specific:
  feature_level: "11_1"
  deferred_context_used: false
  query_count: 5                         # Occlusion/Timestamp Query
```

### D3D12 扩展字段

```yaml
d3d12_specific:
  command_list_count: 3
  root_signature_changes: 12
  descriptor_heap_switches: 4
  barrier_count: 89
```

### Vulkan 扩展字段

```yaml
vulkan_specific:
  render_pass_count: 5
  subpass_count: 8
  pipeline_barrier_count: 45
  descriptor_set_updates: 23
```

---

## 附录 A: 参考资料

- NVIDIA SOL Analysis Method
- AMD RDNA Performance Guide  
- Unity Graphics Optimization Guide
- Unreal Engine Frame Analysis (Interplay of Light)
