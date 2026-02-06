# RDC 文件结构深度分析

> **版本**: 1.0.0  
> **更新日期**: 2025-01-31  
> **作者**: Codex Agent A  
> **目标读者**: 需要理解 RDC 内部结构的开发者

---

## 1. RDC 文件格式概述

### 1.1 文件结构层次

```
RDC 文件 (二进制格式)
├── File Header
│   ├── Magic Number: "RDOC"
│   ├── Version
│   └── Section Index Offset
├── Section 0: FrameCapture (主数据)
│   ├── Chunk 序列 (API 调用 + 系统数据)
│   └── 内嵌 Buffer 数据
├── Section 1: ResolveDatabase
├── Section 2: ExtendedThumbnail
└── Section N: ...
```

### 1.2 核心概念

| 概念 | 说明 |
|------|------|
| **Section** | 文件的顶层分区，每个 Section 有独立用途 |
| **Chunk** | Section 内的数据单元，代表一个 API 调用或系统事件 |
| **SDFile** | Structured Data File，Chunk 的结构化表示 |
| **Buffer** | 二进制数据块，如像素数据、顶点数据 |

---

## 2. Chunk 类型与 ID

### 2.1 SystemChunk（ID < 1000）

源码位置：`renderdoc/core/core.h:216`

```cpp
enum class SystemChunk : uint32_t
{
    DriverInit = 1,           // 驱动初始化参数
    InitialContentsList = 2,  // 初始内容列表
    InitialContents = 3,      // 初始内容数据 ← 关键！
    CaptureBegin = 4,         // 捕获开始标记
    CaptureScope = 5,         // 捕获范围
    CaptureEnd = 6,           // 捕获结束标记
    
    FirstDriverChunk = 1000,  // 驱动特定 Chunk 从此开始
};
```

### 2.2 Vulkan DriverChunk（ID >= 1000）

源码位置：`renderdoc/driver/vulkan/vk_common.h`

| Chunk ID | 名称 | 说明 |
|----------|------|------|
| 1015 | vkCreateImage | 创建纹理 |
| 1016 | vkCreateImageView | 创建纹理视图 |
| 1043 | vkBindImageMemory | 绑定纹理到内存 |
| 1003 | vkAllocateMemory | 分配设备内存 |
| ... | ... | ... |

### 2.3 D3D11 DriverChunk

源码位置：`renderdoc/driver/d3d11/d3d11_common.h`

| Chunk ID | 名称 | 说明 |
|----------|------|------|
| 1001 | CreateTexture2D | 创建 2D 纹理 |
| 1002 | CreateTexture3D | 创建 3D 纹理 |
| ... | ... | ... |

---

## 3. InitialContents 机制详解

### 3.1 为什么需要 InitialContents？

在捕获帧时，GPU 上已经存在大量资源（纹理、Buffer 等）。为了能够完整重放这一帧，RenderDoc 需要保存这些资源在**捕获开始时刻**的状态。

```
捕获时间线:
    
    游戏运行中...  →  [捕获开始]  →  帧渲染  →  [捕获结束]
                         ↑
                    保存所有资源的当前状态
                    = InitialContents
```

### 3.2 InitialContents 的序列化流程

源码位置：`renderdoc/driver/vulkan/vk_initstate.cpp:131`

```cpp
// 序列化初始内容
SCOPED_SERIALISE_CHUNK(SystemChunk::InitialContents, size);
Serialise_InitialState(ser, flushId, NULL, &initData);
```

### 3.3 Vulkan InitialContents 结构

从导出的 XML 分析：

```xml
<chunk id="3" name="Internal::Initial Contents" length="33554624">
    <enum name="type" string="eResDeviceMemory">5</enum>
    <ResourceId name="id">116</ResourceId>
    <bool name="IsSparse">false</bool>
    <uint name="ContentsSize">33554432</uint>
    <buffer name="Contents" byteLength="33554432">425</buffer>
</chunk>
```

| 字段 | 说明 |
|------|------|
| `type` | 资源类型（DeviceMemory=5, Buffer=1, Image=2...） |
| `id` | 资源的 RenderDoc 内部 ID |
| `IsSparse` | 是否为稀疏资源 |
| `ContentsSize` | 内容字节大小 |
| `Contents` | 实际数据（在 ZIP 导出模式下为 buffer 索引） |

### 3.4 不同资源类型的 InitialContents

源码位置：`renderdoc/driver/vulkan/vk_initstate.cpp:159-300`

```cpp
if(type == eResDescriptorSet)
{
    // Descriptor Set: 保存描述符绑定
}
else if(type == eResBuffer)
{
    // Buffer: 保存稀疏表（非稀疏 Buffer 通过内存间接保存）
}
else if(type == eResImage)
{
    // Image: 通过 vkCmdCopyImage 读取像素数据
}
else if(type == eResDeviceMemory)
{
    // DeviceMemory: 直接保存内存内容（如果可映射）
}
```

---

## 4. 纹理数据存储链路

### 4.1 Vulkan 纹理数据链路

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Vulkan 纹理数据存储链路                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  vkCreateImage (Chunk ID: 1015)                                     │
│  ├── 创建 VkImage 对象                                              │
│  ├── 分配 ResourceId (例: 360)                                      │
│  └── 记录元数据:                                                    │
│      - format: VK_FORMAT_R8_UNORM                                   │
│      - extent: {2048, 4096, 1}                                      │
│      - imageType: VK_IMAGE_TYPE_2D                                  │
│                         ↓                                           │
│  vkAllocateMemory (Chunk ID: 1003)                                  │
│  ├── 分配 VkDeviceMemory 对象                                       │
│  ├── 分配 ResourceId (例: 116)                                      │
│  └── 记录大小: 33554432 bytes (32 MB)                               │
│                         ↓                                           │
│  vkBindImageMemory (Chunk ID: 1043)                                 │
│  ├── 建立绑定关系:                                                  │
│  │   image=360 → memory=116, offset=9212928                         │
│  └── 纹理数据存储在 memory[offset] 位置                             │
│                         ↓                                           │
│  InitialContents (Chunk ID: 3, type=eResDeviceMemory)               │
│  ├── 保存 memory=116 的完整内容                                     │
│  ├── buffer_index = 425                                             │
│  └── 原始像素数据在 ZIP:000425 文件中                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 D3D11 纹理数据链路

```
┌─────────────────────────────────────────────────────────────────────┐
│                     D3D11 纹理数据存储链路                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ID3D11Device::CreateTexture2D                                      │
│  ├── 创建 ID3D11Texture2D 对象                                      │
│  ├── 分配 ResourceId                                                │
│  └── 记录 D3D11_TEXTURE2D_DESC:                                     │
│      - Format: DXGI_FORMAT_R8G8B8A8_UNORM                           │
│      - Width, Height, MipLevels...                                  │
│                         ↓                                           │
│  InitialContents (Chunk ID: 3, type=Resource)                       │
│  ├── 直接保存每个 subresource 的像素数据                            │
│  └── 包含所有 mip level 和 array slice                              │
│                                                                     │
│  注: D3D11 的纹理数据直接在 InitialContents 中，                    │
│      不需要像 Vulkan 那样通过 Memory 间接访问                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 5. Buffer 索引机制

### 5.1 序列化时的 Buffer 索引分配

源码位置：`renderdoc/serialise/serialiser.h:369`

```cpp
// 序列化数组时，数据存入 SDFile.buffers，索引存入 SDObject
template <typename T>
void Serialiser::SerialiseBuffer(const char *name, T *buf, uint64_t len)
{
    SDObject *obj = ...;
    
    // 数据存入 buffers 列表
    m_StructuredFile->buffers.push_back({data, len});
    
    // 索引存入对象的 u 字段
    obj->data.basic.u = m_StructuredFile->buffers.size() - 1;
}
```

### 5.2 XML 导出时的 Buffer 表示

当使用 `renderdoccmd convert -c xml` 导出时：

```xml
<!-- 内联模式：数据嵌入 XML -->
<buffer name="Contents" byteLength="64">
    AAECAwQFBgcICQoLDA0ODw==  <!-- Base64 编码 -->
</buffer>
```

当使用 `renderdoccmd convert -c zip.xml` 导出时：

```xml
<!-- 外部模式：数据存入 ZIP -->
<buffer name="Contents" byteLength="33554432">425</buffer>
                                              ↑
                                         Buffer 索引
                                         对应 ZIP 中的 "000425" 文件
```

---

## 6. 源码证据汇总

### 6.1 为什么不同 GPU 无法 Replay？

源码位置：`renderdoc/driver/vulkan/vk_replay.cpp:199`

```cpp
RDResult VulkanReplay::ReadLogInitialisation(RDCFile *rdc, ...)
{
    // 需要创建真实的 Vulkan 设备
    VkResult vkr = ObjDisp(m_Instance)->CreateDevice(...);
    
    if(vkr != VK_SUCCESS)
    {
        // 设备创建失败 = 无法 Replay
        return RDResult(ResultCode::APIHardwareUnsupported, ...);
    }
}
```

**关键点**：Replay 需要创建与捕获时相同的 GPU 设备，如果当前系统没有兼容的 GPU，设备创建会失败。

### 6.2 GetStructuredData 为什么不需要 GPU？

源码位置：`renderdoc/replay/capture_file.cpp`

```cpp
const SDFile &CaptureFile::GetStructuredData()
{
    InitStructuredData();  // 只读取 RDC 结构，不创建 GPU 设备
    return m_StructuredData;
}

void CaptureFile::InitStructuredData()
{
    // 调用驱动特定的结构化处理器
    switch(m_RDC->GetDriver())
    {
        case RDCDriver::Vulkan:
            Vulkan_ProcessStructured(m_RDC, m_StructuredData);
            break;
        // ...
    }
}
```

### 6.3 Vulkan_ProcessStructured 的实现

源码位置：`renderdoc/driver/vulkan/vk_core.cpp`

```cpp
void Vulkan_ProcessStructured(RDCFile *rdc, SDFile &output)
{
    // 创建一个 "虚拟" 的 WrappedVulkan，不需要真实 GPU
    WrappedVulkan vulkan;  // 无参构造 = 无 GPU 初始化
    
    // 读取并解析 RDC 中的 Chunk
    vulkan.ReadLogInitialisation(...);
    
    // 结构化数据输出到 SDFile
    output = vulkan.GetStructuredFile();
}
```

**关键发现**：`WrappedVulkan vulkan;` 无参构造时不会初始化真实的 Vulkan 设备，因此可以在没有 GPU 的环境下运行。

---

## 7. 格式解码参考

### 7.1 常见 Vulkan 纹理格式

| VkFormat | 字节/像素 | 说明 |
|----------|-----------|------|
| VK_FORMAT_R8_UNORM | 1 | 单通道 8 位 |
| VK_FORMAT_R8G8B8A8_UNORM | 4 | RGBA 32 位 |
| VK_FORMAT_B8G8R8A8_SRGB | 4 | BGRA sRGB |
| VK_FORMAT_BC1_RGB_UNORM_BLOCK | 0.5 | DXT1 压缩 (4x4=8B) |
| VK_FORMAT_BC3_UNORM_BLOCK | 1 | DXT5 压缩 (4x4=16B) |
| VK_FORMAT_BC5_UNORM_BLOCK | 1 | 双通道压缩 (4x4=16B) |
| VK_FORMAT_BC7_UNORM_BLOCK | 1 | 高质量压缩 (4x4=16B) |

### 7.2 块压缩格式的数据布局

```
BC7 格式 (VK_FORMAT_BC7_UNORM_BLOCK):

纹理尺寸: 2048 x 2048
块大小:   4 x 4 像素
块数量:   512 x 512 = 262144 块
每块字节: 16 bytes
总大小:   262144 * 16 = 4,194,304 bytes = 4 MB

内存布局:
[Block 0][Block 1][Block 2]...[Block 511]  ← 第一行块
[Block 512]...[Block 1023]                 ← 第二行块
...
[Block 261632]...[Block 262143]            ← 最后一行块
```

---

## 8. 附录：关键文件索引

| 文件路径 | 内容 |
|----------|------|
| `renderdoc/serialise/rdcfile.h` | RDCFile 类定义 |
| `renderdoc/serialise/rdcfile.cpp` | RDC 文件读写实现 |
| `renderdoc/core/core.h:216` | SystemChunk 枚举 |
| `renderdoc/driver/vulkan/vk_initstate.cpp` | Vulkan 初始状态序列化 |
| `renderdoc/driver/vulkan/vk_core.cpp` | Vulkan_ProcessStructured |
| `renderdoc/driver/d3d11/d3d11_initstate.cpp` | D3D11 初始状态序列化 |
| `renderdoc/replay/capture_file.cpp` | CaptureFile::GetStructuredData |
| `renderdoc/serialise/serialiser.h:369` | Buffer 索引分配逻辑 |
