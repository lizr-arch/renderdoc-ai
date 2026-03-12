# RDC 文件格式与解析流程全解

> **版本**: 1.0 | **更新**: 2025-01-31 | **作者**: Codex Agent
>
> **目的**: 为开发者提供 RDC 文件结构和项目解析流程的完整参考文档。

---

## 一、RDC 文件的二进制结构

RDC (RenderDoc Capture) 是 RenderDoc 的专有二进制格式，用于存储一帧 GPU 渲染的完整数据。

### 1.1 文件总体布局

```
┌─────────────────────────────────────────────────────────────────────┐
│                           RDC File                                  │
├─────────────────────────────────────────────────────────────────────┤
│  1. FileHeader (32 bytes)                                           │
│     ├── magic: 0x434F4452 ("RDOC" little-endian)                    │
│     ├── version: 0x00000102 (v1.2)                                  │
│     ├── headerLength: 到 Sections 开始的偏移                         │
│     └── progVersion: "v1.35 abc123" (16字节)                        │
├─────────────────────────────────────────────────────────────────────┤
│  2. BinaryThumbnail (8 + N bytes)                                   │
│     ├── width, height: uint16 × 2                                   │
│     ├── length: uint32                                              │
│     └── data[length]: JPG 压缩图像                                   │
├─────────────────────────────────────────────────────────────────────┤
│  3. CaptureMetaData (variable)                                      │
│     ├── machineIdent: uint64 (机器标识)                              │
│     ├── driverID: uint32 (1=D3D11, 4=D3D12, 6=Vulkan...)            │
│     ├── driverNameLength: uint8                                     │
│     └── driverName[]: ASCII 字符串                                   │
├─────────────────────────────────────────────────────────────────────┤
│  4. CaptureTimeBase (16 bytes) [v1.2+]                              │
│     ├── timeBase: uint64 (基准时间戳)                                │
│     └── timeFreq: double (ticks → 微秒)                              │
├─────────────────────────────────────────────────────────────────────┤
│  5. Sections[] (紧密排列)                                            │
│     ├── Section 0: FrameCapture (必须是第一个)                       │
│     ├── Section 1: ResolveDatabase                                  │
│     ├── Section 2: ExtendedThumbnail                                │
│     ├── Section 3: Bookmarks / Notes / ...                          │
│     └── ...                                                         │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Section 结构详解

每个 Section 有一个 Header，后跟压缩/非压缩的数据：

```
┌─────────────────────────────────────────────────────────────────────┐
│  BinarySectionHeader (40 + nameLen bytes)                           │
├─────────────────────────────────────────────────────────────────────┤
│  isASCII (1B)           │ 0x00=二进制, 'A'=ASCII                    │
│  zero[3] (3B)           │ 保留                                       │
│  sectionType (4B)       │ 0=Unknown, 1=FrameCapture, 2=ResolveDB... │
│  compressedLength (8B)  │ 磁盘上的长度                               │
│  uncompressedLen (8B)   │ 解压后长度                                 │
│  sectionVersion (8B)    │ Section 版本号                             │
│  sectionFlags (4B)      │ 0x02=LZ4, 0x04=Zstd                        │
│  sectionNameLen (4B)    │ 名称长度                                   │
│  name[nameLen]          │ UTF-8 名称                                 │
├─────────────────────────────────────────────────────────────────────┤
│  data[compressedLen]    │ Section 数据                               │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 SectionType 枚举

| 值 | 名称 | 说明 |
|----|------|------|
| 0 | Unknown | 未知/自定义 |
| 1 | **FrameCapture** | 核心帧数据（API 调用 + 资源） |
| 2 | ResolveDatabase | 符号解析数据库 |
| 3 | Bookmarks | UI 书签 |
| 4 | Notes | 用户笔记 |
| 5 | ResourceRenames | 资源重命名 |
| 6 | AMDRGPProfile | AMD RGP 配置 |
| 7 | ExtendedThumbnail | 高质量缩略图 |
| 8 | EmbeddedLogfile | 嵌入日志 |
| 9 | EditedShaders | 编辑过的 Shader |

### 1.4 FrameCapture Section 内部结构（Chunks）

FrameCapture 是 RDC 的核心，包含一系列 **Chunks**，每个 Chunk 代表一个 API 调用：

```
┌─────────────────────────────────────────────────────────────────────┐
│  FrameCapture Section (解压后)                                       │
├─────────────────────────────────────────────────────────────────────┤
│  Chunk 0: SystemChunk::DriverInit                                   │
│  Chunk 1: SystemChunk::InitialContentsList                          │
│  Chunk 2-N: SystemChunk::InitialContents (资源初始状态)              │
│  Chunk N+1: SystemChunk::CaptureBegin                               │
│  Chunk N+2: vkCmdBeginRenderPass / ID3D11DeviceContext::Draw...     │
│  Chunk N+3: vkCmdDraw / vkCmdDispatch / ...                         │
│  ...                                                                 │
│  Chunk M: SystemChunk::CaptureEnd                                   │
└─────────────────────────────────────────────────────────────────────┘
```

**Chunk Header 格式**：

```c
uint32_t c;  // 低16位=chunkID, 高16位=flags
// flags 含义:
//   0x00010000: 有调用栈
//   0x00020000: 有线程ID
//   0x00040000: 有耗时
//   0x00080000: 有时间戳
//   0x00100000: 64位长度字段

// 可选字段...
uint32_t/uint64_t length;  // Chunk 数据长度
byte data[length];         // Chunk 数据
```

---

## 二、三条解析路线

本项目支持三种方式解析 RDC 文件：

```
┌─────────────────────────────────────────────────────────────────────┐
│                         RDC 解析路线图                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐                                                    │
│  │   .rdc 文件  │                                                    │
│  └──────┬──────┘                                                    │
│         │                                                           │
│         ├─────────────────┬─────────────────┬──────────────────┐    │
│         ▼                 ▼                 ▼                  │    │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐          │    │
│  │  Route A    │   │  Route B    │   │  Route C    │          │    │
│  │  XML 静态   │   │ ReplayCtrl  │   │  二进制     │          │    │
│  │  (推荐)     │   │ (需GPU)     │   │  (实验性)   │          │    │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘          │    │
│         │                 │                 │                  │    │
│         ▼                 ▼                 ▼                  │    │
│  renderdoccmd     ReplayController   Python struct            │    │
│  convert → XML    OpenCapture()      直接解析二进制            │    │
│         │                 │                 │                  │    │
│         ▼                 ▼                 ▼                  │    │
│  RdcXmlParser     GetTextures()      binary_parser.py         │    │
│  parse_rdc_xml()  GetBuffers()       read_header()            │    │
│         │                 │                 │                  │    │
│         └────────┬────────┴────────┬────────┘                  │    │
│                  ▼                 ▼                           │    │
│           ┌───────────┐    ┌───────────────┐                   │    │
│           │CaptureData│    │ 像素/顶点数据 │                   │    │
│           │  (JSON)   │    │    (PNG)      │                   │    │
│           └───────────┘    └───────────────┘                   │    │
└─────────────────────────────────────────────────────────────────────┘
```

### Route A: XML 静态解析（推荐 / 无需 GPU）

**流程**：
```
.rdc → renderdoccmd convert -c xml → .xml → RdcXmlParser → CaptureData
```

**入口函数**：
- `parsers/rdc_loader.py::load_rdc_file()` — 主入口
- `parsers/rdc_xml_parser.py::parse_rdc_xml()` — XML 解析

**能获取的数据**：

| 数据 | 可获取 | 说明 |
|------|--------|------|
| Draw Call 列表 | ✅ | 完整事件流 |
| 纹理元数据 | ✅ | 名称/尺寸/格式/ResourceId |
| Buffer 元数据 | ✅ | 名称/大小/用途 |
| Shader 信息 | ✅ | SPIR-V 二进制（通过 ZIP 导出） |
| 管线状态 | ✅ | Viewport/Scissor/BlendState |
| **纹理像素数据** | ⚠️ | 原始格式，需自行解码压缩格式 |

**使用示例**：
```python
from parsers.rdc_loader import load_capture_file

data = load_capture_file("capture.rdc")
print(f"Draw Calls: {len(data['events'])}")
print(f"Textures: {len(data['textures'])}")
```

---

### Route B: ReplayController 回放（需 GPU）

**流程**：
```
.rdc → renderdoc.OpenCaptureFile() → ReplayController → GetTextures() / SaveTexture()
```

**入口函数**：
- `export_textures.py::main()` — 纹理导出
- `extractors/replay_wrapper.py::open_capture()` — 封装入口

**能获取的数据**：

| 数据 | 可获取 | 说明 |
|------|--------|------|
| 所有 Route A 数据 | ✅ | |
| **纹理 PNG/JPG** | ✅ | 自动解码任何格式 |
| 渲染结果 | ✅ | 任意 EID 的帧缓冲 |
| 管线快照 | ✅ | 任意 EID 的完整状态 |
| Mesh 数据 | ✅ | 顶点/索引缓冲 |

**使用示例**：
```python
import renderdoc as rd

cap = rd.OpenCaptureFile()
cap.OpenFile("capture.rdc", "", None)
controller = cap.OpenCapture(rd.ReplayOptions(), None)

textures = controller.GetTextures()
for tex in textures:
    controller.SaveTexture(rd.TextureSave(tex.resourceId), f"{tex.name}.png")

controller.Shutdown()
```

**限制**：
- 需要与捕获时兼容的 GPU
- macOS 无法回放 Windows D3D12 捕获
- 无 GPU 的 CI 环境无法使用

---

### Route C: 二进制直接解析（实验性）

**流程**：
```
.rdc → Python struct 模块 → 直接解析 Header/Sections/Chunks
```

**入口函数**：
- `parsers/binary_parser.py::parse_rdc_header()` — Header 解析
- `parsers/binary_parser.py::list_sections()` — Section 列表

**能获取的数据**：

| 数据 | 可获取 | 说明 |
|------|--------|------|
| Header 信息 | ✅ | Magic/Version/Driver |
| Section 索引 | ✅ | 类型/偏移/大小 |
| Chunk 扫描 | ⚠️ | 需要理解各 API 的序列化格式 |
| 原始二进制 | ✅ | 需自行解压 LZ4/Zstd |

**使用场景**：
- 快速检测文件有效性
- 提取缩略图而不解析整个文件
- 研究 RDC 格式

---

## 三、关键数据结构

### 3.1 纹理数据存储链路（Vulkan）

```
vkCreateImage (Chunk 1015)
    ├── ResourceId: 360
    ├── format: VK_FORMAT_R8G8B8A8_UNORM
    └── extent: {2048, 2048, 1}
            │
            ▼
vkAllocateMemory (Chunk 1003)
    ├── ResourceId: 116
    └── allocationSize: 16777216 (16 MB)
            │
            ▼
vkBindImageMemory (Chunk 1043)
    └── image=360 → memory=116, offset=0
            │
            ▼
InitialContents (Chunk 3, type=eResDeviceMemory)
    ├── id: 116
    ├── ContentsSize: 16777216
    └── Contents: buffer_index=425
            │
            ▼
      ZIP 文件中的 "000425" 文件 = 原始像素数据
```

### 3.2 CaptureData 格式（项目统一格式）

```python
{
    "schema_version": "1.0",
    "meta": {
        "driver": "Vulkan",
        "gpu": "Mali-G710",
        "capture_time": "2025-01-31T10:00:00Z"
    },
    "resources": {
        "textures": {
            "360": {
                "name": "Albedo",
                "width": 2048,
                "height": 2048,
                "format": "VK_FORMAT_R8G8B8A8_UNORM",
                "size_bytes": 16777216,
                "mips": 11
            }
        },
        "buffers": {...},
        "shaders": {...}
    },
    "events": [
        {"eventId": 100, "name": "vkCmdDraw", "drawIndex": 0, ...},
        ...
    ],
    "summary": {
        "draw_call_count": 150,
        "total_triangles": 500000,
        "texture_memory_mb": 128.5
    }
}
```

---

## 四、代码入口快速索引

| 任务 | 文件 | 函数 |
|------|------|------|
| 加载 RDC/XML/JSON | `parsers/rdc_loader.py` | `load_capture_file()` |
| 转换 RDC → XML | `parsers/rdc_loader.py` | `convert_rdc_to_xml()` |
| 解析 XML | `parsers/rdc_xml_parser.py` | `parse_rdc_xml()` |
| 导出纹理 (需 GPU) | `export_textures.py` | `main()` |
| 提取 Shader | `extract_shaders.py` | `main()` |
| 二进制解析 | `parsers/binary_parser.py` | `parse_rdc_header()` |
| 分析主入口 | `main.py` | `AnalysisPipeline.run()` |

---

## 五、核心源码位置（RenderDoc C++）

| 功能 | 源文件 |
|------|--------|
| RDC 文件读写 | `renderdoc/serialise/rdcfile.cpp` |
| Section 类型定义 | `renderdoc/api/replay/replay_enums.h:120` |
| SystemChunk 枚举 | `renderdoc/core/core.h:216` |
| Vulkan Chunk 枚举 | `renderdoc/driver/vulkan/vk_common.h` |
| Vulkan 初始状态 | `renderdoc/driver/vulkan/vk_initstate.cpp` |
| XML 导出逻辑 | `renderdoc/serialise/codecs/xml_codec.cpp` |
| Replay 入口 | `renderdoc/replay/replay_controller.cpp` |

---

## 六、解析路线选择指南

| 路线 | GPU 需求 | 推荐场景 |
|------|----------|----------|
| **Route A (XML)** | ❌ 无需 | 日常分析、CI 环境、第一阶段（无手机） |
| **Route B (Replay)** | ✅ 需要 | 纹理导出、第二阶段（接入手机） |
| **Route C (Binary)** | ❌ 无需 | 格式研究、快速文件检测 |

---

## 附录：相关文档

- [RDC 结构深度分析](./RDC_STRUCTURE_DEEP_ANALYSIS.md) — InitialContents 与资源绑定详解
- [DOC_INDEX.md](./DOC_INDEX.md) — 文档总索引
- [WORK_SUMMARY_2025-01-21.md](./WORK_SUMMARY_2025-01-21.md) — 项目进度总览
