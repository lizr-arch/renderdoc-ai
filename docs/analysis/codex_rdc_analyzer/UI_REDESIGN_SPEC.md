
# RDC Analyzer UI 重构规范

> **版本**: 0.1.0 | **状态**: /spec Phase | **创建日期**: 2025-01-XX

## 目录
1. [现有页面盘点](#1-现有页面盘点)
2. [核心目的定义](#2-核心目的定义)
3. [业界工具调研](#3-业界工具调研)
4. [重构设计方案](#4-重构设计方案)
5. [开发计划](#5-开发计划)

---

## 1. 现有页面盘点

### 1.1 当前 HTML 报告类型总览

| 报告类型 | 入口文件 | 主要内容 | 状态 |
|----------|---------|---------|------|
| **纹理报告 (Offline)** | `generate_offline_report.py` | 纹理列表、去重分析、通道分离、热点分析 | ✅ 主力使用 |
| **事件报告 (Real)** | `generate_real_report.py` | Event Browser、Pass 结构、Pipeline State | ⚠️ 依赖 Offline |
| **Mali GPU 分析报告** | `analyze_rdc_mali.py` | Shader 分析、Mali 优化建议 | 🔧 独立生成 |
| **RDC 结构分析报告** | `analyze_rdc.py` | Draw Calls 列表、问题检测 | ⚠️ 旧版 base.html |
| **Shader 分析报告** | `analyze_extracted_shaders.py` | Shader 代码高亮、ALU 分析 | 🔧 独立工具 |
| **对比报告** | `compare_rdc.py` | 双帧差异、性能回归分析 | 🔧 独立工具 |
| **纹理画廊** | `export_textures.py` / `texture_batch_exporter.py` | 纯纹理缩略图预览 | ⚠️ 冗余 |

### 1.2 问题诊断

#### ❌ 问题 1: 三套视图模式混乱
```
当前 generate_offline_report.py 内含三种视图:
├── App 视图 (主视图): Photoshop 风格，左侧纹理列表 + 右侧详情面板
├── Grid 视图 (网格视图): 纹理卡片网格 + Lightbox
└── Event 视图: Event Browser 树形结构
```
- **问题**: 用户不知道三种视图的关系和切换逻辑
- **代码证据**: `let viewMode = 'app'; // 'app' 或 'grid'` (L6897)

#### ❌ 问题 2: 模板内联 HTML 超过 12000 行
```python
# generate_offline_report.py
html = f'''<!DOCTYPE html>
<html lang="zh-CN">
...
''' # 持续到 L12000+
```
- **问题**: 维护困难、无法复用、修改风险高
- **行数统计**: `generate_offline_report.py` 主函数 `generate_offline_html()` 超过 12000 行

#### ❌ 问题 3: 多个独立报告生成器，缺乏统一设计语言
- `analyze_rdc_mali.py` 使用完全独立的 HTML 模板
- `analyze_extracted_shaders.py` 有自己的样式系统
- `compare_rdc.py` 又是另一套 UI 风格

#### ❌ 问题 4: 功能职责不清晰
- "纹理报告" 实际上包含了: 事件浏览、热点分析、RT 追踪、优化建议...
- 名称与内容不匹配，用户期望与实际功能存在 gap

### 1.3 现有功能模块清单

从代码分析中提取的功能模块:

| 功能模块 | 代码位置 | 视图位置 | 说明 |
|----------|----------|----------|------|
| 纹理列表 | `generate_offline_html()` L6000+ | 左侧面板 | 虚拟滚动、过滤、搜索 |
| 纹理详情 | 同上 | 右侧详情区 | 元数据、通道分离、使用追踪 |
| 纹理网格 | 同上 (Grid View) | 独立视图 | 卡片网格 + Lightbox |
| 去重分析 | `core/optimization_advisor.py` | Issues Tab | 检测相似/重复纹理 |
| 纹理热度 | `usage_analysis` 参数 | Heatmap | 基于引用次数着色 |
| Event Browser | `event_pass_data` 参数 | 独立视图 | Pass/Action 树形结构 |
| RT Timeline | `rt_timeline_component.py` | 独立组件 | Render Target 时间线 |
| Hotspot 分析 | `hotspot_component.py` | 独立组件 | 性能热点可视化 |
| Pipeline State | `parse_pipeline_state_from_related_calls()` | 详情面板 | VS/PS、Blend、Viewport |
| Shader 查看器 | Modal Dialog | 弹窗 | ASM/HLSL 代码高亮 |
| 优化建议 | `OptimizationAdvisor` | Panel | 基于规则的优化提示 |
| 性能统计 | `PerformanceAnalyzer` | Stats Grid | Draw Calls、带宽估算 |
| 帧缩略图 | `frame_thumbnail` 参数 | 菜单栏 | 最终渲染结果预览 |
| 报告链接 | `report_linking.py` | 菜单/Footer | v3/texture 互相跳转 |

---

## 2. 核心目的定义

> **已确认**: 通用平台型单帧深度分析工具

### 2.1 用户画像

| 角色 | 核心目标 | 典型问题 | 关注视图 |
|------|---------|----------|---------|
| **TA (技术美术)** | 审查资源质量 | 纹理过大、格式不合理、mipmap 缺失 | 资源浏览器 |
| **引擎程序员** | 理解渲染流程 | 状态异常、绑定错误、Draw Call 顺序 | 事件时间线 |
| **性能优化工程师** | 识别热点 | 带宽瓶颈、过度绘制、Shader 复杂度 | 问题检测 |
| **QA 工程师** | 回归检测 | 渲染差异、资源变化 | 对比报告 |

### 2.2 核心使用场景

| 优先级 | 场景 | 输入 | 输出 | UI 主视图 |
|--------|------|------|------|----------|
| **P0** | 单帧深度分析 | 1 个 RDC + 导出纹理 | HTML 报告 + 问题清单 | 混合标签页 |
| P1 | 双帧对比 | 2 个 RDC | 差异 HTML | 对比视图 |
| P2 | 批量自动化 | N 个 RDC | JSON 数据 | CI 集成 |

### 2.3 价值定位：与 RenderDoc 原生 GUI 的差异

| RenderDoc GUI 能做 | 我们的 HTML 报告应该做 |
|-------------------|----------------------|
| 实时调试、逐帧回放 | **静态分析**：离线、可分享、可存档 |
| 手动逐事件检查 | **自动问题检测**：规则引擎主动发现问题 |
| 单机使用 | **团队协作**：可通过链接分享分析结果 |
| 需要安装软件 | **零依赖**：纯浏览器打开，跨平台 |
| 查看原始数据 | **可视化增强**：热力图、趋势图、对比图 |
| 单一视角 | **多角色视角**：TA/程序/QA 各取所需 |

### 2.4 设计原则 (基于定位推导)

```
┌─────────────────────────────────────────────────────────────┐
│  1. 问题驱动 > 数据堆砌                                      │
│     - 首页展示"发现了什么问题"，而非"有哪些资源"             │
│     - 每个视图都应有明确的"解答什么问题"的定位               │
├─────────────────────────────────────────────────────────────┤
│  2. 渐进式披露                                               │
│     - 概览 → 详情 → 原始数据 三层结构                        │
│     - 默认折叠复杂信息，需要时再展开                         │
├─────────────────────────────────────────────────────────────┤
│  3. 角色适配                                                 │
│     - 不同用户关注不同视图                                   │
│     - 可快速切换"我关心的"信息                               │
├─────────────────────────────────────────────────────────────┤
│  4. 自包含                                                   │
│     - 单 HTML 文件，无需服务器                               │
│     - 所有资源（缩略图）内嵌为 base64                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 业界工具调研

> **已完成**: 基于官方文档和工具特性分析

### 3.1 调研对象详细分析

#### 3.1.1 PIX for Windows (Microsoft)

**界面架构**:
```
┌─────────────────────────────────────────────────────────────┐
│ Toolbar (Start Analysis | Collect Timing | Counters)        │
├──────────────────────┬──────────────────────────────────────┤
│ Event List           │ Pipeline State / Visualizers         │
│ (按 Queue 分组)       │ ┌──────────────────────────────────┐ │
│ ☑ Filter Events     │ │ State Tab | Pipeline Tab          │ │
│ ☑ Regular Expr      │ ├──────────────────────────────────┤ │
│                      │ │ VS Input | VS Output | PS | OM   │ │
│ 📋 Event Details     │ │ Shader Code (可编辑!)            │ │
│                      │ │ Rendertarget Visualizers         │ │
├──────────────────────┴──────────────────────────────────────┤
│ Timeline View (Execution Duration | EOP Duration)           │
│ ▓▓▓▓░░▓▓▓▓▓░░░▓▓▓░░▓▓▓▓▓▓▓░░░▓▓▓░░░▓▓▓▓▓░░              │
└─────────────────────────────────────────────────────────────┘
```

**核心设计特点**:
| 特点 | 说明 | 可借鉴 |
|------|------|--------|
| **Event List + Details 分离** | 列表只显示关键信息，详情在独立面板 | ✅ |
| **Timeline 可视化** | 用条形图展示 GPU 执行时间 | ✅ |
| **Visualizers** | 线框、过度绘制、深度可视化 | ⭐ 高优 |
| **Shader Edit & Continue** | 实时编辑 Shader 看效果 | ❌ 静态报告不适用 |
| **Pixel History** | 右键查看像素历史 | ⭐ 高优 |

---

#### 3.1.2 NVIDIA Nsight Graphics

**界面架构**:
```
┌─────────────────────────────────────────────────────────────┐
│ Connection | Frame Debugger | GPU Trace | Profile           │
├─────────────────────────────────────────────────────────────┤
│ GPU Trace Timeline (全帧时间线)                              │
│ ════════════════════════════════════════════════════════════│
│ SM Warp Occupancy | Memory Throughput | Cache Hit Rate      │
├──────────────────────┬──────────────────────────────────────┤
│ Resources Explorer   │ Shader Timing Heatmap               │
│ ├─ Textures          │ [像素级 Shader 执行时间着色]          │
│ ├─ Buffers           │                                      │
│ ├─ Pipelines         │ Ray Tracing Inspector               │
│ └─ Shaders           │ [加速结构可视化]                      │
└──────────────────────┴──────────────────────────────────────┘
```

**核心设计特点**:
| 特点 | 说明 | 可借鉴 |
|------|------|--------|
| **Shader Timing Heatmap** | 用热力图展示 Shader 耗时 | ⭐ 高优 |
| **资源浏览器树形结构** | Textures/Buffers/Shaders 分类清晰 | ✅ |
| **自动性能分析** | Trace analysis 自动识别瓶颈 | ⭐ 核心 |
| **多层级 Timeline** | SM/Memory/Cache 分层展示 | ✅ |
| **C++ Capture Export** | 导出可复现的代码 | ❌ 不适用 |

---

#### 3.1.3 Xcode Metal Debugger (Apple)

**界面架构**:
```
┌─────────────────────────────────────────────────────────────┐
│ Navigator         │ Editor                │ Utilities       │
├───────────────────┼───────────────────────┼─────────────────┤
│ 📁 Frame Outline  │ Dependency Graph      │ Quick Help      │
│ ├─ Pass 0         │ [渲染通道依赖图]       │                 │
│ │  ├─ Draw 0      │                       │ Attributes      │
│ │  └─ Draw 1      │ ─────────────────     │ ├─ Format       │
│ └─ Pass 1         │ Attachment Viewer     │ ├─ Size         │
│                   │ [RT/Depth 可视化]      │ └─ Usage        │
│ 📊 Performance    │                       │                 │
│ 📷 Attachments    │ Shader Debugger       │ Memory          │
│ 📦 Resources      │ [断点调试 Shader]      │ GPU Time        │
└───────────────────┴───────────────────────┴─────────────────┘
```

**核心设计特点**:
| 特点 | 说明 | 可借鉴 |
|------|------|--------|
| **Dependency Graph** | 渲染通道依赖关系可视化 | ⭐ 高优 |
| **三栏布局** | Navigator / Editor / Utilities | ✅ |
| **极简主义** | 只展示当前上下文相关信息 | ⭐ 核心 |
| **Performance 分离** | 性能数据独立视图 | ✅ |
| **Inline Attributes** | 右侧面板快速查看属性 | ✅ |

---

#### 3.1.4 Google AGI (Android GPU Inspector)

**界面架构**:
```
┌─────────────────────────────────────────────────────────────┐
│ System Profiler | Frame Profiler                            │
├─────────────────────────────────────────────────────────────┤
│ Frame Timeline (GPU Counters 可视化)                        │
│ ┌─ CPU ════════════════════════════════════════════════ ┐   │
│ ├─ GPU ▓▓▓▓░░▓▓▓▓▓░░░▓▓▓░░▓▓▓▓▓▓▓░░░▓▓▓░░░▓▓▓▓▓░░      │   │
│ ├─ Memory ────────────────────────────────────────────  │   │
│ └─ Battery ─────────────────────────────────────────── ┘   │
├──────────────────────┬──────────────────────────────────────┤
│ Commands (API Calls) │ State (Pipeline/Resources)           │
│ ├─ vkCmdDraw         │ ┌─ Framebuffer Attachments ─────────┐│
│ ├─ vkCmdBindPipeline │ │ Color0 | Depth | Stencil          ││
│ └─ ...               │ └─────────────────────────────────────┘│
└──────────────────────┴──────────────────────────────────────┘
```

**核心设计特点**:
| 特点 | 说明 | 可借鉴 |
|------|------|--------|
| **System vs Frame 分离** | 系统级 vs 帧级分析 | ✅ |
| **GPU Counter 时间线** | Mali/Adreno 硬件计数器 | ✅ (Mali) |
| **命令列表+状态分离** | 左侧命令、右侧状态 | ✅ |
| **Web 技术栈 (Electron)** | 跨平台、可离线 | ⭐ 参考 |
| **Framebuffer Attachments** | RT/Depth 直观展示 | ✅ |

---

#### 3.1.5 RenderDoc (参考对象)

**界面架构**:
```
┌─────────────────────────────────────────────────────────────┐
│ Event Browser    │ Texture Viewer / Pipeline State          │
├──────────────────┼──────────────────────────────────────────┤
│ 📁 Frame         │ [当前选中资源的详细视图]                   │
│ ├─ Pass: GBuffer │                                          │
│ │  ├─ EID 12     │ Tabs: Inputs | Outputs | Vertex | ...   │
│ │  └─ EID 15     │                                          │
│ └─ Pass: Lighting│ Texture Viewer:                          │
│                  │ ┌────────────────────────────────────────┐│
│ 📊 API Inspector │ │ RGBA | R | G | B | A | Custom          ││
│ 📷 Texture List  │ │ [纹理预览 + 通道分离]                   ││
│ 🔧 Pipeline State│ └────────────────────────────────────────┘│
│ 📦 Resource Insp │                                          │
└──────────────────┴──────────────────────────────────────────┘
```

**核心设计特点** (我们应该增强而非复制的):
| 特点 | 说明 | 我们的策略 |
|------|------|-----------|
| Event Browser 树形 | Pass/EID 层级 | ✅ 保留 |
| Texture Viewer | RGBA 通道分离 | ✅ 已实现 |
| Pipeline State | 详细状态面板 | ✅ 需增强可视化 |
| **无自动问题检测** | 需用户手动发现 | ⭐ 我们的核心差异化 |
| **需安装软件** | 无法分享 | ⭐ HTML 报告核心价值 |

---

### 3.2 设计原则提取 (跨工具共性)

```
┌─────────────────────────────────────────────────────────────┐
│  原则 1: 分层信息架构                                        │
│  ───────────────────────────────────────────────────────────│
│  所有工具都采用: Timeline → Event List → Detail 三层结构     │
│  用户可从宏观到微观逐步深入                                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  原则 2: 主从布局 (Master-Detail)                            │
│  ───────────────────────────────────────────────────────────│
│  左侧/上方: 列表/导航 (选择目标)                             │
│  右侧/下方: 详情面板 (展示选中项)                            │
│  避免: 多个独立页面跳转                                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  原则 3: 可视化优先                                          │
│  ───────────────────────────────────────────────────────────│
│  - Timeline 用条形图而非数字表格                             │
│  - Shader 耗时用热力图叠加在渲染结果上                       │
│  - 依赖关系用图而非文字描述                                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  原则 4: 上下文感知                                          │
│  ───────────────────────────────────────────────────────────│
│  选中某个事件后，所有面板都更新为该事件的上下文               │
│  避免: 需要用户手动关联不同视图的信息                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  原则 5: 问题导向入口                                        │
│  ───────────────────────────────────────────────────────────│
│  Nsight: "Trace analysis automatically identifying blockers"│
│  PIX: Visualizers 直接高亮问题区域 (红色=失败)               │
│  我们: 首页应该是 "发现的问题" 而非 "资源列表"               │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 可借鉴的具体 UI 模式

| UI 模式 | 来源工具 | 应用场景 | 实现优先级 |
|---------|---------|----------|-----------|
| **Issues Dashboard** | Nsight | 首页概览 | P0 |
| **Timeline Bar Chart** | PIX/AGI | 性能可视化 | P1 |
| **Shader Heatmap** | Nsight | Shader 分析 | P2 |
| **Dependency Graph** | Xcode | Pass 关系可视化 | P2 |
| **Pixel History** | PIX | 像素调试 | P3 |
| **Master-Detail Layout** | 全部 | 基础架构 | P0 |
| **Collapsible Panels** | RenderDoc | 灵活布局 | P0 |
| **Channel Selector** | RenderDoc | 纹理查看 | ✅ 已有 |
| **Wireframe Overlay** | PIX | 几何可视化 | P3 |

---

## 4. 重构设计方案

> **基于目的定义和业界调研结果**

### 4.1 新信息架构

#### 4.1.1 核心理念：问题驱动的分析报告

```
旧架构 (数据堆砌):                新架构 (问题驱动):
┌───────────────────────┐        ┌───────────────────────┐
│ 纹理列表 (N 个)        │        │ 📊 Issues Dashboard   │ ← 首页
│ 事件列表 (M 个)        │        │   "发现 12 个问题"     │
│ 资源详情...            │        ├───────────────────────┤
│ 杂乱堆放               │        │ 📁 Event Browser      │ ← 流程视图
└───────────────────────┘        │ 📷 Resource Explorer  │ ← 资源视图
                                 │ ⚡ Performance        │ ← 性能视图
                                 └───────────────────────┘
```

#### 4.1.2 四视图架构 (取代原来的三视图)

| 视图 | 定位 | 解答的问题 | 主要用户 |
|------|------|-----------|---------|
| **🎯 Issues** | 问题中心 | "有什么问题？严重程度？如何修复？" | 全部 |
| **📁 Events** | 流程视图 | "渲染顺序是什么？Pass 结构？" | 引擎程序员 |
| **📦 Resources** | 资源视图 | "有哪些纹理/Shader？质量如何？" | TA |
| **⚡ Performance** | 性能视图 | "耗时分布？带宽消耗？热点在哪？" | 性能工程师 |

#### 4.1.3 统一导航结构

```
┌─────────────────────────────────────────────────────────────────────┐
│ 🎮 RDC Analyzer                            capture.rdc | 生成时间   │
├─────────────────────────────────────────────────────────────────────┤
│ [🎯 Issues] [📁 Events] [📦 Resources] [⚡ Performance]             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│                        ┌─ 视图切换后此区域变化 ─┐                    │
│                        │                       │                    │
│                        │   主内容区             │                    │
│                        │                       │                    │
│                        └───────────────────────┘                    │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│ Frame: 帧缩略图 | Draw Calls: 234 | Textures: 89 | Issues: 12      │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 4.2 各视图详细设计

#### 4.2.1 🎯 Issues Dashboard (首页)

**设计目标**: 一眼看清"这一帧有什么问题"

```
┌─────────────────────────────────────────────────────────────────────┐
│ 问题概览                                              [导出报告 ▼]  │
├─────────────────────────────────────────────────────────────────────┤
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐    │
│ │ 🔴 严重 3   │ │ 🟠 警告 5   │ │ 🟡 建议 4   │ │ ✅ 通过 28  │    │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘    │
├─────────────────────────────────────────────────────────────────────┤
│ 问题列表 (按严重程度排序)                        [过滤: 全部 ▼]     │
├─────────────────────────────────────────────────────────────────────┤
│ 🔴 [TEX-001] 纹理 "hero_diffuse" 超过 4096x4096 限制              │
│    尺寸: 8192x8192 | 内存: 256MB | 建议: 降采样或拆分               │
│    [跳转到资源] [查看使用位置]                                      │
├─────────────────────────────────────────────────────────────────────┤
│ 🔴 [PERF-002] Draw Call #145 过度绘制率 > 300%                     │
│    覆盖像素: 12M | 实际输出: 3M | 建议: 检查 Z-Prepass              │
│    [跳转到事件] [查看 Pipeline State]                               │
├─────────────────────────────────────────────────────────────────────┤
│ 🟠 [SHADER-003] Pixel Shader "PBR_Main" ALU 指令数 > 500           │
│    指令数: 623 | 建议: 简化光照计算或使用 LUT                        │
│    [查看 Shader 代码] [Mali 分析报告]                               │
├─────────────────────────────────────────────────────────────────────┤
│ 🟡 [TEX-004] 发现 3 组重复纹理 (哈希相同)                          │
│    可节省内存: 45MB | [查看详情]                                    │
└─────────────────────────────────────────────────────────────────────┘
```

**问题分类体系**:
| 类别 | 前缀 | 检测规则示例 |
|------|------|-------------|
| 纹理问题 | TEX- | 尺寸过大、格式不合理、缺少 mipmap |
| 性能问题 | PERF- | 过度绘制、Draw Call 过多、带宽超标 |
| Shader 问题 | SHADER- | 指令数过多、分支过深、寄存器超限 |
| 状态问题 | STATE- | 不必要的状态切换、资源未绑定 |
| 资源问题 | RES- | 重复资源、未使用资源 |

---

#### 4.2.2 📁 Events View (事件浏览器)

**设计目标**: 理解渲染流程和 Pass 结构

```
┌─────────────────────────────────────────────────────────────────────┐
│ 事件浏览器                              [搜索: ________] [过滤 ▼]   │
├───────────────────────┬─────────────────────────────────────────────┤
│ 事件树                │ 详情面板                                    │
│ ─────────────────── │ ─────────────────────────────────────────── │
│ 📁 Frame              │ [Pipeline] [Inputs] [Outputs] [Shader]     │
│ ├─ 📁 Pass: GBuffer   │ ┌─────────────────────────────────────────┐ │
│ │  ├─ 🎨 EID 12      │ │ Render Targets:                         │ │
│ │  ├─ 🎨 EID 15      │ │ ┌─────┐ ┌─────┐ ┌─────┐                 │ │
│ │  └─ 🎨 EID 18      │ │ │RT0  │ │RT1  │ │Depth│                 │ │
│ ├─ 📁 Pass: Lighting  │ │ └─────┘ └─────┘ └─────┘                 │ │
│ │  └─ 🎨 EID 45      │ │                                         │ │
│ └─ 📁 Pass: PostFX    │ │ Viewport: 1920x1080                     │ │
│    └─ 🎨 EID 89      │ │ Blend: SrcAlpha, OneMinusSrcAlpha       │ │
│                       │ │ DepthTest: LessEqual, Write: On        │ │
│ ──────────────────── │ └─────────────────────────────────────────┘ │
│ 📊 统计                │                                            │
│ Draw Calls: 234       │ Shader: PBR_Main.hlsl                      │
│ Passes: 5             │ [查看代码] [Mali 分析]                       │
│ RT 切换: 8            │                                            │
└───────────────────────┴─────────────────────────────────────────────┘
```

**与旧版对比**:
| 旧版 | 新版 |
|------|------|
| Event 列表和详情混在一起 | Master-Detail 分离 |
| Pass 结构需要手动理解 | 树形结构自动分组 |
| Pipeline State 分散多处 | 统一详情面板 |

---

#### 4.2.3 📦 Resources View (资源浏览器)

**设计目标**: 审查资源质量，发现冗余

```
┌─────────────────────────────────────────────────────────────────────┐
│ 资源浏览器                     [类型: 纹理 ▼] [排序: 大小 ▼] [网格|列表]│
├───────────────────────┬─────────────────────────────────────────────┤
│ 资源列表 (89 个纹理)  │ 纹理详情: hero_diffuse                       │
│ ─────────────────── │ ─────────────────────────────────────────── │
│ ┌─────┐ hero_diffuse │ ┌───────────────────────────────────────────┐ │
│ │     │ 2048x2048    │ │  [RGBA] [R] [G] [B] [A]                    │ │
│ │ 🖼️  │ BC3 | 5.3MB  │ │  ┌─────────────────────────────────────┐  │ │
│ └─────┘ ⚠️ 高使用率   │ │  │                                     │  │ │
│                       │ │  │        [纹理预览区]                 │  │ │
│ ┌─────┐ env_skybox   │ │  │                                     │  │ │
│ │     │ 1024x1024    │ │  └─────────────────────────────────────┘  │ │
│ │ 🖼️  │ BC6H | 2.1MB │ └───────────────────────────────────────────┘ │
│ └─────┘              │                                              │
│                       │ 📋 属性                                      │
│ ┌─────┐ ui_button    │ ├─ 格式: BC3 (DXT5)                          │
│ │     │ 256x256      │ ├─ 尺寸: 2048 x 2048                         │
│ │ 🖼️  │ BC7 | 0.3MB  │ ├─ Mips: 11 级                               │
│ └─────┘ 🔴 重复      │ ├─ 内存: 5.3 MB                              │
│                       │ └─ 使用次数: 23 次 (EID 12, 45, 89...)       │
│ [加载更多...]        │                                              │
│                       │ ⚠️ 问题: 使用率过高，考虑合批或降采样        │
└───────────────────────┴─────────────────────────────────────────────┘
```

**资源类型支持**:
- 纹理 (Texture2D, TextureCube, Array)
- Shader (VS, PS, CS...)
- Buffer (VB, IB, CB)
- Sampler
- Render Target

---

#### 4.2.4 ⚡ Performance View (性能视图)

**设计目标**: 识别性能瓶颈，提供优化方向

```
┌─────────────────────────────────────────────────────────────────────┐
│ 性能分析                                         [Mali ▼] [刷新]    │
├─────────────────────────────────────────────────────────────────────┤
│ 帧时间线 (横轴: Event ID)                                           │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ GPU Time                                                        │ │
│ │ ▓▓▓░░▓▓▓▓▓▓▓▓░░░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░▓▓▓▓▓░░░▓▓░░░           │ │
│ │ ────────────────────────────────────────────────────────────── │ │
│ │ 0ms                                               16.7ms        │ │
│ └─────────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│ 性能指标                                                            │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐    │
│ │ Draw Calls  │ │ 三角形数     │ │ 纹理带宽    │ │ 过度绘制    │    │
│ │ 234         │ │ 1.2M        │ │ 890 MB/s   │ │ 2.3x        │    │
│ │ 🟡 中等     │ │ ✅ 正常     │ │ 🔴 高       │ │ 🟠 偏高     │    │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘    │
├─────────────────────────────────────────────────────────────────────┤
│ Top 5 耗时事件                                                      │
│ ─────────────────────────────────────────────────────────────────  │
│ 1. EID 145 - DrawIndexed (12000 tris) ████████████████ 2.3ms       │
│ 2. EID 89  - DrawIndexed (8000 tris)  ███████████     1.5ms       │
│ 3. EID 201 - Dispatch (256x256x1)     █████████       1.2ms       │
│ 4. EID 45  - DrawIndexed (5000 tris)  ███████         0.9ms       │
│ 5. EID 12  - DrawIndexed (3000 tris)  █████           0.7ms       │
├─────────────────────────────────────────────────────────────────────┤
│ Mali GPU 建议 (如可用)                                              │
│ ├─ Shader "PBR_Main": 建议减少 TEX 指令，当前 45 次采样             │
│ └─ Pass "Lighting": 建议使用 Tile-based 优化，减少带宽              │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 4.3 技术架构重构

#### 4.3.1 模板组件化

**目标**: 将 12000+ 行的单文件拆分为可维护的组件

```
scripts/rdc_analyzer/
├── templates/                      # 新建模板目录
│   ├── base/
│   │   ├── layout.html            # 基础布局框架
│   │   ├── styles.css             # 公共样式
│   │   └── scripts.js             # 公共脚本
│   ├── components/
│   │   ├── header.html            # 顶部导航
│   │   ├── footer.html            # 底部状态栏
│   │   ├── issues_card.html       # 问题卡片
│   │   ├── texture_card.html      # 纹理卡片
│   │   ├── event_tree.html        # 事件树
│   │   └── timeline.html          # 时间线组件
│   └── views/
│       ├── issues.html            # Issues 视图
│       ├── events.html            # Events 视图
│       ├── resources.html         # Resources 视图
│       └── performance.html       # Performance 视图
├── generators/
│   ├── report_generator.py        # 统一报告生成器
│   ├── template_engine.py         # 简易模板引擎
│   └── data_transformer.py        # 数据转换层
└── core/                          # 保持现有分析逻辑
    ├── issue_detector.py          # 新增: 统一问题检测
    └── ...
```

#### 4.3.2 数据契约 (JSON Schema)

**统一的中间数据格式**:
```json
{
  "meta": {
    "capture_name": "game_frame_001.rdc",
    "api": "D3D11",
    "generated_at": "2025-01-21T12:00:00Z"
  },
  "summary": {
    "draw_calls": 234,
    "textures": 89,
    "shaders": 12,
    "issues": { "critical": 3, "warning": 5, "info": 4 }
  },
  "issues": [
    {
      "id": "TEX-001",
      "severity": "critical",
      "category": "texture",
      "title": "纹理超过尺寸限制",
      "resource_id": "res_45",
      "details": { ... },
      "suggestion": "..."
    }
  ],
  "events": [ ... ],
  "resources": {
    "textures": [ ... ],
    "shaders": [ ... ],
    "buffers": [ ... ]
  },
  "performance": { ... }
}
```

#### 4.3.3 渐进式迁移策略

```
Phase 1: 基础架构          Phase 2: 功能迁移          Phase 3: 增强
─────────────────────     ─────────────────────     ─────────────────
├─ 新建模板目录            ├─ Issues 视图              ├─ Timeline 可视化
├─ 实现模板引擎            ├─ Resources 视图           ├─ Dependency Graph
├─ 定义数据契约            ├─ Events 视图              ├─ Shader Heatmap
├─ issue_detector.py       ├─ Performance 视图         ├─ 对比报告整合
└─ 生成 v2 报告骨架        └─ 废弃旧生成器             └─ 高级可视化
```

---

## 5. 开发计划

> **详细任务分解，按 2-5 分钟粒度规划**

### 5.0 总览

| Phase | 名称 | 预估工时 | 目标产物 |
|-------|------|---------|---------|
| **Phase 1** | 基础架构 | 2-3 天 | 模板引擎 + 数据契约 + v2 骨架 |
| **Phase 2** | 功能迁移 | 3-4 天 | 四视图完整实现 |
| **Phase 3** | 增强功能 | 2-3 天 | 高级可视化 + 对比报告整合 |

---

### 5.1 Phase 1: 基础架构 (P0)

#### 5.1.1 创建模板目录结构
```
[ ] 创建 scripts/rdc_analyzer/templates/ 目录
[ ] 创建 templates/base/ 子目录
[ ] 创建 templates/components/ 子目录
[ ] 创建 templates/views/ 子目录
[ ] 创建 scripts/rdc_analyzer/generators/ 目录
```

#### 5.1.2 实现简易模板引擎
```python
# generators/template_engine.py
[ ] 实现 load_template(name: str) -> str
    - 从 templates/ 目录加载 HTML 文件
    - 支持 {{variable}} 占位符替换
[ ] 实现 render(template: str, data: dict) -> str
    - 递归替换嵌套变量
    - 支持简单的 {{#each items}} 循环
[ ] 实现 include(component_name: str) -> str
    - 支持组件嵌套 {{include "header"}}
[ ] 单元测试: tests/test_template_engine.py
```

#### 5.1.3 定义数据契约 Schema
```
[ ] 创建 schemas/report_data.json (JSON Schema)
[ ] 定义 meta 字段 (capture_name, api, generated_at)
[ ] 定义 summary 字段 (draw_calls, textures, issues 计数)
[ ] 定义 issues 数组结构 (id, severity, category, title, details, suggestion)
[ ] 定义 events 数组结构 (eid, name, pass_name, ...)
[ ] 定义 resources 对象 (textures, shaders, buffers)
[ ] 定义 performance 对象 (timeline, metrics, top_events)
[ ] 创建 Python dataclass: core/report_schema.py
```

#### 5.1.4 实现问题检测器
```python
# core/issue_detector.py
[ ] 定义 Issue dataclass (id, severity, category, title, ...)
[ ] 定义 Severity 枚举 (critical, warning, info, pass)
[ ] 定义 Category 枚举 (texture, performance, shader, state, resource)
[ ] 实现 detect_texture_issues(textures: list) -> list[Issue]
    - 规则: 尺寸 > 4096 → critical
    - 规则: 无 mipmap → warning
    - 规则: 非压缩格式 → info
[ ] 实现 detect_performance_issues(events: list) -> list[Issue]
    - 规则: Draw Calls > 500 → warning
    - 规则: 过度绘制 > 3x → critical
[ ] 实现 detect_duplicate_resources(textures: list) -> list[Issue]
    - 复用现有 optimization_advisor.py 逻辑
[ ] 实现 run_all_detectors(data: dict) -> list[Issue]
[ ] 单元测试: tests/test_issue_detector.py
```

#### 5.1.5 创建基础布局模板
```html
<!-- templates/base/layout.html -->
[ ] HTML5 基础结构
[ ] 顶部导航栏占位 {{include "header"}}
[ ] 四视图标签页容器
[ ] 底部状态栏占位 {{include "footer"}}
[ ] 内联 CSS 变量 (深色主题)
[ ] 内联基础 JS (视图切换逻辑)
```

#### 5.1.6 生成 v2 报告骨架
```python
# generators/report_generator.py
[ ] 实现 generate_v2_report(data: dict, output_path: str)
    - 加载 layout.html
    - 渲染四个视图模板
    - 内联所有 CSS/JS
    - 输出单 HTML 文件
[ ] 创建 CLI 入口点: --report-version=2
[ ] 集成测试: 生成空报告验证结构
```

**Phase 1 验收标准**:
- [ ] `py -3 -m rdc_analyzer test.rdc --report-version=2` 生成包含四视图标签页的 HTML
- [ ] 视图切换正常工作
- [ ] 深色主题样式正确

---

### 5.2 Phase 2: 功能迁移 (P0)

#### 5.2.1 Issues 视图实现
```html
<!-- templates/views/issues.html -->
[ ] 问题统计卡片 (严重/警告/建议/通过)
[ ] 问题列表容器 (虚拟滚动或分页)
[ ] 问题卡片组件 {{include "issues_card"}}
[ ] 过滤器 (按严重程度/类别)
[ ] 导出按钮 (JSON/Markdown)
```
```javascript
[ ] renderIssuesList(issues: Issue[])
[ ] filterIssues(severity: string, category: string)
[ ] jumpToResource(resourceId: string) // 切换到 Resources 视图
[ ] jumpToEvent(eid: number) // 切换到 Events 视图
```

#### 5.2.2 Events 视图实现
```html
<!-- templates/views/events.html -->
[ ] 左侧事件树 (Pass 分组)
[ ] 右侧详情面板 (Pipeline State)
[ ] 搜索框
[ ] 统计面板 (Draw Calls / Passes / RT 切换)
```
```javascript
[ ] buildEventTree(events: Event[])
[ ] selectEvent(eid: number)
[ ] renderPipelineState(event: Event)
[ ] renderShaderInfo(event: Event)
```
```
[ ] 从 generate_offline_report.py 迁移:
    - Event Browser 树形结构逻辑
    - Pipeline State 渲染逻辑
    - Shader 查看器 Modal
```

#### 5.2.3 Resources 视图实现
```html
<!-- templates/views/resources.html -->
[ ] 左侧资源列表 (网格/列表切换)
[ ] 右侧详情面板 (纹理预览 + 属性)
[ ] 类型过滤器 (纹理/Shader/Buffer)
[ ] 排序选项 (大小/名称/使用次数)
```
```javascript
[ ] renderResourceList(resources: Resource[], viewMode: 'grid'|'list')
[ ] selectResource(resourceId: string)
[ ] renderTextureDetail(texture: Texture)
[ ] renderChannelPreview(channel: 'rgba'|'r'|'g'|'b'|'a')
```
```
[ ] 从 generate_offline_report.py 迁移:
    - 纹理列表逻辑 (含虚拟滚动)
    - 通道分离预览
    - Lightbox 模态框
```

#### 5.2.4 Performance 视图实现
```html
<!-- templates/views/performance.html -->
[ ] 帧时间线图表 (SVG/Canvas)
[ ] 性能指标卡片 (Draw Calls/三角形/带宽/过度绘制)
[ ] Top N 耗时事件列表
[ ] Mali GPU 建议区域 (可选)
```
```javascript
[ ] renderTimeline(events: Event[])
[ ] renderMetricsCards(metrics: Metrics)
[ ] renderTopEvents(events: Event[], n: number)
[ ] renderMaliSuggestions(maliData: MaliData)
```
```
[ ] 从 generate_offline_report.py 迁移:
    - Stats Grid 逻辑
    - Hotspot 组件
    - RT Timeline 组件
```

#### 5.2.5 废弃旧生成器
```
[ ] 在 generate_offline_report.py 添加 deprecation warning
[ ] 更新 generate_real_report.py 调用 v2 生成器
[ ] 更新 __main__.py 默认使用 v2
[ ] 保留 --legacy-report 选项 (兼容)
```

**Phase 2 验收标准**:
- [ ] 四个视图功能完整
- [ ] 现有测试 RDC 文件生成的 v2 报告与 v1 功能等价
- [ ] 视图间跳转正常工作

---

### 5.3 Phase 3: 增强功能 (P1-P2)

#### 5.3.1 Timeline 可视化增强 (P1)
```
[ ] 实现 SVG 条形图组件
[ ] 支持 Hover 显示详情
[ ] 支持点击跳转到事件
[ ] 支持缩放/平移
```

#### 5.3.2 Dependency Graph (P2)
```
[ ] 使用 dagre.js 或手工布局
[ ] Pass 节点可视化
[ ] RT 依赖边
[ ] 点击节点查看详情
```

#### 5.3.3 Shader Heatmap (P2)
```
[ ] 如有 Mali 数据，叠加热力图到帧缩略图
[ ] 按 Shader 指令数着色
[ ] 点击区域高亮相关事件
```

#### 5.3.4 对比报告整合 (P1)
```
[ ] 统一对比报告到 v2 模板
[ ] 新增 Comparison 视图标签
[ ] 双列对比布局
[ ] 差异高亮
```

#### 5.3.5 文档与清理
```
[ ] 更新 README.md
[ ] 删除冗余的旧 demo 生成器
[ ] 更新 DOC_INDEX.md
```

**Phase 3 验收标准**:
- [ ] Timeline 图表可交互
- [ ] 对比报告使用 v2 模板
- [ ] 文档完整

---

## 附录

### A. 代码位置速查

```
scripts/rdc_analyzer/
├── generate_offline_report.py   # 主报告生成器 (12000+ 行)
├── generate_real_report.py      # 调用 offline 生成器
├── analyze_rdc.py               # 旧版分析 + 报告 (使用 base.html)
├── analyze_rdc_mali.py          # Mali 专用分析器
├── compare_rdc.py               # 双帧对比
├── export_textures.py           # 纹理导出 + 画廊
├── exporters/
│   ├── templates/
│   │   └── base.html            # 旧版模板 (170 行)
├── components/
│   ├── rt_timeline_component.py # RT 时间线组件
│   └── hotspot_component.py     # 热点分析组件
├── core/
│   ├── optimization_advisor.py  # 优化建议生成器
│   └── performance_standalone.py # 性能分析器
└── tools/
    └── report_linking.py        # 报告链接管理
```

### B. 待解决的技术债务

1. 12000+ 行内联 HTML 需要拆分为组件化模板
2. CSS 重复定义需要提取公共样式库
3. JavaScript 逻辑需要模块化
4. 多个独立报告生成器需要统一接口
