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

### 2.2 一步式（zip.xml + zip -> intermediate -> import bundle）

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

如果结构不合法会直接抛错，避免把坏数据传入后续引擎转换步骤。

---

## 5. 与 FBX/Messiah 的关系

- 本导出是“中间资产包”步骤，主要解决单 Event 资源闭环。
- 后续可继续走：
  1) `export_fbx_assets.py`（Unity/Unreal FBX）
  2) `export_messiah_assets.py`（Messiah Repository）

---

## 6. 常见问题

1. **纹理为什么是 `.bin` 不是 `.png`？**
   - 原因：缺少 `width/height/format` 或格式暂不支持。
   - 行为：工具会回退到 `raw_copy`，状态写入 `materials.json`。

2. **Shader 为什么只有 json/bin 没有 hlsl？**
   - 当前保留“中间态”原始信息，HLSL 反编译属于下一阶段（可接现有 shader 转换链路）。

3. **没有 `--event` 可以吗？**
   - 传 `--intermediate` 时可省略，工具会尝试从 `event_<id>` 路径自动推断。
