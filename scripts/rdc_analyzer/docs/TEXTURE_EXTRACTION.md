# RDC 纹理提取方案速查

> **版本**: 1.0 | **更新日期**: 2026-01-31 | **作者**: Codex Agent

## 概述

从 `.rdc` 捕获文件中提取纹理有三种方式，适用于不同场景。

| 方式 | 工具 | GPU 依赖 | 输出 | 适用场景 |
|------|------|---------|------|----------|
| **1. CLI 命令** | `renderdoccmd export` | ✅ 需要 | PNG/JPG/DDS/BMP/TGA | 自动化流水线、批量导出 |
| **2. Python API** | `export_textures.py` | ✅ 需要 | PNG + manifest.json | RenderDoc GUI 内交互 |
| **3. 元数据解析** | `rdc_parser.extract_textures()` | ❌ 不需要 | TextureInfo 列表 | 仅需纹理信息（不含像素） |

---

## 方案 1：renderdoccmd export（推荐）

最简单的命令行方式，适用于批量自动化。

### 编译依赖

需要先编译 `renderdoccmd.exe`：

```powershell
# 使用 VS2022 + v140 工具集
"E:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe" ^
  renderdoccmd\renderdoccmd.vcxproj ^
  /p:Configuration=Development ^
  /p:Platform=x64 ^
  /p:SolutionDir=D:\Code\git\renderdoc\ ^
  /m
```

产物路径：`x64\Development\renderdoccmd.exe`

### 用法

```powershell
# 基本用法：导出所有纹理为 PNG
renderdoccmd export --out output_dir/ capture.rdc

# 指定格式
renderdoccmd export --out output_dir/ --format jpg capture.rdc
renderdoccmd export --out output_dir/ --format dds capture.rdc

# 限制最大尺寸（0 = 原始尺寸）
renderdoccmd export --out output_dir/ --max-size 512 capture.rdc

# 同时导出元数据 JSON
renderdoccmd export --out output_dir/ --metadata capture.rdc

# 导出资源绑定信息
renderdoccmd export --out output_dir/ --bindings capture.rdc

# 使用软件渲染（无 GPU 环境）
renderdoccmd export --out output_dir/ --software-render capture.rdc

# 远程主机回放
renderdoccmd export --out output_dir/ --remote-host 192.168.1.100 capture.rdc
```

### 支持的格式

| 格式 | 扩展名 | 特点 |
|------|--------|------|
| PNG | `.png` | 默认，无损压缩 |
| JPG | `.jpg` | 有损压缩，体积小 |
| DDS | `.dds` | 保留 GPU 格式，支持 mipmap |
| BMP | `.bmp` | 无压缩 |
| TGA | `.tga` | 支持 Alpha |

### 限制

- **需要 GPU 回放**：Vulkan 捕获需 Vulkan 支持，D3D12 需 D3D12 支持
- **SwiftShader 替代**：无 GPU 时可用 `--software-render`，但速度慢 10-100x

---

## 方案 2：Python API (export_textures.py)

在 RenderDoc GUI 的 Python Shell 中运行，或独立调用（需 `renderdoc` 模块）。

### 在 RenderDoc GUI 中使用

```python
# 1. 打开 RenderDoc，加载一个捕获文件
# 2. 打开 Python Shell (Window → Python Shell)
# 3. 执行以下代码：

import sys
sys.path.insert(0, r'd:\Code\git\renderdoc\scripts\rdc_analyzer')

from export_textures import export_textures_from_capture
export_textures_from_capture(pyrenderdoc.GetCaptureContext())
```

输出目录自动创建为：`<capture_name>_textures/`

### 独立脚本调用（需 renderdoc 模块）

```python
from export_textures import export_textures_from_rdc

results = export_textures_from_rdc(
    rdc_path="capture.rdc",
    output_dir="textures",
    max_textures=50,  # -1 = 全部
    verbose=True
)

# 返回的 results 是导出纹理的元数据列表
for tex in results:
    print(f"{tex['filename']}: {tex['width']}x{tex['height']} {tex['format']}")
```

### 生成 HTML 图库

```python
from export_textures import generate_html_gallery

generate_html_gallery("textures/manifest.json")
# 输出: textures/texture_gallery.html
```

### 核心 API

```python
# TextureExporter 类
from export_textures import TextureExporter

exporter = TextureExporter(output_dir="my_textures")
results = exporter.export_from_controller(controller, max_textures=100, verbose=True)
exporter.save_manifest()
```

### 相关文件

| 文件 | 说明 |
|------|------|
| `scripts/rdc_analyzer/export_textures.py` | 主模块 (TextureExporter) |
| `scripts/rdc_analyzer/export_textures_rdoc.py` | 简化版，用于 GUI |
| `scripts/rdc_analyzer/test_texture_extract.py` | 测试脚本 |

---

## 方案 3：元数据解析（无 GPU）

仅提取纹理的**元信息**（尺寸、格式、用途），**不导出像素数据**。

适用于：
- 统计纹理数量和内存占用
- 识别大纹理和潜在问题
- 在无 GPU 环境中分析 RDC

### 用法

```python
from rdc_parser import extract_textures

textures = extract_textures("capture.rdc")

for tex in textures:
    print(f"名称: {tex.name}")
    print(f"尺寸: {tex.width} x {tex.height} x {tex.depth}")
    print(f"格式: {tex.format}")
    print(f"用途: RT={tex.is_render_target}, DS={tex.is_depth_stencil}")
    print(f"估算大小: {tex.estimated_size_mb:.2f} MB")
    print("---")
```

### TextureInfo 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | str | 纹理名称（可能为空） |
| `resource_id` | int | RenderDoc 资源 ID |
| `width` | int | 宽度 (像素) |
| `height` | int | 高度 (像素) |
| `depth` | int | 深度 (3D 纹理) 或数组层数 |
| `mip_levels` | int | Mipmap 层级数 |
| `format` | str | 像素格式 (如 R8G8B8A8_UNORM) |
| `usage` | int | 用途标志位 |
| `is_render_target` | bool | 是否为渲染目标 |
| `is_depth_stencil` | bool | 是否为深度/模板缓冲 |
| `estimated_size_mb` | float | 估算内存占用 (MB) |

### 相关文件

| 文件 | 说明 |
|------|------|
| `scripts/rdc_analyzer/rdc_parser.py:2843` | `extract_textures()` 函数 |
| `scripts/rdc_analyzer/rdc_parser.py` | `TextureInfo` 数据类 |

---

## 场景决策树

```
需要从 RDC 获取纹理？
│
├─ 需要像素数据（图片文件）？
│   │
│   ├─ 批量自动化 → 方案 1: renderdoccmd export
│   │
│   ├─ 交互式调试 → 方案 2: RenderDoc GUI + Python
│   │
│   └─ 无 GPU 环境？
│       ├─ 有远程 GPU 服务器 → renderdoccmd --remote-host
│       └─ 无任何 GPU → renderdoccmd --software-render (慢)
│
└─ 只需元信息（尺寸/格式/统计）？
    └─ 方案 3: extract_textures() ← 快速、无 GPU 依赖
```

---

## 常见问题

### Q1: "Local replay not supported" 错误

**原因**: 当前 GPU 不支持该捕获的图形 API

**解决**:
- Vulkan 捕获 → 确保安装 Vulkan 驱动
- D3D12 捕获 → 需要 Windows + 兼容 D3D12 的 GPU
- 尝试 `--software-render` 使用软件渲染

### Q2: 纹理导出后是黑色/损坏的

**原因**: 可能是压缩格式或特殊格式

**解决**:
- 尝试导出为 DDS 格式保留原始数据
- 检查纹理格式是否为 BCn 压缩格式

### Q3: 如何只导出特定事件使用的纹理？

目前 `renderdoccmd export` 导出所有纹理。若需按事件筛选，使用 Python API：

```python
controller.SetFrameEvent(event_id, True)
# 然后读取当前绑定的纹理
state = controller.GetPipelineState()
# ... 筛选逻辑
```

### Q4: 元数据解析和实际导出结果纹理数量不一致

**原因**: 
- 元数据解析读取 RDC chunk 中的纹理创建记录
- 实际导出依赖 GPU 回放后的资源状态
- 部分纹理可能在回放时被优化掉

---

## 相关文档

- [RDC 文件格式规范](./rdc_format_spec.md)
- [GPU 回放架构](../../docs/analysis/gpu-replay-architecture.md)
- [GPU 依赖解决方案](../../docs/analysis/gpu-dependency-solutions.md)
