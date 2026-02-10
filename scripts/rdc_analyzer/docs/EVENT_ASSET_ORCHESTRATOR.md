# Event Asset Orchestrator（M1）

> 目标：把单 Event 的资产导出流程串成“一条命令”：`intermediate -> import_bundle -> fbx`，并生成 `artifact_index.json` 作为统一入口。

---

## 1. 脚本位置

- `scripts/rdc_analyzer/event_asset_orchestrator.py`
- schema：`scripts/rdc_analyzer/schema/artifact_index.schema.json`

---

## 2. 使用方式

### 2.1 输入为已有 intermediate（推荐离线复用）

```bash
py -3 scripts/rdc_analyzer/event_asset_orchestrator.py \
  --intermediate "D:/backup/out/event_22149/intermediate" \
  --event 22149 \
  --out "D:/backup/orchestrator_out" \
  --allow-missing-fbx-backend
```

### 2.2 输入为 zip.xml + zip（一步式）

```bash
py -3 scripts/rdc_analyzer/event_asset_orchestrator.py \
  --xml "D:/backup/capture_export.zip.xml" \
  --zip "D:/backup/capture_export.zip" \
  --event 22149 \
  --out "D:/backup/orchestrator_out" \
  --allow-missing-fbx-backend
```

### 2.3 可选参数

- `--texture-mode auto|decoded|raw`
- `--raw-source-kinds "vulkan_device_memory_raw,..."`
- `--rgba-manifest <path>`
- `--spirv-cross <path>`
- `--fxc <path>`
- `--dxc <path>`

---

## 3. 输出结构

```text
<out>/event_<id>/
  import_bundle/
    bundle_manifest.json
    mesh/mesh.obj
    materials/materials.json
    textures/*
    shaders/*
  fbx/
    unity/shader_import_plan.json
    unreal/shader_import_plan.json
    unity/mesh.fbx           # 若后端可用
    unreal/mesh.fbx          # 若后端可用
  stats.json
  artifact_index.json
```

---

## 4. artifact_index.json 作用

- 统一记录：输入来源、阶段状态、关键输出路径、状态统计（shader/texture）、统计信息。
- 供后续导入器（Unity/Unreal/Messiah）或自动化流程直接消费。
- 结构由 `artifact_index.schema.json` 强校验，不合法即失败。

---

## 5. 阶段状态说明

- `extract_intermediate`
  - `ok`：由 `xml+zip` 新生成 intermediate
  - `reused`：直接复用现有 intermediate
- `export_import_bundle`
  - `ok`
- `export_fbx_assets`
  - `ok`：已生成 Unity/Unreal `.fbx`
  - `degraded_missing_fbx_backend`：缺 FBX 后端但保留 import_bundle + shader_plan

---

## 6. 注意事项

1. 当前优先支持 Vulkan / D3D11（与现有 offline intermediate 提取能力一致）。
2. `--allow-missing-fbx-backend` 建议在 CI 或无 FBX SDK 环境开启。
3. 真实引擎导入仍需人工做材质语义复核（本脚本保证结构与可追溯性，不保证审美结果）。
