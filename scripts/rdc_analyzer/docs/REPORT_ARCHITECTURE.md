# RDC 报告架构设计文档

> **版本**: 1.0.0 | **日期**: 2025-01-28 | **状态**: 已确认

## 一、设计目标

1. **职责单一**: 每个页面专注一类数据分析
2. **命名统一**: 消除 `*_report.html`, `*_report_v2.html` 等混乱命名
3. **双向链接**: 页面间可互相跳转，形成分析闭环
4. **风格统一**: 所有页面使用相同的 Photoshop 深色主题

---

## 二、页面架构

### 2.1 目录结构

```
{capture_name}/
├── index.html              ← 📊 概览 Dashboard (入口页)
├── textures.html           ← 🖼️ 纹理分析器
├── events.html             ← 📋 事件浏览器
├── shaders.html            ← 🎨 Shader 分析器 (含 Mali 分析)
├── manifest.json           ← 元数据 + 页面链接
└── assets/                 ← 资源文件夹
    ├── textures/           ← 纹理缩略图
    └── thumbnails/         ← 帧缩略图
```

### 2.2 页面职责

| 页面 | 文件名 | 核心职责 | 功能列表 |
|------|--------|----------|----------|
| **概览** | `index.html` | 快速了解问题，导航入口 | VRAM统计、格式/尺寸分布图、优化建议摘要、一致性检查、页面跳转 |
| **纹理** | `textures.html` | 纹理深度分析 | 网格/表格视图、虚拟滚动、Lightbox、通道分离、对比模式、重复检测 |
| **事件** | `events.html` | GPU 调用追踪 | Event树、Pass依赖图、Pipeline State、绑定资源、Mesh预览、API调用参数 |
| **Shader** | `shaders.html` | Shader 性能分析 | Shader列表、反编译代码、Mali分析结果、指令周期、寄存器使用 |

---

## 三、页面详细设计

### 3.1 index.html (概览 Dashboard)

**目标用户**: 所有人（美术、程序、TA）
**使用场景**: 打开报告后的第一个页面，快速了解帧的整体情况

**功能模块**:
```
┌─────────────────────────────────────────────────────────────────┐
│ [Logo] RDC Report - {capture_name}               [帧缩略图]     │
├────────────┬────────────┬────────────┬────────────┬────────────┤
│ 📊 概览    │ 🖼️ 纹理    │ 📋 事件    │ 🎨 Shader  │            │
│  (当前)    │   (138)    │   (97)     │   (113)    │            │
├────────────┴────────────┴────────────┴────────────┴────────────┤
│                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │  VRAM 使用      │  │  格式分布       │  │  尺寸分布       │  │
│  │  [饼图]         │  │  [饼图]         │  │  [柱状图]       │  │
│  │  总计: 256MB    │  │  BC7: 45%       │  │  2K: 30%        │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 🔴 优化建议 (12 条)                      [查看详情 →]      │  │
│  │ ├─ 严重 (3): 超大纹理未压缩                               │  │
│  │ ├─ 警告 (5): 检测到重复纹理                               │  │
│  │ └─ 建议 (4): 可合并的小纹理                               │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 📋 一致性检查                                              │  │
│  │ ├─ ✅ Event 数量: 97 (XML ↔ JSON 匹配)                    │  │
│  │ ├─ ✅ 纹理数量: 138 (匹配)                                │  │
│  │ └─ ⚠️ Shader 数量: 113 (XML) vs 55 (JSON) - 部分缺失      │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**从现有代码迁移**:
- `renderConsistencyPanel()` → 一致性检查模块
- `renderVRAMCharts()` → VRAM 统计图表
- `renderOptimizationPanelInSidebar()` → 优化建议摘要

---

### 3.2 textures.html (纹理分析器)

**目标用户**: 美术、TA
**使用场景**: 检查纹理质量、查找问题纹理、对比分析

**功能模块**:
```
┌─────────────────────────────────────────────────────────────────┐
│ [导航栏: 概览 | 纹理(当前) | 事件 | Shader]                      │
├─────────────────────────────────────────────────────────────────┤
│ 工具栏: [网格] [表格] | [搜索...] | 筛选: [格式▼] [尺寸▼] [问题▼]│
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐       │
│  │ ⚠️  │ │     │ │     │ │ ⚠️  │ │     │ │     │ │     │       │
│  │ Tex │ │ Tex │ │ Tex │ │ Tex │ │ Tex │ │ Tex │ │ Tex │       │
│  │  1  │ │  2  │ │  3  │ │  4  │ │  5  │ │  6  │ │  7  │       │
│  │2048²│ │512² │ │1024²│ │4096²│ │256² │ │512² │ │1024²│       │
│  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘       │
│  ... (虚拟滚动支持 1000+ 纹理)                                  │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│ Lightbox (选中纹理详情):                                         │
│  ┌─────────────────────────────┐  ┌────────────────────────┐    │
│  │                             │  │ 属性:                   │    │
│  │     [纹理预览大图]          │  │  名称: diffuse_hero     │    │
│  │                             │  │  尺寸: 2048 x 2048      │    │
│  │     [R] [G] [B] [A] [RGB]  │  │  格式: BC7_UNORM        │    │
│  │                             │  │  VRAM: 5.33 MB          │    │
│  └─────────────────────────────┘  │                         │    │
│                                    │ 使用此纹理的 Events:    │    │
│  [对比模式] [导出] [书签]          │  [EID 45] [EID 67] →   │    │
│                                    └────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

**从现有代码迁移**:
- `renderGrid()`, `renderTable()` → 双视图模式
- `initVirtualScroll()` → 虚拟滚动
- `openLightbox()`, `showChannelImage()` → Lightbox + 通道分离
- `toggleCompare()`, `openCompare()` → 对比模式
- `renderDuplicateAnalysis()` → 重复纹理检测

**跳转链接**:
- 点击 "使用此纹理的 Events" → `events.html?texture={texture_id}`

---

### 3.3 events.html (事件浏览器)

**目标用户**: 程序员、图形工程师
**使用场景**: 追踪 Draw Call、分析 Pipeline State、查看资源绑定

**功能模块**:
```
┌─────────────────────────────────────────────────────────────────┐
│ [导航栏: 概览 | 纹理 | 事件(当前) | Shader]                      │
├───────────────────────┬─────────────────────────────────────────┤
│ Event 树 (左侧面板)    │ 主工作区                                │
│ ┌───────────────────┐ │ ┌─────────────────────────────────────┐ │
│ │ ▼ Frame Start     │ │ │ Pass 依赖图 (SVG)                   │ │
│ │ ▼ Pass: GBuffer   │ │ │                                     │ │
│ │   ├─ Draw 1 ⚡    │ │ │  [Main] ─→ [Shadow] ─→ [Post]      │ │
│ │   ├─ Draw 2       │ │ │     ↓         ↓                     │ │
│ │   └─ Draw 3       │ │ │  [GBuffer] ─→ [Lighting]            │ │
│ │ ▼ Pass: Shadow    │ │ │                                     │ │
│ │   └─ Draw 4       │ │ └─────────────────────────────────────┘ │
│ │ ▼ Pass: Post      │ │                                         │
│ │   └─ Draw 5       │ │ ┌─────────────────────────────────────┐ │
│ └───────────────────┘ │ │ Event 详情 (EID: 45)                 │ │
│                       │ │                                       │ │
│ [搜索 Event...]       │ │ 📦 Pipeline State:                    │ │
│ [按类型筛选▼]          │ │   VS: VS_Character [→ Shader 页]     │ │
│                       │ │   PS: PS_Main [→ Shader 页]           │ │
│                       │ │                                       │ │
│                       │ │ 🖼️ 绑定的纹理:                        │ │
│                       │ │   Slot 0: diffuse [→ 纹理页]          │ │
│                       │ │   Slot 1: normal [→ 纹理页]           │ │
│                       │ │                                       │ │
│                       │ │ 📐 Mesh 信息:                         │ │
│                       │ │   顶点: 1,234 | 三角形: 456           │ │
│                       │ │   [3D 预览]                           │ │
│                       │ │                                       │ │
│                       │ │ 📝 API 调用:                          │ │
│                       │ │   DrawIndexed(456, 0, 0)              │ │
│                       │ └─────────────────────────────────────┘ │
└───────────────────────┴─────────────────────────────────────────┘
```

**从现有代码迁移**:
- `renderEventTree()` → Event 树
- `renderPassGraph()` → Pass 依赖图
- `renderEventDetail()` → Event 详情
- `renderEventPipeline()` → Pipeline State
- `renderEventBindings()` → 绑定资源
- `renderEventMeshInfo()` → Mesh 预览
- `renderEventApiCall()` → API 调用参数

**跳转链接**:
- 点击 Shader 名称 → `shaders.html?id={shader_id}`
- 点击纹理名称 → `textures.html?id={texture_id}`

---

### 3.4 shaders.html (Shader 分析器)

**目标用户**: 程序员、图形工程师、TA
**使用场景**: 分析 Shader 性能、查看 Mali 优化建议、审查指令

**功能模块**:
```
┌─────────────────────────────────────────────────────────────────┐
│ [导航栏: 概览 | 纹理 | 事件 | Shader(当前)]                      │
├───────────────────────┬─────────────────────────────────────────┤
│ Shader 列表 (左侧)     │ Shader 详情 (右侧)                      │
│ ┌───────────────────┐ │ ┌─────────────────────────────────────┐ │
│ │ [搜索...]         │ │ │ PS_Main (Fragment Shader)           │ │
│ │ [按问题排序]      │ │ │                                     │ │
│ │ [按 Event 数排序] │ │ │ ┌─────────────────────────────────┐ │ │
│ │                   │ │ │ │ 📊 Mali 分析 (Mali-G78)         │ │ │
│ │ ▸ PS_Main ⚠️     │ │ │ │                                 │ │ │
│ │   12 Events       │ │ │ │ 总周期: 1.23 cycles/pixel      │ │ │
│ │   Cycles: 1.23    │ │ │ │ ├─ ALU: 0.55 (45%)             │ │ │
│ │                   │ │ │ │ ├─ L/S: 0.37 (30%)             │ │ │
│ │ ▸ VS_Character    │ │ │ │ └─ Tex: 0.31 (25%)             │ │ │
│ │   8 Events        │ │ │ │                                 │ │ │
│ │   Cycles: 0.45    │ │ │ │ 寄存器: 32/64 (50%)            │ │ │
│ │                   │ │ │ │ Uniform: 16                     │ │ │
│ │ ▸ PS_Shadow       │ │ │ └─────────────────────────────────┘ │ │
│ │   3 Events        │ │ │                                     │ │
│ │   Cycles: 0.12    │ │ │ 📝 反编译代码:                      │ │
│ │                   │ │ │ ┌─────────────────────────────────┐ │ │
│ │ ▸ CS_Compute      │ │ │ │ // SPIR-V Disassembly           │ │ │
│ │   2 Events        │ │ │ │ OpCapability Shader             │ │ │
│ │                   │ │ │ │ OpMemoryModel Logical GLSL450   │ │ │
│ └───────────────────┘ │ │ │ ...                             │ │ │
│                       │ │ └─────────────────────────────────┘ │ │
│                       │ │                                     │ │
│                       │ │ 使用此 Shader 的 Events:            │ │
│                       │ │ [EID 12] [EID 45] [EID 67] → 跳转  │ │
│                       │ └─────────────────────────────────────┘ │
└───────────────────────┴─────────────────────────────────────────┘
```

**从现有代码迁移**:
- `renderShaderList()` → Shader 列表
- `showShaderDetails()`, `showShaderModal()` → Shader 详情
- 从 `renderdoc_mali_shell.py` 迁移 → Mali 分析结果

**跳转链接**:
- 点击 "使用此 Shader 的 Events" → `events.html?shader={shader_id}`

---

## 四、manifest.json 规范

```json
{
  "version": "1.0.0",
  "capture_id": "sha256:a1317bfdb3bc73d929ddfc840afb2769f5343235097dab23fe93c7e8f66e0569",
  "capture_name": "战斗特写1",
  "generated_at": "2025-01-28T10:30:00Z",
  "generator_version": "rdc_analyzer 2.0.0",
  
  "pages": {
    "index": "index.html",
    "textures": "textures.html",
    "events": "events.html",
    "shaders": "shaders.html"
  },
  
  "counts": {
    "events": 97,
    "textures": 138,
    "shaders": 113,
    "draw_calls": 85,
    "passes": 6
  },
  
  "data_sources": {
    "xml": "战斗特写1.xml",
    "json": "战斗特写1.json",
    "mali_report": "mali_analysis.json"
  },
  
  "frame_thumbnail": "assets/thumbnails/frame.png"
}
```

---

## 4.5 数据来源方式总表（索引）

- 路径：`docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`
- 说明：统一维护所有数据来源分类、可用性与限制；后续新增来源应先更新此表。

---

## 五、统一样式规范

所有页面共享以下 CSS 变量（沿用现有 Photoshop 深色主题）：

```css
:root {
    /* 背景色阶 */
    --bg-darkest: #0d1117;
    --bg-darker: #161b22;
    --bg-dark: #21262d;
    --bg-medium: #30363d;
    
    /* 边框 */
    --border: #30363d;
    --border-light: #484f58;
    
    /* 文字 */
    --text-primary: #e6edf3;
    --text-secondary: #8b949e;
    --text-muted: #6e7681;
    
    /* 强调色 */
    --accent-red: #e94560;
    --accent-blue: #58a6ff;
    --accent-green: #3fb950;
    --accent-yellow: #f9c513;
    --accent-orange: #f0883e;
    --accent-purple: #a371f7;
}
```

---

## 六、实施路线图

### Phase 1: 基础拆分 (优先级: 高)
1. 从现有 `战斗特写1_report.html` 提取公共样式 → `common.css`
2. 拆分 `index.html` (概览页)
3. 拆分 `textures.html` (纹理页)

### Phase 2: 事件与 Shader (优先级: 高)
4. 拆分 `events.html` (事件页)
5. 整合 Mali 分析 → `shaders.html` (Shader页)

### Phase 3: 联动优化 (优先级: 中)
6. 实现跨页面跳转链接
7. 更新 `manifest.json` 生成逻辑
8. 统一命名，清理旧报告

### Phase 4: 增强功能 (优先级: 低)
9. Pass 依赖图真实数据
10. API 调用参数展示
11. 深色/浅色主题切换

---

## 七、旧文件迁移对照表

| 旧文件名 | 新文件名 | 备注 |
|----------|----------|------|
| `*_report.html` | `index.html` | 主入口 |
| `*_report_v2.html` | (删除) | 合并到新架构 |
| `*_report_xml.html` | `textures.html` | 纹理专用 |
| `mali_shader_report.html` | `shaders.html` | 整合 Mali 分析 |
| `rdc_manifest.json` + `report_links.json` | `manifest.json` | 合并元数据 |

---

## 八、附录: 命名规范

### 文件命名
- 页面文件: 小写 + 下划线，如 `index.html`, `textures.html`
- 资源文件夹: 小写，如 `assets/textures/`
- 元数据: `manifest.json`

### URL 参数
- 跳转到特定纹理: `textures.html?id={texture_id}`
- 跳转到特定事件: `events.html?eid={event_id}`
- 跳转到特定 Shader: `shaders.html?id={shader_id}`
- 筛选: `textures.html?filter=large` 或 `?format=BC7`

### ID 命名
- 纹理 ID: `TEX_{resource_id}` 或直接使用 ResourceId
- Shader ID: `{stage}_{name}` 如 `PS_Main`, `VS_Character`
- Event ID: 使用 EID 数字

---

*文档结束*
