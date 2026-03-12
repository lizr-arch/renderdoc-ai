# GPU 兼容性分析：为什么 RDC 文件无法跨 GPU 解析

> **分析日期**: 2025-01-22  
> **基于版本**: RenderDoc 主分支  
> **目标**: 提供源码级证据，解释 RDC 跨 GPU 失败的根本原因

---

## 1. 核心结论

RDC 文件跨 GPU 失败的**根本原因**不是文件格式问题，而是 **Replay 过程需要创建真实的 GPU 设备**，而不同 GPU 的：

1. **API 扩展支持**不同
2. **内存类型布局**不同  
3. **厂商专用功能**不可跨品牌

---

## 2. 源码证据

### 2.1 Vulkan 扩展不匹配（硬性失败）

**文件**: `renderdoc/driver/vulkan/wrappers/vk_device_funcs.cpp:361-370`

```cpp
// verify that extensions are supported
for(size_t i = 0; i < params.Extensions.size(); i++)
{
  if(supportedExtensions.find(params.Extensions[i]) == supportedExtensions.end())
  {
    RETURN_ERROR_RESULT(ResultCode::APIHardwareUnsupported,
                        "Capture requires instance extension '%s' which is not supported\n",
                        params.Extensions[i].c_str());
  }
}
```

**影响**: 如果捕获时使用了 `VK_KHR_ray_tracing_pipeline` 等扩展，而 Replay GPU 不支持，直接失败。

---

### 2.2 内存类型索引不兼容（最常见原因）

**文件**: `renderdoc/driver/vulkan/wrappers/vk_resource_funcs.cpp:337-348`

```cpp
if(patched.memoryTypeIndex >= m_PhysicalDeviceData.memProps.memoryTypeCount)
{
  SET_ERROR_RESULT(
      m_FailedReplayResult, ResultCode::APIHardwareUnsupported,
      "Tried to allocate memory from index %u, but on replay we only have %u memory types.\n"
      "\n%s",
      patched.memoryTypeIndex, m_PhysicalDeviceData.memProps.memoryTypeCount,
      GetPhysDeviceCompatString(...).c_str());
  return false;
}
```

**场景示例**:
- 捕获 GPU: NVIDIA RTX 4090，有 11 种内存类型
- Replay GPU: Intel UHD 730，只有 3 种内存类型
- RDC 记录了 "分配内存类型 #7" → Replay 时找不到 → 失败

---

### 2.3 D3D12 设备创建失败

**文件**: `renderdoc/driver/d3d12/d3d12_replay.cpp:4770-4775`

```cpp
if(FAILED(hr))
{
  RETURN_ERROR_RESULT(ResultCode::APIHardwareUnsupported, 
                      "Couldn't create a d3d12 device: %s", ToStr(hr).c_str());
}
```

---

### 2.4 厂商专用扩展检查

**NVIDIA (nvapi)** - `d3d12_replay.cpp:4778-4792`:
```cpp
if(nvapiDev)
{
  BOOL ok = nvapiDev->SetReal(dev);
  if(!ok)
  {
    RETURN_ERROR_RESULT(ResultCode::APIHardwareUnsupported,
        "This capture needs nvapi extensions to replay, but device selected for replay can't "
        "support nvapi extensions");
  }
}
```

**AMD (AGS)** - `d3d12_replay.cpp:4794-4806`:
```cpp
if(agsDev)
{
  if(!agsDev->ExtensionsSupported())
  {
    RETURN_ERROR_RESULT(ResultCode::APIHardwareUnsupported,
        "This capture needs AGS extensions to replay, but device selected for replay can't "
        "support AGS extensions");
  }
}
```

---

### 2.5 跨厂商警告

**文件**: `renderdoc/driver/vulkan/vk_core.cpp:5464-5476`

```cpp
if(capture.Vendor() != replay.Vendor())
{
  ret += "Captures are not commonly portable across vendors, but may work.";
}
```

---

## 3. 失败原因分类表

| 原因层级 | 具体场景 | 失败类型 | 源码位置 |
|---------|---------|---------|---------|
| **扩展不支持** | 需要 `VK_KHR_ray_tracing` 但 GPU 不支持 | 硬性失败 | `vk_device_funcs.cpp:366` |
| **内存类型不匹配** | 内存类型索引超出 Replay GPU 范围 | 硬性失败 | `vk_resource_funcs.cpp:337` |
| **厂商专用 API** | NVIDIA 捕获 → AMD 回放，nvapi 不可用 | 硬性失败 | `d3d12_replay.cpp:4787` |
| **功能特性差异** | `descriptorIndexing` 等高级特性 | 硬性失败 | 各 `*_funcs.cpp` |
| **驱动版本** | 捕获/回放驱动差异过大 | 软性警告 | `vk_core.cpp:5435` |

---

## 4. 与纹理提取的关系

这解释了为什么传统方式"必须 GPU Replay 才能提取纹理"：

1. **传统流程**: `OpenCapture()` → 创建 GPU 设备 → Replay 到某帧 → 读取 GPU 内存中的纹理
2. **失败点**: 如果无法创建兼容的 GPU 设备，整个 Replay 链条断裂

**但是**：纹理的**原始像素数据**确实存储在 RDC 的 `InitialContents` 中。如果能绕过 Replay 直接解析 RDC 文件，理论上可以不依赖 GPU。

---

## 5. 绕过 GPU 限制的可能方案

| 方案 | 可行性 | 难度 | 说明 |
|------|-------|------|------|
| **1. 软件解码** | ✅ 可行 | 高 | 实现 ASTC/BC7 等压缩格式的 CPU 解码 |
| **2. RemoteServer** | ✅ 可行 | 中 | 在有兼容 GPU 的远程机器上回放 |
| **3. 虚拟 GPU** | ⚠️ 有限 | 高 | lavapipe/SwiftShader 可能缺扩展 |
| **4. 直接解析 RDC** | 🔬 探索中 | 高 | 绕过 Replay，直接读取 InitialContents |

---

## 6. 参考文件

- `renderdoc/api/replay/replay_enums.h` - `ResultCode::APIHardwareUnsupported` 定义
- `renderdoc/driver/vulkan/vk_core.cpp` - 物理设备兼容性检查
- `renderdoc/driver/d3d12/d3d12_replay.cpp` - D3D12 设备创建逻辑
- `scripts/rdc_analyzer/docs/TEXTURE_EXTRACTION_METHODS.md` - 纹理提取方案文档
