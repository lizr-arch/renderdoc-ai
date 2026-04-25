# 06_TASK_SIDECAR_WRITER — 任务 4：Sidecar Writer

目标：实现 `*.rmeta.json` sidecar 写入，让 RenderDoc capture 附带结构化引擎语义数据，可被 CLI、规则引擎、CI、MCP、AI 读取。

---

## 1. 输入文档

Codex 本轮必须读取：

- `02_EAP_PROTOCOL_SPEC.md`
- `04_TASK_EAP_CORE_TYPES.md`
- `05_TASK_ENGINE_HOOKS.md`
- 本文件

---

## 2. 本轮目标

实现：

1. `ISidecarSink` 的具体实现；
2. frame/pass/command/resource 的内存收集；
3. JSON sidecar 序列化；
4. 原子写入；
5. capture 文件名绑定；
6. redaction 最小实现；
7. sidecar 单测。

---

## 3. 推荐文件

```text
Source/Runtime/RenderDocEAP/Public/EAPSidecar.h
Source/Runtime/RenderDocEAP/Public/EAPRedaction.h
Source/Runtime/RenderDocEAP/Private/EAPSidecarWriter.cpp
Source/Runtime/RenderDocEAP/Private/EAPRedaction.cpp
Source/Runtime/RenderDocEAP/Tests/EAPSidecarTests.cpp
Docs/EAP/EAP_SIDECAR_SCHEMA.md
```

如果仓库已有 JSON writer，必须优先使用已有库。不要重复引入大型 third-party。

---

## 4. SidecarWriter 接口

```cpp
namespace eap {

enum class RedactionPolicy {
  LocalFull,
  ProjectInternal,
  CrossProject,
  ExternalVendor,
};

struct SidecarConfig {
  bool enabled = true;
  bool writeEveryFrameWhenNoCapture = false;
  std::string outputDirectory;
  std::string capturePath;
  RedactionPolicy redactionPolicy = RedactionPolicy::LocalFull;
  uint32_t maxCommands = 200000;
  uint32_t maxResources = 100000;
};

class SidecarWriter final : public ISidecarSink {
public:
  explicit SidecarWriter(SidecarConfig config);

  void OnFrameBegin(const FrameContext&) override;
  void OnPassBegin(const PassContext&) override;
  void OnCommand(const PassContext&, const DrawContext&) override;
  void OnResource(const ResourceContext&) override;
  void OnFrameEnd() override;

  bool FlushToFile(std::string_view path);
  std::string BuildDefaultSidecarPath() const;
  void SetCapturePath(std::string_view rdcPath);
  void SetRedactionPolicy(RedactionPolicy policy);

private:
  // implementation storage
};

} // namespace eap
```

---

## 5. Capture 文件名绑定

优先顺序：

1. 如果 RenderDocBridge 可用，使用 `GetNumCaptures/GetCapture` 获取最新 capture 文件路径。
2. 如果引擎已有 capture path 回调，使用该路径。
3. 如果都没有，写：

```text
<outputDirectory>/last_frame.rmeta.json
```

并在 JSON 中标注：

```json
"capture": {
  "rdc_path": null,
  "rdc_binding": "unknown"
}
```

后续可以用工具手动绑定：

```bash
eap-analyze bind --rdc foo.rdc --sidecar last_frame.rmeta.json
```

---

## 6. Sidecar 内存模型

实现轻量记录结构，避免存完整 C++ 对象。

```cpp
struct SidecarPassRecord {
  std::string id;
  std::string nodeId;
  std::string name;
  std::string category;
  std::string queue;
  std::string viewId;
  uint32_t firstCommandIndex = UINT32_MAX;
  uint32_t lastCommandIndex = 0;
};

struct SidecarCommandRecord {
  std::string id;
  uint32_t index = 0;
  std::string kind;
  std::string passId;
  std::string viewId;
  std::string materialId;
  std::string materialName;
  std::string materialPath;
  std::string meshId;
  std::string meshName;
  std::string meshPath;
  uint32_t meshLod = UINT32_MAX;
  uint64_t psoHash = 0;
  uint64_t shaderVsHash = 0;
  uint64_t shaderPsHash = 0;
  uint64_t shaderCsHash = 0;
  uint64_t permutationHash = 0;
  std::string permutationKey;
  uint32_t indexCount = 0;
  uint32_t vertexCount = 0;
  uint32_t instanceCount = 0;
  uint32_t dispatchX = 0;
  uint32_t dispatchY = 0;
  uint32_t dispatchZ = 0;
};

struct SidecarResourceRecord {
  std::string id;
  std::string assetId;
  std::string kind;
  std::string name;
  std::string owner;
  std::string format;
  uint32_t width = 0;
  uint32_t height = 0;
  uint32_t depth = 1;
  uint32_t mips = 1;
  uint32_t samples = 1;
  std::string usage;
  std::string assetGuid;
  std::string assetPath;
  uint32_t residentMip = UINT32_MAX;
  uint32_t wantedMip = UINT32_MAX;
};
```

---

## 7. JSON 输出规则

### 7.1 不输出无效字段

- 空 string 不输出；
- `UINT32_MAX` 表示 unknown，不输出；
- hash 为 0 时不输出，除非 0 是合法 hash 并有额外标记。

### 7.2 Hash 格式

统一输出 16 位 hex string：

```json
"pso_hash": "0x00000000abcd1234"
```

### 7.3 路径规范化

- 使用 `/` 分隔；
- 去掉用户本机绝对路径前缀；
- 可保留项目虚拟路径，例如 `/Game/...`；
- redaction 时 hash 化。

---

## 8. Atomic write

实现：

```cpp
bool WriteFileAtomic(path, contents) {
  tmp = path + ".tmp";
  write tmp;
  flush;
  close;
  rename tmp -> path;
}
```

Windows 下注意：

- 如果目标文件已存在，使用 replace/MoveFileEx；
- 失败时保留 `.tmp` 或删除，按仓库文件工具约定。

---

## 9. Redaction

### 9.1 Redaction 函数

```cpp
std::string RedactPath(std::string_view path, RedactionPolicy policy);
std::string RedactGuid(std::string_view guid, RedactionPolicy policy);
bool ShouldEmitShaderDebugPath(RedactionPolicy policy);
bool ShouldEmitAssetPath(RedactionPolicy policy);
```

### 9.2 行为

| Policy | asset path | guid | user path | shader debug path |
|---|---|---|---|---|
| LocalFull | 保留 | 保留 | 去掉用户名前缀或保留，按公司规则 | 保留 |
| ProjectInternal | 保留虚拟路径 | 保留 | 移除 | 移除绝对路径 |
| CrossProject | hash + basename | hash | 移除 | 移除 |
| ExternalVendor | hash only | hash | 移除 | 移除 |

### 9.3 标注安全信息

JSON 顶层写：

```json
"security": {
  "redaction_policy": "project_internal",
  "contains_asset_paths": true,
  "contains_shader_paths": false,
  "contains_user_paths": false,
  "redacted_fields": ["shader.debug_symbols.path"]
}
```

---

## 10. Diagnostics

Sidecar 必须包含：

```json
"diagnostics": {
  "annotation_budget_exceeded": false,
  "command_limit_exceeded": false,
  "resource_limit_exceeded": false,
  "missing_fields": [],
  "warnings": []
}
```

如果 commands 超过 `maxCommands`：

- 停止记录后续 commands；
- 设置 `command_limit_exceeded = true`；
- 继续记录 pass/resource 总览。

---

## 11. Example output

```json
{
  "schema": {
    "name": "EngineAnnotationProtocol",
    "version": 1,
    "created_utc": "2026-04-24T07:30:00Z"
  },
  "capture": {
    "id": "cap:20260424_073000",
    "rdc_path": "captures/foo.rdc",
    "rdc_binding": "latest_renderdoc_capture",
    "frame_index": 1942
  },
  "project": {
    "name": "ProjectA",
    "branch": "main",
    "commit": "abc123",
    "build_id": "dev"
  },
  "frame": {
    "index": 1942,
    "map": "City_Day_03"
  },
  "render_graph": {
    "nodes": [
      {
        "id": "pass:base_opaque",
        "name": "BasePass/Opaque",
        "category": "base_pass",
        "queue": "graphics",
        "event_range": { "first_cmd": 1200, "last_cmd": 8450 }
      }
    ],
    "edges": []
  },
  "commands": [
    {
      "id": "draw:8251",
      "index": 8251,
      "kind": "draw_indexed",
      "pass_id": "pass:base_opaque",
      "material_id": "mat:hero_face",
      "material_path": "/Game/Characters/Hero/M_HeroFace",
      "mesh_id": "mesh:hero_head",
      "mesh_lod": 1,
      "pso_hash": "0x000000001234abcd",
      "shader_hashes": {
        "ps": "0x0000000083a1c0fe"
      },
      "counts": {
        "index_count": 9216,
        "instance_count": 1
      }
    }
  ],
  "resources": [
    {
      "id": "res:hero_face_d",
      "kind": "texture2d",
      "name": "T_HeroFace_D",
      "format": "BC7_UNORM_SRGB",
      "width": 2048,
      "height": 2048,
      "mips": 12,
      "asset_path": "/Game/Characters/Hero/T_HeroFace_D",
      "streaming": {
        "resident_mip": 4,
        "wanted_mip": 2
      }
    }
  ],
  "diagnostics": {
    "annotation_budget_exceeded": false,
    "command_limit_exceeded": false,
    "resource_limit_exceeded": false,
    "missing_fields": [],
    "warnings": []
  },
  "security": {
    "redaction_policy": "local_full",
    "contains_asset_paths": true,
    "contains_shader_paths": false,
    "contains_user_paths": false
  }
}
```

---

## 12. 单测要求

1. 写出最小 sidecar；
2. 空字段不输出；
3. hash 格式正确；
4. atomic write 成功；
5. atomic write 失败时不破坏旧文件；
6. redaction policy 生效；
7. command/resource limit 生效；
8. frame begin/end 清理状态；
9. 多线程 `OnCommand` 不崩溃，首版可用 mutex。

---

## 13. 与 RenderDocBridge 的联动

在 frame end 时尝试：

```cpp
if (RenderDocBridge::Instance().IsAvailable()) {
  auto latest = RenderDocBridge::Instance().TryGetLatestCapturePath();
  if (!latest.empty()) sidecar.SetCapturePath(latest);
}
sidecar.FlushToFile(sidecar.BuildDefaultSidecarPath());
```

如果 `TryGetLatestCapturePath()` 尚未在 bridge 实现，本轮可以新增。它封装：

- `GetNumCaptures()`；
- `GetCapture(index, filename, pathLength, timestamp)`。

注意 buffer size 处理。

---

## 14. Codex 禁止事项

- 不要上传 sidecar；
- 不要读取 `.rdc` 二进制；
- 不要引入网络服务；
- 不要把完整 shader source 写进 sidecar；
- 不要把用户绝对路径默认写到可共享策略里；
- 不要让 sidecar 写入失败影响渲染。

---

## 15. 本轮完成输出

Codex 最终输出：

1. sidecar 写入路径；
2. JSON 示例；
3. redaction 行为；
4. 单测结果；
5. 如何与真实 capture 文件绑定；
6. 下一轮进入 `07_TASK_RULE_ENGINE_MVP.md`。

