#!/usr/bin/env markdown
# Phase 1 接口需求清单 (For Phase 2 RDC Comparison Engine)

> **版本**: 1.0.0  
> **日期**: 2026-01-19  
> **作者**: Phase 2 RDC Comparison Engine

---

## 📋 概述

Phase 2 对比引擎已完成，但完整的对比分析需要 Phase 1 提供以下额外数据。

### 当前 Phase 1 输出结构

```json
[{
  "summary": {...},
  "shaders": [...],
  "textures": [...]
}]
```

### 期望 Phase 1 输出结构

```json
[{
  "summary": {...},
  "shaders": [...],
  "textures": [...],
  "buffers": [...],      // 🆕 需要新增
  "draw_calls": [...]    // 🆕 需要新增
}]
```

---

## 🔴 缺失数据 (高优先级)

### 1. 顶点/三角形统计

| 字段 | 位置 | 说明 |
|------|------|------|
| `total_vertices` | `summary` | 帧内所有 Draw Call 的顶点总数 |
| `total_triangles` | `summary` | 帧内所有 Draw Call 的三角形总数 |

**Phase 1 实现建议**:
```python
# 遍历 Draw Call 累加
total_vertices = 0
total_triangles = 0
for action in controller.GetRootActions():
    if action.flags & ActionFlags.Drawcall:
        total_vertices += action.numIndices  # 或 numInstances * vertexCount
        total_triangles += action.numIndices // 3  # 假设三角形列表
```

---

### 2. Buffer 列表

| 字段 | 类型 | 说明 |
|------|------|------|
| `buffers` | `List[Dict]` | 所有 Buffer 资源列表 |

**每个 Buffer 需要的字段**:
```json
{
  "resource_id": 12345,
  "name": "VertexBuffer_0",
  "size_bytes": 1048576,
  "usage": "Vertex",           // Vertex / Index / Uniform / Storage
  "format": "R32G32B32_FLOAT"  // 可选
}
```

**Phase 1 实现建议**:
```python
buffers = []
for buf in controller.GetBuffers():
    buffers.append({
        "resource_id": buf.resourceId,
        "name": buf.name or f"Buffer_{buf.resourceId}",
        "size_bytes": buf.length,
        "usage": str(buf.creationFlags),
    })
```

---

### 3. Draw Call 详情列表

| 字段 | 类型 | 说明 |
|------|------|------|
| `draw_calls` | `List[Dict]` | 每个 Draw Call 的详细信息 |

**每个 Draw Call 需要的字段**:
```json
{
  "event_id": 100,
  "name": "vkCmdDrawIndexed",
  "num_indices": 3600,
  "num_instances": 1,
  "base_vertex": 0,
  "first_index": 0,
  "shader_hash": "abc123...",      // 使用的 shader
  "pipeline_id": 456,              // 使用的 pipeline
  "render_target_id": 789          // 当前 render target
}
```

**Phase 1 实现建议**:
```python
draw_calls = []
def traverse_actions(action_list):
    for action in action_list:
        if action.flags & ActionFlags.Drawcall:
            draw_calls.append({
                "event_id": action.eventId,
                "name": action.GetName(structured_file),
                "num_indices": action.numIndices,
                "num_instances": action.numInstances,
                "base_vertex": action.baseVertex,
                "first_index": action.indexOffset,
            })
        traverse_actions(action.children)

traverse_actions(controller.GetRootActions())
```

---

## 🟡 可选增强 (中优先级)

### 4. 纹理内存 size_bytes

当前 Phase 2 使用估算值，如果 Phase 1 能提供精确值更好：

```json
{
  "resource_id": 119808,
  "width": 1024,
  "height": 1024,
  "format_name": "R8G8B8A8_UNORM",
  "size_bytes": 4194304  // 🆕 精确内存大小
}
```

**Phase 1 实现建议**:
```python
# RenderDoc 的 TextureDescription 可能包含 byteSize
size_bytes = tex.width * tex.height * tex.depth * tex.arraysize * bytes_per_pixel(tex.format)
```

---

### 5. Pipeline 关联信息

将 Shader 与 Pipeline 关联，便于分析：

```json
{
  "pipelines": [
    {
      "pipeline_id": 456,
      "vertex_shader_hash": "abc...",
      "fragment_shader_hash": "def...",
      "blend_state": {...},
      "depth_state": {...}
    }
  ]
}
```

---

## 📊 数据格式总结

### Phase 1 完整输出模板

```json
[{
  "summary": {
    "file": "capture.rdc",
    "file_name": "capture",
    "driver": "Vulkan",
    "gpu_core": "Mali-G715",
    "total_draw_events": 148,
    "total_vertices": 1250000,       // 🆕
    "total_triangles": 416666,       // 🆕
    "total_shaders": 84,
    "total_textures": 38,
    "total_buffers": 25,             // 🆕
    "total_pipelines": 55,
    "timestamp": "2026-01-19T12:00:00"
  },
  "shaders": [...],                  // 已有
  "textures": [...],                 // 已有
  "buffers": [...],                  // 🆕
  "draw_calls": [...]                // 🆕
}]
```

---

## 🔗 Phase 2 兼容性说明

Phase 2 的 `compare_rdc.py` 已实现向后兼容：

- ✅ 支持当前 Phase 1 输出格式（无 buffers/draw_calls）
- ✅ 自动估算缺失的纹理内存
- ✅ 使用 shader hash 作为唯一标识
- ⚠️ 顶点/三角形/Buffer 统计将显示为 0（直到 Phase 1 补充数据）

---

## 📌 优先级建议

| 优先级 | 数据 | 影响 |
|--------|------|------|
| P0 (必须) | `total_vertices`, `total_triangles` | 核心性能指标 |
| P0 (必须) | `buffers` 列表 | Buffer 内存对比 |
| P1 (重要) | `draw_calls` 列表 | Draw Call 详细对比 |
| P2 (可选) | `size_bytes` (纹理) | 精确内存统计 |
| P2 (可选) | `pipelines` 关联 | Pipeline 变化分析 |

---

*文档结束*
