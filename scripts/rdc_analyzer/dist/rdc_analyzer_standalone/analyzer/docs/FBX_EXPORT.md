# FBX Export Pipeline (OBJ Intermediate)

> 目标：从 `intermediate/` 输出 OBJ+MTL，再转换为 Unity/Unreal 专用 FBX 2020.2。

## 1. 使用方式
```bash
py -3 export_fbx_assets.py --intermediate <path_to_intermediate> --out <out_dir> --event <event_id>
```

## 2. 输出结构
```
<out>/event_<id>/
  obj/
    mesh.obj
    mesh.mtl
    textures/tex_<id>.png
  fbx/
    unity/mesh.fbx
    unreal/mesh.fbx
  stats.json
```

## 3. 中间态输入
- `intermediate/mesh/mesh.json` + `vertex.bin` + `index.bin`
- `intermediate/materials/material.json` (textures 列表包含 width/height/format)

## 4. 环境变量
- `FBX_SDK_ROOT`：FBX SDK 根路径（默认路径约定）
- `FBX_CLI_PATH`：可选，若使用独立 CLI 转换器
- `RDC_FBX_ALLOW_MISSING=1`：允许在无 SDK 时跳过 FBX 转换（用于测试）

## 5. 坐标系与单位
- Unity：Y-up + meter
- Unreal：Z-up + centimeter

## 6. 注意事项
- 当前仅支持单事件导出
- 法线/切线缺失时由引擎计算
- 纹理默认输出 RGBA8 PNG
