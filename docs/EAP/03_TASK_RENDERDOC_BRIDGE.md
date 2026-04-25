# 03_TASK_RENDERDOC_BRIDGE — 任务 1：RenderDocBridge

目标：新增一个安全、可 no-op 的 C++ bridge，用于动态发现 RenderDoc in-application API 1.7.0，并封装 `SetObjectAnnotation` / `SetCommandAnnotation`。

---

## 1. 输入文档

Codex 在本轮必须先读取：

- `00_README_FEED_ORDER.md`
- `01_REPO_RECON_AND_BOUNDARIES.md`
- `02_EAP_PROTOCOL_SPEC.md`
- 本文件
- 仓库中已有的 RenderDoc integration/debug marker 代码

---

## 2. 开发目标

实现：

```text
EAPRenderDocBridge
  - Init()
  - Shutdown()
  - IsAvailable()
  - GetApiVersion()
  - IsCapturing()
  - SetCaptureTitle()
  - SetCaptureComments()
  - SetCommandAnnotation()
  - SetObjectAnnotation()
  - typed wrappers: bool/int/u32/u64/float/double/string
```

必须支持：

- Windows：`GetModuleHandleA("renderdoc.dll")` / `LoadLibraryA` 受控尝试；
- Linux：`dlopen("librenderdoc.so", RTLD_NOLOAD | RTLD_NOW)`；
- macOS/其它平台：默认 no-op；
- API version 低于 1.7.0：仍可保留 capture title/comments 等旧功能，但 rich annotation no-op；
- RenderDoc 不存在：no-op；
- 运行期关闭：no-op。

---

## 3. 推荐文件

根据仓库实际结构调整。如果没有更好位置，新增：

```text
Source/Runtime/RenderDocEAP/Public/EAPRenderDocBridge.h
Source/Runtime/RenderDocEAP/Private/EAPRenderDocBridge.cpp
Source/Runtime/RenderDocEAP/Public/EAPConfig.h
Source/Runtime/RenderDocEAP/Tests/EAPBridgeTests.cpp
ThirdParty/RenderDoc/renderdoc_app.h   # 如果仓库没有该 header
```

如果仓库已有 `renderdoc_app.h`，不要重复引入。

---

## 4. 配置开关

新增或使用现有配置：

```cpp
#ifndef EAP_ENABLE_RENDERDOC
  #if defined(_DEBUG) || defined(DEBUG) || defined(DEVELOPMENT_BUILD)
    #define EAP_ENABLE_RENDERDOC 1
  #else
    #define EAP_ENABLE_RENDERDOC 0
  #endif
#endif

#ifndef EAP_ENABLE_ANNOTATIONS
  #define EAP_ENABLE_ANNOTATIONS EAP_ENABLE_RENDERDOC
#endif

#ifndef EAP_ENABLE_SIDEcar
  #define EAP_ENABLE_SIDECAR 1
#endif
```

Codex 需要修正大小写，避免 `SIDEcar` 这类 typo。上面故意保留一处大小写异常，用于提醒：**实际代码中只保留 `EAP_ENABLE_SIDECAR`。**

---

## 5. 公共接口建议

```cpp
#pragma once

#include <cstdint>
#include <string_view>

namespace eap {

struct RenderDocApiVersion {
  int major = 0;
  int minor = 0;
  int patch = 0;
};

enum class AnnotationStatus : uint32_t {
  Ok = 0,
  Unavailable,
  UnsupportedApiVersion,
  InvalidDevice,
  UnsupportedObjectOrCommand,
  InvalidArgument,
  Disabled,
};

enum class AnnotationType : uint8_t {
  Bool,
  Int32,
  UInt32,
  Int64,
  UInt64,
  Float,
  Double,
  String,
  ApiObject,
};

struct AnnotationValue {
  AnnotationType type;
  union {
    bool b;
    int32_t i32;
    uint32_t u32;
    int64_t i64;
    uint64_t u64;
    float f32;
    double f64;
    void* apiObject;
  } scalar{};
  std::string_view str;

  static AnnotationValue Bool(bool v);
  static AnnotationValue Int32(int32_t v);
  static AnnotationValue UInt32(uint32_t v);
  static AnnotationValue Int64(int64_t v);
  static AnnotationValue UInt64(uint64_t v);
  static AnnotationValue Float(float v);
  static AnnotationValue Double(double v);
  static AnnotationValue String(std::string_view v);
  static AnnotationValue ApiObject(void* v);
};

class RenderDocBridge {
public:
  static RenderDocBridge& Instance();

  bool Init();
  void Shutdown();

  bool IsAvailable() const;
  bool SupportsRichAnnotations() const;
  bool IsCapturing() const;
  RenderDocApiVersion GetApiVersion() const;

  void SetCaptureTitle(std::string_view title);
  void SetCaptureComments(std::string_view comments);

  AnnotationStatus SetCommandAnnotation(
      void* device,
      void* queueOrCommandBuffer,
      std::string_view key,
      const AnnotationValue& value);

  AnnotationStatus SetObjectAnnotation(
      void* device,
      void* object,
      std::string_view key,
      const AnnotationValue& value);

private:
  RenderDocBridge() = default;
};

} // namespace eap
```

注意：`void* device` / `void* object` 是 bridge 层最低公共抽象。后端适配在 `05_TASK_ENGINE_HOOKS.md` 实现，不要在 bridge 里写死 Vulkan/D3D12 业务逻辑。

---

## 6. 实现要点

### 6.1 初始化

伪代码：

```cpp
bool RenderDocBridge::Init() {
#if !EAP_ENABLE_RENDERDOC
  return false;
#else
  if (initialized_) return available_;
  initialized_ = true;

  void* module = FindRenderDocModule();
  if (!module) {
    available_ = false;
    return false;
  }

  auto getApi = reinterpret_cast<pRENDERDOC_GetAPI>(FindSymbol(module, "RENDERDOC_GetAPI"));
  if (!getApi) {
    available_ = false;
    return false;
  }

  void* api = nullptr;
  if (getApi(eRENDERDOC_API_Version_1_7_0, &api) == 1 && api) {
    api_ = static_cast<RENDERDOC_API_1_7_0*>(api);
    available_ = true;
    supportsRichAnnotations_ = api_->SetObjectAnnotation && api_->SetCommandAnnotation;
    return true;
  }

  // Optional fallback: try 1.6.0 for title/comments only.
  // If the header typedef aliases 1.6.0 to the same struct, still check function pointers.
  available_ = false;
  supportsRichAnnotations_ = false;
  return false;
#endif
}
```

### 6.2 不要多线程并发调用 `RENDERDOC_GetAPI`

RenderDoc header 说明 `RENDERDOC_GetAPI` 不应多线程并发调用。Codex 必须：

- 在引擎启动早期调用一次；或
- 在 `RenderDocBridge::Init()` 内用 mutex / call_once 防并发。

### 6.3 Annotation 调用

伪代码：

```cpp
AnnotationStatus RenderDocBridge::SetCommandAnnotation(
    void* device,
    void* cmd,
    std::string_view key,
    const AnnotationValue& value) {
  if (!enabled_) return AnnotationStatus::Disabled;
  if (!api_ || !supportsRichAnnotations_) return AnnotationStatus::Unavailable;
  if (!device || !cmd || key.empty()) return AnnotationStatus::InvalidArgument;

  RENDERDOC_AnnotationValue rdValue{};
  RENDERDOC_AnnotationType rdType = eRENDERDOC_Empty;
  std::string tmpString;

  switch (value.type) {
    case AnnotationType::UInt64:
      rdType = eRENDERDOC_UInt64;
      rdValue.uint64 = value.scalar.u64;
      break;
    case AnnotationType::String:
      rdType = eRENDERDOC_String;
      tmpString.assign(value.str.data(), value.str.size());
      rdValue.string = tmpString.c_str();
      break;
    // ... other cases
  }

  std::string tmpKey(key.data(), key.size());
  uint32_t rc = api_->SetCommandAnnotation(
      device, cmd, tmpKey.c_str(), rdType, 1, &rdValue);
  return ConvertRenderDocReturnCode(rc);
}
```

### 6.4 Return code 映射

RenderDoc annotation API 返回：

| RenderDoc code | Bridge status |
|---:|---|
| 0 | `Ok` |
| 1 | `InvalidDevice` |
| 2 | `UnsupportedObjectOrCommand` |
| 3 | `InvalidArgument` |
| 其它 | `InvalidArgument` 或 `Unavailable`，并记录诊断 |

### 6.5 字符串生命周期

RenderDoc API 调用中 `const char*` 只需要在调用期间有效。实现中：

- 对 `std::string_view` 复制为局部 `std::string`；
- 调用结束后销毁；
- 不保存外部指针。

### 6.6 运行期启停

提供运行期总开关：

```cpp
void SetEapAnnotationsEnabled(bool enabled);
bool AreEapAnnotationsEnabled();
```

若仓库已有 CVar / console variable 系统，接入：

```text
r.EAP.EnableAnnotations = 1
r.EAP.EnableSidecar = 1
r.EAP.OnlyWhenCapturing = 1
```

默认建议：

```text
OnlyWhenCapturing = 1
```

因为 draw 级 annotation 很多，不应在非 capture 时长期写。

---

## 7. 后端 adapter 预留

Bridge 不负责把引擎 handle 转成 RenderDoc handle。新增轻量接口：

```cpp
namespace eap {

struct RenderDocNativeHandles {
  void* device = nullptr;
  void* command = nullptr; // command list / command buffer / queue
  void* object = nullptr;
};

class IRenderDocBackendAdapter {
public:
  virtual ~IRenderDocBackendAdapter() = default;
  virtual void* GetRenderDocDeviceHandle() const = 0;
  virtual void* GetRenderDocCommandHandle(void* engineCommandContext) const = 0;
  virtual void* GetRenderDocObjectHandle(void* engineResource) const = 0;
};

} // namespace eap
```

后续第 5 轮根据引擎 RHI 实际实现 D3D12/Vulkan/GL adapter。

---

## 8. 单测要求

如果仓库支持单测，新增以下测试：

### 8.1 No RenderDoc loaded

- `Init()` 返回 false 或 available false；
- `SetCommandAnnotation()` 返回 `Unavailable` 或 `Disabled`；
- 不崩溃。

### 8.2 Invalid arguments

- 空 key；
- null device；
- null command；
- string 过长。

### 8.3 Mock API

如果可以注入 mock function pointer：

- `SetCommandAnnotation` 被调用；
- type 映射正确；
- key 字符串正确；
- return code 映射正确。

### 8.4 Thread safety

- 多线程同时调用 `Init()`；
- 只执行一次加载逻辑；
- 不 data race。

---

## 9. 日志要求

初始化失败时只输出一次：

```text
[EAP] RenderDoc API not available; annotations disabled.
```

API 版本不足：

```text
[EAP] RenderDoc rich annotations require API 1.7.0; current API is x.y.z. Sidecar remains enabled.
```

不要每帧刷日志。

---

## 10. Codex 禁止事项

本任务禁止：

- 接入 render graph / draw path；
- 写 sidecar；
- 修改 RenderDoc 源码；
- 引入网络依赖；
- 在 bridge 层硬编码业务 key；
- 在 shipping build 默认启用；
- 因 RenderDoc 缺失导致程序退出。

---

## 11. 验收命令

Codex 应根据仓库输出实际命令。例如：

```bash
cmake --build build --target RenderDocEAPTests
ctest -R EAPBridge
```

或 Unreal 风格：

```bash
RunTests RenderDocEAP
```

如果无法运行测试，Codex 必须说明：

```text
Unable to run tests because <具体原因>. Code compiles logically but requires <missing dependency/toolchain>.
```

---

## 12. 本轮完成输出

Codex 最终输出：

1. 修改文件清单；
2. 新增接口摘要；
3. 单测结果；
4. 已知限制；
5. 下一轮应接入 `04_TASK_EAP_CORE_TYPES.md`。

