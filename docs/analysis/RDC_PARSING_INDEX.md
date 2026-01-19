# RDC 文件解析专题索引

> **目的**: 为构建 RDC 分析 MCP/Skill 提供详细的代码入口和数据结构参考
> 
> **更新时间**: 2025-01-16
> **版本**: v2.0 - 补充完整的二进制格式和官方代码路径

---

## 1. RDC 文件二进制格式

### 1.1 完整文件布局 (官方文档: rdcfile.cpp:46-140)

```
┌─────────────────────────────────────────────────────────────────┐
│                        RDC 文件布局                              │
├─────────────────────────────────────────────────────────────────┤
│  FileHeader (32 bytes)                                          │
│    ├─ magic: uint64 = "RDOC\0\0\0\0" (8 bytes)                 │
│    ├─ version: uint32 (当前 0x00000102)                         │
│    ├─ headerLength: uint32 (从文件开头到 Section 开始)          │
│    └─ progVersion: char[16] ("1.30 xxxxxx")                    │
├─────────────────────────────────────────────────────────────────┤
│  BinaryThumbnail                                                │
│    ├─ width: uint16                                             │
│    ├─ height: uint16                                            │
│    ├─ length: uint32                                            │
│    └─ data[length]: bytes (JPG 压缩)                           │
├─────────────────────────────────────────────────────────────────┤
│  CaptureMetaData                                                │
│    ├─ machineIdent: uint64                                      │
│    ├─ driverID: uint32 (RDCDriver 枚举)                         │
│    ├─ driverNameLength: uint8                                   │
│    └─ driverName[len]: char (ASCII, 含 \0)                     │
├─────────────────────────────────────────────────────────────────┤
│  CaptureTimeBase (if version >= 0x102)                          │
│    ├─ timeBase: uint64                                          │
│    └─ timeFreq: double                                          │
├─────────────────────────────────────────────────────────────────┤
│  Section 0: BinarySectionHeader + Data                          │
│  Section 1: BinarySectionHeader + Data                          │
│  ...                                                            │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 BinarySectionHeader 结构 (rdcfile.cpp:203-227)

```cpp
struct BinarySectionHeader {
  byte isASCII;                      // 0x00 for binary, 'A' for ASCII
  byte zero[3];                      // padding
  SectionType sectionType;           // uint32_t
  uint64_t sectionCompressedLength;  // 磁盘上的压缩大小
  uint64_t sectionUncompressedLength;// 解压后大小
  uint64_t sectionVersion;           // Section 版本号
  SectionFlags sectionFlags;         // uint32_t: 0x2=LZ4, 0x4=Zstd
  uint32_t sectionNameLength;        // 名称长度 (含 \0)
  char name[];                       // 实际长度 = sectionNameLength
  // byte data[sectionCompressedLength]; // 紧随其后
};
// 总头部大小: 40 + sectionNameLength bytes
```

### 1.3 SectionFlags 定义 (replay_enums.h:4595-4600)

```cpp
enum class SectionFlags : uint32_t {
  NoFlags = 0x0,
  ASCIIStored = 0x1,      // ASCII 格式存储
  LZ4Compressed = 0x2,    // LZ4 压缩
  ZstdCompressed = 0x4,   // Zstd 压缩
};
```

### 1.4 SectionType 枚举 (replay_enums.h:4540-4560)

| 值 | 名称 | 说明 |
|----|------|------|
| 0 | Unknown | 未知 |
| 1 | FrameCapture | 主数据 - API 调用和资源 |
| 2 | ResolveDatabase | 符号解析数据库 |
| 3 | Bookmarks | 用户书签 |
| 4 | Notes | 用户注释 |
| 5 | ResourceRenames | 资源重命名映射 |
| 6 | AMDRGPProfile | AMD RGP 性能数据 |
| 7 | ExtendedThumbnail | 高分辨率缩略图 |
| 8 | EmbeddedLogfile | 嵌入的日志文件 |
| 9 | EditedShaders | 用户编辑过的 Shader |
| 10 | D3D12Core | D3D12 Core DLL |
| 11 | D3D12SDKLayers | D3D12 SDK Layers |

---

## 2. LZ4 压缩格式 (lz4io.cpp)

### 2.1 RenderDoc 自定义 LZ4 流格式

RenderDoc **不使用标准 LZ4 帧格式**，而是自定义的分块流格式：

```
┌─────────────────────────────────────────────────────────────────┐
│  Block 0                                                        │
│    ├─ compSize: int32_t (压缩块大小)                            │
│    └─ compData[compSize]: bytes (LZ4 压缩数据)                  │
├─────────────────────────────────────────────────────────────────┤
│  Block 1                                                        │
│    ├─ compSize: int32_t                                         │
│    └─ compData[compSize]: bytes                                 │
├─────────────────────────────────────────────────────────────────┤
│  ...                                                            │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 关键参数

| 参数 | 值 | 说明 |
|------|----|----|
| lz4BlockSize | 1MB (1024*1024) | 每块解压后最大大小 |
| 压缩函数 | LZ4_compress_fast_continue | 使用字典的流式压缩 |
| 解压函数 | LZ4_decompress_safe_continue | 使用字典的流式解压 |

### 2.3 解压伪代码 (lz4io.cpp:263-324)

```python
def decompress_lz4_renderdoc(compressed_data, uncompressed_size):
    LZ4_BLOCK_SIZE = 1024 * 1024  # 1MB
    result = bytearray()
    offset = 0
    prev_block = b''  # 字典
    
    while offset < len(compressed_data) and len(result) < uncompressed_size:
        # 1. 读取 4 字节压缩块大小 (int32_t)
        comp_size = struct.unpack_from('<i', compressed_data, offset)[0]
        offset += 4
        
        # 2. 读取压缩数据
        comp_block = compressed_data[offset:offset + comp_size]
        offset += comp_size
        
        # 3. 解压 (使用前一块作为字典)
        decomp_block = lz4.block.decompress(
            comp_block, 
            uncompressed_size=LZ4_BLOCK_SIZE,
            dict=prev_block  # 关键: 字典上下文
        )
        
        result.extend(decomp_block)
        prev_block = decomp_block  # 更新字典
    
    return bytes(result)
```

---

## 3. Chunk 二进制格式 (serialiser.h:103-111)

### 3.1 Chunk 控制字

每个 Chunk 以一个 32 位控制字开始：

```
┌─────────────────────────────────────────────────────────────────┐
│ uint32_t control                                                │
│  ├─ bits 0-15:  ChunkID (16 位)                                │
│  ├─ bit 16:     ChunkCallstack (有调用栈)                       │
│  ├─ bit 17:     ChunkThreadID (有线程 ID)                       │
│  ├─ bit 18:     ChunkDuration (有持续时间)                      │
│  ├─ bit 19:     ChunkTimestamp (有时间戳)                       │
│  └─ bit 20:     Chunk64BitSize (使用 64 位长度)                 │
└─────────────────────────────────────────────────────────────────┘
```

```cpp
enum ChunkFlags {
  ChunkIndexMask = 0x0000FFFF,  // 低 16 位 = Chunk ID
  ChunkCallstack = 0x00010000,  // bit 16
  ChunkThreadID  = 0x00020000,  // bit 17
  ChunkDuration  = 0x00040000,  // bit 18
  ChunkTimestamp = 0x00080000,  // bit 19
  Chunk64BitSize = 0x00100000,  // bit 20
};
```

### 3.2 Chunk 完整结构 (serialiser.cpp:112-191)

```
┌─────────────────────────────────────────────────────────────────┐
│ uint32_t control                                                │
├─────────────────────────────────────────────────────────────────┤
│ [可选] Callstack (if bit 16 set)                               │
│   ├─ uint32_t numFrames                                        │
│   └─ uint64_t[numFrames] addresses                             │
├─────────────────────────────────────────────────────────────────┤
│ [可选] uint64_t threadID (if bit 17 set)                       │
├─────────────────────────────────────────────────────────────────┤
│ [可选] int64_t durationMicro (if bit 18 set)                   │
├─────────────────────────────────────────────────────────────────┤
│ [可选] uint64_t timestampMicro (if bit 19 set)                 │
├─────────────────────────────────────────────────────────────────┤
│ uint32_t length  或  uint64_t length (if bit 20 set)           │
├─────────────────────────────────────────────────────────────────┤
│ byte payload[length]  (序列化的参数数据)                        │
├─────────────────────────────────────────────────────────────────┤
│ [padding] 对齐到 64 字节边界 (ChunkAlignment)                   │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 Chunk 对齐 (serialiser.h:1536)

```cpp
static const uint64_t ChunkAlignment = 64;
```

**重要**：每个 Chunk 读取完成后，流位置会对齐到 64 字节边界。这意味着在计算下一个 Chunk 的起始偏移时，必须执行：

```python
next_chunk_offset = ((current_offset + payload_length + 63) // 64) * 64
```

---

## 4. Chunk ID 映射表

### 4.1 SystemChunk (core.h:194-205)

所有驱动共享的系统 Chunk：

| ID | 名称 | 说明 |
|----|------|------|
| 0 | (保留) | 调试用空 chunk |
| 1 | DriverInit | 驱动初始化 |
| 2 | InitialContentsList | 初始内容列表 |
| 3 | InitialContents | 初始内容数据 |
| 4 | CaptureBegin | 捕获开始 |
| 5 | CaptureScope | 捕获范围 |
| 6 | CaptureEnd | 捕获结束 |
| 1000 | FirstDriverChunk | 驱动特定 Chunk 起始 |

### 4.2 D3D11Chunk (d3d11_common.h:273+)

从 ID=1000 开始：

| ID | 名称 | 说明 |
|----|------|------|
| 1000 | DeviceInitialisation | 设备初始化 |
| 1001 | SetResourceName | 设置资源名称 |
| 1002 | CreateSwapBuffer | 创建交换链缓冲 |
| 1003 | CreateTexture1D | 创建 1D 纹理 |
| 1004 | CreateTexture2D | 创建 2D 纹理 |
| 1005 | CreateTexture3D | 创建 3D 纹理 |
| 1006 | CreateBuffer | 创建缓冲区 |
| 1007 | CreateVertexShader | 创建顶点着色器 |
| 1012 | CreatePixelShader | 创建像素着色器 |
| 1013 | CreateComputeShader | 创建计算着色器 |
| 1032 | IASetInputLayout | 设置输入布局 |
| 1033 | IASetVertexBuffers | 设置顶点缓冲 |
| 1034 | IASetIndexBuffer | 设置索引缓冲 |
| 1035 | IASetPrimitiveTopology | 设置图元拓扑 |
| 1065 | OMSetRenderTargets | 设置渲染目标 |
| 1069 | DrawIndexedInstanced | 索引实例化绘制 |
| 1070 | DrawInstanced | 实例化绘制 |
| 1071 | DrawIndexed | 索引绘制 |
| 1072 | Draw | 直接绘制 |
| 1090 | Dispatch | 计算调度 |
| 1123 | SwapchainPresent | 交换链呈现 |

### 4.3 Vulkan/D3D12/OpenGL Chunk

- **D3D12**: `renderdoc/driver/d3d12/d3d12_common.h`
- **Vulkan**: `renderdoc/driver/vulkan/vk_common.h`
- **OpenGL**: `renderdoc/driver/gl/gl_common.h`

---

## 5. 官方解析代码路径

### 5.1 完整调用链

```
用户调用
   │
   ▼
┌──────────────────────────────────────────────────────────────────┐
│ CaptureFile::OpenFile(filename)                                  │
│ 文件: renderdoc/replay/capture_file.cpp:201-240                  │
│ 职责: 创建 RDCFile，调用 Open()                                   │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│ RDCFile::Open(path)                                              │
│ 文件: renderdoc/serialise/rdcfile.cpp:236-297                    │
│ 职责: 打开文件，创建 StreamReader，调用 Init()                    │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│ RDCFile::Init(reader)                                            │
│ 文件: renderdoc/serialise/rdcfile.cpp:309-677                    │
│ 职责:                                                            │
│   1. 读取 FileHeader (magic, version, headerLength, progVersion) │
│   2. 读取 BinaryThumbnail                                        │
│   3. 读取 CaptureMetaData (driver info)                          │
│   4. 读取 CaptureTimeBase (if version >= 0x102)                  │
│   5. 循环读取所有 Section 头，构建索引                            │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 Chunk 解析流程 (以 D3D11 为例)

```
CaptureFile::InitStructuredData()
   │
   ▼
┌──────────────────────────────────────────────────────────────────┐
│ D3D11_ProcessStructured(rdc, output)                             │
│ 文件: renderdoc/driver/d3d11/d3d11_replay.cpp:4462-4478          │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│ WrappedID3D11Device::ReadLogInitialisation(rdc, storeBuffers)    │
│ 文件: renderdoc/driver/d3d11/d3d11_device.cpp:1322-1480          │
│ 职责:                                                            │
│   1. 读取 FrameCapture Section (自动解压)                        │
│   2. 创建 ReadSerialiser                                         │
│   3. 循环: ReadChunk -> ProcessChunk -> EndChunk                 │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│ Serialiser::BeginChunk(chunkID, length)                          │
│ 文件: renderdoc/serialise/serialiser.cpp:112-191                 │
│ 职责:                                                            │
│   1. 读取 control word (chunk ID + flags)                        │
│   2. 按 flags 读取可选字段 (callstack, threadID, duration, ts)   │
│   3. 读取 length (32 或 64 位)                                   │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│ WrappedID3D11Device::ProcessChunk(ser, context)                  │
│ 文件: renderdoc/driver/d3d11/d3d11_device.cpp:1022-1200+         │
│ 职责: 根据 Chunk ID 分发到具体的序列化函数                        │
│   switch(context) {                                              │
│     case D3D11Chunk::CreateTexture2D:                            │
│       return Serialise_CreateTexture2D(ser, ...);                │
│     case D3D11Chunk::Draw:                                       │
│       // 转发到 ImmediateContext                                 │
│       return m_pImmediateContext->ProcessChunk(ser, context);    │
│   }                                                              │
└──────────────────────────────────────────────────────────────────┘
```

### 5.3 Section 读取与解压 (rdcfile.cpp:868-907)

```cpp
StreamReader* RDCFile::ReadSection(int index) const {
  // 定位到 Section 数据偏移
  FileIO::fseek64(m_File, offsetSize.dataOffset, SEEK_SET);
  
  StreamReader *fileReader = new StreamReader(m_File, diskLength);
  
  // 根据压缩标志选择解压器
  if(props.flags & SectionFlags::LZ4Compressed) {
    return new StreamReader(
      new LZ4Decompressor(fileReader, Ownership::Stream),
      props.uncompressedSize,
      Ownership::Stream
    );
  }
  else if(props.flags & SectionFlags::ZstdCompressed) {
    return new StreamReader(
      new ZSTDDecompressor(fileReader, Ownership::Stream),
      props.uncompressedSize,
      Ownership::Stream
    );
  }
  
  return fileReader;  // 未压缩
}
```

---

## 6. Python API 解析示例

### 6.1 基础解析流程

```python
import renderdoc as rd

def analyze_rdc(filepath):
    """分析 RDC 文件的基本信息"""
    
    # 1. 打开文件
    cap = rd.OpenCaptureFile()
    result = cap.OpenFile(filepath, "", None)
    
    if result != rd.ResultCode.Succeeded:
        print(f"打开失败: {result}")
        return
    
    # 2. 获取基本信息
    print(f"驱动类型: {cap.DriverName()}")
    print(f"机器标识: {cap.MachineIdent()}")
    
    # 3. 枚举 Sections
    for i in range(cap.NumSections()):
        props = cap.GetSectionProperties(i)
        print(f"Section {i}: {props.name} ({props.type})")
        print(f"  大小: {props.uncompressedSize} bytes")
    
    # 4. 创建回放控制器
    status, controller = cap.OpenCapture(rd.ReplayOptions(), None)
    
    if status != rd.ResultCode.Succeeded:
        print(f"打开回放失败: {status}")
        cap.Shutdown()
        return
    
    # 5. 获取帧信息
    frame = controller.GetFrameInfo()
    print(f"帧号: {frame.frameNumber}")
    
    # 6. 遍历绘制调用
    actions = controller.GetRootActions()
    print(f"根操作数: {len(actions)}")
    
    def print_actions(actions, indent=0):
        for action in actions:
            flags = str(action.flags)
            print(f"{'  ' * indent}EID {action.eventId}: {action.customName} [{flags}]")
            if action.children:
                print_actions(action.children, indent + 1)
    
    print_actions(actions)
    
    # 7. 获取资源列表
    textures = controller.GetTextures()
    print(f"\n纹理数量: {len(textures)}")
    for tex in textures[:5]:  # 只显示前 5 个
        print(f"  {tex.name}: {tex.width}x{tex.height} ({tex.format.name})")
    
    buffers = controller.GetBuffers()
    print(f"\n缓冲区数量: {len(buffers)}")
    for buf in buffers[:5]:
        print(f"  {buf.name}: {buf.length} bytes")
    
    # 8. 清理
    controller.Shutdown()
    cap.Shutdown()
```

### 6.2 提取特定数据

```python
def extract_textures(controller, output_dir):
    """导出所有纹理"""
    textures = controller.GetTextures()
    
    for tex in textures:
        if tex.width > 0 and tex.height > 0:
            save_data = rd.TextureSave()
            save_data.resourceId = tex.resourceId
            save_data.mip = 0
            save_data.slice.sliceIndex = 0
            save_data.destType = rd.FileType.PNG
            
            path = f"{output_dir}/{tex.name}.png"
            controller.SaveTexture(save_data, path)

def get_buffer_data(controller, buffer_id, offset=0, length=0):
    """读取缓冲区数据"""
    data = controller.GetBufferData(buffer_id, offset, length)
    return bytes(data)
```

### 6.3 遍历结构化数据

```python
def analyze_structured_data(controller):
    """分析结构化数据文件 (SDFile)"""
    sd = controller.GetStructuredFile()
    
    # 遍历所有 chunks
    for i, chunk in enumerate(sd.chunks):
        print(f"Chunk {i}: {chunk.name}")
        print(f"  类型 ID: {chunk.metadata.chunkID}")
        print(f"  字节大小: {chunk.metadata.length}")
        
        # 遍历 chunk 内的数据
        for child in chunk.data.children:
            print(f"  - {child.name}: {child.type.name}")
```

---

## 7. 关键搜索命令

```bash
# 查找 Section 类型使用
rg -n "SectionType::" renderdoc/

# 查找 Chunk 定义
rg -n "enum class.*Chunk" renderdoc/driver/

# 查找序列化入口
rg -n "SERIALISE_ELEMENT" renderdoc/driver/ | head -50

# 查找 ReadLogInitialisation
rg -n "ReadLogInitialisation" renderdoc/

# 查找资源创建
rg -n "CreateTexture|CreateBuffer" renderdoc/driver/

# 查找 Python 绑定的类
rg -n "%include.*\.h" qrenderdoc/Code/pyrenderdoc/renderdoc.i
```

---

## 8. 调试和开发技巧

### 8.1 启用调试日志

```bash
# Windows
set RENDERDOC_DEBUG_LOG=1
renderdoccmd.exe replay capture.rdc

# Linux
RENDERDOC_DEBUG_LOG=1 renderdoccmd replay capture.rdc
```

### 8.2 关键断点位置

| 断点 | 文件:行号 | 用途 |
|------|-----------|------|
| `RDCFile::Init` | `serialise/rdcfile.cpp:80` | 文件头解析 |
| `ReadSection` | `serialise/rdcfile.cpp:380` | Section 读取 |
| `CreateDevice` | `replay/replay_controller.cpp:2167` | 设备创建 |
| `ReadLogInitialisation` | 各驱动 `*_replay.cpp` | Chunk 解析 |

### 8.3 常见问题排查

| 问题 | 可能原因 | 检查位置 |
|------|----------|----------|
| 文件打开失败 | Magic 不匹配 | `rdcfile.cpp:Init()` |
| 版本不兼容 | 版本号检查 | `rdcfile.cpp:100` |
| 驱动不支持 | RDCDriver 检查 | `replay_controller.cpp:CreateDevice()` |
| Section 读取失败 | 压缩算法不支持 | `streamio.cpp` |

---

## 附录: 文件路径速查表

| 功能 | 路径 |
|------|------|
| RDC 文件解析 | `renderdoc/serialise/rdcfile.h/.cpp` |
| 流式 I/O | `renderdoc/serialise/streamio.h/.cpp` |
| 序列化模板 | `renderdoc/serialise/serialiser.h/.cpp` |
| 回放控制器 | `renderdoc/replay/replay_controller.h/.cpp` |
| 高层文件接口 | `renderdoc/replay/capture_file.cpp` |
| Section 类型枚举 | `renderdoc/api/replay/replay_enums.h:120` |
| 数据结构定义 | `renderdoc/api/replay/data_types.h` |
| D3D11 Chunk | `renderdoc/driver/d3d11/d3d11_common.h` |
| D3D12 Chunk | `renderdoc/driver/d3d12/d3d12_common.h` |
| Vulkan Chunk | `renderdoc/driver/vulkan/vk_common.h` |
| OpenGL Chunk | `renderdoc/driver/gl/gl_common.h` |
| Python SWIG | `qrenderdoc/Code/pyrenderdoc/renderdoc.i` |