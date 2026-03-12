# Report Engine 重构计划

> **创建时间**: 2025-07-25  
> **目标**: 将 13,700 行的 `generate_offline_report.py` 单体脚本重构为模块化的 `report_engine` 包  
> **预计总时长**: 约 2 小时

---

## 🏗️ 框架设计

### 类图 (Class Diagram)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              REPORT ENGINE ARCHITECTURE                              │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Data Sources  │    │   Data Sources  │    │   Data Sources  │
│   (RDC API)     │    │   (XML File)    │    │   (JSON File)   │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                         ADAPTERS LAYER                          │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐       │
│  │ RdcAdapter    │  │ XmlAdapter    │  │ JsonAdapter   │       │
│  │ from_rdc()    │  │ from_xml()    │  │ from_json()   │       │
│  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘       │
└──────────┼──────────────────┼──────────────────┼────────────────┘
           │                  │                  │
           ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ReportDataContract (contract.py)             │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ @dataclass                                                  │ │
│  │ class ReportDataContract:                                   │ │
│  │     meta: MetaData              # 元信息                    │ │
│  │     textures: List[Texture]     # 纹理列表                  │ │
│  │     shaders: List[Shader]       # Shader 列表              │ │
│  │     events: List[Event]         # 事件/DrawCall            │ │
│  │     buffers: List[Buffer]       # Buffer 列表              │ │
│  │     issues: List[Issue]         # 问题列表                  │ │
│  │     performance: PerfData       # 性能数据                  │ │
│  │     pipeline_states: List[...]  # Pipeline State           │ │
│  │     # --- 扩展字段 (v2.1) ---                               │ │
│  │     duplicate_analysis: Dict    # 重复分析                  │ │
│  │     usage_analysis: Dict        # 使用热度分析              │ │
│  │     rt_tracking: Dict           # RT 追踪                   │ │
│  │     hotspot_data: Dict          # 热点数据                  │ │
│  │     optimization: Dict          # 优化建议                  │ │
│  │     frame_thumbnail: str        # 帧缩略图 Base64           │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                      RENDERER LAYER                             │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ class HtmlRenderer:                                        │ │
│  │     def __init__(self, contract: ReportDataContract)       │ │
│  │     def render(self) -> str  # 返回完整 HTML               │ │
│  │     def render_to_file(self, path: Path)                   │ │
│  │                                                             │ │
│  │ 内部调用:                                                   │ │
│  │   _load_css() -> str         # 从 assets/styles.css       │ │
│  │   _load_js() -> str          # 从 assets/scripts.js       │ │
│  │   _render_section(name) -> str                             │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                        ASSETS (Static Files)                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ assets/         │  │ templates/      │  │ sections/       │ │
│  │   styles.css    │  │   base.html     │  │   summary.py    │ │
│  │   scripts.js    │  │   (optional)    │  │   textures.py   │ │
│  │   icons/        │  │                 │  │   events.py     │ │
│  └─────────────────┘  └─────────────────┘  │   shaders.py    │ │
│                                            │   issues.py     │ │
│                                            └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 模块职责表

| 模块 | 文件 | 职责 | 行数上限 |
|------|------|------|----------|
| **Contract** | `contract.py` | 定义 `ReportDataContract` 数据结构 | 200 行 |
| **Adapters** | `adapters/rdc_adapter.py` | 从 RDC API 提取数据填充 Contract | 300 行 |
|              | `adapters/xml_adapter.py` | 从 XML 文件提取数据填充 Contract | 300 行 |
|              | `adapters/json_adapter.py` | 从 JSON 加载 Contract | 100 行 |
| **Renderer** | `renderers/html_renderer.py` | 核心 HTML 渲染逻辑 | 500 行 |
| **Sections** | `sections/summary.py` | 生成摘要部分 HTML | 150 行 |
|              | `sections/textures.py` | 生成纹理列表 HTML | 200 行 |
|              | `sections/events.py` | 生成事件列表 HTML | 200 行 |
|              | `sections/issues.py` | 生成问题列表 HTML | 150 行 |
| **Assets** | `assets/styles.css` | 全部 CSS 样式 | N/A |
|            | `assets/scripts.js` | 全部 JavaScript | N/A |
| **Utils** | `utils/asset_loader.py` | 资源加载工具 | 100 行 |

### 接口定义 (Python Protocols)

```python
# contract.py
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Protocol
from pathlib import Path


@dataclass
class MetaData:
    """报告元信息"""
    capture_name: str = ""
    api: str = "Unknown"           # D3D11, D3D12, Vulkan, OpenGL
    source: str = "unknown"        # rdc, xml, json
    generated_at: str = ""
    frame_thumbnail: str = ""      # Base64 图像数据


@dataclass
class ReportDataContract:
    """统一的报告数据契约 v2.1"""
    
    # --- 核心字段 (v2.0) ---
    meta: MetaData = field(default_factory=MetaData)
    textures: List[Dict[str, Any]] = field(default_factory=list)
    shaders: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    buffers: List[Dict[str, Any]] = field(default_factory=list)
    issues: List[Dict[str, Any]] = field(default_factory=list)
    performance: Dict[str, Any] = field(default_factory=dict)
    pipeline_states: List[Dict[str, Any]] = field(default_factory=list)
    
    # --- 扩展字段 (v2.1, 对应 generate_offline_html 参数) ---
    duplicate_analysis: Dict[str, Any] = field(default_factory=dict)
    usage_analysis: Dict[str, Any] = field(default_factory=dict)
    event_pass_data: Dict[str, Any] = field(default_factory=dict)
    optimization_data: Dict[str, Any] = field(default_factory=dict)
    rt_tracking_data: Dict[str, Any] = field(default_factory=dict)
    hotspot_data: Dict[str, Any] = field(default_factory=dict)
    texture_usage_map: Dict[str, Any] = field(default_factory=dict)
    report_links: Dict[str, str] = field(default_factory=dict)
    manifest_data: Dict[str, Any] = field(default_factory=dict)


class DataAdapter(Protocol):
    """数据适配器协议"""
    def load(self, source: Any) -> ReportDataContract:
        """从数据源加载并返回 Contract"""
        ...


class SectionRenderer(Protocol):
    """Section 渲染器协议"""
    def render(self, contract: ReportDataContract) -> str:
        """渲染并返回 HTML 片段"""
        ...
```

### 数据流图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA FLOW                                   │
└─────────────────────────────────────────────────────────────────────┘

[用户输入]                    [处理流程]                    [输出]
    │                             │                          │
    ▼                             │                          │
┌─────────┐                       │                          │
│ .rdc    │───────┐               │                          │
└─────────┘       │               │                          │
                  ▼               │                          │
┌─────────┐  ┌────────────┐       │                          │
│ .xml    │──│ Adapter    │───────┼────►┌─────────────────┐  │
└─────────┘  │ Selection  │       │     │ ReportData      │  │
                  ▲               │     │ Contract        │  │
┌─────────┐       │               │     └────────┬────────┘  │
│ .json   │───────┘               │              │           │
└─────────┘                       │              ▼           │
                                  │     ┌─────────────────┐  │
                                  │     │ HtmlRenderer    │  │
                                  │     │   + CSS/JS      │  │
                                  │     └────────┬────────┘  │
                                  │              │           │
                                  │              ▼           │
                                  │     ┌─────────────────┐  │
                                  └────►│ output.html     │──┘
                                        └─────────────────┘
```

### 目录结构

```
scripts/rdc_analyzer/
├── report_engine/                   # 新模块化引擎
│   ├── __init__.py                  # 包入口，导出核心类
│   ├── contract.py                  # ReportDataContract 定义 (~200 行)
│   │
│   ├── adapters/                    # 数据适配器
│   │   ├── __init__.py
│   │   ├── rdc_adapter.py           # 从 RDC API 加载 (~300 行)
│   │   ├── xml_adapter.py           # 从 XML 文件加载 (~300 行)
│   │   └── json_adapter.py          # 从 JSON 加载 (~100 行)
│   │
│   ├── renderers/                   # 渲染器
│   │   ├── __init__.py
│   │   └── html_renderer.py         # HTML 生成逻辑 (~500 行)
│   │
│   ├── sections/                    # HTML Section 生成器
│   │   ├── __init__.py
│   │   ├── summary.py               # 摘要 Section (~150 行)
│   │   ├── textures.py              # 纹理 Section (~200 行)
│   │   ├── events.py                # 事件 Section (~200 行)
│   │   ├── issues.py                # 问题 Section (~150 行)
│   │   └── shaders.py               # Shader Section (~150 行)
│   │
│   ├── assets/                      # 静态资源
│   │   ├── styles.css               # 提取的 CSS (~2000 行)
│   │   └── scripts.js               # 提取的 JS (~1500 行)
│   │
│   └── utils/                       # 工具函数
│       ├── __init__.py
│       └── asset_loader.py          # 资源加载 (~100 行)
│
├── __main__.py                      # CLI 入口 (更新)
├── generate_offline_report.py       # 兼容层 (保留，调用 report_engine)
└── examples/                        # 示例脚本
    ├── generate_real_report.py      # 移动自根目录
    └── rdc_to_html.py               # 移动自根目录
```

---

## 📋 背景

### 当前问题

1. **入口碎片化**：6 个脚本功能重叠
   - `main.py` - 尝试统一但未完成
   - `analyze_xml_report.py` - XML 分析
   - `rdc_to_bundle_report.py` - 4 页报告包
   - `generate_offline_report.py` - 核心渲染（13,700 行）
   - `generate_real_report.py` - 真实数据报告
   - `rdc_to_html.py` - 简版入口

2. **巨型单体**：`generate_offline_report.py` 包含
   - CSS 样式（~2,000 行字符串）
   - JavaScript 代码（~1,500 行字符串）
   - HTML 模板（~3,000 行）
   - 数据处理逻辑（~7,000 行）

3. **难以维护**：AI 辅助开发时容易遗忘上下文

### 重构目标

```
scripts/rdc_analyzer/
├── report_engine/           # 新模块化引擎
│   ├── __init__.py
│   ├── contract.py          # 数据契约 (ReportDataContract)
│   ├── assets/
│   │   ├── styles.css       # 提取的 CSS
│   │   └── scripts.js       # 提取的 JS
│   ├── renderers/
│   │   └── html_renderer.py # 核心渲染逻辑
│   └── sections/            # 报告各部分模块
│       ├── summary.py
│       ├── textures.py
│       ├── events.py
│       └── ...
├── __main__.py              # 统一 CLI 入口
└── examples/                # 演示脚本（原冗余脚本移至此）
```

---

## 🚀 执行计划

### Phase 1: 创建目录骨架 (P1)

**任务**：
- [ ] 创建 `report_engine/` 目录结构
- [ ] 创建 `__init__.py` 文件确保可导入
- [ ] 验证 import 不报错

**验收命令**：
```powershell
py -3 -c "from rdc_analyzer import report_engine; print('P1 OK')"
```

**预计时长**: 5 分钟

---

### Phase 2: 提取 CSS 资源 (P2)

**任务**：
- [ ] 从 `generate_offline_report.py` 提取 CSS 字符串
- [ ] 写入 `report_engine/assets/styles.css`
- [ ] 在原文件中改为读取外部 CSS 文件

**验收命令**：
```powershell
# 1. CSS 文件存在且非空
Test-Path scripts/rdc_analyzer/report_engine/assets/styles.css

# 2. 语法检查（无报错即可）
py -3 -m py_compile scripts/rdc_analyzer/generate_offline_report.py
```

**预计时长**: 15 分钟

---

### Phase 3: 提取 JS 资源 (P3)

**任务**：
- [ ] 从 `generate_offline_report.py` 提取 JavaScript 字符串
- [ ] 写入 `report_engine/assets/scripts.js`
- [ ] 在原文件中改为读取外部 JS 文件

**验收命令**：
```powershell
# 1. JS 文件存在且非空
Test-Path scripts/rdc_analyzer/report_engine/assets/scripts.js

# 2. 语法检查
py -3 -m py_compile scripts/rdc_analyzer/generate_offline_report.py
```

**预计时长**: 15 分钟

---

### Phase 4: 提取数据契约 (P4)

**任务**：
- [ ] 定义 `ReportDataContract` dataclass
- [ ] 包含所有报告所需的数据字段
- [ ] 提供 `from_xml()` 和 `from_rdc()` 工厂方法（存根）

**验收命令**：
```powershell
py -3 -c "from rdc_analyzer.report_engine.contract import ReportDataContract; print('P4 OK')"
```

**预计时长**: 20 分钟

---

### Phase 5: 提取核心渲染器 (P5)

**任务**：
- [ ] 将 `generate_offline_html()` 核心逻辑迁移到 `html_renderer.py`
- [ ] 使用 `ReportDataContract` 作为输入
- [ ] 保持 `generate_offline_report.py` 作为兼容层调用新模块

**验收命令**：
```powershell
# 1. 导入检查
py -3 -c "from rdc_analyzer.report_engine.renderers.html_renderer import render_html; print('P5 OK')"

# 2. 完整语法检查
py -3 -m py_compile scripts/rdc_analyzer/report_engine/renderers/html_renderer.py
```

**预计时长**: 30 分钟

---

### Phase 6: 统一入口 + 清理 (P6)

**任务**：
- [ ] 更新 `__main__.py` 添加 `report` 子命令
- [ ] 将冗余脚本移至 `examples/`
  - `generate_real_report.py` → `examples/`
  - `rdc_to_html.py` → `examples/`
- [ ] 更新 `docs/INDEX.md`

**验收命令**：
```powershell
# 1. CLI 帮助可用
py -3 -m rdc_analyzer report --help

# 2. 冗余脚本已移动
Test-Path scripts/rdc_analyzer/examples/generate_real_report.py
```

**预计时长**: 20 分钟

---

## ⚠️ 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| CSS/JS 提取不完整导致样式丢失 | 每个阶段验收前手动对比输出 HTML |
| 数据契约字段遗漏 | 从现有代码逆向提取所有数据字段 |
| 兼容性破坏 | 保留 `generate_offline_report.py` 作为 wrapper |

---

## 📝 决策记录

| 日期 | 决策 | 原因 |
|------|------|------|
| 2025-07-25 | 采用 6 阶段渐进式重构 | 用户要求"每阶段有验收" |
| 2025-07-25 | 保留原入口作为兼容层 | 避免破坏现有用户工作流 |

---

## ✅ 验收定义 (Definition of Done)

- [ ] 所有 6 个阶段验收命令通过
- [ ] `py -3 -m rdc_analyzer report sample.xml -o out.html` 可生成报告
- [ ] `generate_offline_report.py` 作为兼容入口仍可正常工作
- [ ] `docs/INDEX.md` 更新反映新架构

---

## 📌 执行状态

| 阶段 | 状态 | 完成时间 |
|------|------|----------|
| P1 - 目录骨架 | ⏳ 待执行 | - |
| P2 - CSS 提取 | ⏳ 待执行 | - |
| P3 - JS 提取 | ⏳ 待执行 | - |
| P4 - 数据契约 | ⏳ 待执行 | - |
| P5 - 核心渲染器 | ⏳ 待执行 | - |
| P6 - 统一入口 | ⏳ 待执行 | - |
