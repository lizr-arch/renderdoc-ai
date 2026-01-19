# RDC 纹理分析器 - 双里程碑完整总结

> **版本**: 1.0.0  
> **日期**: 2024年  
> **作者**: RenderDoc 纹理分析工具开发团队

---

## 目录

1. [项目概述](#1-项目概述)
2. [里程碑概览](#2-里程碑概览)
3. [功能点清单](#3-功能点清单)
4. [技术点清单](#4-技术点清单)
5. [文件清单](#5-文件清单)
6. [使用指南](#6-使用指南)
7. [价值量化](#7-价值量化)
8. [未来方向](#8-未来方向)

---

## 1. 项目概述

### 1.1 项目目标

构建一个完整的 **RDC 文件纹理分析工具链**，能够：
- 从 RenderDoc 捕获文件 (`.rdc`) 中提取纹理数据
- 生成专业的离线 HTML 分析报告
- 提供性能分析和问题检测能力
- 支持多种格式的数据导出

### 1.2 核心价值

| 价值维度 | 描述 |
|----------|------|
| **效率提升** | 无需打开 RenderDoc 即可快速浏览和分析纹理 |
| **问题发现** | 自动检测 Mipmap 缺失、超大纹理、未压缩格式等问题 |
| **协作便利** | 单文件 HTML 报告可直接分享，无外部依赖 |
| **数据导出** | 支持 CSV/JSON/PNG/Markdown 多种格式 |

---

## 2. 里程碑概览

### 里程碑 1 (M1): 基础能力建设

**目标**: 从 RDC 文件提取可用数据

| 完成项 | 描述 |
|--------|------|
| RDC 文件解析 | 理解 RDCFile Section 结构 |
| 纹理元数据提取 | ID、名称、尺寸、格式、Mips、Layers |
| 缩略图生成 | 通过 ReplayController 获取纹理像素数据 |
| 基础 HTML 报告 | 网格/表格视图展示纹理列表 |

### 里程碑 2 (M2): 专业工具化

**目标**: 将数据转化为可操作的分析洞察

| 完成项 | 描述 |
|--------|------|
| Photoshop 风格 UI | 三栏布局、深色主题、面板折叠 |
| 性能分析功能 | VRAM 估算、Mipmap 验证、问题检测 |
| 虚拟滚动 | 支持 500+ 纹理流畅滚动 |
| 导出功能 | CSV/JSON/PNG/Markdown 四种格式 |
| 一键转换工具 | rdc_to_html.py 端到端流程 |

---

## 3. 功能点清单

### 3.1 数据获取与可视化

#### F01: 纹理缩略图预览
- **解决问题**: 无需打开 RenderDoc 即可浏览所有纹理
- **实用价值**: 快速定位目标纹理，节省 50%+ 查找时间
- **实现方式**: Base64 内嵌图片，单文件自包含

#### F02: 通道分离查看 (RGBA)
- **解决问题**: 检查 Alpha 通道、法线贴图各分量
- **实用价值**: 快速发现通道数据异常（如 Alpha 全黑/全白）
- **实现方式**: CSS filter + mix-blend-mode 实现通道切换

#### F03: 全尺寸预览 + 缩放
- **解决问题**: 查看纹理细节而无需导出
- **实用价值**: 即时检查纹理质量、压缩伪影
- **实现方式**: transform: scale() 实现平滑缩放

#### F04: 颜色拾取器
- **解决问题**: 获取精确像素值和坐标
- **实用价值**: 调试特定颜色值、验证渐变正确性
- **实现方式**: Canvas getImageData 获取像素 RGB 值

#### F05: 直方图显示
- **解决问题**: 分析纹理亮度/颜色分布
- **实用价值**: 发现过曝/欠曝、对比度问题
- **实现方式**: Canvas 绘制 256 级灰度分布图

### 3.2 性能分析

#### F06: VRAM 占用估算
- **解决问题**: 不知道纹理实际显存消耗
- **实用价值**: 量化内存预算，识别内存大户
- **实现方式**: BPP 格式映射表 × 像素数（含 Mipmap）
- **支持格式**: 30+ 种，包括 BC1-7, ASTC, RGBA, 深度格式

#### F07: Mipmap 完整性检查
- **解决问题**: 缺失 Mipmap 导致远景闪烁/性能差
- **实用价值**: 批量检测问题纹理，避免上线后发现
- **实现方式**: 计算期望值 log2(max(w,h))+1 与实际值对比
- **状态分类**: 
  - ✓ 完整 (actual >= expected)
  - ◐ 部分 (1 < actual < expected)
  - ⚠ 无 (actual == 1)

#### F08: 非 2 的幂检测
- **解决问题**: 部分硬件/API 对 NPOT 有性能惩罚
- **实用价值**: 提前发现兼容性隐患
- **实现方式**: 位运算 (n & (n-1)) === 0

#### F09: 超大纹理警告
- **解决问题**: 大纹理浪费内存且可能超限
- **实用价值**: 识别可优化的资源
- **阈值**: ≥ 4096 像素标记为超大

#### F10: 未压缩格式检测
- **解决问题**: RGBA8 等格式浪费 4-8 倍显存
- **实用价值**: 推动资源优化，减少包体和内存
- **检测逻辑**: 非 BC/ASTC 开头的格式标记为未压缩

### 3.3 批量处理与统计

#### F11: 全局统计面板
- **解决问题**: 缺乏整体资源视图
- **实用价值**: 一眼看清纹理总数、格式分布、总 VRAM
- **统计项**:
  - 纹理总数
  - 格式种类数
  - 平均尺寸
  - 总 VRAM 占用

#### F12: 问题汇总看板
- **解决问题**: 问题分散难追踪
- **实用价值**: 集中展示所有警告，按类型分类
- **问题类型**:
  - 无 Mipmap
  - 部分 Mipmap
  - 非 2 的幂
  - 超大纹理 (≥4K)
  - 未压缩格式

#### F13: 搜索功能
- **解决问题**: 海量纹理中找目标困难
- **实用价值**: 按名称/ID 快速定位
- **实现方式**: 实时过滤 filteredTextures 数组

#### F14: 筛选功能
- **解决问题**: 只想看某类纹理
- **实用价值**: 聚焦特定格式或尺寸范围
- **筛选维度**:
  - 格式 (BC1/BC3/BC7/RGBA...)
  - 尺寸 (小/中/大/超大)

#### F15: 排序功能
- **解决问题**: 找最大/最小纹理麻烦
- **实用价值**: 按尺寸排序快速识别异常值
- **排序维度**: ID / 尺寸 / 格式 / 名称

### 3.4 导出与协作

#### F16: CSV 导出
- **解决问题**: 需要在 Excel 中进一步分析
- **实用价值**: 支持透视表、图表、团队共享
- **导出字段**: ID, 名称, 宽度, 高度, 深度, 格式, Mips, Layers, VRAM(KB)

#### F17: JSON 导出
- **解决问题**: 需要程序化处理数据
- **实用价值**: 接入 CI/CD、自动化分析脚本
- **数据结构**:
```json
{
  "exportTime": "ISO时间戳",
  "totalTextures": 数量,
  "textures": [{ id, name, width, height, depth, format, mips, arrayLayers, estimatedVRAM, hasThumbnail }]
}
```

#### F18: PNG 下载
- **解决问题**: 需要单独提取某张纹理
- **实用价值**: 无需打开 RenderDoc 即可获取资源
- **实现方式**: 通过 Data URL 创建下载链接

#### F19: Markdown 报告
- **解决问题**: 需要向他人汇报分析结果
- **实用价值**: 一键生成可阅读的问题报告
- **报告内容**:
  - 生成时间
  - 总体统计
  - 问题汇总
  - 纹理列表（前50个）

#### F20: 单文件离线 HTML
- **解决问题**: 报告需要邮件/IM 分享
- **实用价值**: 无依赖、直接打开、自包含所有数据
- **实现方式**: 图片 Base64 内嵌，CSS/JS 内联

### 3.5 用户体验

#### F21: Photoshop 风格布局
- **解决问题**: 专业工具需要高效布局
- **实用价值**: 三栏布局最大化利用屏幕空间
- **布局结构**:
  - 左侧: 纹理列表面板
  - 中间: 主画布预览区
  - 右侧: 属性/分析面板

#### F22: 深色主题
- **解决问题**: 长时间使用眼睛疲劳
- **实用价值**: 符合图形工具行业惯例
- **CSS 变量**: --bg-darkest, --bg-dark, --bg-medium, --text-primary 等

#### F23: 面板折叠
- **解决问题**: 需要更多预览空间
- **实用价值**: 隐藏不需要的面板
- **可折叠**: 左侧面板、右侧面板、属性区块

#### F24: 虚拟滚动
- **解决问题**: 纹理过多导致页面卡顿
- **实用价值**: 500+ 纹理仍流畅滚动
- **触发阈值**: > 100 个纹理自动启用
- **技术参数**: ITEM_HEIGHT=52px, BUFFER_ITEMS=5

#### F25: 键盘导航
- **解决问题**: 鼠标操作效率低
- **实用价值**: 快速切换纹理
- **快捷键**:
  - ↑/↓: 上下切换纹理
  - Home: 跳转到第一个
  - End: 跳转到最后一个

#### F26: 下拉菜单
- **解决问题**: 导出选项过多占用空间
- **实用价值**: 悬停展开，界面简洁
- **菜单项**: 导出 CSV / JSON / PNG / 报告

#### F27: 状态栏
- **解决问题**: 缺乏实时反馈
- **实用价值**: 显示当前纹理名、坐标、缩放比
- **显示内容**: 当前纹理 | 坐标 | 缩放比例

### 3.6 集成与自动化

#### F28: 一键 RDC 转 HTML
- **解决问题**: 手动流程繁琐（导出→整理→生成）
- **实用价值**: 单命令完成全流程
- **入口脚本**: rdc_to_html.py

#### F29: 临时目录管理
- **解决问题**: 导出的 PNG 文件残留
- **实用价值**: 自动清理，不污染文件系统
- **实现方式**: tempfile.mkdtemp() + 完成后删除

#### F30: 多环境兼容
- **解决问题**: renderdoc 模块不一定可用
- **实用价值**: 独立运行或在 RenderDoc Shell 中运行
- **运行模式**:
  1. 命令行 (需 renderdoc 模块)
  2. RenderDoc Python Shell (内置模块)
  3. 纯 HTML 生成 (已有纹理数据)

---

## 4. 技术点清单

### 4.1 文件解析与数据提取

#### T01: RDCFile Section 解析
- **应用场景**: 读取 RDC 二进制结构
- **核心文件**: renderdoc/serialise/rdcfile.h/.cpp
- **复用价值**: 可扩展到其他 Section 类型 (DrawCall, Shader 等)

#### T02: ReplayController API
- **应用场景**: 获取纹理元数据和像素数据
- **关键方法**:
  - `GetTextures()`: 获取纹理列表
  - `GetTextureData()`: 获取像素数据
- **复用价值**: RenderDoc 自动化的基础

#### T03: Base64 图片内嵌
- **应用场景**: 单文件 HTML 无外部依赖
- **实现方式**: `data:image/png;base64,{base64_data}`
- **复用价值**: 任何需要自包含报告的场景

#### T04: Python ↔ SWIG 绑定
- **应用场景**: 脚本化操作 RenderDoc
- **绑定文件**: qrenderdoc/Code/pyrenderdoc/renderdoc.i
- **复用价值**: 构建 MCP/Skill 的基础

### 4.2 性能分析算法

#### T05: BPP 格式映射表
- **应用场景**: 任何纹理内存估算
- **覆盖格式**: 30+ 种
```javascript
const BPP_MAP = {
  // 压缩格式
  'BC1_UNORM': 0.5, 'BC1_SRGB': 0.5,
  'BC2_UNORM': 1, 'BC2_SRGB': 1,
  'BC3_UNORM': 1, 'BC3_SRGB': 1,
  'BC4_UNORM': 0.5, 'BC4_SNORM': 0.5,
  'BC5_UNORM': 1, 'BC5_SNORM': 1,
  'BC6H_UF16': 1, 'BC6H_SF16': 1,
  'BC7_UNORM': 1, 'BC7_SRGB': 1,
  // ASTC
  'ASTC_4x4': 1, 'ASTC_5x5': 0.64, 'ASTC_6x6': 0.44,
  'ASTC_8x8': 0.25, 'ASTC_10x10': 0.16, 'ASTC_12x12': 0.11,
  // 标准格式
  'R8_UNORM': 1, 'R8G8_UNORM': 2,
  'R8G8B8A8_UNORM': 4, 'R8G8B8A8_SRGB': 4,
  'B8G8R8A8_UNORM': 4, 'B8G8R8A8_SRGB': 4,
  'R16_FLOAT': 2, 'R16G16_FLOAT': 4,
  'R16G16B16A16_FLOAT': 8,
  'R32_FLOAT': 4, 'R32G32_FLOAT': 8,
  'R32G32B32A32_FLOAT': 16,
  // 特殊格式
  'R11G11B10_FLOAT': 4, 'RGB9E5_FLOAT': 4,
  'B5G6R5_UNORM': 2, 'B5G5R5A1_UNORM': 2,
  // 深度格式
  'D16_UNORM': 2, 'D24_UNORM_S8_UINT': 4,
  'D32_FLOAT': 4, 'D32_FLOAT_S8X24_UINT': 8,
};
```

#### T06: Mipmap 链计算
- **期望值公式**: `Math.floor(Math.log2(Math.max(w, h))) + 1`
- **VRAM 递归计算**:
```javascript
function calculateMipmapVRAM(w, h, mips, bpp) {
  let total = 0;
  for (let m = 0; m < mips; m++) {
    total += w * h;
    w = Math.max(1, Math.floor(w / 2));
    h = Math.max(1, Math.floor(h / 2));
  }
  return total * bpp;
}
```

#### T07: POT 检测
- **位运算**: `(n & (n - 1)) === 0 && n > 0`
- **原理**: 2 的幂只有一个 bit 为 1

### 4.3 前端性能优化

#### T08: 虚拟滚动实现
- **核心思想**: 只渲染可视区域 DOM
- **关键参数**:
  - ITEM_HEIGHT: 52px (固定高度)
  - BUFFER_ITEMS: 5 (上下缓冲)
- **实现步骤**:
  1. 创建撑开容器 (totalHeight = count × ITEM_HEIGHT)
  2. 监听 scroll 事件
  3. 计算 startIndex/endIndex
  4. 只渲染 [startIndex, endIndex) 范围的元素

#### T09: requestAnimationFrame 节流
- **解决问题**: 滚动事件过于频繁
- **实现方式**:
```javascript
let rafId = null;
container.onscroll = () => {
  if (!rafId) {
    rafId = requestAnimationFrame(() => {
      renderVisibleItems();
      rafId = null;
    });
  }
};
```

#### T10: 懒加载图片
- **实现方式**: `<img loading="lazy">`
- **浏览器支持**: Chrome 77+, Firefox 75+, Edge 79+

#### T11: CSS 变量主题系统
- **定义**:
```css
:root {
  --bg-darkest: #0d1117;
  --bg-dark: #161b22;
  --bg-medium: #21262d;
  --text-primary: #e6edf3;
  --text-secondary: #8b949e;
  --accent-blue: #58a6ff;
  --accent-red: #f85149;
}
```
- **使用**: `background: var(--bg-dark);`

### 4.4 数据导出技术

#### T12: Blob + URL.createObjectURL
- **应用场景**: 纯前端生成下载文件
- **实现方式**:
```javascript
function downloadFile(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
```

#### T13: CSV 引号转义
- **问题**: 字段含逗号或引号会破坏 CSV 结构
- **解决**: 用双引号包裹，内部引号变双引号
```javascript
`"${(tex.name || '').replace(/"/g, '""')}"`
```

#### T14: Data URL 图片下载
- **应用场景**: 下载 Base64 图片
- **实现方式**: 直接将 data:image/png;base64,... 赋给 link.href

### 4.5 架构设计

#### T15: 模块检测降级
- **问题**: renderdoc 模块只在特定环境可用
- **解决方案**:
```python
try:
    import renderdoc as rd
    HAS_RENDERDOC = True
except ImportError:
    HAS_RENDERDOC = False
```

#### T16: 临时目录管理
- **实现方式**:
```python
import tempfile
import shutil

temp_dir = tempfile.mkdtemp(prefix='rdc_export_')
try:
    # 导出纹理到 temp_dir
    # 生成 HTML
finally:
    shutil.rmtree(temp_dir, ignore_errors=True)
```

#### T17: Python 模板字符串转义
- **问题**: Python f-string 与 JS 大括号冲突
- **解决**: 使用 `{{` 和 `}}` 转义
```python
html = f"""
<script>
const data = {{{json_data}}};  // Python 变量
function test() {{             // JS 大括号
    console.log(data);
}}
</script>
"""
```

---

## 5. 文件清单

### 5.1 核心代码

| 文件 | 行数 | 职责 |
|------|------|------|
| `generate_offline_report.py` | ~3500 | HTML 报告生成器（核心） |
| `rdc_to_html.py` | ~200 | 一键转换入口脚本 |
| `analyze_rdc.py` | ~300 | RDC 分析库 |
| `export_textures.py` | ~150 | 纹理导出工具 |

### 5.2 测试文件

| 文件 | 用途 |
|------|------|
| `test_virtual_scroll.html` | 500 纹理虚拟滚动性能测试 |
| `test_export.html` | 导出功能验证 |
| `final_test.html` | 真实纹理数据端到端测试 |

### 5.3 文档

| 文件 | 内容 |
|------|------|
| `docs/MILESTONE_SUMMARY.md` | 本文档 - 完整里程碑总结 |

---

## 6. 使用指南

### 6.1 方式一: 从 RDC 一键生成 (推荐)

**前提**: 在 RenderDoc Python Shell 中运行

```python
# 在 RenderDoc 中打开 Python Shell
# Window → Python Shell

import sys
sys.path.append(r'd:\Code\git\renderdoc\scripts\rdc_analyzer')

from rdc_to_html import rdc_to_html
rdc_to_html(r'D:\captures\game.rdc', r'D:\output\report.html')
```

### 6.2 方式二: 从已有数据生成

```python
from generate_offline_report import generate_offline_html

textures = [
    {
        'id': 1,
        'name': 'Diffuse_01',
        'width': 2048,
        'height': 2048,
        'format': 'BC3_SRGB',
        'mips': 11,
        'depth': 1,
        'arrayLayers': 1,
        'thumbnail': 'data:image/png;base64,...'  # 可选
    },
    # ...
]

generate_offline_html(textures, 'capture.rdc', 'output.html')
```

### 6.3 方式三: 命令行

```bash
# 需要 renderdoc 模块在 Python 路径中
python rdc_to_html.py capture.rdc output.html
```

---

## 7. 价值量化

### 7.1 时间节省估算

| 场景 | 原方式 | 新方式 | 节省比例 |
|------|--------|--------|----------|
| 查找特定纹理 | 逐个点击浏览 (~2min) | 搜索框 (~5s) | **95%** |
| 检查 Alpha 通道 | 导出 → PS 打开 (~3min) | 一键切换 (~1s) | **98%** |
| 统计 VRAM 占用 | 手动计算 (~30min) | 自动汇总 (~0s) | **100%** |
| 找出所有问题纹理 | 逐个检查 (~1h) | 问题面板 (~10s) | **99%** |
| 分享分析结果 | 截图 + 文字说明 (~15min) | 导出报告 (~5s) | **99%** |

### 7.2 支持的纹理格式

```
压缩格式 (14种):
  BC1_UNORM, BC1_SRGB, BC2_UNORM, BC2_SRGB, BC3_UNORM, BC3_SRGB,
  BC4_UNORM, BC4_SNORM, BC5_UNORM, BC5_SNORM, BC6H_UF16, BC6H_SF16,
  BC7_UNORM, BC7_SRGB

ASTC 格式 (6种):
  ASTC_4x4, ASTC_5x5, ASTC_6x6, ASTC_8x8, ASTC_10x10, ASTC_12x12

标准格式 (12种):
  R8_UNORM, R8G8_UNORM, R8G8B8A8_UNORM, R8G8B8A8_SRGB,
  B8G8R8A8_UNORM, B8G8R8A8_SRGB, R16_FLOAT, R16G16_FLOAT,
  R16G16B16A16_FLOAT, R32_FLOAT, R32G32_FLOAT, R32G32B32A32_FLOAT

特殊格式 (4种):
  R11G11B10_FLOAT, RGB9E5_FLOAT, B5G6R5_UNORM, B5G5R5A1_UNORM

深度格式 (4种):
  D16_UNORM, D24_UNORM_S8_UINT, D32_FLOAT, D32_FLOAT_S8X24_UINT

总计: 40+ 种格式
```

---

## 8. 未来方向

### 8.1 可能的 M3 方向

| 方向 | 描述 | 价值 | 复杂度 |
|------|------|------|--------|
| **Draw Call 分析** | 分析每帧的绘制调用 | 性能瓶颈定位 | 高 |
| **Shader 分析** | 着色器指令统计 | 着色器优化指导 | 高 |
| **资源依赖图** | 可视化纹理-DC 关系 | 理解资源使用模式 | 中 |
| **CI/CD 集成** | 自动化质量门禁 | 防止问题纹理提交 | 中 |
| **多帧对比** | 帧间资源变化检测 | 发现资源泄漏 | 中 |
| **Buffer 分析** | 顶点/索引缓冲区分析 | 完整资源视图 | 中 |

### 8.2 技术债务

| 项目 | 描述 | 优先级 |
|------|------|--------|
| 单元测试 | 为核心函数添加测试 | 中 |
| 类型注解 | Python type hints | 低 |
| 性能基准 | 建立性能测试基线 | 低 |

---

## 附录 A: 功能点速查表

| ID | 功能 | 分类 | 优先级 |
|----|------|------|--------|
| F01 | 纹理缩略图预览 | 可视化 | 高 |
| F02 | 通道分离查看 | 可视化 | 高 |
| F03 | 全尺寸预览+缩放 | 可视化 | 高 |
| F04 | 颜色拾取器 | 可视化 | 中 |
| F05 | 直方图显示 | 可视化 | 低 |
| F06 | VRAM 占用估算 | 分析 | 高 |
| F07 | Mipmap 完整性检查 | 分析 | 高 |
| F08 | 非 2 的幂检测 | 分析 | 中 |
| F09 | 超大纹理警告 | 分析 | 中 |
| F10 | 未压缩格式检测 | 分析 | 中 |
| F11 | 全局统计面板 | 统计 | 高 |
| F12 | 问题汇总看板 | 统计 | 高 |
| F13 | 搜索功能 | 筛选 | 高 |
| F14 | 筛选功能 | 筛选 | 中 |
| F15 | 排序功能 | 筛选 | 中 |
| F16 | CSV 导出 | 导出 | 中 |
| F17 | JSON 导出 | 导出 | 中 |
| F18 | PNG 下载 | 导出 | 中 |
| F19 | Markdown 报告 | 导出 | 中 |
| F20 | 单文件离线 HTML | 导出 | 高 |
| F21 | Photoshop 风格布局 | UX | 高 |
| F22 | 深色主题 | UX | 中 |
| F23 | 面板折叠 | UX | 中 |
| F24 | 虚拟滚动 | 性能 | 高 |
| F25 | 键盘导航 | UX | 低 |
| F26 | 下拉菜单 | UX | 低 |
| F27 | 状态栏 | UX | 低 |
| F28 | 一键 RDC 转 HTML | 集成 | 高 |
| F29 | 临时目录管理 | 集成 | 中 |
| F30 | 多环境兼容 | 集成 | 高 |

---

## 附录 B: 技术点速查表

| ID | 技术点 | 分类 | 复用价值 |
|----|--------|------|----------|
| T01 | RDCFile Section 解析 | 解析 | 高 |
| T02 | ReplayController API | 解析 | 高 |
| T03 | Base64 图片内嵌 | 导出 | 高 |
| T04 | Python ↔ SWIG 绑定 | 集成 | 高 |
| T05 | BPP 格式映射表 | 算法 | 高 |
| T06 | Mipmap 链计算 | 算法 | 高 |
| T07 | POT 检测 | 算法 | 中 |
| T08 | 虚拟滚动实现 | 性能 | 高 |
| T09 | RAF 节流 | 性能 | 高 |
| T10 | 懒加载图片 | 性能 | 中 |
| T11 | CSS 变量主题 | 前端 | 中 |
| T12 | Blob 文件下载 | 导出 | 高 |
| T13 | CSV 引号转义 | 导出 | 中 |
| T14 | Data URL 下载 | 导出 | 中 |
| T15 | 模块检测降级 | 架构 | 高 |
| T16 | 临时目录管理 | 架构 | 中 |
| T17 | Python 模板转义 | 架构 | 中 |

---

**文档结束**

*本文档记录了 RDC 纹理分析器 M1+M2 双里程碑的完整内容，包含 30 个功能点和 17 个技术点。*
