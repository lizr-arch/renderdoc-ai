# 04_TASK_EAP_CORE_TYPES — 任务 2：EAP Core Types

目标：实现 EAP 的强类型数据结构、key 校验、annotation 写入 builder、上下文栈和采样预算。  
本任务仍不直接接入具体 render graph / draw 路径。

---

## 1. 输入文档

Codex 在本轮必须读取：

- `02_EAP_PROTOCOL_SPEC.md`
- `03_TASK_RENDERDOC_BRIDGE.md`
- 本文件
- 第 0 轮生成的 `EAP_IMPLEMENTATION_MAP.md`

---

## 2. 新增模块

建议新增：

```text
Source/Runtime/RenderDocEAP/Public/EAPIds.h
Source/Runtime/RenderDocEAP/Public/EAPTypes.h
Source/Runtime/RenderDocEAP/Public/EAPKeys.h
Source/Runtime/RenderDocEAP/Public/EAPContext.h
Source/Runtime/RenderDocEAP/Private/EAPKeyValidation.cpp
Source/Runtime/RenderDocEAP/Private/EAPContext.cpp
Source/Runtime/RenderDocEAP/Tests/EAPKeyValidationTests.cpp
Source/Runtime/RenderDocEAP/Tests/EAPContextTests.cpp
```

根据仓库实际命名风格调整。

---

## 3. EAP ID 类型

实现轻量 strong typedef，避免把 material id、mesh id、resource id 混用。

```cpp
namespace eap {

struct IdString {
  std::string value;
  bool empty() const { return value.empty(); }
};

struct ProjectId  : IdString { using IdString::IdString; };
struct BuildId    : IdString { using IdString::IdString; };
struct CaptureId  : IdString { using IdString::IdString; };
struct FrameId    : IdString { using IdString::IdString; };
struct PassId     : IdString { using IdString::IdString; };
struct RenderGraphNodeId : IdString { using IdString::IdString; };
struct CommandId  : IdString { using IdString::IdString; };
struct ResourceId : IdString { using IdString::IdString; };
struct AssetId    : IdString { using IdString::IdString; };
struct MaterialId : IdString { using IdString::IdString; };
struct ShaderId   : IdString { using IdString::IdString; };
struct PipelineId : IdString { using IdString::IdString; };
struct MeshId     : IdString { using IdString::IdString; };
struct ViewId     : IdString { using IdString::IdString; };

} // namespace eap
```

如果仓库不允许继承 string wrapper，可以用：

```cpp
template <typename Tag>
struct TypedId { std::string value; };
```

---

## 4. Key 常量

不要在代码各处手写字符串。实现 `EAPKeys.h`：

```cpp
namespace eap::keys {
inline constexpr const char* SchemaVersion = "eap.schema.version";
inline constexpr const char* FrameIndex = "eap.frame.index";
inline constexpr const char* CmdKind = "eap.cmd.kind";
inline constexpr const char* CmdIndex = "eap.cmd.index";
inline constexpr const char* PassId = "eap.pass.id";
inline constexpr const char* PassName = "eap.pass.name";
inline constexpr const char* RenderGraphNodeId = "eap.rg.node_id";
inline constexpr const char* MaterialId = "eap.material.id";
inline constexpr const char* MaterialName = "eap.material.name";
inline constexpr const char* MaterialPath = "eap.material.path";
inline constexpr const char* ShaderVsHash = "eap.shader.vs.hash";
inline constexpr const char* ShaderPsHash = "eap.shader.ps.hash";
inline constexpr const char* ShaderCsHash = "eap.shader.cs.hash";
inline constexpr const char* ShaderPermutationHash = "eap.shader.permutation_hash";
inline constexpr const char* ShaderPermutationKey = "eap.shader.permutation_key";
inline constexpr const char* PsoHash = "eap.pso.hash";
inline constexpr const char* MeshId = "eap.mesh.id";
inline constexpr const char* MeshName = "eap.mesh.name";
inline constexpr const char* MeshPath = "eap.mesh.path";
inline constexpr const char* MeshLod = "eap.mesh.lod";
inline constexpr const char* ResourceId = "eap.resource.id";
inline constexpr const char* ResourceKind = "eap.resource.kind";
inline constexpr const char* ResourceName = "eap.resource.name";
inline constexpr const char* ResourceOwner = "eap.resource.owner";
inline constexpr const char* ResourceFormat = "eap.resource.format";
inline constexpr const char* ResourceWidth = "eap.resource.width";
inline constexpr const char* ResourceHeight = "eap.resource.height";
inline constexpr const char* ResourceMips = "eap.resource.mips";
inline constexpr const char* AssetId = "eap.asset.id";
inline constexpr const char* AssetGuid = "eap.asset.guid";
inline constexpr const char* AssetPath = "eap.asset.path";
inline constexpr const char* StreamingResidentMip = "eap.streaming.resident_mip";
inline constexpr const char* StreamingWantedMip = "eap.streaming.wanted_mip";
} // namespace eap::keys
```

---

## 5. Key 校验

实现：

```cpp
namespace eap {

struct KeyValidationResult {
  bool ok = false;
  const char* reason = nullptr;
};

KeyValidationResult ValidateAnnotationKey(std::string_view key);
KeyValidationResult ValidateAnnotationStringValue(std::string_view value);

} // namespace eap
```

规则：

- key 非空；
- key 必须以 `eap.` 开头；
- key 长度 <= 128；
- 只允许 `[a-z0-9_.]`；
- 不能有连续 `..`；
- 不能以 `.` 结尾；
- string value 长度默认 <= 512；
- value 内不允许控制字符，`	`、`
` 如确需支持必须转义。

单测覆盖：

```text
eap.pass.name               ok
eap.shader.ps.hash          ok
pass.name                   fail: missing prefix
eap.Pass.Name               fail: uppercase
eap.material path           fail: space
eap..pass.name              fail: empty segment
eap.asset.path.             fail: trailing dot
```

---

## 6. 核心数据结构

### 6.1 FrameContext

```cpp
struct FrameContext {
  uint64_t frameIndex = 0;
  std::string projectName;
  std::string branch;
  std::string commit;
  std::string buildId;
  std::string mapName;
  std::string worldName;
};
```

### 6.2 PassContext

```cpp
struct PassContext {
  PassId passId;
  RenderGraphNodeId nodeId;
  std::string name;
  std::string category;
  std::string queue; // graphics / compute / copy
  ViewId viewId;
};
```

### 6.3 DrawContext

```cpp
struct DrawContext {
  uint32_t commandIndex = 0;
  std::string kind;       // draw_indexed / dispatch / ray_dispatch
  std::string reason;     // static_mesh / ui / particles / postprocess
  MaterialId materialId;
  std::string materialName;
  std::string materialPath;
  MeshId meshId;
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
```

### 6.4 ResourceContext

```cpp
struct ResourceContext {
  ResourceId resourceId;
  AssetId assetId;
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

## 7. Annotation builder

实现一个 builder，把 context 转为 bridge 调用。

```cpp
class AnnotationWriter {
public:
  explicit AnnotationWriter(RenderDocBridge& bridge);

  void WritePassCommandAnnotations(void* device, void* command, const FrameContext&, const PassContext&);
  void WriteDrawCommandAnnotations(void* device, void* command, const FrameContext&, const PassContext&, const DrawContext&);
  void WriteResourceObjectAnnotations(void* device, void* object, const ResourceContext&);

  void SetEnabled(bool enabled);
  void SetOnlyWhenCapturing(bool enabled);
  void SetBudget(uint32_t maxCommandAnnotationsPerFrame, uint32_t maxObjectAnnotationsPerFrame);

private:
  bool ShouldWrite() const;
  void WriteString(void* device, void* command, const char* key, std::string_view value);
  void WriteU32(void* device, void* command, const char* key, uint32_t value);
  void WriteU64(void* device, void* command, const char* key, uint64_t value);
};
```

注意：

- `WriteDrawCommandAnnotations` 先写 pass，再写 draw/material/shader/mesh；
- 如果字段为空，不写；
- 如果 `OnlyWhenCapturing = true` 且 RenderDoc 未 capture，不写；
- 预算超出时停止写 command annotation，但 sidecar 仍可收集。

---

## 8. Scope / Context 栈

实现 RAII scope，供引擎 hooks 使用。

```cpp
class EAPRuntime {
public:
  static EAPRuntime& Get();

  void BeginFrame(const FrameContext& frame);
  void EndFrame();

  void PushPass(const PassContext& pass);
  void PopPass();

  const FrameContext* CurrentFrame() const;
  const PassContext* CurrentPass() const;

  AnnotationWriter& Writer();
};

class ScopedPass {
public:
  explicit ScopedPass(const PassContext& pass) { EAPRuntime::Get().PushPass(pass); }
  ~ScopedPass() { EAPRuntime::Get().PopPass(); }
};
```

如果引擎多线程录制 command buffers：

- FrameContext 可全局只读；
- PassContext 用 thread_local 栈；
- command index 用 atomic；
- sidecar event 收集用 lock-free queue 或 mutex-protected vector，首版可用 mutex。

---

## 9. 采样与预算

实现：

```cpp
struct AnnotationBudget {
  uint32_t maxCommandAnnotationsPerFrame = 50000;
  uint32_t maxObjectAnnotationsPerFrame = 20000;
  uint32_t commandAnnotationsWritten = 0;
  uint32_t objectAnnotationsWritten = 0;
  bool exceeded = false;
};
```

每帧 `BeginFrame()` 重置。预算超出：

- 不写更多 RenderDoc annotations；
- 记录 diagnostics；
- sidecar 中保存 `annotation_budget_exceeded`。

---

## 10. 和 Sidecar 的关系

本轮只定义接口，不实现写文件：

```cpp
class ISidecarSink {
public:
  virtual ~ISidecarSink() = default;
  virtual void OnFrameBegin(const FrameContext&) = 0;
  virtual void OnPassBegin(const PassContext&) = 0;
  virtual void OnCommand(const PassContext&, const DrawContext&) = 0;
  virtual void OnResource(const ResourceContext&) = 0;
  virtual void OnFrameEnd() = 0;
};

void RegisterSidecarSink(ISidecarSink* sink);
```

如果仓库不喜欢 global registry，可以把 sink 挂在 `EAPRuntime` 上。

---

## 11. 单测要求

新增测试：

1. key validation；
2. string value validation；
3. empty fields skipped；
4. `OnlyWhenCapturing` 生效；
5. budget exceeded 后不继续写 bridge；
6. `ScopedPass` push/pop 正常；
7. 多线程 push pass 不串数据，如果引擎支持多线程测试。

---

## 12. Codex 禁止事项

本任务禁止：

- 直接接入 render graph；
- 写 JSON sidecar 文件；
- 修改 RenderDoc 源码；
- 引入大型 third-party JSON 库，除非仓库已有；
- 在 `AnnotationWriter` 中写资产系统业务逻辑。

---

## 13. 本轮完成输出

Codex 最终输出：

- 新增类型和接口；
- 单测结果；
- 与 `RenderDocBridge` 的连接方式；
- 下一轮需要在哪些引擎 hook 调用 `ScopedPass` / `WriteDrawCommandAnnotations` / `WriteResourceObjectAnnotations`。

