# Event Import Bundle 导出指南（单 Event）

> 目标：把 `intermediate/` 直接整理成可导入资源包，输出 `mesh.obj + materials.json + shaders + textures + bundle_manifest.json`。

---

## 1. 支持范围

- 输入：`extract_event_intermediate.py` 生成的 `event_<id>/intermediate/`
- API：与中间态一致（当前优先 Vulkan / D3D11）
- 输出纹理：优先解码到 RGBA8 PNG；失败时回退为原始 `.bin`；若源 payload 为空则标记 `missing_source`

---

## 2. 快速使用

### 2.1 从已有 intermediate 导出

```bash
py -3 scripts/rdc_analyzer/export_event_import_bundle.py \
  --intermediate "D:\\backup\\out\\event_100\\intermediate" \
  --event 100 \
  --out "D:\\backup\\import_bundle_out"
```

### 2.2 外部 RGBA bytes 覆盖（可选）

当离线中间态里的 `textures/tex_*.bin` 为空，且你已经有自己的纹理解码器产出的 RGBA bytes 时，
可以通过 `--rgba-manifest` 注入，直接导出 PNG：

```bash
py -3 scripts/rdc_analyzer/export_event_import_bundle.py \
  --intermediate "D:\\backup\\out\\event_100\\intermediate" \
  --event 100 \
  --out "D:\\backup\\import_bundle_out" \
  --rgba-manifest "D:\\backup\\rgba_manifest.json"
```

`rgba_manifest.json` 示例：

```json
{
  "textures": [
    {
      "texture_id": 7,
      "slot": "set3.binding4",
      "rgba_path": "tex_7.rgba",
      "width": 128,
      "height": 192,
      "row_pitch": 0
    }
  ]
}
```

说明：
- `texture_id` 与 `slot` 用于匹配 `materials/material.json` 中的纹理条目。
- `rgba_path` 可用绝对路径，也可用相对路径（优先相对 manifest 所在目录解析）。
- `row_pitch` 可选；若存在行对齐 padding，会按每行 `width*4` 自动裁切。

### 2.3 固定目录自动发现（无需命令行参数）

如果未传 `--rgba-manifest`，工具会自动尝试以下路径：

1. `event_<id>/rgba/rgba_manifest.json`（推荐）
2. `event_<id>/rgba_manifest.json`
3. `intermediate/rgba_manifest.json`
4. `intermediate/textures/rgba_manifest.json`

另外，如果上述 manifest 都不存在，工具还会尝试直接读取：
- `event_<id>/rgba/tex_<texture_id>.rgba`
- `intermediate/textures/tex_<texture_id>.rgba`

> 直接文件模式下，宽高来自 `material.textures[]` 的 `width/height` 字段。



### 2.5 批处理导出（多个 event）

当你已经有一批 `event_<id>/intermediate/` 时，可一次性批量导出：

```bash
py -3 scripts/rdc_analyzer/export_event_import_bundle_batch.py   --root "D:\backup\out_new4"   --out "D:\backup\import_bundle_batch_out"
```

可选参数：
- `--events "22149,22150"`：只导出指定 event。
- `--rgba-manifest <path>`：给所有 event 使用同一个 RGBA manifest。
- `--fail-fast`：遇到第一个失败就停止。
- `--from-summary <summary.json>`：从上一次 summary 里的失败列表自动重跑（可叠加 `--out` 指定新输出目录）。

输出：
- 每个 event 仍输出 `event_<id>/import_bundle/`。
- `batch_import_bundle_summary.json`：统计成功/失败、`failed_event_ids`、`retry_command`。
- 失败时自动生成：
  - `batch_import_bundle_failed_events.txt`
  - `batch_import_bundle_retry_command.txt`

重跑示例：

```bash
py -3 scripts/rdc_analyzer/export_event_import_bundle_batch.py   --from-summary "D:\backup\import_bundle_batch_out\batch_import_bundle_summary.json"   --out "D:\backup\import_bundle_batch_retry"
```

### 2.4 一步式（zip.xml + zip -> intermediate -> import bundle）

```bash
py -3 scripts/rdc_analyzer/export_event_import_bundle.py \
  --xml "D:\\backup\\capture_export.zip.xml" \
  --zip "D:\\backup\\capture_export.zip" \
  --event 100 \
  --out "D:\\backup\\import_bundle_out"
```

---

## 3. 输出目录

```text
<out>/event_<id>/
  obj/
    mesh.obj
    mesh.mtl
  import_bundle/
    bundle_manifest.json
    mesh/
      mesh.obj
      mesh.mtl
    materials/
      materials.json
    shaders/
      *.json
      *.bin
    textures/
      *.png or *.bin
```

说明：
- `obj/` 是复用已有 OBJ 导出链路的产物。
- `import_bundle/` 是给后续引擎导入器消费的主目录。

---

## 4. 结构校验（Schema）

导出时会自动校验：
- `schema/import_bundle_manifest.schema.json`
- `schema/import_bundle_materials.schema.json`
- `schema/batch_import_bundle_summary.schema.json`（批处理 summary）

如果结构不合法会直接抛错，避免把坏数据传入后续引擎转换步骤。

---

## 5. 与 FBX/Messiah 的关系

- 本导出是“中间资产包”步骤，主要解决单 Event 资源闭环。
- 后续可继续走：
  1) `export_fbx_assets.py`（Unity/Unreal FBX）
  2) `export_messiah_assets.py`（Messiah Repository）

---

## 6. 常见问题

1. **纹理为什么是 `missing_source`？**
   - 原因：中间态存在纹理绑定，但当前没有可用像素 payload（常见于离线 Vulkan）。
   - 处理：提供 `--rgba-manifest`，或按固定目录放置 `tex_<texture_id>.rgba`。

2. **纹理状态有哪些？**
   - `rgba_bytes_png`：来自外部 RGBA bytes 覆盖。
   - `decoded_rgba8_png`：由工具从源格式解码。
   - `copied_image`：源文件本身是图片格式，直接拷贝。
   - `raw_copy`：无法解码，保留原始 `.bin`。
   - `missing_source`：找不到有效输入数据。

3. **Shader 为什么只有 json/bin 没有 hlsl？**
   - 当前保留“中间态”原始信息，HLSL 反编译属于下一阶段（可接现有 shader 转换链路）。

4. **没有 `--event` 可以吗？**
   - 传 `--intermediate` 时可省略，工具会尝试从 `event_<id>` 路径自动推断。
