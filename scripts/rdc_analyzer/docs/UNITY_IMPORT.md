# Unity China 1.6.9 导入需求（基于官方文档）

> 目标：明确 Unity（团结引擎 1.6.9）导入 Mesh/Material/Texture 所需的最小数据，用于从中间态生成可导入资源。

## 1. 支持的模型格式（推荐 FBX）
Unity 的模型导入链路内部使用 FBX，并建议优先使用 FBX。Unity 也支持 OBJ/DAE/DXF 等标准格式。将中间态导出为 **FBX** 或 **OBJ+MTL**，均可被导入。  
参考：https://docs.unity.cn/2020.3/Documentation/Manual/3D-formats.html

## 2. Mesh 最小数据要求（Static Mesh）
Unity 的 Mesh 需要：

- **Positions**（必需）
- **Indices**（必需）
- **SubMesh 拆分**：一个 SubMesh 对应一个材质（Material）。
- **UV0**（强烈建议，做纹理采样）
- **Normals**（建议；用于光照）
- **Tangents**（用于法线贴图；无切线则法线贴图无法工作）
- 可选：Vertex Color、UV1（光照贴图/二套 UV）

官方要点：
- Unity 的 SubMesh 与材质一一对应。  
- Unity 可导入或自动计算法线；切线可导入或用 MikkTSpace 计算；若无切线，法线贴图无法正常使用。  

## 3. 纹理格式（RGBA8 输出建议）
Unity 支持常见贴图格式：PNG / TGA / JPG / PSD / TIFF / EXR 等。建议输出 **PNG（RGBA8）** 或 **TGA（RGBA8）**，交由引擎做压缩与平台化。  
参考：https://docs.unity.cn/2022.1/Documentation/Manual/ImportingTextures.html

## 4. Shader/Material 最小要求（ShaderLab）
Unity 使用 ShaderLab 定义材质属性与渲染 Pass：

- 通过 `Shader "Name" { Properties ... SubShader ... }` 定义 Shader
- `Properties` 中的 `2D` 纹理字段可作为材质贴图槽
- Unity 默认将 `_MainTex` 视作主纹理，将 `_Color` 视作主颜色；  
  也可通过 `[MainTexture]` / `[MainColor]` 标注其它属性名

> 导出策略：生成一个最小 ShaderLab（Unlit/PBR 简化）+ 生成 `.mat` 绑定纹理。

## 5. 中间态 → Unity 资产字段映射（建议）

| 中间态字段 | Unity 导入数据 | 说明 |
|---|---|---|
| positions | Mesh.vertices | 必需 |
| indices + material_id | Mesh.subMeshCount + SetIndices | 每个材质一个 SubMesh |
| normals | Mesh.normals | 可导入或让 Unity 计算 |
| tangents | Mesh.tangents | 用于法线贴图 |
| uv0/uv1 | Mesh.uv / Mesh.uv2 | 纹理与光照 |
| vertex_color | Mesh.colors | 可选 |
| textures (RGBA8) | Texture2D (PNG/TGA) | 支持多种格式 |
| shader_disasm / shader_meta | ShaderLab stub | 用最小 ShaderLab 组装 |

## 6. 导出建议（最小可用）
1. Mesh：导出 FBX（首选）或 OBJ（次选），保持 SubMesh/材质分组。
2. Texture：输出 PNG/TGA（RGBA8）。
3. Material：生成 ShaderLab stub（Unlit/PBR）+ `.mat` 绑定贴图。

## 参考链接（官方）
- https://docs.unity.cn/2020.3/Documentation/Manual/3D-formats.html
- https://docs.unity.cn/2018.2/Documentation/Manual/FBXImporter-Model.html
- https://docs.unity.cn/2022.1/Documentation/Manual/ImportingTextures.html
- https://docs.unity.cn/Manual/SL-Properties.html
- https://docs.unity.cn/2020.2/Documentation/Manual/SL-Shader.html
- https://docs.unity.cn/2021.2/Documentation/ScriptReference/Mesh.SetIndices.html
