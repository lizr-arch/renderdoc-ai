# Mesh / Shader 导出指南（EventId）

> **状态**: 可用 | **适用**: D3D11 / Vulkan | **入口脚本**: `extract_mesh_shader.py`

本指南说明如何从 RDC 中导出 **VB/IB 原始字节** 与 **Shader 反汇编**，并解释数据来源链路。新人可直接按步骤操作。

---

## 1. 用途

- 导出**单个 draw event** 的顶点/索引数据（VB/IB）
- 导出该 event 的 shader 反汇编文本（按 stage）
- 生成 manifest 记录数据来源与输出路径

---

## 2. 依赖与前置条件

1) **RenderDoc Python API 可用**（`renderdoc` module）  
2) **可回放环境**（GPU 或软件回放）。否则会返回错误并在 manifest 中记录。
3) 已知目标 **eventId**（在 RenderDoc UI 的 Event Browser 中获取）

---

## 3. 命令示例

```bash
py -3 scripts/rdc_analyzer/extract_mesh_shader.py --rdc <capture.rdc> --event <eventId> --out <output_dir>
```

示例：

```bash
py -3 scripts/rdc_analyzer/extract_mesh_shader.py --rdc D:\backup\大远景.rdc --event 12345 --out D:\backup\mesh_out
```

---

## 4. 输出结构

```
<output_dir>/
  manifest.json
  vertex_buffers/
    vb_<resourceId>.bin
  index_buffers/
    ib_<resourceId>.bin
  shaders/
    vertex.asm
    fragment.asm
```

---

## 5. 数据来源链路（核心）

| 输出数据 | 来源 API/结构 | 说明 |
|---|---|---|
| VB/IB 绑定信息 | `ReplayController.GetPipelineState()` → `PipeState` → `D3D11Pipe/VKPipe` | 得到 resourceId/offset/stride |
| VB/IB 原始字节 | `ReplayController.GetBufferData(resourceId, offset, len)` | 按绑定信息读取 bytes |
| Shader 反汇编 | `ReplayController.DisassembleShader(...)` | 输出汇编文本 |

**说明**：所有数据都来自 **ReplayController**，因此必须能回放。

### 5.1 manifest.json 字段说明

```json
{
  "rdc_path": "capture.rdc",
  "event_id": 12345,
  "api": "D3D11",
  "status": "ok",
  "outputs": {
    "vertex_buffers": "vertex_buffers/",
    "index_buffers": "index_buffers/",
    "shaders": "shaders/"
  },
  "data_provenance": {
    "pipeline_state": "ReplayController.GetPipelineState()",
    "buffers": "ReplayController.GetBufferData(resourceId, offset, len)",
    "shader_disassembly": "ReplayController.DisassembleShader(...)"
  }
}
```

若回放失败，`status` 为 `error`，并包含 `error` 字段说明原因。

---

## 6. 常见问题

### Q1: 没有 GPU / 无法回放怎么办？
该脚本依赖 ReplayController，无法在完全无回放环境下导出 VB/IB 或 shader。  
如需离线数据，请参考 `NO_GPU_TEXTURE_EXTRACTION.md` 相关方案。

### Q2: 只有 .bin 文件，如何转换成 mesh？
`vb_*.bin` / `ib_*.bin` 是**原始字节**，需结合输入布局（顶点格式、stride）进行解析。  
建议在你的资产管线中统一做一次“格式映射 + 导出”。

### Q3: Shader 反汇编输出内容太低级怎么办？
这是 RenderDoc 的原生反汇编结果。后续可用 DXC/spirv-cross 等工具转为 HLSL/GLSL。
