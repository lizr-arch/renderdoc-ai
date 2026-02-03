# Unreal 导入需求（基于官方文档）

> 目标：明确 Unreal 导入 Static Mesh/Material/Texture 所需的最小数据，用于从中间态生成可导入资源。

## 1. 主要导入管线（FBX / Interchange）
Unreal 的传统 FBX 管线支持导入 Static Mesh，并要求 FBX 2020.2。也可使用 Interchange 管线导入 FBX、glTF/GLB、MaterialX 等格式。  
参考：https://dev.epicgames.com/documentation/en-us/unreal-engine/fbx-static-mesh-pipeline-in-unreal-engine
参考：https://dev.epicgames.com/documentation/en-us/unreal-engine/interchange-import-reference-in-unreal-engine

## 2. Static Mesh 最小数据要求
FBX Static Mesh 管线支持：  
- 多个 UV 集（Multiple UV sets）  
- 平滑组（Smoothing Groups）  
- 顶点色（Vertex Colors）  
- 多材质（Materials & Textures）  
- LODs  

因此最小建议数据为：  
- **Positions + Indices**（必需）  
- **Normals + Tangents**（建议；否则将由导入器计算）  
- **UV0**（必需；用于贴图采样）  
- **SubMesh/Section → Material**（一段网格对应一个材质槽）  

## 3. 法线/切线（Import vs Compute）
FBX Import 允许选择：导入法线/切线或由引擎计算（如 MikkTSpace）。导出时若提供切线，可提升与源一致性。  
参考：https://dev.epicgames.com/documentation/en-us/unreal-engine/fbx-import-options-reference-in-unreal-engine

## 4. 纹理格式（RGBA8 输出建议）
Unreal 支持常见贴图格式：PNG / TGA / EXR / BMP / JPG 等。建议输出 **PNG（RGBA8）** 或 **TGA（RGBA8）**，交由引擎做压缩与平台化。  
参考：https://dev.epicgames.com/documentation/en-us/unreal-engine/textures-in-unreal-engine

## 5. Material/Shader 最小要求（PBR 输入）
Unreal 材质使用 PBR 输入（Base Color / Metallic / Roughness / Normal / Emissive 等）。  
导出策略：生成基础材质并将贴图绑定到对应输入，或生成材质实例并绑定贴图。  
参考：https://dev.epicgames.com/documentation/en-us/unreal-engine/material-inputs-in-unreal-engine

## 6. 中间态 → Unreal 资产字段映射（建议）

| 中间态字段 | Unreal 导入数据 | 说明 |
|---|---|---|
| positions | StaticMesh vertex positions | 必需 |
| indices + material_id | Mesh Sections / Material Slots | 一段网格对应一个材质槽 |
| normals | Import Normals | 可导入或计算 |
| tangents | Import Tangents | 与法线贴图匹配 |
| uv0/uv1 | UV Channels | 纹理与光照 |
| vertex_color | Vertex Color | 可选 |
| textures (RGBA8) | Texture2D (PNG/TGA) | 支持多种格式 |
| shader_disasm / shader_meta | Base Material / MI | 生成基础材质或材质实例 |

## 7. 导出建议（最小可用）
1. Mesh：导出 FBX（Static Mesh），保持 Section/Material 分组。  
2. Texture：输出 PNG/TGA（RGBA8）。  
3. Material：生成基础材质（PBR）或材质实例并绑定贴图。  

## 参考链接（官方）
- https://dev.epicgames.com/documentation/en-us/unreal-engine/fbx-static-mesh-pipeline-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/fbx-import-options-reference-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/interchange-import-reference-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/textures-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/material-inputs-in-unreal-engine
