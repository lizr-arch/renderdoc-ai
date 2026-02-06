# Pipeline State 数据源说明

## 概述

RDC Analyzer 支持两种方式获取 Pipeline State 数据：

1. **XML 解析**（默认）- 从 RDC 导出的 XML 中推断
2. **Python API**（可选）- 在 RenderDoc Python 环境中直接查询 GPU 状态

## 数据源对比

| 特性 | XML 解析 | Python API |
|------|----------|------------|
| **运行环境** | 任意 Python 环境 | RenderDoc Python Shell 或配置好的环境 |
| **依赖** | 无外部依赖 | 需要 `renderdoc.pyd` 模块 |
| **数据来源** | 从 API 调用推断 | 实时查询 GPU 状态 |
| **准确性** | 可能不完整 | 100% 准确 |
| **Shader 信息** | 仅有 ResourceId | 完整反射数据 (CB 成员、输入输出) |
| **CB 绑定** | ⚠️ 需额外 --bindings | ✅ 包含 members |
| **顶点布局** | ❌ 需额外解析 | ✅ 完整 InputLayout |
| **渲染目标** | ⚠️ 推断 | ✅ 精确 |
| **深度/混合状态** | ⚠️ 部分 | ✅ 完整 |

## 使用方法

### 方法 1: 仅使用 XML（默认）

```bash
# 导出 XML
renderdoccmd convert --input capture.rdc --output capture.xml

# 解析并生成报告
py -3 parse_rdc_xml.py capture.xml capture_data.json
py -3 generate_real_report.py capture_data.json report.html
```

### 方法 2: 使用 Python API 增强数据

#### 步骤 1: 在 RenderDoc Python Shell 中运行 extract_pipeline_state.py

```python
# 在 RenderDoc UI 的 Python Shell 中执行:
exec(open(r"D:\Code\git\renderdoc\scripts\rdc_analyzer\extract_pipeline_state.py").read())

# 或使用 qrenderdoc 的 Python 命令行:
# 需要 RenderDoc 构建中包含 Python 支持
```

#### 步骤 2: 生成报告时指定 --pipeline-json

```bash
py -3 generate_real_report.py capture_data.json report.html \
    --pipeline-json pipeline_state.json
```

## 优先级规则

当同时提供多个数据源时，合并优先级为：

```
Python API (--pipeline-json) > renderdoccmd bindings (--bindings) > XML 解析
```

事件中的 `pipelineState.dataSource` 字段会标记数据来源：
- `"python_api"` - 来自 Python API
- `undefined` - 来自 XML 解析

## extract_pipeline_state.py 输出格式

```json
{
  "capture_file": "capture.rdc",
  "events": [
    {
      "eventId": 101,
      "name": "DrawIndexed(3600, 0, 0)",
      "shaders": {
        "VS": {
          "resourceId": "123",
          "name": "Vertex Shader",
          "entryPoint": "main",
          "debugInfo": {...}
        },
        "PS": {...}
      },
      "viewport": {
        "x": 0.0, "y": 0.0,
        "width": 1920.0, "height": 1080.0,
        "minDepth": 0.0, "maxDepth": 1.0
      },
      "blendState": {
        "enabled": true,
        "colorBlend": {...},
        "alphaBlend": {...}
      },
      "depthState": {
        "testEnabled": true,
        "writeEnabled": true,
        "compareFunc": "Less"
      },
      "meshData": {
        "topology": "TriangleList",
        "vertexBuffers": [...],
        "indexBuffer": {...}
      },
      "bindings": {
        "VS": {
          "constantBuffers": [
            {
              "slot": 0,
              "resourceId": "456",
              "name": "cbPerObject",
              "size": 256,
              "members": [
                {"name": "WorldViewProj", "type": "float4x4", "offset": 0}
              ]
            }
          ]
        }
      }
    }
  ]
}
```

## 常见问题

### Q: 为什么需要两种数据源？

**A:** XML 解析可以在任何环境中运行，无需 RenderDoc 依赖。但它只能从 API 调用记录中推断状态，可能丢失某些信息。Python API 可以直接查询 GPU 实际状态，但需要在 RenderDoc 环境中运行。

### Q: 如何判断报告中的数据来源？

**A:** 查看事件的 `pipelineState.dataSource` 字段：
- 如果是 `"python_api"`，则来自 Python API
- 如果不存在该字段，则来自 XML 解析

### Q: Python API 需要 GPU 吗？

**A:** 是的，RenderDoc 需要 replay 捕获以查询 Pipeline State。这意味着需要与捕获时兼容的 GPU 或驱动程序。

## 相关文件

- `extract_pipeline_state.py` - Python API 提取脚本
- `parse_rdc_xml.py` - XML 解析脚本
- `generate_real_report.py` - 报告生成器（支持合并多数据源）
