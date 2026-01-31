# 纹理批量导出 CLI 工具

> `batch_export_textures.py` - 从 RenderDoc 捕获文件中批量导出纹理

## 功能概述

- **双模式支持**：自动检测输入类型，选择最佳导出策略
  - 📁 XML+ZIP 模式：无需 GPU，适合服务器/CI 环境
  - 🎮 RDC 直接模式：需要 GPU，导出质量最佳
- **批量处理**：支持目录递归处理多个捕获文件
- **灵活过滤**：正则表达式过滤纹理格式/尺寸
- **可视化输出**：自动生成 HTML 图库预览

## 快速开始

### 安装依赖

```bash
# 核心依赖（必需）
pip install Pillow

# 移动端纹理支持（可选）
pip install texture2ddecoder
```

### 基本用法

```bash
# 从 XML+ZIP 导出（推荐，无需 GPU）
py -3 batch_export_textures.py capture.xml -o ./textures

# 从 RDC 直接导出（需要 GPU + renderdoc.pyd）
py -3 batch_export_textures.py capture.rdc -o ./textures
```

### 预转换 RDC 为 XML+ZIP

如果没有可用的 GPU 环境，需要先将 RDC 转换为 XML+ZIP：

```bash
# 使用 RenderDoc 命令行工具
renderdoccmd convert -c zip.xml capture.rdc -o capture.xml
```

这会生成：
- `capture.xml` - 结构化的捕获元数据
- `capture` - ZIP 文件（无扩展名），包含二进制缓冲区

## 命令行参数

```
用法: batch_export_textures.py [-h] [-o OUTPUT] [--png] [--no-png] [--bin]
                               [--filter REGEX] [--max MAX] [--gallery]
                               [--manifest] [-r] [-q] input

位置参数:
  input                 输入文件 (.rdc 或 .xml) 或目录

选项:
  -h, --help            显示帮助信息
  -o, --output DIR      输出目录 (默认: ./textures_export)
  --png                 导出为 PNG (默认启用)
  --no-png              禁用 PNG 导出，仅保存原始数据
  --bin                 同时保存原始二进制数据
  --filter REGEX        正则过滤 (匹配格式名或尺寸)
  --max N               最大导出数量
  --gallery             生成 HTML 图库预览
  --manifest            生成 JSON 清单
  -r, --recursive       递归处理子目录
  -q, --quiet           静默模式
```

## 使用示例

### 导出所有纹理

```bash
py -3 batch_export_textures.py capture.xml -o ./output
```

### 只导出 BC7 格式纹理

```bash
py -3 batch_export_textures.py capture.xml -o ./output --filter "BC7"
```

### 导出 1024x1024 或更大的纹理

```bash
py -3 batch_export_textures.py capture.xml -o ./output --filter "1024x|2048x|4096x"
```

### 导出前 10 个纹理并生成预览

```bash
py -3 batch_export_textures.py capture.xml -o ./output --max 10 --gallery
```

### 批量处理目录

```bash
py -3 batch_export_textures.py ./captures/ -o ./output -r --gallery --manifest
```

### 同时保存原始数据

```bash
py -3 batch_export_textures.py capture.xml -o ./output --bin
```

## 输出结构

```
textures_export/
├── capture1/                    # 按输入文件名分组
│   ├── tex_12345_1024x1024.png  # 导出的纹理
│   ├── tex_12345_1024x1024.bin  # 原始数据 (如果 --bin)
│   ├── tex_67890_512x512.png
│   ├── gallery.html             # HTML 预览 (如果 --gallery)
│   └── manifest.json            # 导出清单 (如果 --manifest)
├── capture2/
│   └── ...
└── summary.json                 # 批量处理汇总 (多文件时)
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `tex_<id>_<size>.png` | 解码后的 PNG 纹理 |
| `tex_<id>_<size>.bin` | 原始压缩数据（需 `--bin`） |
| `gallery.html` | 可视化预览页面 |
| `manifest.json` | 导出结果清单（含格式/尺寸/路径） |
| `summary.json` | 批量处理汇总 |

## manifest.json 格式

```json
{
  "total": 50,
  "success": 48,
  "failed": 2,
  "skipped": 0,
  "textures": [
    {
      "resource_id": 12345,
      "width": 1024,
      "height": 1024,
      "format": "VK_FORMAT_BC7_UNORM_BLOCK",
      "success": true,
      "png": "tex_12345_1024x1024.png",
      "bin": null,
      "error": null
    }
  ]
}
```

## 支持的格式

### 桌面端 (纯 Python，无额外依赖)

| 格式 | 说明 |
|------|------|
| BC1 (DXT1) | RGB 4bpp |
| BC2 (DXT3) | RGBA 8bpp |
| BC3 (DXT5) | RGBA 8bpp |
| BC4 | 单通道 4bpp |
| BC5 | 双通道 8bpp（法线贴图） |
| BC6H | HDR 8bpp |
| BC7 | 高质量 RGBA 8bpp |

### 移动端 (需要 texture2ddecoder)

| 格式 | 说明 |
|------|------|
| ASTC 4x4 ~ 12x12 | 自适应可伸缩（14 种块大小） |
| ETC1 / ETC2 | Ericsson 纹理压缩 |
| EAC R11 / RG11 | 高精度单/双通道 |
| PVRTC 2bpp / 4bpp | PowerVR 纹理 |
| ATC | Adreno 纹理压缩 |

## 依赖环境检测

脚本启动时会自动检测环境：

```
============================================================
 Texture Batch Exporter v1.0.0
============================================================
 Decoder available: ✓
 RenderDoc module:  ✗
 Input: capture.xml
 Output: ./textures_export
 Files to process: 1
```

- **Decoder available**: 纯 Python 解码器是否可用
- **RenderDoc module**: `renderdoc.pyd` 是否可用（RDC 直接模式需要）

## 错误处理

| 错误类型 | 原因 | 解决方案 |
|----------|------|----------|
| `Unsupported format` | 纹理格式暂不支持 | 使用 `--bin` 保存原始数据 |
| `renderdoc module not available` | 缺少 renderdoc.pyd | 改用 XML+ZIP 模式 |
| `ZIP file not found` | XML 对应的 ZIP 不存在 | 检查 `renderdoccmd convert` 输出 |
| `Failed to extract texture data` | 内存映射问题 | 检查 RDC 是否完整 |

## 相关文档

- [纹理解码器模块](TEXTURE_DECODERS.md) - 解码器 API 详解
- [无 GPU 纹理提取](NO_GPU_TEXTURE_EXTRACTION.md) - 离线提取架构
- [RDC 结构深度分析](RDC_STRUCTURE_DEEP_ANALYSIS.md) - 文件格式说明
