# RDC Analyzer - 离线纹理分析工具

> 从 RenderDoc 捕获文件 (.rdc) 生成 100% 离线的 HTML 纹理分析报告

## ✨ 功能特性

### 基础功能

| 功能 | 描述 |
|------|------|
| 🖼️ **纹理浏览** | 网格/表格视图切换，支持搜索过滤和多种排序 |
| 🔍 **Lightbox 预览** | 点击放大查看，键盘导航 (← → ESC) |
| 🎨 **RGBA 通道分离** | 单独查看 R/G/B/A 通道（需要 Pillow） |
| ☀️ **亮度/对比度调整** | 深度图可视化利器，0-300% 范围调节 |
| 📦 **100% 离线** | 单个 HTML 文件，无需网络，可直接分享 |

### 高级分析功能 (v2.0)

| 功能 | 描述 |
|------|------|
| 📊 **VRAM 分析** | 饼图/柱状图展示格式分布和尺寸分布，点击图例可筛选 |
| 🔗 **Event ID 跳转** | 点击 EID 标签查看 Draw Call 详情弹窗 |
| 🔄 **重复纹理检测** | 基于 hash 识别重复纹理，计算浪费的 VRAM |
| 🧊 **冷热分析** | 识别未使用/低频使用的纹理 |
| 🔬 **纹理对比视图** | 并排对比两张纹理，同步缩放/平移，确认是否真正重复 |
| 📤 **优化建议导出** | 导出 Markdown/JSON/CSV 格式的优化清单 |

## 📁 文件结构

```
scripts/rdc_analyzer/
├── README.md                    # 本文档
├── generate_offline_report.py   # 离线 HTML 报告生成器 (主工具)
├── export_textures.py           # RenderDoc 纹理导出脚本
├── frame_analyzer.py            # RDC 帧分析器
└── __init__.py                  # 包初始化
```

## 🚀 快速开始

### 前置条件

1. **Python 3.6+**
2. **Pillow** (可选，用于 RGBA 通道分离)
   ```bash
   pip install Pillow
   ```

### 使用流程

#### 步骤 1: 在 RenderDoc 中导出纹理

1. 打开 RenderDoc，加载 `.rdc` 捕获文件
2. 打开 **Python Shell** (Window → Python Shell)
3. 执行以下代码：

```python
import sys
sys.path.insert(0, r'd:\Code\git\renderdoc\scripts\rdc_analyzer')
from export_textures import export_textures_from_capture
export_textures_from_capture(pyrenderdoc.GetCaptureContext())
```

这将在 RDC 文件同目录下创建 `{capture_name}_textures/` 文件夹，包含：
- 所有纹理的 PNG 文件
- `textures.json` 清单文件

#### 步骤 2: 生成离线 HTML 报告

```bash
py -3 scripts/rdc_analyzer/generate_offline_report.py "path/to/your_capture.rdc"
```

输出：`your_capture.html`（与 RDC 文件同目录）

#### 自定义输出路径

```bash
py -3 scripts/rdc_analyzer/generate_offline_report.py "capture.rdc" -o "report.html"
```

## 🎮 报告使用指南

### 主界面

- **搜索框**: 按名称、格式、ID 过滤纹理
- **排序下拉框**: 按 ID / 尺寸 / 格式 / 名称排序
- **视图切换**: 网格视图 / 表格视图

### Lightbox 预览

| 操作 | 说明 |
|------|------|
| 点击纹理卡片 | 打开 Lightbox |
| ← / → 键 | 上一张 / 下一张 |
| ESC 键 | 关闭 Lightbox |
| RGB / R / G / B / A 按钮 | 切换通道显示 |
| 亮度滑块 | 调整图像亮度 (0-300%) |
| 对比度滑块 | 调整图像对比度 (0-300%) |
| 重置按钮 | 恢复默认亮度/对比度 |

### 深度图查看技巧

深度图通常看起来全黑或全白，使用以下设置可视化：

| 场景 | 推荐设置 |
|------|----------|
| 深度图太暗 | 亮度 150-200%, 对比度 150% |
| 深度图太亮 | 亮度 50-80% |
| 深度范围小 | 对比度 200-300% |

### 纹理对比视图

1. 在列表中选择第一张纹理，点击 **"添加到对比"** 按钮
2. 选择第二张纹理，再次点击 **"添加到对比"**
3. 点击工具栏的 **"对比"** 按钮打开对比视图

| 操作 | 说明 |
|------|------|
| 鼠标滚轮 | 缩放 (10% - 1000%) |
| 鼠标拖拽 | 平移图像 |
| Sync 开关 | 开启：两图同步移动；关闭：独立操作 |
| Swap 按钮 | 交换左右图像位置 |
| Reset 按钮 | 重置缩放和平移 |

### 导出优化清单

点击顶部菜单 **"导出"** 按钮，选择导出格式：

| 格式 | 用途 | 内容 |
|------|------|------|
| **Markdown** | 人类阅读 | 格式化的优化建议报告 |
| **JSON** | 程序处理/CI 集成 | 结构化数据，含详细统计 |
| **CSV** | Excel/表格处理 | 扁平化表格，便于筛选排序 |

**导出内容包括**：
- 重复纹理组（含哈希值、浪费空间）
- 未使用/低频使用纹理
- 无 Mipmap 纹理
- 超大纹理 (4K+)
- 未压缩纹理
- 非 2 的幂次纹理

## 🔧 高级用法

### 直接从命令行导出纹理（需要 GPU）

```bash
py -3 scripts/rdc_analyzer/export_textures.py "capture.rdc" -o textures/
```

> ⚠️ 此方式需要兼容的 GPU 和 RenderDoc Python 模块

### 仅生成 HTML 图库（从已有清单）

```bash
py -3 scripts/rdc_analyzer/export_textures.py --gallery textures/manifest.json
```

## 📋 依赖说明

| 依赖 | 必需 | 用途 |
|------|------|------|
| Python 3.6+ | ✅ | 运行脚本 |
| Pillow | ❌ | RGBA 通道分离（无此依赖仍可运行，但无通道功能） |
| RenderDoc | ✅ | 导出纹理（步骤 1） |

## ❓ 常见问题

### Q: 报告中没有纹理数据？

确保已执行步骤 1，在 RenderDoc 中导出纹理。检查 RDC 文件同目录下是否存在 `{capture_name}_textures/textures.json`。

### Q: RGBA 通道按钮不可用？

1. 确保已安装 Pillow: `pip install Pillow`
2. 重新生成报告

### Q: 某些通道显示为灰色（禁用）？

表示该通道为纯色（如 Alpha=255 全不透明），无需单独查看。

### Q: 如何在没有 GPU 的服务器上使用？

步骤 1 必须在有 GPU 的机器上执行（RenderDoc 需要回放捕获）。步骤 2 可以在任意机器上执行。

## 📝 版本历史

- **v2.0.0** - 高级分析版本
  - ✨ VRAM 分析仪表盘（饼图/柱状图）
  - ✨ Event ID 跳转和 Draw Call 详情弹窗
  - ✨ 重复纹理检测和冷热分析
  - ✨ 纹理对比视图（同步缩放/平移）
  - ✨ 优化建议导出（Markdown/JSON/CSV）
  - 🐛 修复 Grid View 返回按钮和标题重叠
  - 🐛 修复 EID 标签对大多数纹理不显示
  - 🐛 修复导出功能数据格式不匹配

- **v1.0.0** - 初始版本
  - 100% 离线 HTML 报告
  - RGBA 通道分离
  - 亮度/对比度调整
  - 网格/表格视图
  - 搜索过滤和排序

## 📄 License

MIT License - 与 RenderDoc 项目保持一致
