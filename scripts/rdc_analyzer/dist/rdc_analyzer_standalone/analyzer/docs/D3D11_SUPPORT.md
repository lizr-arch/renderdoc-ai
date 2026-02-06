# D3D11 纹理提取支持

> 从 RenderDoc D3D11 捕获文件中离线提取纹理

## 概述

本工具支持从 D3D11 RenderDoc 捕获文件中提取纹理，无需 GPU 回放。通过解析 RDC 导出的 XML+ZIP 格式，直接提取纹理数据并转换为 PNG。

### 支持的格式 (v1.5.1)

> **最新验证**: 12/12 纹理成功提取 (100%)

| 类别 | 格式 |
|------|------|
| **未压缩 RGBA** | R8G8B8A8_UNORM, B8G8R8A8_UNORM, R8G8B8A8_SRGB 等 |
| **浮点 HDR** | R16G16B16A16_FLOAT, R32G32B32A32_FLOAT, **R11G11B10_FLOAT** |
| **单/双通道** | R8_UNORM, R16_FLOAT, **R16G16_FLOAT**, R32_FLOAT 等 |
| **BC 压缩** | BC1 (DXT1), BC2 (DXT3), BC3 (DXT5), BC4, BC5, BC6H, BC7 |
| **深度/模板** | D32_FLOAT, D24_UNORM_S8_UINT, **D32_FLOAT_S8X24_UINT**, **R32G8X24_TYPELESS** ✅ |

> **v1.5.1 新增**: R16G16_FLOAT, R11G11B10_FLOAT, D32_FLOAT_S8X24_UINT 现已完整支持解码和可视化

## 快速开始

### 1. 导出 RDC 为 XML+ZIP

在 RenderDoc 中：
```
File → Export Capture As XML
```

这将生成：
- `capture.xml` - 序列化的 API 调用
- `capture/` 或 `capture.zip` - 二进制资源数据

### 2. 运行提取

```bash
# 使用批量导出 CLI（自动检测 API 类型）
py -3 batch_export_textures.py capture.xml -o ./textures

# 或使用专用 D3D11 提取器
py -3 -m extractors.d3d11_texture_extractor capture.xml capture.zip -o ./textures
```

### 3. 查看结果

```bash
# 生成 HTML 画廊
py -3 batch_export_textures.py capture.xml -o ./textures --gallery

# 打开 gallery.html 预览所有纹理
```

## 技术架构

### D3D11 vs Vulkan 差异

| 特性 | Vulkan | D3D11 |
|------|--------|-------|
| 纹理创建 | `vkCreateImage` | `ID3D11Device::CreateTexture2D` |
| 内存绑定 | `vkBindImageMemory` | **不需要** |
| 数据存储 | 绑定到 `VkDeviceMemory` 偏移 | 直接存储在纹理资源 |
| 子资源 | 线性内存块 | 每个 Mip/Array 独立 buffer |

### D3D11 InitialContents 结构

```xml
<chunk name="Internal::Initial Contents">
    <ResourceId name="id">123</ResourceId>
    <uint name="NumSubresources">11</uint>
    <bool name="OmittedContents">false</bool>
    
    <!-- Mip 0 -->
    <uint name="RowPitch">8192</uint>
    <buffer name="SubresourceContents">45</buffer>
    
    <!-- Mip 1 -->
    <uint name="RowPitch">4096</uint>
    <buffer name="SubresourceContents">46</buffer>
    
    <!-- ... -->
</chunk>
```

### 代码结构

```
scripts/rdc_analyzer/
├── decoders/
│   ├── dxgi_format_map.py      # DXGI 格式映射
│   └── texture_decoder.py      # 通用纹理解码
├── parsers/
│   └── d3d11_texture_parser.py # D3D11 XML 解析
├── extractors/
│   └── d3d11_texture_extractor.py  # D3D11 提取引擎
└── exporters/
    └── texture_batch_exporter.py   # 集成导出（自动检测 API）
```

## API 参考

### D3D11TextureInfo

```python
@dataclass
class D3D11TextureInfo:
    resource_id: int            # 资源 ID
    width: int                  # 宽度
    height: int                 # 高度
    depth: int = 1              # 深度 (3D 纹理)
    mip_levels: int = 1         # Mip 级别数
    array_size: int = 1         # 数组大小
    format: str = ""            # DXGI 格式
    subresources: List[D3D11SubresourceData]  # 子资源列表
```

### 解析 XML

```python
from parsers.d3d11_texture_parser import parse_d3d11_xml

textures, api_type = parse_d3d11_xml(Path("capture.xml"))
# textures: Dict[int, D3D11TextureInfo]
# api_type: "D3D11"
```

### 提取纹理

```python
from extractors.d3d11_texture_extractor import D3D11TextureExtractor

extractor = D3D11TextureExtractor(
    xml_path=Path("capture.xml"),
    zip_path=Path("capture.zip"),
    output_dir=Path("./output"),
)
extractor.parse()
stats = extractor.extract_all(min_size=64, max_count=100)
```

## DXGI 格式映射

完整映射表见 `decoders/dxgi_format_map.py`，核心格式：

### 未压缩格式

| DXGI 格式 | 解码器 | 每像素字节 | 说明 |
|-----------|--------|------------|------|
| DXGI_FORMAT_R8G8B8A8_UNORM | RGBA8 | 4 | 标准 RGBA |
| DXGI_FORMAT_B8G8R8A8_UNORM | BGRA8 | 4 | 通道交换 |
| DXGI_FORMAT_R8_UNORM | R8 | 1 | 灰度 |
| DXGI_FORMAT_R16G16_FLOAT | RG16F | 4 | 双通道 HDR |
| DXGI_FORMAT_R16G16B16A16_FLOAT | RGBA16F | 8 | 四通道 HDR |
| DXGI_FORMAT_R32G32B32A32_FLOAT | RGBA32F | 16 | 高精度 HDR |
| DXGI_FORMAT_R11G11B10_FLOAT | R11G11B10F | 4 | **打包 HDR** |

### BC 压缩格式

| DXGI 格式 | 解码器 | 每像素字节 |
|-----------|--------|------------|
| DXGI_FORMAT_BC1_UNORM | BC1 | 0.5 |
| DXGI_FORMAT_BC3_UNORM | BC3 | 1 |
| DXGI_FORMAT_BC7_UNORM | BC7 | 1 |

### 深度/模板格式 (v1.5.1 新增)

| DXGI 格式 | 解码器 | 每像素字节 | 可视化输出 |
|-----------|--------|------------|------------|
| DXGI_FORMAT_D32_FLOAT | D32F | 4 | R=深度灰度 |
| DXGI_FORMAT_D24_UNORM_S8_UINT | D24S8 | 4 | R=深度, G=模板 |
| DXGI_FORMAT_D32_FLOAT_S8X24_UINT | D32S8 | 8 | R=深度, G=模板 |
| DXGI_FORMAT_R32G8X24_TYPELESS | D32S8 | 8 | 自动映射为 D32S8 |

## 常见问题

### Q: 为什么有些纹理显示 "No initial contents"？

A: 这些纹理在捕获时没有初始数据（如渲染目标、动态纹理）。只有在帧开始时已有数据的纹理才能提取。

### Q: 支持 D3D12 吗？

A: 目前不支持。D3D12 使用 `CreateCommittedResource`，数据结构更复杂，计划在未来版本添加。

### Q: 如何处理 3D 纹理？

A: 3D 纹理 (`CreateTexture3D`) 会被识别并列出，但目前只提取第一个深度切片。

### Q: 格式不支持怎么办？

A: 使用 `--bin` 参数保存原始二进制数据：
```bash
py -3 batch_export_textures.py capture.xml -o ./output --bin --no-png
```

## 版本历史

- **v1.5.1** (2026-02) - 浮点/深度格式完整支持：R16G16_FLOAT, R11G11B10_FLOAT, D32_FLOAT_S8X24_UINT, R32G8X24_TYPELESS
- **v1.5.0** (2025-01) - 添加 D3D11 离线提取支持
- **v1.4.0** (2025-01) - 批量导出 CLI 发布
