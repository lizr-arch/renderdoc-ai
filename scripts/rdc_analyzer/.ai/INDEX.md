# RDC Analyzer 项目索引

> **最后更新**: 2025-01-19 | **版本**: 1.1.0
>
> ⚠️ **AI 必读**: 每次会话开始时必须阅读此文件和 `TASK_INDEX.md`

---

## 1. 项目概述

**一句话描述**: 从 RenderDoc `.rdc` 捕获文件生成离线 HTML 分析报告，支持 D3D11/D3D12/Vulkan/OpenGL，包含纹理、事件、Pipeline、Mesh 数据。

**目标用户**: 游戏开发者、图形程序员、性能优化工程师

**核心价值**: 无需 RenderDoc GUI，即可在浏览器中分析帧捕获数据

---

## 2. 目录结构

```
scripts/rdc_analyzer/
├── .ai/                          # AI 协同开发专用目录
│   ├── INDEX.md                  # 📍 你正在阅读的文件
│   ├── TASKS.md                  # 任务看板
│   ├── CONVENTIONS.md            # 开发规范
│   ├── CHANGELOG.md              # 变更日志
│   └── locks/                    # 任务锁文件
│
├── parse_rdc_xml.py              # XML 解析器 (核心)
├── generate_real_report.py       # 报告数据整合
├── generate_offline_report.py    # HTML 生成器 (9000+ 行)
├── test_e2e_real_data.py         # 端到端测试
├── extract_pipeline_state.py     # Pipeline 提取 (RenderDoc Python API)
│
├── output/                       # 生成的报告输出目录
└── test_captures/                # 测试用 RDC 文件
```

---

## 3. 模块速查表

| 模块 | 入口文件 | 职责 | 状态 |
|------|----------|------|------|
| **CLI 纹理导出** | `renderdoccmd export` | 从 RDC 导出 PNG + JSON | ✅ 完成 |
| **XML 解析** | `parse_rdc_xml.py` | 提取事件/DrawCall/状态 | ✅ 完成 |
| **报告整合** | `generate_real_report.py` | 整合纹理+事件数据 | ✅ 完成 |
| **HTML 生成** | `generate_offline_report.py` | 生成单文件 HTML | ✅ 完成 |
| **E2E 测试** | `test_e2e_real_data.py` | 端到端验证 | ✅ 完成 |
| **Pipeline 提取** | `extract_pipeline_state.py` | 提取渲染状态 | 🔧 待集成 |

---

## 4. 数据流

```
┌─────────────┐
│  .rdc 文件   │
└──────┬──────┘
       │
       ├─────────────────────────────────────────┐
       │                                         │
       ▼                                         ▼
┌──────────────────┐                   ┌──────────────────┐
│ renderdoccmd     │                   │ renderdoccmd     │
│ export -f png    │                   │ convert -c xml   │
└────────┬─────────┘                   └────────┬─────────┘
         │                                      │
         ▼                                      ▼
┌──────────────────┐                   ┌──────────────────┐
│ textures/*.png   │                   │ capture.xml      │
│ textures.json    │                   │ (4-50 MB)        │
└────────┬─────────┘                   └────────┬─────────┘
         │                                      │
         │                                      ▼
         │                             ┌──────────────────┐
         │                             │ parse_rdc_xml.py │
         │                             └────────┬─────────┘
         │                                      │
         │                                      ▼
         │                             ┌──────────────────┐
         │                             │ capture_data.json│
         │                             └────────┬─────────┘
         │                                      │
         └──────────────┬───────────────────────┘
                        │
                        ▼
              ┌──────────────────────┐
              │ generate_real_report │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ generate_offline_    │
              │ report.py            │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ report.html          │
              │ (100-300 MB)         │
              └──────────────────────┘
```

---

## 5. 关键数据结构

### 5.1 Event (事件对象)

```json
{
  "eid": 10,
  "name": "DrawIndexed",
  "type": "draw",
  "flags": ["indexed"],
  "apiCall": {
    "signature": "ID3D11DeviceContext::DrawIndexed",
    "params": [
      {"name": "IndexCount", "value": "420", "type": "uint32_t"}
    ],
    "relatedCalls": [
      "ID3D11DeviceContext::VSSetShader(pShader: 2582319)",
      "ID3D11DeviceContext::IASetVertexBuffers(...)"
    ]
  },
  "pipelineState": { ... },  // 🔧 待实现
  "meshData": { ... }        // 🔧 待实现
}
```

### 5.2 Texture (纹理对象)

```json
{
  "id": "tex_001",
  "name": "Albedo_Diffuse",
  "width": 2048,
  "height": 2048,
  "format": "BC7_UNORM",
  "mipLevels": 11,
  "thumbnail": "data:image/png;base64,..."
}
```

### 5.3 Pass (渲染 Pass)

```json
{
  "id": "pass_0",
  "name": "GBuffer",
  "eventStart": 10,
  "eventEnd": 150,
  "drawCount": 45,
  "outputs": ["RT0", "RT1", "Depth"]
}
```

---

## 6. 支持的图形 API

| API | Draw Call 前缀 | 状态设置前缀 | 测试状态 |
|-----|---------------|-------------|---------|
| **D3D11** | `ID3D11DeviceContext::Draw*` | `ID3D11DeviceContext::*Set*` | ✅ 已测试 |
| **D3D12** | `ID3D12GraphicsCommandList::Draw*` | `ID3D12GraphicsCommandList::Set*` | ⚠️ 待测试 |
| **Vulkan** | `vkCmdDraw*` | `vkCmdBind*`, `vkCmdSet*` | ✅ 已测试 |
| **OpenGL** | `glDraw*` | `glBind*`, `glUniform*` | ⚠️ 待测试 |

---

## 7. 快速命令

### 生成报告 (完整流程)
```bash
cd scripts/rdc_analyzer
py -3 test_e2e_real_data.py "path/to/capture.rdc" output/my_report
```

### 仅解析 XML
```bash
py -3 parse_rdc_xml.py capture.xml capture_data.json
```

### 仅生成 HTML
```bash
py -3 generate_real_report.py capture_data.json textures/ report.html
```

---

## 8. 相关文档

| 文档 | 路径 | 说明 |
|------|------|------|
| **入职引导** | `.ai/ONBOARDING.md` | 🆕 新 AI 快速入门模板 |
| 任务总索引 | `.ai/TASK_INDEX.md` | 任务入口，查找每日任务 |
| 今日任务 | `.ai/tasks/YYYY-MM-DD.md` | 当天任务看板 |
| 开发规范 | `.ai/CONVENTIONS.md` | 代码和协作规则 |
| 变更日志 | `.ai/CHANGELOG.md` | 历史变更记录 |
| 项目规范 | `../../Agents.md` | RenderDoc 项目级规范 |

---

## 9. 常见问题

### Q: 报告中纹理显示为空？
**A**: 检查 `renderdoccmd export` 是否成功。移动端 RDC 在 PC 上可能无法导出纹理（硬件不兼容）。

### Q: Event Browser 显示空白？
**A**: 检查 JSON 字段名是否正确：`eid`（不是 `eventId`），`frameDuration`（不是 `frameDurationMs`）。

### Q: 如何添加新的图形 API 支持？
**A**: 修改 `parse_rdc_xml.py` 中的 `draw_call_names` 和 `binding_calls` 列表。
