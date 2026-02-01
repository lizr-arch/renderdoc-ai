# 纹理解码器模块文档

> **版本**: 1.5.0 | **更新日期**: 2026-02-01 | **维护**: Codex Agent
>
> **关键词**: 纹理, 解码, BCn, ASTC, ETC2, Vulkan, D3D11, PNG, 格式转换

---

## 概述

`scripts/rdc_analyzer/decoders/` 模块提供纹理压缩格式的 CPU 解码功能，可将游戏中的压缩纹理数据转换为标准 PNG 图像。

### 特性

- ✅ **76 种纹理格式支持** (v1.5.0)
- ✅ **跨平台**：Desktop (BCn) + Mobile (ASTC/ETC2) + **D3D11 (DXGI)** + **Vulkan**
- ✅ **纯 Python BCn 实现**：无需额外依赖
- ✅ **可选移动端支持**：通过 `texture2ddecoder` 库扩展

---

## 快速开始

### 安装依赖

```bash
# 必需 (PNG 输出)
pip install Pillow

# 可选 (移动端格式)
pip install texture2ddecoder
```

### 基本用法

```python
from scripts.rdc_analyzer.decoders import (
    decode_texture,
    save_as_png,
    get_supported_formats,
)

# 1. 解码压缩纹理
rgba_data = decode_texture(
    data=compressed_bytes,      # 压缩纹理数据
    width=1024,                 # 纹理宽度
    height=1024,                # 纹理高度
    format_name='BC7'           # 格式名称
)

# 2. 保存为 PNG
save_as_png(rgba_data, 1024, 1024, 'output.png')

# 3. 查看支持的格式
print(get_supported_formats())  # ['BC1', 'BC2', ..., 'ASTC_4x4', ...]
```

---

## 文件结构

```
scripts/rdc_analyzer/decoders/
├── __init__.py              # 模块入口，导出公共 API
├── texture_decoder.py       # 核心调度器，格式注册表
├── texture_metadata.py      # 纹理元数据结构定义
├── bc1_decoder.py           # BC1 (DXT1) 解码
├── bc2_decoder.py           # BC2 (DXT3) 解码
├── bc3_decoder.py           # BC3 (DXT5) 解码
├── bc4_decoder.py           # BC4 单通道解码
├── bc5_decoder.py           # BC5 双通道解码
├── bc6h_decoder.py          # BC6H HDR 解码
├── bc7_decoder.py           # BC7 高质量解码
├── astc_decoder.py          # ASTC 解码 (需要 texture2ddecoder)
└── etc_decoder.py           # ETC/PVRTC/ATC 解码 (需要 texture2ddecoder)
```

---

## 模块详解

### 1. `__init__.py` - 模块入口

**作用**: 统一导出公共 API，触发所有解码器注册

**导出的符号**:

| 名称 | 类型 | 说明 |
|------|------|------|
| `decode_texture()` | 函数 | 解码压缩纹理为 RGBA |
| `save_as_png()` | 函数 | 保存 RGBA 数据为 PNG |
| `get_supported_formats()` | 函数 | 获取支持的格式列表 |
| `check_mobile_support()` | 函数 | 检查移动端格式是否可用 |
| `get_format_categories()` | 函数 | 按类别分组格式 |
| `TextureDecodeError` | 异常 | 解码错误 |

---

### 2. `texture_decoder.py` - 核心调度器

**作用**: 格式注册表管理、格式名称标准化、解码调度

#### 主要函数

##### `decode_texture(data, width, height, format_name, apply_srgb=True) -> bytes`

解码压缩纹理为 RGBA 像素数据。

| 参数 | 类型 | 说明 |
|------|------|------|
| `data` | bytes | 压缩纹理原始数据 |
| `width` | int | 纹理宽度（像素） |
| `height` | int | 纹理高度（像素） |
| `format_name` | str | 格式名称（支持 Vulkan/DXGI 格式字符串） |
| `apply_srgb` | bool | 是否应用 SRGB 转换 |

**返回**: `bytes` - RGBA8 像素数据 (width × height × 4 字节)

**示例**:
```python
# 支持多种格式字符串
rgba = decode_texture(data, 512, 512, 'VK_FORMAT_BC7_UNORM_BLOCK')
rgba = decode_texture(data, 512, 512, 'DXGI_FORMAT_BC7_UNORM')
rgba = decode_texture(data, 512, 512, 'BC7')  # 简写也可以
```

---

##### `save_as_png(rgba_data, width, height, output_path, flip_vertical=False) -> Path`

将 RGBA 像素数据保存为 PNG 文件。

| 参数 | 类型 | 说明 |
|------|------|------|
| `rgba_data` | bytes | RGBA8 像素数据 |
| `width` | int | 图像宽度 |
| `height` | int | 图像高度 |
| `output_path` | Path/str | 输出文件路径 |
| `flip_vertical` | bool | 是否垂直翻转（OpenGL 纹理需要） |

**返回**: `Path` - 保存的文件路径

---

##### `normalize_format_name(format_name) -> str`

将 Vulkan/DXGI 格式字符串标准化为内部格式名。

| 输入示例 | 输出 |
|----------|------|
| `VK_FORMAT_BC7_UNORM_BLOCK` | `BC7` |
| `VK_FORMAT_ASTC_4x4_SRGB_BLOCK` | `ASTC_4x4` |
| `VK_FORMAT_ETC2_R8G8B8_UNORM_BLOCK` | `ETC2_RGB` |
| `DXGI_FORMAT_BC1_UNORM` | `BC1` |

---

##### `check_mobile_support() -> Tuple[bool, str]`

检查移动端格式支持状态。

**返回**:
- `(True, "texture2ddecoder v1.0.6 installed")` - 已安装
- `(False, "Mobile formats unavailable. Run: pip install ...")` - 未安装

---

##### `get_format_categories() -> Dict[str, List[str]]`

按类别分组返回支持的格式。

```python
{
    'bcn': ['BC1', 'BC2', 'BC3', 'BC4', 'BC5', 'BC6H', 'BC7', ...],
    'astc': ['ASTC_4x4', 'ASTC_5x5', ...],
    'etc': ['ETC1', 'ETC2_RGB', 'EAC_R11', ...],
    'pvrtc_atc': ['PVRTC_4BPP', 'ATC_RGB', ...],
    'other': ['UNCOMPRESSED', 'R8_UNORM']
}
```

---

### 3. `texture_metadata.py` - 元数据结构

**作用**: 定义纹理元数据 dataclass，用于记录解码上下文

```python
@dataclass
class TextureMetadata:
    resource_id: int              # 资源 ID
    name: str                     # 纹理名称
    width: int                    # 宽度
    height: int                   # 高度
    depth: int = 1                # 深度（3D 纹理）
    array_size: int = 1           # 数组大小
    mip_levels: int = 1           # Mipmap 层级数
    format: str = ""              # 格式字符串
    dimension: str = "2D"         # 维度 (1D/2D/3D/Cube)
    is_srgb: bool = False         # 是否 SRGB
    byte_size: int = 0            # 数据大小
    sample_count: int = 1         # 采样数（MSAA）
```

---

### 4. BCn 解码器系列 (纯 Python)

这些解码器无需额外依赖，直接用 Python 实现。

| 文件 | 格式 | 压缩比 | 用途 |
|------|------|--------|------|
| `bc1_decoder.py` | BC1/DXT1 | 8:1 | 不透明纹理、有 1-bit Alpha |
| `bc2_decoder.py` | BC2/DXT3 | 4:1 | 锐利 Alpha 边缘（UI） |
| `bc3_decoder.py` | BC3/DXT5 | 4:1 | 平滑 Alpha 渐变 |
| `bc4_decoder.py` | BC4 | 2:1 | 单通道（高度图、遮罩） |
| `bc5_decoder.py` | BC5 | 2:1 | 双通道（法线贴图 RG） |
| `bc6h_decoder.py` | BC6H | 6:1 | HDR 纹理（天空盒、IBL） |
| `bc7_decoder.py` | BC7/BPTC | 4:1 | 高质量 RGBA |

#### BC1 解码器示例

```python
from scripts.rdc_analyzer.decoders.bc1_decoder import decode_bc1

# 输入: BC1 压缩数据
# - 每 4x4 像素块 = 8 字节
# - 总大小 = ceil(width/4) * ceil(height/4) * 8

rgba = decode_bc1(compressed_data, width=512, height=512)
# 输出: 512 * 512 * 4 = 1,048,576 字节 RGBA
```

#### BC6H 解码器 (HDR)

BC6H 是 HDR 格式，输出会经过 Reinhard 色调映射转换为 LDR。

```python
from scripts.rdc_analyzer.decoders.bc6h_decoder import decode_bc6h

# 默认使用 unsigned half-float (UF16)
rgba = decode_bc6h(hdr_data, 1024, 1024)

# 有符号格式 (SF16)
rgba = decode_bc6h(hdr_data, 1024, 1024, signed=True)
```

---

### 5. `astc_decoder.py` - ASTC 解码

**作用**: 封装 `texture2ddecoder` 库的 ASTC 解码功能

**依赖**: `pip install texture2ddecoder`

**支持的块大小**: 14 种
- 4x4, 5x4, 5x5, 6x5, 6x6
- 8x5, 8x6, 8x8
- 10x5, 10x6, 10x8, 10x10
- 12x10, 12x12

```python
from scripts.rdc_analyzer.decoders import decode_texture

# ASTC 格式会自动从格式字符串解析块大小
rgba = decode_texture(data, 512, 512, 'VK_FORMAT_ASTC_8x8_UNORM_BLOCK')
rgba = decode_texture(data, 512, 512, 'ASTC_4x4')  # 简写
```

---

### 6. `etc_decoder.py` - ETC/PVRTC/ATC 解码

**作用**: 封装移动端压缩格式解码

**依赖**: `pip install texture2ddecoder`

| 格式族 | 具体格式 | 平台 |
|--------|----------|------|
| ETC1 | ETC1 | Android (OpenGL ES 2.0) |
| ETC2 | ETC2_RGB, ETC2_RGBA1, ETC2_RGBA8 | Android (OpenGL ES 3.0) |
| EAC | EAC_R11, EAC_RG11, ±SIGNED 变体 | Android (法线/高度图) |
| PVRTC | PVRTC_2BPP, PVRTC_4BPP | iOS (PowerVR) |
| ATC | ATC_RGB, ATC_RGBA | Qualcomm Adreno |

```python
from scripts.rdc_analyzer.decoders import decode_texture

# Android ETC2
rgba = decode_texture(data, 512, 512, 'VK_FORMAT_ETC2_R8G8B8A8_UNORM_BLOCK')

# iOS PVRTC
rgba = decode_texture(data, 512, 512, 'PVRTC_4BPP')

# Qualcomm ATC
rgba = decode_texture(data, 512, 512, 'ATC_RGBA')
```

---

## 支持的格式完整列表

### Desktop (BCn) - 9 种

| 内部名 | Vulkan 格式 | DXGI 格式 |
|--------|-------------|-----------|
| BC1 | VK_FORMAT_BC1_*_BLOCK | DXGI_FORMAT_BC1_* |
| BC2 | VK_FORMAT_BC2_*_BLOCK | DXGI_FORMAT_BC2_* |
| BC3 | VK_FORMAT_BC3_*_BLOCK | DXGI_FORMAT_BC3_* |
| BC4 | VK_FORMAT_BC4_*_BLOCK | DXGI_FORMAT_BC4_* |
| BC5 | VK_FORMAT_BC5_*_BLOCK | DXGI_FORMAT_BC5_* |
| BC6H | VK_FORMAT_BC6H_*_BLOCK | DXGI_FORMAT_BC6H_* |
| BC6H_UF16 | (无符号变体) | |
| BC6H_SF16 | (有符号变体) | |
| BC7 | VK_FORMAT_BC7_*_BLOCK | DXGI_FORMAT_BC7_* |

### Mobile ASTC - 15 种

| 块大小 | Vulkan 格式 | 压缩比 (相对 RGBA8) |
|--------|-------------|---------------------|
| 4x4 | VK_FORMAT_ASTC_4x4_*_BLOCK | 8:1 |
| 5x4 | VK_FORMAT_ASTC_5x4_*_BLOCK | 10:1 |
| 5x5 | VK_FORMAT_ASTC_5x5_*_BLOCK | 12.5:1 |
| 6x5 | VK_FORMAT_ASTC_6x5_*_BLOCK | 15:1 |
| 6x6 | VK_FORMAT_ASTC_6x6_*_BLOCK | 18:1 |
| 8x5 | VK_FORMAT_ASTC_8x5_*_BLOCK | 20:1 |
| 8x6 | VK_FORMAT_ASTC_8x6_*_BLOCK | 24:1 |
| 8x8 | VK_FORMAT_ASTC_8x8_*_BLOCK | 32:1 |
| 10x5 | VK_FORMAT_ASTC_10x5_*_BLOCK | 25:1 |
| 10x6 | VK_FORMAT_ASTC_10x6_*_BLOCK | 30:1 |
| 10x8 | VK_FORMAT_ASTC_10x8_*_BLOCK | 40:1 |
| 10x10 | VK_FORMAT_ASTC_10x10_*_BLOCK | 50:1 |
| 12x10 | VK_FORMAT_ASTC_12x10_*_BLOCK | 60:1 |
| 12x12 | VK_FORMAT_ASTC_12x12_*_BLOCK | 72:1 |

### Mobile ETC/EAC - 12+ 种

| 内部名 | Vulkan 格式 | 用途 |
|--------|-------------|------|
| ETC1 | N/A (OpenGL ES 扩展) | Legacy Android |
| ETC2_RGB | VK_FORMAT_ETC2_R8G8B8_*_BLOCK | RGB 纹理 |
| ETC2_RGBA1 | VK_FORMAT_ETC2_R8G8B8A1_*_BLOCK | 1-bit 透明 |
| ETC2_RGBA8 | VK_FORMAT_ETC2_R8G8B8A8_*_BLOCK | 完整 Alpha |
| EAC_R11 | VK_FORMAT_EAC_R11_*_BLOCK | 高度图 |
| EAC_R11_SIGNED | VK_FORMAT_EAC_R11_SNORM_BLOCK | 有符号单通道 |
| EAC_RG11 | VK_FORMAT_EAC_R11G11_*_BLOCK | 法线贴图 |
| EAC_RG11_SIGNED | VK_FORMAT_EAC_R11G11_SNORM_BLOCK | 有符号双通道 |

### iOS/Qualcomm - 7 种

| 内部名 | 说明 |
|--------|------|
| PVRTC_4BPP | PowerVR 4bpp |
| PVRTC_2BPP | PowerVR 2bpp |
| PVRTC1_4BPP | 同上 (别名) |
| PVRTC1_2BPP | 同上 (别名) |
| ATC_RGB | Adreno RGB |
| ATC_RGBA | Adreno RGBA (显式) |
| ATC_RGBA8 | 同上 (别名) |

### 未压缩/浮点/深度格式 - 15 种 (v1.4.0 新增)

> **说明**: 这些格式常见于 D3D11/DXGI 渲染目标和深度缓冲，现已完整支持。

#### 单通道格式

| 内部名 | DXGI 格式 | 每像素字节 | 输出 |
|--------|-----------|------------|------|
| R8 | DXGI_FORMAT_R8_UNORM | 1 | 灰度 → RGBA |
| R16F | DXGI_FORMAT_R16_FLOAT | 2 | Half-float 灰度 |
| R32F | DXGI_FORMAT_R32_FLOAT | 4 | Float 灰度 |

#### 双通道格式

| 内部名 | DXGI 格式 | 每像素字节 | 输出 |
|--------|-----------|------------|------|
| RG8 | DXGI_FORMAT_R8G8_UNORM | 2 | RG → RGBA (B=0) |
| RG16F | DXGI_FORMAT_R16G16_FLOAT | 4 | 双 Half-float |
| RG32F | DXGI_FORMAT_R32G32_FLOAT | 8 | 双 Float |

#### 四通道格式

| 内部名 | DXGI 格式 | 每像素字节 | 输出 |
|--------|-----------|------------|------|
| RGBA8 | DXGI_FORMAT_R8G8B8A8_UNORM | 4 | 直接拷贝 |
| BGRA8 | DXGI_FORMAT_B8G8R8A8_UNORM | 4 | 通道交换 |
| RGBA16F | DXGI_FORMAT_R16G16B16A16_FLOAT | 8 | 四 Half-float |
| RGBA32F | DXGI_FORMAT_R32G32B32A32_FLOAT | 16 | 四 Float |

#### HDR 打包格式

| 内部名 | DXGI 格式 | 每像素字节 | 说明 |
|--------|-----------|------------|------|
| R11G11B10F | DXGI_FORMAT_R11G11B10_FLOAT | 4 | R11+G11+B10 无符号浮点 |

#### 深度/模板格式

| 内部名 | DXGI 格式 | 每像素字节 | 输出 |
|--------|-----------|------------|------|
| D32F | DXGI_FORMAT_D32_FLOAT | 4 | 深度灰度 |
| D24S8 | DXGI_FORMAT_D24_UNORM_S8_UINT | 4 | R=深度, G=模板 |
| D32S8 | DXGI_FORMAT_D32_FLOAT_S8X24_UINT | 8 | R=深度, G=模板 |

> **注意**: `DXGI_FORMAT_R32G8X24_TYPELESS` 自动映射为 `D32S8` 处理。

### Vulkan 特有格式 - 8 种 (v1.5.0 新增)

> **说明**: 这些格式是 Vulkan 专有的未压缩格式，命名和通道布局与 DXGI 有所不同。

#### HDR 打包格式 (Vulkan)

| 内部名 | Vulkan 格式 | 每像素字节 | 说明 |
|--------|-------------|------------|------|
| B10G11R11F | VK_FORMAT_B10G11R11_UFLOAT_PACK32 | 4 | B10+G11+R11 (通道顺序与 R11G11B10F 相反) |

#### 10-bit HDR 格式

| 内部名 | Vulkan 格式 | 每像素字节 | 说明 |
|--------|-------------|------------|------|
| A2R10G10B10 | VK_FORMAT_A2R10G10B10_UNORM_PACK32 | 4 | 2-bit Alpha + 10-bit RGB |
| A2B10G10R10 | VK_FORMAT_A2B10G10R10_UNORM_PACK32 | 4 | 通道顺序不同 |

> **用途**: HDR 渲染目标、Wide Color Gamut 显示输出

#### 8-bit RGBA 变体

| 内部名 | Vulkan 格式 | 每像素字节 | 说明 |
|--------|-------------|------------|------|
| A8B8G8R8 | VK_FORMAT_A8B8G8R8_UNORM_PACK32 | 4 | Vulkan 专用打包格式 |

#### 16-bit 归一化格式

| 内部名 | Vulkan 格式 | 每像素字节 | 说明 |
|--------|-------------|------------|------|
| R16_UNORM | VK_FORMAT_R16_UNORM | 2 | 单通道 16-bit 归一化 |
| R16G16_UNORM | VK_FORMAT_R16G16_UNORM | 4 | 双通道 16-bit 归一化 |

> **用途**: 高精度高度图、法线贴图

#### Vulkan 深度/模板格式

| 内部名 | Vulkan 格式 | 每像素字节 | 输出 |
|--------|-------------|------------|------|
| D16_UNORM | VK_FORMAT_D16_UNORM | 2 | 灰度深度 |
| S8_UINT | VK_FORMAT_S8_UINT | 1 | 灰度模板 |

#### Vulkan 格式示例

```python
from scripts.rdc_analyzer.decoders import decode_texture

# HDR 渲染目标
rgba = decode_texture(data, 1920, 1080, 'VK_FORMAT_B10G11R11_UFLOAT_PACK32')

# 10-bit HDR
rgba = decode_texture(data, 1920, 1080, 'VK_FORMAT_A2B10G10R10_UNORM_PACK32')

# 16-bit 高精度
rgba = decode_texture(data, 2048, 2048, 'VK_FORMAT_R16G16_UNORM')
```

---

#### 深度/模板可视化说明

深度模板格式解码后：
- **R 通道**: 深度值 (归一化到 0-255)
- **G 通道**: 模板值 (原始 8-bit)
- **B 通道**: 0
- **A 通道**: 255

```python
# 示例: 提取深度缓冲
rgba = decode_texture(data, 1920, 1080, 'DXGI_FORMAT_D32_FLOAT_S8X24_UINT')
# R = 深度可视化, G = 模板值
```

---

## 错误处理

### TextureDecodeError

所有解码错误都会抛出 `TextureDecodeError` 异常：

```python
from scripts.rdc_analyzer.decoders import decode_texture, TextureDecodeError

try:
    rgba = decode_texture(data, 512, 512, 'UNKNOWN_FORMAT')
except TextureDecodeError as e:
    print(f"解码失败: {e}")
    # 输出: Unsupported format: UNKNOWN_FORMAT. Supported: BC1, BC2, ...
```

### 常见错误

| 错误信息 | 原因 | 解决方案 |
|----------|------|----------|
| `Unsupported format: XXX` | 格式不支持 | 检查 `get_supported_formats()` |
| `texture2ddecoder not installed` | 移动端库缺失 | `pip install texture2ddecoder` |
| `PIL not installed` | Pillow 缺失 | `pip install Pillow` |
| `RGBA data size mismatch` | 数据大小不匹配 | 检查 width/height 是否正确 |

---

## 与提取工具集成

### 配合 `extract_texture_from_zipxml.py`

```bash
# 提取并解码纹理
py -3 scripts/rdc_analyzer/extract_texture_from_zipxml.py \
    capture.zip \
    --resource-id 123 \
    --decode \
    --output textures/
```

### 编程方式

```python
from scripts.rdc_analyzer.decoders import decode_texture, save_as_png
from scripts.rdc_analyzer.extract_texture_from_zipxml import extract_texture_data

# 1. 从 ZIP+XML 提取原始数据
tex_info = extract_texture_data('capture.zip', resource_id=123)

# 2. 解码
rgba = decode_texture(
    tex_info['data'],
    tex_info['width'],
    tex_info['height'],
    tex_info['format']
)

# 3. 保存
save_as_png(rgba, tex_info['width'], tex_info['height'], 'output.png')
```

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.5.0 | 2026-02-01 | **Vulkan 格式支持**: 8种 Vulkan 特有格式 (B10G11R11F, A2R10G10B10, A2B10G10R10, A8B8G8R8, R16_UNORM, R16G16_UNORM, D16_UNORM, S8_UINT)，总计 76 种格式 |
| 1.4.0 | 2026-02-01 | **D3D11 格式支持**: 15种未压缩/浮点/深度格式 (R8, RG16F, R11G11B10F, D32S8 等) |
| 1.3.0 | 2025-01-31 | 添加移动端格式 (ASTC/ETC2/PVRTC/ATC) |
| 1.2.0 | 2025-01-30 | 添加 BC2/BC6H，纹理元数据结构 |
| 1.1.1 | 2025-01-29 | 添加 BC4/BC5 |
| 1.1.0 | 2025-01-28 | 添加 BC7 |
| 1.0.0 | 2025-01-27 | 初始版本 (BC1/BC3) |

---

## 相关文档

- [TEXTURE_EXTRACTION.md](TEXTURE_EXTRACTION.md) - 纹理提取方案概述
- [NO_GPU_EXTRACTION_IMPLEMENTATION_GUIDE.md](NO_GPU_EXTRACTION_IMPLEMENTATION_GUIDE.md) - 无 GPU 提取实现指南
- [rdc_format_spec.md](rdc_format_spec.md) - RDC 文件格式规范
