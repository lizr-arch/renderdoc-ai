# 02_EAP_PROTOCOL_SPEC — Engine Annotation Protocol v0

版本：0.2  
状态：MVP 开发版  
目标：定义引擎写入 RenderDoc annotations 和 `*.rmeta.json` sidecar 的统一协议。

---

## 1. 设计原则

1. **RenderDoc annotation 只放短、关键、可过滤的数据。**
2. **复杂结构放 sidecar。** 不要把完整 render graph、完整 material 参数、完整 shader include tree 塞进 RenderDoc annotation。
3. **所有 key 必须稳定。** AI、CLI、CI、规则引擎依赖 key，不允许频繁改名。
4. **所有 value 必须 typed。** 不要把所有东西都转成字符串。
5. **所有 ID 必须可跨系统关联。** Draw 能关联 pass、material、shader、mesh、resource、asset。
6. **没有数据就不写，不要写假数据。** 如果 material path 不可用，写 `material.id`，不要伪造路径。
7. **首版宁可字段少，也要字段可信。**

---

## 2. 双通道数据模型

```text
RenderDoc annotations
  - per-command：当前 draw/dispatch 属于哪个 pass/material/shader/mesh/PSO
  - per-object：texture/buffer/pipeline/shader 等 GPU object 的引擎语义
  - 低容量、短 key、短 value、方便 UI 过滤

Sidecar `*.rmeta.json`
  - frame/build/device/render_graph/assets/materials/shaders/resources/draws/rules
  - 高容量、可 diff、可上传、可被 AI/MCP/CI 读取
```

---

## 3. Key 命名规范

### 3.1 总规则

- 全部 key 以 `eap.` 开头。
- 使用 dot path：`eap.pass.name`、`eap.shader.ps.hash`。
- 全部小写，单词用 `_`。
- 不在 key 中写动态 ID。动态 ID 放 value。
- 不使用空格、斜杠、冒号。
- 推荐 key 长度 <= 96 字符。

### 3.2 禁止示例

```text
# 禁止：动态 ID 放 key 里
eap.resource.12345.name

# 禁止：含空格
eap.material display name

# 禁止：路径做 key
eap.asset./Game/Characters/Hero/M_HeroFace
```

### 3.3 推荐示例

```text
eap.schema.version = 1
eap.pass.name = "BasePass/Opaque"
eap.material.path = "/Game/Characters/Hero/M_HeroFace"
eap.shader.ps.hash = 0x83a1c0fe1234abcd
```

---

## 4. ID 规范

### 4.1 ID 格式

所有 ID 推荐使用字符串形式，便于 JSON 和日志统一：

```text
project:<name>
build:<hash>
frame:<number>
pass:<stable_hash_or_index>
rg:<node_id>
draw:<frame_draw_index>
res:<engine_resource_id>
asset:<guid_or_hash>
mat:<guid_or_hash>
shader:<stage>:<hash>
pso:<hash>
mesh:<guid_or_hash>
view:<id>
```

### 4.2 稳定性要求

| ID | 是否跨帧稳定 | 是否跨 build 稳定 | 说明 |
|---|---:|---:|---|
| asset id | 是 | 是 | 资产 GUID 或规范化路径 hash |
| material id | 是 | 是 | 材质资产 GUID 或路径 hash |
| shader hash | 是 | 部分 | shader 编译产物 hash |
| pso hash | 是 | 部分 | pipeline desc hash |
| resource id | 否 | 否 | GPU resource 每次运行可变 |
| draw id | 否 | 否 | 当前 frame 内递增 |
| pass id | 部分 | 部分 | 推荐 render graph node stable name hash |

---

## 5. Annotation 字段：Command 级

Command 级字段写在 command buffer / command list 上，目标是让选中 draw/dispatch 时能看到引擎上下文。

### 5.1 必填字段

| Key | Type | 示例 | 说明 |
|---|---|---|---|
| `eap.schema.version` | UInt32 | `1` | 协议版本 |
| `eap.frame.index` | UInt64 | `1942` | 引擎帧号 |
| `eap.cmd.kind` | String | `draw_indexed` | draw / dispatch / ray_dispatch / copy / clear |
| `eap.cmd.index` | UInt32 | `8251` | 当前 frame 内 EAP command index |
| `eap.pass.id` | String | `pass:base_opaque` | pass id |
| `eap.pass.name` | String | `BasePass/Opaque` | pass display name |
| `eap.rg.node_id` | String | `rg:000012ef` | render graph node id |

### 5.2 Draw / Dispatch 字段

| Key | Type | 示例 | 说明 |
|---|---|---|---|
| `eap.draw.reason` | String | `static_mesh` | draw 来源：static_mesh/skinned_mesh/particles/ui 等 |
| `eap.draw.vertex_count` | UInt32 | `4832` | 顶点数 |
| `eap.draw.index_count` | UInt32 | `9216` | index 数 |
| `eap.draw.instance_count` | UInt32 | `1` | instance 数 |
| `eap.dispatch.group_x` | UInt32 | `64` | compute dispatch x |
| `eap.dispatch.group_y` | UInt32 | `32` | compute dispatch y |
| `eap.dispatch.group_z` | UInt32 | `1` | compute dispatch z |

### 5.3 Material / Shader / Mesh / PSO 字段

| Key | Type | 示例 | 说明 |
|---|---|---|---|
| `eap.material.id` | String | `mat:7a21...` | 材质 id |
| `eap.material.name` | String | `M_HeroFace` | 短名 |
| `eap.material.path` | String | `/Game/Characters/Hero/M_HeroFace` | 可被脱敏 |
| `eap.shader.vs.hash` | UInt64/String | `0x...` | VS hash |
| `eap.shader.ps.hash` | UInt64/String | `0x...` | PS hash |
| `eap.shader.cs.hash` | UInt64/String | `0x...` | CS hash |
| `eap.shader.permutation_hash` | UInt64/String | `0x...` | permutation hash |
| `eap.shader.permutation_key` | String | `SKIN=1;SSS=1` | 短 key，过长放 sidecar |
| `eap.pso.hash` | UInt64/String | `0x...` | PSO desc hash |
| `eap.mesh.id` | String | `mesh:...` | mesh id |
| `eap.mesh.name` | String | `SK_Hero_Head` | mesh name |
| `eap.mesh.path` | String | `/Game/...` | mesh path，可被脱敏 |
| `eap.mesh.lod` | UInt32 | `1` | LOD |

### 5.4 View / Camera / XR 字段

| Key | Type | 示例 | 说明 |
|---|---|---|---|
| `eap.view.id` | String | `view:main` | view id |
| `eap.view.name` | String | `MainCamera` | view name |
| `eap.view.eye` | String | `left` | mono/left/right/both |
| `eap.view.width` | UInt32 | `1920` | render width |
| `eap.view.height` | UInt32 | `1080` | render height |

---

## 6. Annotation 字段：Object 级

Object 级字段写在 GPU object 上，主要用于 texture/buffer/pipeline/shader。

### 6.1 Resource 通用字段

| Key | Type | 示例 | 说明 |
|---|---|---|---|
| `eap.schema.version` | UInt32 | `1` | 协议版本 |
| `eap.resource.id` | String | `res:00001234` | 引擎 resource id |
| `eap.resource.kind` | String | `texture2d` | texture2d/texturecube/buffer/accel_struct |
| `eap.resource.name` | String | `T_HeroFace_D` | display name |
| `eap.resource.owner` | String | `TextureStreaming` | owner system |
| `eap.resource.format` | String | `BC7_UNORM_SRGB` | format |
| `eap.resource.width` | UInt32 | `2048` | width |
| `eap.resource.height` | UInt32 | `2048` | height |
| `eap.resource.depth` | UInt32 | `1` | depth/layers |
| `eap.resource.mips` | UInt32 | `12` | mip count |
| `eap.resource.samples` | UInt32 | `1` | MSAA samples |
| `eap.resource.usage` | String | `srv|rtv` | usage flags 简写 |

### 6.2 Asset / Streaming 字段

| Key | Type | 示例 | 说明 |
|---|---|---|---|
| `eap.asset.id` | String | `asset:...` | asset id |
| `eap.asset.guid` | String | `...` | 原始 guid，可脱敏 |
| `eap.asset.path` | String | `/Game/.../T_HeroFace_D` | 资产路径，可脱敏 |
| `eap.streaming.resident_mip` | UInt32 | `4` | 当前 resident mip |
| `eap.streaming.wanted_mip` | UInt32 | `2` | 期望 mip |
| `eap.streaming.priority` | Float | `0.75` | streaming priority |
| `eap.streaming.budget_group` | String | `CharacterTextures` | budget group |

---

## 7. Annotation 写入预算

避免 draw 级爆量写入导致性能问题。

| 项 | 默认预算 |
|---|---:|
| 每个 command 最多 annotation 数 | 32 |
| 每个 object 最多 annotation 数 | 32 |
| 字符串值最大长度 | 256 字符 |
| permutation key 最大长度 | 512 字符，超过写 sidecar |
| 每帧最大 command annotation 数 | 50,000 |
| 每帧最大 object annotation 数 | 20,000 |

超出预算时：

1. 不崩溃；
2. 丢弃低优先级字段；
3. 在 sidecar 写 `diagnostics.annotation_budget_exceeded = true`。

字段优先级：

1. schema/frame/pass/cmd；
2. material/shader/pso/mesh；
3. view/camera；
4. draw counts；
5. 其它扩展字段。

---

## 8. Sidecar 文件命名

RDC：

```text
MyCapture_2026_04_24_151230.rdc
```

Sidecar：

```text
MyCapture_2026_04_24_151230.rmeta.json
```

临时写入文件：

```text
MyCapture_2026_04_24_151230.rmeta.json.tmp
```

---

## 9. Sidecar 顶层结构

```json
{
  "schema": {
    "name": "EngineAnnotationProtocol",
    "version": 1,
    "created_utc": "2026-04-24T07:30:00Z"
  },
  "capture": {
    "id": "cap:...",
    "rdc_path": "...",
    "title": "ProjectA City_Day_03 BasePass issue",
    "trigger": "manual|qa_report|ci|hotkey",
    "frame_index": 1942
  },
  "project": {
    "name": "ProjectA",
    "branch": "release_candidate",
    "commit": "abc123",
    "build_id": "2026.04.24.1512",
    "configuration": "Development"
  },
  "device": {
    "platform": "Windows",
    "api": "D3D12",
    "gpu_vendor": "NVIDIA",
    "gpu_name": "...",
    "driver_version": "..."
  },
  "frame": {
    "index": 1942,
    "map": "City_Day_03",
    "world": "...",
    "camera": {
      "name": "MainCamera",
      "position": [0.0, 0.0, 0.0],
      "rotation": [0.0, 0.0, 0.0, 1.0],
      "fov_y": 60.0
    }
  },
  "views": [],
  "render_graph": {
    "nodes": [],
    "edges": []
  },
  "commands": [],
  "resources": [],
  "assets": [],
  "materials": [],
  "shaders": [],
  "pipelines": [],
  "rules": {
    "results": []
  },
  "diagnostics": {
    "annotation_budget_exceeded": false,
    "missing_fields": []
  },
  "security": {
    "redaction_policy": "local_full",
    "contains_asset_paths": true,
    "contains_shader_paths": true,
    "contains_user_paths": false
  }
}
```

---

## 10. Sidecar 子结构

### 10.1 RenderGraph node

```json
{
  "id": "pass:base_opaque",
  "name": "BasePass/Opaque",
  "category": "base_pass",
  "queue": "graphics",
  "event_range": { "first_cmd": 1200, "last_cmd": 8450 },
  "inputs": ["res:depth_prepass", "res:scene_uniforms"],
  "outputs": ["res:gbuffer_albedo", "res:gbuffer_normal"],
  "timing_ms": 2.35
}
```

### 10.2 Command

```json
{
  "id": "draw:8251",
  "index": 8251,
  "kind": "draw_indexed",
  "pass_id": "pass:base_opaque",
  "view_id": "view:main",
  "material_id": "mat:hero_face",
  "mesh_id": "mesh:hero_head",
  "pso_hash": "0x83a1c0fe1234abcd",
  "shader_hashes": {
    "vs": "0x...",
    "ps": "0x..."
  },
  "counts": {
    "index_count": 9216,
    "instance_count": 1
  },
  "resources_read": ["res:hero_face_d", "res:hero_face_n"],
  "resources_written": ["res:gbuffer_albedo", "res:gbuffer_normal"]
}
```

### 10.3 Resource

```json
{
  "id": "res:hero_face_d",
  "kind": "texture2d",
  "name": "T_HeroFace_D",
  "asset_id": "asset:hero_face_d",
  "format": "BC7_UNORM_SRGB",
  "width": 2048,
  "height": 2048,
  "depth": 1,
  "mips": 12,
  "samples": 1,
  "usage": ["srv"],
  "streaming": {
    "resident_mip": 4,
    "wanted_mip": 2,
    "budget_group": "CharacterTextures"
  }
}
```

### 10.4 Shader

```json
{
  "id": "shader:ps:83a1c0fe1234abcd",
  "stage": "ps",
  "hash": "0x83a1c0fe1234abcd",
  "source_file": "BasePassPixel.usf",
  "entry_point": "MainPS",
  "permutation_hash": "0x1111222233334444",
  "permutation_key": "SKIN=1;SSS=1;HAIR=0",
  "debug_symbols": {
    "available": true,
    "embedded": false,
    "path": "..."
  }
}
```

### 10.5 Rule result

```json
{
  "id": "rule:texture.streaming_low_mip",
  "severity": "warning",
  "title": "Texture resident mip is lower than wanted mip",
  "evidence": [
    {
      "kind": "resource",
      "id": "res:hero_face_d",
      "key": "streaming.resident_mip",
      "value": 4
    }
  ],
  "related_commands": ["draw:8251"],
  "recommendation": "Check texture streaming budget or residency for CharacterTextures."
}
```

---

## 11. Redaction 规范

默认策略：`local_full`。后续共享时可使用：

| Policy | 行为 |
|---|---|
| `local_full` | 保留路径、GUID、shader source path |
| `project_internal` | 保留项目内路径，移除用户机器路径 |
| `cross_project` | asset path hash 化，保留 display name |
| `external_vendor` | 移除路径，仅保留 hash、尺寸、格式、规则结果 |

字段级标记：

```json
"security": {
  "redaction_policy": "project_internal",
  "redacted_fields": ["asset.path", "shader.debug_symbols.path"],
  "contains_asset_paths": false,
  "contains_shader_paths": false
}
```

---

## 12. 版本兼容

### 12.1 协议版本

- `schema.version = 1`：本文件定义的 MVP。
- 后续新增字段不增加 major version。
- 删除/改名 key 必须增加 major version。

### 12.2 Key 废弃

废弃 key 时保留至少两个版本：

```text
eap.material.path        # current
eap.material.asset_path  # deprecated alias
```

sidecar 中写：

```json
"schema": {
  "version": 1,
  "deprecated_keys": ["eap.material.asset_path"]
}
```

---

## 13. 允许 Codex 自行决策的默认值

如果引擎没有某字段：

| 缺失字段 | 默认处理 |
|---|---|
| material path | 写 material id/name，不写 path |
| shader permutation key | 写 permutation hash |
| PSO hash | 从 pipeline desc 计算 64-bit hash |
| render graph node id | 用 pass name + frame-local index hash |
| asset GUID | 用 normalized asset path hash |
| capture end 回调 | 每帧写 `last_frame.rmeta.json`，后续再绑定 capture 文件名 |
| RenderDoc API 1.7.0 不可用 | no-op annotation，但 sidecar 仍可写 |

---

## 14. 与 RenderDoc API 的关系

RenderDoc v1.43+ 的 in-application API 1.7.0 提供：

- `SetObjectAnnotation(device, object, key, type, vector_width, value)`
- `SetCommandAnnotation(device, queueOrCommandBuffer, key, type, vector_width, value)`

协议字段应通过这两个 API 写入。RenderDoc API 支持 dot-separated key path、typed value、vector value、API object reference。实际对象/command handle 由后端 adapter 处理。

---

## 15. 最小写入示例

Command annotation：

```text
eap.schema.version = 1
eap.frame.index = 1942
eap.cmd.kind = draw_indexed
eap.cmd.index = 8251
eap.pass.name = BasePass/Opaque
eap.rg.node_id = pass:base_opaque
eap.material.path = /Game/Characters/Hero/M_HeroFace
eap.shader.ps.hash = 0x83a1c0fe1234abcd
eap.pso.hash = 0x1111222233334444
eap.mesh.lod = 1
```

Object annotation：

```text
eap.resource.kind = texture2d
eap.resource.name = T_HeroFace_D
eap.resource.format = BC7_UNORM_SRGB
eap.resource.width = 2048
eap.resource.height = 2048
eap.resource.mips = 12
eap.asset.path = /Game/Characters/Hero/T_HeroFace_D
eap.streaming.resident_mip = 4
eap.streaming.wanted_mip = 2
```

