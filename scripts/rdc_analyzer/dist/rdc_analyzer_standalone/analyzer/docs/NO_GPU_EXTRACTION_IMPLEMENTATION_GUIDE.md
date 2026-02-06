# 无 GPU 纹理提取实现指南

> **版本**: 1.0.0  
> **更新日期**: 2025-01-31  
> **作者**: Codex Agent A  
> **目标读者**: 希望使用或扩展纹理提取功能的开发者

---

## 1. 快速开始

### 1.1 环境要求

| 组件 | 版本要求 | 说明 |
|------|----------|------|
| Python | 3.7+ | 仅使用标准库 |
| renderdoccmd | 与 RDC 版本匹配 | 用于 RDC → ZIP+XML 转换 |
| 磁盘空间 | RDC 大小 × 3 | 转换输出可能膨胀 |

### 1.2 基本工作流

```bash
# 步骤 1: 将 RDC 转换为 ZIP+XML 格式
renderdoccmd convert -c zip.xml capture.rdc output.zip

# 步骤 2: 查看可提取的纹理列表
py -3 scripts/rdc_analyzer/extract_texture_from_zipxml.py output.zip.xml -l

# 步骤 3: 提取指定纹理
py -3 scripts/rdc_analyzer/extract_texture_from_zipxml.py output.zip.xml -e 360 -o ./textures/
```

### 1.3 输出说明

```
./textures/
├── texture_360_memory_116.bin     # 完整内存块（包含多个纹理）
└── texture_360_offset_9212928.bin # 从绑定偏移开始的数据
```

---

## 2. 工具详细说明

### 2.1 extract_texture_from_zipxml.py

**位置**: `scripts/rdc_analyzer/extract_texture_from_zipxml.py`

**依赖**: 仅 Python 标准库（无需 `renderdoc.pyd`）

**命令行参数**:

| 参数 | 说明 | 示例 |
|------|------|------|
| `xml_file` | 必需，XML 文件路径 | `output.zip.xml` |
| `-l, --list-textures` | 列出所有可提取纹理 | |
| `-e, --extract ID` | 提取指定 ID 的纹理 | `-e 360` |
| `-o, --output DIR` | 输出目录 | `-o ./textures/` |

**示例输出**:

```
$ py -3 extract_texture_from_zipxml.py output.zip.xml -l

[*] XML: output.zip.xml
[*] ZIP: output.zip (exists)
[*] Parsing XML: output.zip.xml
    File size: 335.05 MB
    Found 1087 images
    Found 1087 bindings
    Found 1101 initial contents

================================================================================
EXTRACTABLE TEXTURES
================================================================================

Found 1022 extractable textures out of 1087 total

      ID |            Size |                              Format |   Buffer |       Offset
------------------------------------------------------------------------------------------
     360 |     2048x4096x1 |                  VK_FORMAT_R8_UNORM |      425 |      9212928
  507585 |     4096x2048x1 |            VK_FORMAT_BC7_SRGB_BLOCK |      436 |    237543424
  ...
```

### 2.2 renderdoccmd convert

**转换格式选项**:

| 格式 | 参数 | 输出 | 用途 |
|------|------|------|------|
| XML | `-c xml` | 单个 XML | 小文件，可内嵌 Base64 |
| ZIP+XML | `-c zip.xml` | ZIP + XML | 大文件，buffer 单独存储 |
| RDC | `-c rdc` | RDC | 格式转换/修复 |

**使用示例**:

```bash
# 基本转换
renderdoccmd convert -c zip.xml input.rdc output.zip

# 输出文件
# - output.zip      # 包含所有 buffer 文件
# - output.zip.xml  # 结构化元数据
```

---

## 3. API 编程指南

### 3.1 作为 Python 模块使用

```python
import sys
sys.path.append('scripts/rdc_analyzer')
from extract_texture_from_zipxml import parse_xml_regex, list_textures, extract_texture
from pathlib import Path

# 解析 XML
xml_path = Path('output.zip.xml')
images, bindings, initial_contents = parse_xml_regex(xml_path)

# 查找特定格式的纹理
bc7_textures = [
    img for img in images.values() 
    if 'BC7' in img.format
]
print(f"Found {len(bc7_textures)} BC7 textures")

# 提取纹理
for tex in bc7_textures[:5]:  # 提取前5个
    extract_texture(
        tex.resource_id,
        images,
        bindings,
        initial_contents,
        zip_path=xml_path.parent / 'output.zip',
        output_dir=Path('./extracted/')
    )
```

### 3.2 核心数据结构

```python
@dataclass
class ImageInfo:
    resource_id: int    # VkImage 资源 ID
    width: int          # 纹理宽度
    height: int         # 纹理高度
    depth: int          # 纹理深度（3D 纹理）
    format: str         # 格式字符串，如 "VK_FORMAT_BC7_UNORM_BLOCK"
    format_id: int      # 格式枚举值
    image_type: str     # "VK_IMAGE_TYPE_2D" 等

@dataclass
class MemoryBinding:
    image_id: int       # VkImage ID
    memory_id: int      # VkDeviceMemory ID
    offset: int         # 在内存中的字节偏移

@dataclass
class InitialContents:
    resource_type: str  # "eResDeviceMemory" 等
    resource_id: int    # 内存资源 ID
    is_sparse: bool     # 是否稀疏资源
    contents_size: int  # 内容大小（字节）
    buffer_index: int   # ZIP 中的文件索引
```

### 3.3 资源映射查询

```python
def find_texture_data(image_id: int, images, bindings, initial_contents):
    """查找纹理的原始数据位置"""
    
    # 1. 获取纹理元数据
    if image_id not in images:
        return None
    image = images[image_id]
    
    # 2. 查找内存绑定
    binding = None
    for b in bindings:
        if b.image_id == image_id:
            binding = b
            break
    if not binding:
        return None
    
    # 3. 查找 InitialContents
    ic = initial_contents.get(binding.memory_id)
    if not ic:
        return None
    
    return {
        'image': image,
        'binding': binding,
        'initial_contents': ic,
        'zip_file': f"{ic.buffer_index:06d}",  # 如 "000425"
        'data_offset': binding.offset,
    }
```

---

## 4. 纹理格式处理

### 4.1 计算纹理字节大小

```python
def calculate_texture_size(width: int, height: int, depth: int, format: str) -> int:
    """根据格式计算纹理字节大小"""
    
    # 未压缩格式
    UNCOMPRESSED_FORMATS = {
        'VK_FORMAT_R8_UNORM': 1,
        'VK_FORMAT_R8G8_UNORM': 2,
        'VK_FORMAT_R8G8B8A8_UNORM': 4,
        'VK_FORMAT_R8G8B8A8_SRGB': 4,
        'VK_FORMAT_B8G8R8A8_UNORM': 4,
        'VK_FORMAT_B8G8R8A8_SRGB': 4,
        'VK_FORMAT_R16_SFLOAT': 2,
        'VK_FORMAT_R16G16_SFLOAT': 4,
        'VK_FORMAT_R16G16B16A16_SFLOAT': 8,
        'VK_FORMAT_R32_SFLOAT': 4,
        'VK_FORMAT_R32G32B32A32_SFLOAT': 16,
        # ... 更多格式
    }
    
    # 块压缩格式 (4x4 块)
    BLOCK_FORMATS = {
        'VK_FORMAT_BC1_RGB_UNORM_BLOCK': 8,    # 8 bytes per 4x4 block
        'VK_FORMAT_BC1_RGBA_UNORM_BLOCK': 8,
        'VK_FORMAT_BC1_RGB_SRGB_BLOCK': 8,
        'VK_FORMAT_BC1_RGBA_SRGB_BLOCK': 8,
        'VK_FORMAT_BC3_UNORM_BLOCK': 16,       # 16 bytes per 4x4 block
        'VK_FORMAT_BC3_SRGB_BLOCK': 16,
        'VK_FORMAT_BC5_UNORM_BLOCK': 16,
        'VK_FORMAT_BC5_SNORM_BLOCK': 16,
        'VK_FORMAT_BC7_UNORM_BLOCK': 16,
        'VK_FORMAT_BC7_SRGB_BLOCK': 16,
        # ... 更多格式
    }
    
    if format in UNCOMPRESSED_FORMATS:
        bytes_per_pixel = UNCOMPRESSED_FORMATS[format]
        return width * height * depth * bytes_per_pixel
    
    elif format in BLOCK_FORMATS:
        bytes_per_block = BLOCK_FORMATS[format]
        blocks_x = (width + 3) // 4
        blocks_y = (height + 3) // 4
        return blocks_x * blocks_y * depth * bytes_per_block
    
    else:
        raise ValueError(f"Unknown format: {format}")
```

### 4.2 块压缩格式解码（扩展方向）

对于 BC7 等压缩格式，需要 CPU 解码才能获得 RGBA 像素：

```python
# 伪代码：BC7 解码流程
def decode_bc7_block(block_data: bytes) -> list:
    """解码单个 BC7 块（16 bytes → 64 RGBA pixels）"""
    # BC7 有 8 种模式，需要按规范解码
    # 参考: https://registry.khronos.org/DataFormat/specs/1.3/dataformat.1.3.html#BPTC
    pass

def decode_bc7_texture(data: bytes, width: int, height: int) -> bytes:
    """解码整个 BC7 纹理"""
    output = bytearray(width * height * 4)  # RGBA
    blocks_x = (width + 3) // 4
    blocks_y = (height + 3) // 4
    
    for by in range(blocks_y):
        for bx in range(blocks_x):
            block_offset = (by * blocks_x + bx) * 16
            block_data = data[block_offset:block_offset + 16]
            pixels = decode_bc7_block(block_data)
            # 写入 output...
    
    return bytes(output)
```

> **推荐方案**: 使用现有库如 `texture2ddecoder`（需安装）或调用 RenderDoc 的格式转换功能。

---

## 5. 常见问题与解决

### 5.1 转换输出文件为 0 字节

**症状**: `renderdoccmd convert -c zip.xml` 输出 0 字节的 ZIP 文件

**可能原因**:
1. RDC 文件损坏
2. 内存不足（大文件需要足够内存）
3. 驱动版本不匹配

**解决方案**:
```bash
# 先尝试 XML 格式验证
renderdoccmd convert -c xml input.rdc output.xml

# 如果成功，检查文件大小后再尝试 zip.xml
```

### 5.2 部分纹理无法提取

**症状**: 1087 个纹理中只有 1022 个可提取

**原因分析**:

| 原因 | 说明 | 比例 |
|------|------|------|
| SwapChain Image | 由驱动管理，无绑定 | ~40 |
| 延迟创建资源 | 运行时动态创建 | ~15 |
| 外部内存 | 如视频帧、共享纹理 | ~10 |

**解决方案**: 这些资源本身就没有保存像素数据，无法提取。

### 5.3 提取的数据看起来不正确

**症状**: 提取的 bin 文件用图像查看器打开是乱码

**可能原因**:
1. 格式是块压缩（BC7 等），需要解码
2. offset 计算错误
3. 多个纹理共享同一内存块

**解决方案**:
```python
# 检查格式
print(f"Format: {image.format}")

# 如果是 BC* 格式，需要解码
if 'BC7' in image.format:
    print("需要 BC7 解码器")

# 验证数据大小
expected_size = calculate_texture_size(
    image.width, image.height, image.depth, image.format
)
print(f"Expected size: {expected_size} bytes")
```

### 5.4 XML 解析内存不足

**症状**: 解析大型 XML 时内存溢出

**当前实现**: 使用正则表达式流式解析，避免加载整个 DOM

**如果仍有问题**:
```python
# 分块读取大文件
CHUNK_SIZE = 100 * 1024 * 1024  # 100 MB

with open(xml_path, 'rb') as f:
    while True:
        chunk = f.read(CHUNK_SIZE)
        if not chunk:
            break
        # 处理 chunk...
```

---

## 6. 扩展开发指南

### 6.1 添加新的纹理格式支持

1. 更新 `calculate_texture_size()` 函数
2. 实现格式特定的解码器
3. 添加到格式注册表

```python
# 格式注册表模式
FORMAT_REGISTRY = {
    'VK_FORMAT_BC7_UNORM_BLOCK': {
        'block_size': (4, 4),
        'bytes_per_block': 16,
        'decoder': decode_bc7_texture,
    },
    # ...
}
```

### 6.2 添加 D3D11 支持

D3D11 RDC 的纹理数据结构略有不同：

```python
def parse_d3d11_textures(xml_path):
    """解析 D3D11 RDC 中的纹理"""
    
    # D3D11 使用不同的 chunk 名称
    create_pattern = rb'<chunk[^>]+name="CreateTexture2D"[^>]*>(.*?)</chunk>'
    
    # D3D11 InitialContents 直接包含纹理数据
    # 不需要像 Vulkan 那样通过 Memory 间接访问
```

### 6.3 集成到 MCP Server

```python
# MCP Tool 封装示例
@mcp_tool("extract_rdc_texture")
async def extract_rdc_texture(
    rdc_path: str,
    texture_id: int,
    output_path: str
) -> dict:
    """从 RDC 提取纹理（无需 GPU）"""
    
    # 1. 转换为 ZIP+XML
    zip_path = convert_rdc_to_zipxml(rdc_path)
    
    # 2. 解析并提取
    images, bindings, ic = parse_xml_regex(zip_path + '.xml')
    
    # 3. 提取纹理
    extract_texture(texture_id, images, bindings, ic, zip_path, output_path)
    
    return {
        'success': True,
        'output': output_path,
        'format': images[texture_id].format,
    }
```

---

## 7. 参考资料

### 7.1 相关工具

| 工具 | 用途 |
|------|------|
| `renderdoccmd` | RDC 格式转换 |
| `extract_texture_from_zipxml.py` | 纹理提取 |
| RenderDoc UI | 验证结果 |

### 7.2 相关文档

- [NO_GPU_TEXTURE_EXTRACTION_ARCHITECTURE.md](./NO_GPU_TEXTURE_EXTRACTION_ARCHITECTURE.md) - 架构设计
- [RDC_STRUCTURE_DEEP_ANALYSIS.md](./RDC_STRUCTURE_DEEP_ANALYSIS.md) - 格式分析
- [TEXTURE_EXTRACTION_METHODS.md](./TEXTURE_EXTRACTION_METHODS.md) - 方案对比

### 7.3 外部参考

- [Vulkan Format Specifications](https://registry.khronos.org/vulkan/specs/1.3/html/vkspec.html#formats)
- [BC Compression Specification](https://registry.khronos.org/DataFormat/specs/1.3/dataformat.1.3.html#BPTC)
- [RenderDoc Python API](https://renderdoc.org/docs/python_api/index.html)
