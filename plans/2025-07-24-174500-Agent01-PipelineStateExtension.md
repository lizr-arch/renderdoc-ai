# Pipeline State 功能扩展计划

> **日期**: 2025-07-24  
> **目标**: 根据调研报告补充 Pipeline State 解析功能

---

## 执行概览

根据 XML 结构分析结果，需要添加以下解析功能：

| 调用类型 | XML 关键参数 | 输出数据结构 |
|---------|-------------|-------------|
| `*SetShaderResources` | StartSlot, NumViews, ppShaderResourceViews (ResourceId[]) | `{slot: resourceId}` |
| `*SetConstantBuffers` | StartSlot, NumBuffers, ppConstantBuffers (ResourceId[]) | `{slot: resourceId}` |
| `*SetSamplers` | StartSlot, NumSamplers, ppSamplers (ResourceId[]) | `{slot: resourceId}` |
| `OMSetRenderTargets` | NumViews, ppRenderTargetViews[], pDepthStencilView | `{rtvs: [], dsv: ...}` |
| `IASetVertexBuffers` | StartSlot, ppVertexBuffers[], pStrides[], pOffsets[] | `[{slot, buffer, stride, offset}]` |
| `IASetIndexBuffer` | pIndexBuffer, Format, Offset | `{buffer, format, offset}` |
| `CreateRasterizerState` | Descriptor (FillMode, CullMode, ...), pState | state_objects 映射 |

---

## 任务分解

### Task 1: 添加 Shader Resources 解析 (P0)

**修改文件**: `scripts/rdc_analyzer/parse_rdc_xml.py`

**新增函数**:
```python
def parse_shader_resources_from_params(params, shader_stage):
    """解析 *SetShaderResources 参数
    Returns: [{slot: int, resourceId: str}]
    """
```

**Pipeline State 扩展**:
```python
"shaderResources": {
    "vs": [],  # [{slot, resourceId}]
    "ps": [],
    "gs": [],
    "hs": [],
    "ds": [],
    "cs": [],
}
```

### Task 2: 添加 Constant Buffers 解析 (P0)

**新增函数**:
```python
def parse_constant_buffers_from_params(params, shader_stage):
    """解析 *SetConstantBuffers 参数
    Returns: [{slot: int, resourceId: str}]
    """
```

**Pipeline State 扩展**:
```python
"constantBuffers": {
    "vs": [],
    "ps": [],
    # ...
}
```

### Task 3: 添加 RenderTarget 绑定解析 (P0)

**新增函数**:
```python
def parse_render_targets_from_params(params):
    """解析 OMSetRenderTargets 参数
    Returns: {
        "renderTargetViews": [{slot, resourceId}],
        "depthStencilView": resourceId or None
    }
    """
```

### Task 4: 添加 Sampler 解析 (P1)

**新增函数**:
```python
def parse_samplers_from_params(params, shader_stage):
    """解析 *SetSamplers 参数
    Returns: [{slot: int, resourceId: str}]
    """
```

### Task 5: 添加 Vertex/Index Buffer 解析 (P1)

**新增函数**:
```python
def parse_vertex_buffers_from_params(params):
    """解析 IASetVertexBuffers 参数
    Returns: [{slot, buffer, stride, offset}]
    """

def parse_index_buffer_from_params(params):
    """解析 IASetIndexBuffer 参数
    Returns: {buffer, format, offset}
    """
```

### Task 6: 添加 Rasterizer State 解析 (P2)

**修改 collect_state_objects_from_xml**:
- 添加 CreateRasterizerState 解析
- 存储 FillMode, CullMode 等配置

### Task 7: 更新 HTML 报告模板

**修改文件**: `scripts/rdc_analyzer/generate_real_report.py`

- 在 Pipeline Tab 中添加新数据展示
- 按 RenderDoc 风格分组显示

---

## 数据结构设计

完整的 `pipelineState` 结构：

```python
{
    # 现有字段
    "viewport": {...},
    "scissor": {...},
    "blendState": {...},
    "depthState": {...},
    "rasterizerState": {...},
    "shaders": {"vs": ..., "ps": ..., ...},
    "primitiveTopology": "...",
    "inputLayout": "...",
    
    # 新增字段
    "shaderResources": {
        "vs": [{"slot": 0, "resourceId": "2581970"}],
        "ps": [{"slot": 0, "resourceId": "2583306"}],
        # ...
    },
    "constantBuffers": {
        "vs": [{"slot": 1, "resourceId": "1235976"}],
        "ps": [{"slot": 0, "resourceId": "1987770"}],
        # ...
    },
    "samplers": {
        "vs": [],
        "ps": [{"slot": 0, "resourceId": "286"}],
        # ...
    },
    "renderTargets": {
        "views": [{"slot": 0, "resourceId": "..."}],
        "depthStencil": {"resourceId": "..."}
    },
    "vertexBuffers": [
        {"slot": 0, "buffer": "2561956", "stride": 12, "offset": 0}
    ],
    "indexBuffer": {
        "buffer": "2561954",
        "format": "DXGI_FORMAT_R16_UINT",
        "offset": 0
    }
}
```

---

## 风险与注意事项

1. **资源累积**: 某些调用可能设置 slot 0-3，后续调用设置 slot 4-7，需要正确合并
2. **空值处理**: ResourceId 为 0 表示解绑，需要特殊处理
3. **性能**: 新增解析逻辑不应显著增加处理时间

---

## 验收标准

1. 运行 `py -3 parse_rdc_xml.py capture.xml output.json` 生成的 JSON 包含新字段
2. HTML 报告 Pipeline Tab 正确展示新数据
3. 不破坏现有功能（VS/PS shader ID 仍正常显示）
