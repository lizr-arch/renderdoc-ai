# FBX Export Pipeline (OBJ Intermediate)

> 目标：从 `intermediate/` 输出 OBJ+MTL，并生成 Unity/Unreal 的 FBX 导入配套数据（含 Shader 导入计划）。

## 1. 使用方式

```bash
# 基础导出（会自动尝试发现 spirv-cross）
py -3 scripts/rdc_analyzer/export_fbx_assets.py \
  --intermediate <path_to_intermediate> \
  --out <out_dir> \
  --event <event_id>

# 显式指定 spirv-cross 路径（推荐用于 CI）
py -3 scripts/rdc_analyzer/export_fbx_assets.py \
  --intermediate <path_to_intermediate> \
  --out <out_dir> \
  --event <event_id> \
  --spirv-cross "C:\\Program Files\\RenderDoc\\plugins\\spirv\\spirv-cross.exe"
```

## 2. 输出结构

```text
<out>/event_<id>/
  obj/
    mesh.obj
    mesh.mtl
    textures/tex_<id>.png
  fbx/
    unity/
      mesh.fbx
      shader_import_plan.json
      shaders/*.hlsl
    unreal/
      mesh.fbx
      shader_import_plan.json
      shaders/*.usf
  stats.json
```

说明：
- `shader_import_plan.json` 包含每个 stage 的来源、转换策略、输出文件与执行状态。
- 当 FBX 后端不可用且 `RDC_FBX_ALLOW_MISSING=1` 时，仍会生成 OBJ + shader plan（便于离线验证）。

## 3. Shader 转换策略

按 `intermediate/shaders/*.json` 的 `source_kind` / `bytecode_format` 分流：

- `vulkan_shader_module` / `vulkan_shader_object` / `bytecode_format=spirv` → `spirv_to_hlsl`（工具：`spirv-cross`）
- `d3d11_shader_bytecode` / `bytecode_format=dxbc|dxil` → `dxbc_to_hlsl`（当前为占位适配器）
- 其他来源 → `manual_review`

`shader_import_plan.json` 中常见状态：
- `converted`
- `missing_source`
- `missing_spirv_cross`
- `spirv_cross_failed`
- `stubbed_dxbc`
- `manual_review`

## 4. spirv-cross 路径解析优先级

`resolve_spirv_cross_path` 采用以下顺序：

1. `--spirv-cross`
2. 环境变量 `SPIRV_CROSS` / `SPIRV_CROSS_PATH`
3. `PATH` 中的 `spirv-cross` / `spirv-cross.exe`
4. Windows 常见路径：
   - `<repo>/dist/Release64/plugins/spirv/spirv-cross.exe`
   - `<repo>/dist/Release32/plugins/spirv/spirv-cross.exe`
   - `C:\Program Files\RenderDoc\plugins\spirv\spirv-cross.exe`
5. Everything CLI (`es.exe`) 快速搜索（best-effort）

## 5. 环境变量

- `FBX_SDK_ROOT`：FBX SDK 根路径（默认路径约定）
- `FBX_CLI_PATH`：可选，若使用独立 CLI 转换器
- `RDC_FBX_ALLOW_MISSING=1`：无 FBX 后端时继续产出 OBJ + plan

## 6. 坐标系与单位

- Unity：Y-up + meter
- Unreal：Z-up + centimeter

## 7. 注意事项

- 当前仍是单事件导出。
- 法线/切线缺失时建议由引擎重建。
- 纹理默认输出 RGBA8 PNG。
- DXBC/DXIL→HLSL 目前保留占位输出，后续可接入真实工具链。
