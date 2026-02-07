# ZIPXML Event 离线导出指南（Vulkan + D3D11）

> 目标：在**不依赖 GPU 回放**的情况下，从 `capture.zip.xml + capture.zip` 针对单个 `event_id` 导出可用于后续转换的中间态（mesh/material/shader 占位 + manifest）。

---

## 1. 适用范围

当前实现支持：
- API：Vulkan、D3D11
- 事件：`vkCmdDrawIndexed`（Vulkan）与 `ID3D11DeviceContext::DrawIndexed`（D3D11）（单 event）
- 输入：`renderdoccmd convert -c zip.xml` 生成的 `.zip.xml` 与 `.zip`

---

## 2. 数据来源（证据链）

离线导出按 API 分流，使用以下链路拼接数据：

### Vulkan

1. **事件绑定信息（IB/VB + Draw 参数）**
   - 来自 `vkCmdBindIndexBuffer` / `vkCmdBindVertexBuffers` / `vkCmdDrawIndexed`
   - 解析结果：
     - index buffer `resource_id`、`byte_offset`、`index_format`
     - vertex buffer `resource_id`、`byte_offset`
     - draw `indexCount/firstIndex/vertexOffset`

2. **Buffer -> DeviceMemory 映射**
   - 来自 `vkBindBufferMemory`
   - 解析结果：`buffer resource_id -> (memory_id, memoryOffset)`

3. **DeviceMemory -> ZIP 条目映射**
   - 来自 `Internal::Initial Contents`（`type = eResDeviceMemory`）
   - 解析结果：`memory_id -> (buffer_index, ContentsSize)`

4. **ZIP 数据读取**
   - 按 `buffer_index` 解析 ZIP entry（优先顺序）：
     - `000123`
     - `buffers/buffer123`
     - `buffer123`

5. **字节切片**

### D3D11

1. **事件绑定信息（IB/VB + Draw 参数）**
   - 来自 `ID3D11DeviceContext::IASetVertexBuffers` / `ID3D11DeviceContext::IASetIndexBuffer` / `ID3D11DeviceContext::DrawIndexed`
   - 解析结果：
     - index buffer `resource_id`、`byte_offset`、`index_format`
     - vertex buffer `resource_id`、`byte_offset`、`stride`
     - draw `IndexCount/StartIndexLocation/BaseVertexLocation`

2. **Buffer -> ZIP 条目映射**
   - 优先来源：`ID3D11Device::CreateBuffer` 的 `InitialData`
   - 更新来源：`ID3D11DeviceContext::Unmap` 的 `MapWrittenData`（在目标 event 之前的最后一次写入优先生效）
   - 解析结果：`resource_id -> buffer_index`

3. **ZIP 数据读取 + 切片**
   - 按 `buffer_index` 解析 ZIP entry（`000123` / `buffers/buffer123` / `buffer123`）
   - `index.bin` 按 `StartIndexLocation + IndexCount` 切片
   - `vertex.bin` 优先用 IA stride 与索引范围估算切片
   - `index.bin`：按 `index_format + firstIndex + indexCount` 精确切片
   - `vertex.bin`：优先以 `vb_start -> ib_start` 或 `vkCreateBuffer.size` 估算切片范围

---

## 3. 命令行用法

```bash
py -3 scripts/rdc_analyzer/extract_event_intermediate.py \
  --xml "D:\\backup\\capture_export.zip.xml" \
  --zip "D:\\backup\\capture_export.zip" \
  --event 23300 \
  --out "D:\\backup\\event_extract_out"
```

可选参数：
- `--vertex-stride <int>`：手工指定顶点步长（不传则使用启发式推断，`layout_source=heuristic`）

---

## 4. 输出目录

```text
<out>/
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
      textures/
```

`mesh.json` 中包含：
- `schema_version`
- `schema_path`
- `mesh.axis/unit_scale/topology`
- `mesh.vertex_layout/index_format/vertex_count/index_count`

`manifest.json` 中包含：
- 源文件路径（`sources.zip_xml / sources.zip_bin`）
- IB/VB 映射与落盘信息（resource/memory/zip_entry/byte_size）
- `texture_decode`（与现有 texture 写盘流程兼容）

---

## 5. 结构校验（.schema.json）

新增 schema：
- `scripts/rdc_analyzer/schema/intermediate_mesh.schema.json`
- `scripts/rdc_analyzer/schema/intermediate_material.schema.json`
- `scripts/rdc_analyzer/schema/intermediate_shader.schema.json`
- `scripts/rdc_analyzer/schema/intermediate_manifest.schema.json`

运行时会自动校验：
- `mesh.json`
- `material.json`
- `manifest.json`
- `shaders/*.json`（若存在）

---

## 6. 与后续 FBX 管线关系

- 当前导出的是**中间态**（offline 可得）
- 可接 `export_fbx_assets.py` 进入 OBJ/FBX 管线
- 若启发式 stride/layout 不准确，建议在引擎侧或后处理阶段修正顶点布局

---

## 7. 已知限制

1. 当前只覆盖 DrawIndexed 路径（Vulkan/D3D11）
2. 顶点布局无法完全从离线数据可靠恢复，`vertex_layout` 可能依赖启发式
3. shader/material 的完整语义映射仍需结合更多 chunk 与引擎规则

---

## 8. 回归测试

```bash
py -3 -m pytest scripts/rdc_analyzer/tests/test_zipxml_event_parser.py \
  scripts/rdc_analyzer/tests/test_zipxml_event_resources.py \
  scripts/rdc_analyzer/tests/test_extract_event_intermediate.py \
  scripts/rdc_analyzer/tests/test_intermediate_schemas.py -v --tb=short
```

预期：全部通过。
