# FBX Export Pipeline (OBJ Intermediate)

> 目标：从 `intermediate/` 输出 OBJ+MTL，并生成 Unity/Unreal 的 FBX 导入配套数据（含 Shader 导入计划）。

## 1. 使用方式

```bash
# 基础导出（自动发现 spirv-cross / fxc / dxc）
py -3 scripts/rdc_analyzer/export_fbx_assets.py \
  --intermediate <path_to_intermediate> \
  --out <out_dir> \
  --event <event_id>

# 显式指定工具路径（推荐用于 CI）
py -3 scripts/rdc_analyzer/export_fbx_assets.py \
  --intermediate <path_to_intermediate> \
  --out <out_dir> \
  --event <event_id> \
  --spirv-cross "C:\\Program Files\\RenderDoc\\plugins\\spirv\\spirv-cross.exe" \
  --fxc "C:\\Program Files (x86)\\Windows Kits\\10\\bin\\10.0.22621.0\\x64\\fxc.exe" \
  --dxc "C:\\Program Files (x86)\\Windows Kits\\10\\bin\\10.0.22621.0\\x64\\dxc.exe"
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
      shaders/*.hlsl.asm.txt
    unreal/
      mesh.fbx
      shader_import_plan.json
      shaders/*.usf
      shaders/*.usf.asm.txt
  stats.json
```

说明：
- `shader_import_plan.json` 包含每个 stage 的来源、转换策略、输出文件、执行状态。
- DXBC/DXIL 分支会额外产出 `*.asm.txt`（dumpbin 原始文本）。
- 当 FBX 后端不可用且 `RDC_FBX_ALLOW_MISSING=1` 时，仍会生成 OBJ + shader plan。

## 3. Shader 转换策略

按 `intermediate/shaders/*.json` 的 `source_kind` / `bytecode_format` 分流：

- `vulkan_shader_module` / `vulkan_shader_object` / `bytecode_format=spirv` → `spirv_to_hlsl`（`spirv-cross`）
- `d3d11_shader_bytecode` / `bytecode_format=dxbc|dxil` → `dxbc_to_hlsl`（`fxc/dxc dumpbin` + HLSL scaffold）
- 其他来源 → `manual_review`

### 3.1 DXBC/DXIL 说明

DXBC/DXIL 字节码无法无损恢复“原始手写 HLSL”。当前实现是：
1. 使用 `fxc /dumpbin`（DXBC 优先）或 `dxc -dumpbin`（DXIL）提取反汇编；
2. 根据声明信息（cbuffer/texture/sampler/input/output）生成结构化 HLSL 骨架；
3. 将 dumpbin 文本写入 sidecar，供人工或后续工具链继续精修。

`shader_import_plan.json` 常见状态：
- `converted`（SPIR-V → HLSL 成功）
- `reconstructed_hlsl`（DXBC/DXIL 生成了 HLSL scaffold）
- `missing_source`
- `missing_spirv_cross`
- `missing_dxbc_tool`
- `spirv_cross_failed`
- `dxbc_tool_failed`
- `manual_review`

## 4. 工具路径解析优先级

### 4.1 spirv-cross

1. `--spirv-cross`
2. 环境变量 `SPIRV_CROSS` / `SPIRV_CROSS_PATH`
3. `PATH` 中的 `spirv-cross` / `spirv-cross.exe`
4. Windows 常见路径：
   - `<repo>/dist/Release64/plugins/spirv/spirv-cross.exe`
   - `<repo>/dist/Release32/plugins/spirv/spirv-cross.exe`
   - `C:\Program Files\RenderDoc\plugins\spirv\spirv-cross.exe`
5. Everything CLI (`es.exe`) best-effort 搜索

### 4.2 fxc / dxc

1. `--fxc` / `--dxc`
2. 环境变量 `RDC_FXC` / `RDC_DXC`（兼容 `FXC_PATH` / `DXC_PATH`）
3. `PATH` 中 `fxc(.exe)` / `dxc(.exe)`
4. Windows SDK 自动探测（`Windows Kits/10/bin/<version>/<arch>/`）

## 5. 环境变量

- `FBX_SDK_ROOT`：FBX SDK 根路径（默认路径约定）
- `FBX_CLI_PATH`：可选，若使用独立 CLI 转换器
- `RDC_FBX_ALLOW_MISSING=1`：无 FBX 后端时继续产出 OBJ + plan
- `RDC_FXC` / `RDC_DXC`：显式指定 DXBC/DXIL dumpbin 工具

## 6. 坐标系与单位

- Unity：Y-up + meter
- Unreal：Z-up + centimeter

## 7. 注意事项

- 当前仍是单事件导出。
- 法线/切线缺失时建议由引擎重建。
- 纹理默认输出 RGBA8 PNG。
- DXBC/DXIL 产物是“可组装的 HLSL 骨架 + dumpbin sidecar”，不是原始源码级反编译结果。
