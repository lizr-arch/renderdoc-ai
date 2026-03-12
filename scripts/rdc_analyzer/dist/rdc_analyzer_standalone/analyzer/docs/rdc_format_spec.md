# RDC File Format Specification

> 基于 RenderDoc 源码分析 (`renderdoc/serialise/rdcfile.cpp`)
> 版本: 0x102 (v1.2)

## 文件总体结构

```
┌─────────────────────────────────────┐
│ FileHeader (32 bytes)               │
├─────────────────────────────────────┤
│ BinaryThumbnail (8 + N bytes)       │
├─────────────────────────────────────┤
│ CaptureMetaData (variable)          │
├─────────────────────────────────────┤
│ CaptureTimeBase (16 bytes) [v1.2+]  │
├─────────────────────────────────────┤
│ Sections[] (variable)               │
│   - FrameCapture (必须是第一个)      │
│   - ResolveDatabase                 │
│   - ExtendedThumbnail               │
│   - ...                             │
└─────────────────────────────────────┘
```

## 1. FileHeader (32 bytes)

```c
struct FileHeader {
    uint64_t magic;           // 0x434F4452 ('RDOC' little-endian)
    uint32_t version;         // 0x00000102 for v1.2
    uint32_t headerLength;    // 总 header 长度（到 Sections 开始前）
    char progVersion[16];     // 例如 "v1.35 abc123"
};
```

## 2. BinaryThumbnail (variable)

```c
struct BinaryThumbnail {
    uint16_t width;           // 缩略图宽度，0 表示无缩略图
    uint16_t height;          // 缩略图高度
    uint32_t length;          // JPG 数据长度
    byte data[length];        // JPG 压缩数据
};
```

## 3. CaptureMetaData (variable)

```c
struct CaptureMetaData {
    uint64_t machineIdent;        // 机器标识
    uint32_t driverID;            // RDCDriver 枚举 (4 = Vulkan)
    uint8_t driverNameLength;     // 驱动名长度（含 null）
    char driverName[driverNameLength];  // ASCII 驱动名
};
```

### RDCDriver 枚举值
| 值 | 驱动 |
|----|------|
| 1 | D3D11 |
| 2 | OpenGL |
| 3 | Mantle |
| 4 | D3D12 |
| 5 | OpenGLES |
| 6 | Vulkan |

## 4. CaptureTimeBase (16 bytes) [v1.2+]

```c
struct CaptureTimeBase {
    uint64_t timeBase;    // 基准时间戳
    double timeFreq;      // 时间频率（ticks -> 微秒）
};
```

## 5. Section 格式

### 5.1 Binary Section Header (40 + nameLen bytes)

```c
struct BinarySectionHeader {
    byte isASCII;                     // 0x00 = binary, 'A' = ASCII
    byte zero[3];                     // 保留，必须为 0
    uint32_t sectionType;             // SectionType 枚举
    uint64_t sectionCompressedLength; // 压缩后长度
    uint64_t sectionUncompressedLength; // 原始长度
    uint64_t sectionVersion;          // Section 版本号
    uint32_t sectionFlags;            // SectionFlags
    uint32_t sectionNameLength;       // 名称长度（含 null）
    char name[sectionNameLength];     // UTF-8 名称
    byte data[sectionCompressedLength]; // Section 数据
};
```

### 5.2 SectionType 枚举
| 值 | 类型 | 说明 |
|----|------|------|
| 0 | Unknown | |
| 1 | FrameCapture | 帧数据（Chunks） |
| 2 | ResolveDatabase | 符号解析数据库 |
| 3 | Bookmarks | 书签 |
| 4 | Notes | 笔记 |
| 5 | ResourceRenames | 资源重命名 |
| 6 | AMDRGPProfile | AMD RGP 配置 |
| 7 | ExtendedThumbnail | 扩展缩略图 |
| 8 | EmbeddedLogfile | 嵌入日志 |
| 9 | EditedShaders | 编辑过的着色器 |
| 10 | D3D12Core | D3D12 Core |
| 11 | D3D12SDKLayers | D3D12 SDK Layers |
| 12 | EmbeddedExternalFiles | 嵌入外部文件 |

### 5.3 SectionFlags
| 值 | 标志 | 说明 |
|----|------|------|
| 0x01 | NoFlags | 无压缩 |
| 0x02 | LZ4Compressed | LZ4 压缩 |
| 0x04 | ZstdCompressed | Zstd 压缩 |
| 0x10 | ASCIIStored | ASCII 存储 |

## 6. FrameCapture Section 内部结构 (Chunks)

FrameCapture Section 包含多个 Chunk，每个 Chunk 代表一个 API 调用。

### 6.1 Chunk Header 格式

```c
// 第一个 uint32_t
uint32_t c;
// 低 16 位: chunkID (ChunkIndexMask = 0x0000FFFF)
// 高 16 位: flags
//   - 0x00010000: ChunkCallstack
//   - 0x00020000: ChunkThreadID
//   - 0x00040000: ChunkDuration
//   - 0x00080000: ChunkTimestamp
//   - 0x00100000: Chunk64BitSize

// 可选字段（根据 flags）
if (ChunkCallstack) {
    uint32_t numFrames;
    uint64_t callstack[numFrames];
}
if (ChunkThreadID) {
    uint64_t threadID;
}
if (ChunkDuration) {
    int64_t durationMicro;
}
if (ChunkTimestamp) {
    uint64_t timestampMicro;
}

// Chunk 长度
if (Chunk64BitSize) {
    uint64_t length;
} else {
    uint32_t length;
}

// Chunk 数据
byte data[length];
```

## 7. Vulkan Shader Chunk

对于 `VulkanChunk::vkCreateShaderModule` (ID = 1019):

### Chunk 数据布局

```
Chunk Data:
├── device: ResourceId (uint64_t)
├── VkShaderModuleCreateInfo:
│   ├── sType: VkStructureType (uint32_t)
│   ├── pNext: 链表 (通常为 null)
│   ├── flags: uint32_t
│   ├── codeSize: uint64_t (SPIR-V 字节数)
│   └── pCode: byte[codeSize] (SPIR-V 二进制，64字节对齐)
├── pAllocator: (通常为 null)
└── ShaderModule: ResourceId (uint64_t)
```

### 关键提取逻辑

1. 扫描所有 Chunks 寻找 chunkID == 1019
2. 在 chunk 数据中定位 `codeSize` 字段
3. 读取 `codeSize` 字节的 SPIR-V 数据（注意 64 字节对齐）

## 8. 压缩处理

FrameCapture Section 通常使用 LZ4 或 Zstd 压缩。需要先解压才能解析 Chunks。

### LZ4 解压
- 使用 `lz4` Python 库
- `lz4.frame.decompress(data)`

### Zstd 解压
- 使用 `zstandard` Python 库
- `zstd.decompress(data)`

## 9. SPIR-V 识别

SPIR-V 二进制以 magic number 开头：
```
0x07230203  (little-endian)
```

## 10. 参考代码位置

| 功能 | 文件 |
|------|------|
| RDC 文件解析 | `renderdoc/serialise/rdcfile.cpp` |
| Chunk 读取 | `renderdoc/serialise/serialiser.cpp` |
| Vulkan Shader 序列化 | `renderdoc/driver/vulkan/vk_serialise.cpp:3919` |
| VulkanChunk 枚举 | `renderdoc/driver/vulkan/vk_common.h:1169` |
| SystemChunk 基值 | `renderdoc/core/core.h:204` (FirstDriverChunk = 1000) |
