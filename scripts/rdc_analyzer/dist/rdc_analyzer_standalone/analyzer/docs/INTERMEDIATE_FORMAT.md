# XML/ZIP Intermediate Format (Single Event)

> **目标**：从 `zip.xml + zip` 提取单个 Event 的 Mesh/Material/Shader/Texture 中间态，作为 Unity/Unreal/Messiah 的转换输入。

---

## 1. 输入与前置条件

- 输入来自 `renderdoccmd convert -c zip.xml`：
  - `capture.zip.xml`：结构化状态与绑定信息
  - `capture.zip`：二进制资源数据
- 当前阶段：**单 EventId** 输出，优先 Vulkan + D3D11。

---

## 2. 输出目录结构（建议）

```
<out>/
  capture_<name>/
    event_<id>/
      manifest.json
      intermediate/
        mesh/
          mesh.json
          vertex.bin
          index.bin
        materials/
          material.json
        shaders/
          vs.json
          vs.bin
          ps.json
          ps.bin
        textures/
          tex_<id>.bin
      logs/
        extractor.log
```

---

## 3. manifest.json（出口清单）

用于记录来源与写入目录，便于追溯：

```json
{
  "schema_version": "1.0",
  "schema_path": "schema/mesh_shader_manifest.schema.json",
  "rdc_path": "capture.rdc",
  "event_id": 100,
  "api": "Vulkan",
  "outputs": {
    "vertex_buffers": "vertex_buffers/",
    "index_buffers": "index_buffers/",
    "shaders": "shaders/"
  },
  "data_provenance": {
    "pipeline_state": "ReplayController.GetPipelineState()",
    "buffers": "ReplayController.GetBufferData(resourceId, offset, len)",
    "shader_disassembly": "ReplayController.DisassembleShader(...)"
  },
  "status": "ok"
}
```

---

## 4. Mesh（mesh.json + bin）

### 4.1 mesh.json（示例）

```json
{
  "mesh": {
    "axis": "unknown",
    "unit_scale": 1.0,
    "topology": "triangle_list",
    "vertex_layout": [
      { "semantic": "POSITION", "format": "float3", "offset": 0, "stride": 32 }
    ],
    "index_format": "uint16",
    "vertex_count": 1234,
    "index_count": 5678
  }
}
```

### 4.2 vertex.bin / index.bin

- `vertex.bin`：按 `vertex_layout` 原始字节序列
- `index.bin`：按 `index_format` 原始索引

---

## 5. Material（material.json）

```json
{
  "material": {
    "name": "",
    "shader": "ps",
    "textures": [
      { "slot": "albedo", "texture_id": 42, "sampler": "s0" }
    ],
    "constants": [
      { "name": "_BaseColor", "type": "float4", "value": [1, 1, 1, 1] }
    ]
  }
}
```

---

## 6. Shader（vs.json / ps.json + bin）

```json
{
  "shader": {
    "stage": "vs",
    "bytecode_format": "spirv",
    "entry": "main",
    "disassembly": ""
  }
}
```

对应字节码写入 `vs.bin / ps.bin`。

---

## 7. Texture（tex_<id>.bin）

- 记录原始字节数据（或解码后 RGBA8 视实现）
- `material.textures` 中通过 `texture_id` 关联

---

## 8. Unity / Unreal / Messiah 转换建议

- **Unity**：优先转换到 FBX + ShaderLab + `.mat`；中间态保留 axis/unit 以便坐标系转换。
- **Unreal**：优先转换到 FBX/Interchange 输入；避免直接写 `.uasset`。
- **Messiah**：可映射为 `Repository/<name>.local/` 结构（Mesh/Texture/Material/Model 各自 `resource.xml + resource.data`）。

---

## 9. 约束与下一步

- 当前只保证单 EventId 的导出。
- D3D12 / GLES 需在 Vulkan + D3D11 稳定后补充。
- 后续可增加 JSON Schema 对中间态做结构校验。
