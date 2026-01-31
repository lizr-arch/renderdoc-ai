# 无 GPU 纹理提取技术分析

> **更新日期**: 2026-01-31 | **状态**: 原型验证中

## 概述

本文档记录了从 RDC 文件提取纹理数据**无需 GPU 回放**的技术可行性分析。

### 核心发现

| 结论 | 说明 |
|------|------|
| **可行性** | ✅ **可行** - 通过 `GetStructuredData()` API |
| **GPU 依赖** | 不需要匹配的 GPU |
| **数据完整性** | 包含完整像素数据（取决于捕获时配置） |
| **限制** | 压缩纹理需要 CPU 解码 |

---

## 技术原理

### 1. 两条 API 路径对比

```
路径 A: GPU 回放（传统方式）
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ OpenFile()  │ -> │ OpenCapture │ -> │ GetTexture  │
│             │    │ (需要 GPU)  │    │ (GPU 渲染)  │
└─────────────┘    └─────────────┘    └─────────────┘

路径 B: 结构化数据（无 GPU）
┌─────────────┐    ┌──────────────────┐    ┌─────────────┐
│ OpenFile()  │ -> │ GetStructuredData│ -> │ 读取 buffers│
│             │    │ (纯 CPU 解析)    │    │ (原始像素)  │
└─────────────┘    └──────────────────┘    └─────────────┘
```

### 2. 关键源码证据

#### 证据 1: GetStructuredData 不需要 GPU

**文件**: `renderdoc/replay/capture_file.cpp:133-139`

```cpp
const SDFile &GetStructuredData()
{
  // decompile to structured data on demand.
  InitStructuredData();  // 自动初始化，不需要 GPU！
  return m_StructuredData;
}
```

#### 证据 2: InitStructuredData 使用 StructuredProcessor

**文件**: `renderdoc/replay/capture_file.cpp:327-355`

```cpp
RDResult CaptureFile::InitStructuredData(RENDERDOC_ProgressCallback progress)
{
  if(m_StructuredData.chunks.empty())
  {
    if(m_RDC && m_RDC->SectionIndex(SectionType::FrameCapture) >= 0)
    {
      StructuredProcessor proc = RenderDoc::Inst().GetStructuredProcessor(m_RDC->GetDriver());
      // ...
      if(proc)
        result = proc(m_RDC, m_StructuredData);  // 纯软件处理！
    }
  }
  return RDResult();
}
```

#### 证据 3: D3D11 StructuredProcessor 使用 NULL 设备

**文件**: `renderdoc/driver/d3d11/d3d11_replay.cpp:4464-4480`

```cpp
RDResult D3D11_ProcessStructured(RDCFile *rdc, SDFile &output)
{
  WrappedID3D11Device device(NULL, D3D11InitParams());  // NULL 设备！
  
  int sectionIdx = rdc->SectionIndex(SectionType::FrameCapture);
  
  device.SetStructuredExport(rdc->GetSectionProperties(sectionIdx).version);
  RDResult result = device.ReadLogInitialisation(rdc, true);  // 结构化导出模式
  
  if(result == ResultCode::Succeeded)
    device.GetStructuredFile()->Swap(output);
  
  return result;
}
```

#### 证据 4: 纹理数据存储在 SDFile.buffers

**文件**: `renderdoc/serialise/serialiser.h:363-377`

```cpp
if(ExportStructure())
{
  if(m_ExportBuffers)
  {
    SDObject &obj = *m_StructureStack.back();
    
    obj.data.basic.u = m_StructuredFile->buffers.size();  // buffer 索引
    
    bytebuf *alloc = new bytebuf;
    alloc->resize((size_t)byteSize);
    if(el)
      memcpy(alloc->data(), el, (size_t)byteSize);
    
    m_StructuredFile->buffers.push_back(alloc);  // 添加到 buffers
  }
}
```

---

## 数据结构

### SDFile 结构

```cpp
struct SDFile {
  StructuredChunkList chunks;   // 所有 chunk（包括 InitialContents）
  StructuredBufferList buffers; // 二进制缓冲区（包括纹理像素）
  uint64_t version;
};
```

### Chunk 与 Buffer 关联

```
SDFile
├── chunks[]
│   ├── Chunk[0]: "CreateTexture2D"
│   │   └── children: Texture2D_Desc {...}
│   ├── Chunk[1]: "InitialContents"
│   │   └── children:
│   │       ├── ResourceId: 12345
│   │       ├── RowPitch: 4096
│   │       └── SubresourceContents: buffer_idx=7  ← 索引到 buffers[7]
│   └── ...
└── buffers[]
    ├── buffers[0]: byte[] (某资源数据)
    ├── ...
    └── buffers[7]: byte[] (纹理像素数据)  ← 被 Chunk[1] 引用
```

---

## 纹理数据格式

### D3D11 Texture2D 序列化

**文件**: `renderdoc/driver/d3d11/d3d11_initstate.cpp`

```cpp
// 对于每个 subresource (mip level / array slice)
for(UINT sub = 0; sub < NumSubresources; sub++)
{
  SERIALISE_ELEMENT(RowPitch);            // 每行字节数
  SERIALISE_ELEMENT_ARRAY(SubresourceContents, ContentsLength);  // 像素数据
}
```

### 简单格式示例 (R8G8B8A8_UNORM)

```
纹理尺寸: 256x256
格式: R8G8B8A8_UNORM (4 bytes/pixel)
RowPitch: 256 * 4 = 1024 bytes
ContentLength: 256 * 1024 = 262144 bytes

Buffer 布局:
┌────────────────────────────────┐
│ Row 0: R G B A R G B A ...     │ 1024 bytes
│ Row 1: R G B A R G B A ...     │ 1024 bytes
│ ...                            │
│ Row 255: R G B A R G B A ...   │ 1024 bytes
└────────────────────────────────┘
Total: 262144 bytes
```

---

## Python 原型脚本

### 位置
`scripts/rdc_analyzer/extract_texture_nogpu.py`

### 用法
```bash
# 基本用法
python extract_texture_nogpu.py capture.rdc

# 分析 chunks 结构
python extract_texture_nogpu.py capture.rdc --analyze-chunks

# 导出所有 buffers
python extract_texture_nogpu.py capture.rdc --dump-buffers -o output/

# 输出 JSON 分析
python extract_texture_nogpu.py capture.rdc -j analysis.json
```

### 核心代码

```python
import renderdoc as rd

# 初始化
rd.InitialiseReplay(rd.GlobalEnvironment(), [])

# 打开文件（不需要 OpenCapture！）
cap = rd.OpenCaptureFile()
cap.OpenFile('capture.rdc', '', None)

# 获取结构化数据（无 GPU）
sd_file = cap.GetStructuredData()

# 访问数据
print(f"Chunks: {len(sd_file.chunks)}")
print(f"Buffers: {len(sd_file.buffers)}")

# 遍历 buffers
for i, buf in enumerate(sd_file.buffers):
    print(f"Buffer {i}: {len(buf)} bytes")
    
# 清理
cap.Shutdown()
rd.ShutdownReplay()
```

---

## 待解决问题

### 1. Chunk-Buffer 映射

需要解析 chunk 结构来找到纹理资源与 buffer 的对应关系。

### 2. 格式元数据

需要从 `CreateTexture2D` 等 chunk 中提取：
- 纹理格式 (DXGI_FORMAT / VkFormat)
- 尺寸 (Width, Height, Depth)
- Mip levels
- Array size

### 3. 压缩格式解码

对于 BC/ASTC/ETC 等压缩格式，需要：
- 识别压缩格式
- 实现 CPU 解压算法（或使用现有库）

---

## 下一步

1. [ ] 在实际 RDC 上测试脚本
2. [ ] 解析 InitialContents chunk 结构
3. [ ] 建立 ResourceId → Buffer 映射
4. [ ] 实现 R8G8B8A8 格式到 PNG 转换
5. [ ] 添加 BC 压缩格式支持

---

## 参考文件

| 文件 | 说明 |
|------|------|
| `renderdoc/replay/capture_file.cpp` | CaptureFile API 实现 |
| `renderdoc/api/replay/structured_data.h` | SDFile/SDChunk 定义 |
| `renderdoc/serialise/serialiser.h` | 序列化器，buffer 存储逻辑 |
| `renderdoc/driver/d3d11/d3d11_initstate.cpp` | D3D11 InitialContents 序列化 |
| `renderdoc/driver/d3d11/d3d11_replay.cpp` | D3D11_ProcessStructured 实现 |
