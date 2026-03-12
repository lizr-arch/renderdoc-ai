# RDC Analyzer 统一架构技术设计文档 (TDD)

> **版本**: 1.0.0  
> **作者**: AI Assistant  
> **创建日期**: 2025-02-05  
> **状态**: 📝 草案 (Draft) - 待评审  
> **评审人**: _(待指定)_

---

## 目录

1. [概述与目标](#1-概述与目标)
2. [现状分析](#2-现状分析)
3. [架构设计](#3-架构设计)
4. [核心组件详细设计](#4-核心组件详细设计)
5. [数据模型设计](#5-数据模型设计)
6. [输出适配器设计](#6-输出适配器设计)
7. [跨平台支持策略](#7-跨平台支持策略)
8. [实施路线图](#8-实施路线图)
9. [风险与缓解措施](#9-风险与缓解措施)
10. [附录](#10-附录)

---

## 1. 概述与目标

### 1.1 项目背景

RDC Analyzer 是一个用于分析 RenderDoc 捕获文件 (`.rdc`) 的工具集，旨在：
- 从单帧捕获中提取性能问题
- 生成可执行的优化建议
- 支持双帧对比分析

### 1.2 核心问题

当前实现存在以下挑战：

| 问题 | 影响 | 根因 |
|------|------|------|
| **纹理/RT/Shader 提取困难** | HTML 报告缺少可视化内容 | 纯 XML 模式无法访问 GPU 回放能力 |
| **移动端 RDC 不兼容** | 无法分析 Android 捕获 | 原版 RenderDoc 跨 GPU 回放受限 |
| **输出格式单一** | 只有 HTML，无 EXE 集成 | 架构未考虑多输出适配 |
| **开发反馈周期长** | 修改 → 验证需要多步 | 缺少统一的测试框架 |

### 1.3 设计目标

1. **统一分析引擎**：一套代码，多种输出（HTML / EXE Panel / API）
2. **完整资源提取**：纹理缩略图、Shader 源码、RT 快照全覆盖
3. **跨平台兼容**：支持 PC + 移动端 RDC 文件
4. **渐进式增强**：分阶段实施，每阶段可独立交付

### 1.4 非目标 (Out of Scope)

- 实时性能分析（需要运行时插桩）
- 多帧捕获合并分析
- 商业发布版本打包

---

## 2. 现状分析

### 2.1 现有代码结构

```
scripts/rdc_analyzer/
├── __main__.py              # CLI 入口
├── main.py                  # 分析主流程
├── rdc_to_bundle_report.py  # RDC → HTML Bundle
├── analyze_xml_report.py    # XML → HTML
├── compare_rdc.py           # 双帧对比
├── parsers/
│   ├── xml_parser.py        # XML 解析器
│   └── rdc_parser.py        # RDC 直接解析（Python API）
├── analyzers/
│   ├── performance_analyzer.py
│   └── rules/               # 性能规则集
├── exporters/
│   └── html_exporter.py     # HTML 生成
└── templates/
    ├── index.html
    ├── events.html
    ├── textures.html
    ├── shaders.html
    └── recommendations.html
```

### 2.2 当前数据流

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   RDC 文件  │────▶│  XML 解析   │────▶│  分析引擎   │
└─────────────┘     └─────────────┘     └─────────────┘
       │                                       │
       │  (Python API)                         ▼
       │            ┌─────────────────────────────────────┐
       └───────────▶│  资源提取 (需要 RenderDoc 回放)      │
                    │  - 纹理内容 → PNG                    │
                    │  - Shader 源码 → GLSL/HLSL          │
                    │  - RT 快照 → PNG                    │
                    └─────────────────────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────────────┐
                    │        HTML Bundle 输出             │
                    └─────────────────────────────────────┘
```

### 2.3 能力缺口分析

| 功能 | XML 模式 | RDC + Python API | 缺口 |
|------|---------|------------------|------|
| Draw Call 列表 | ✅ | ✅ | - |
| 纹理元数据 | ✅ | ✅ | - |
| 纹理内容/缩略图 | ❌ | ✅ | **需要 Python API** |
| Shader 元数据 | ✅ | ✅ | - |
| Shader 源码 | ❌ | ✅ | **需要 Python API** |
| Pipeline State | 部分 | ✅ | **XML 信息不完整** |
| RT 快照 | ❌ | ✅ | **需要 Python API + 回放** |
| 性能计数器 | ❌ | ⚠️ 驱动依赖 | **需要 GPU 厂商 SDK** |

---

## 3. 架构设计

### 3.1 总体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           RDC Analyzer Core                             │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                        Input Layer                                 │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │ │
│  │  │  XML Parser  │  │  RDC Parser  │  │  Remote API (Future)     │ │ │
│  │  │ (Standalone) │  │ (Python API) │  │  (WebSocket/REST)        │ │ │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘ │ │
│  └─────────────────────────────┬──────────────────────────────────────┘ │
│                                ▼                                        │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                     Analysis Context                                │ │
│  │  (统一内部数据模型 - 与输入源解耦)                                   │ │
│  └─────────────────────────────┬──────────────────────────────────────┘ │
│                                ▼                                        │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                     Processing Layer                                │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │ │
│  │  │  Analyzers   │  │  Extractors  │  │  Comparators (双帧对比)  │ │ │
│  │  │ (规则引擎)   │  │ (资源提取)   │  │                          │ │ │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘ │ │
│  └─────────────────────────────┬──────────────────────────────────────┘ │
│                                ▼                                        │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                     Analysis Result                                 │ │
│  │  (JSON Schema v1.0 - 可序列化的分析结果)                            │ │
│  └─────────────────────────────┬──────────────────────────────────────┘ │
│                                ▼                                        │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                      Output Adapters                                │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │ │
│  │  │ HTML Bundle  │  │ EXE Panel    │  │ JSON API (CI/CD)         │ │ │
│  │  │ Exporter     │  │ (Qt Widget)  │  │                          │ │ │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 设计原则

| 原则 | 说明 | 实现方式 |
|------|------|----------|
| **输入解耦** | 分析逻辑不依赖输入格式 | 通过 `AnalysisContext` 抽象层 |
| **输出解耦** | 分析结果不绑定输出格式 | 通过 `AnalysisResult` + Adapter 模式 |
| **渐进增强** | 有 GPU 时提取更多信息，无 GPU 时 graceful degrade | 提取器返回 Optional 数据 |
| **可测试性** | 每个组件可独立单元测试 | 依赖注入 + Mock |

### 3.3 关键接口定义

```python
# 输入抽象
class IParser(Protocol):
    def parse(self, source: Path) -> AnalysisContext: ...

# 分析抽象
class IAnalyzer(Protocol):
    def analyze(self, ctx: AnalysisContext) -> list[Issue]: ...

# 提取抽象
class IExtractor(Protocol):
    def extract(self, ctx: AnalysisContext, output_dir: Path) -> ExtractResult: ...

# 输出抽象
class IExporter(Protocol):
    def export(self, result: AnalysisResult, output_dir: Path) -> None: ...
```

---

## 4. 核心组件详细设计

### 4.1 解析器 (Parsers)

#### 4.1.1 XML Parser

**职责**: 从 `renderdoccmd convert -c xml` 输出中提取元数据

**输入**: XML 文件路径  
**输出**: `AnalysisContext`

**局限性**:
- 无法获取纹理内容
- 无法获取 Shader 源码
- Pipeline State 信息不完整

```python
class XMLParser:
    def parse(self, xml_path: Path) -> AnalysisContext:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        ctx = AnalysisContext()
        ctx.api = root.get('api', 'Unknown')
        ctx.events = self._parse_events(root)
        ctx.textures = self._parse_textures(root)
        ctx.buffers = self._parse_buffers(root)
        ctx.shaders = self._parse_shaders(root)
        
        return ctx
```

#### 4.1.2 RDC Parser (Python API)

**职责**: 通过 RenderDoc Python API 直接解析 RDC 文件

**依赖**: 
- `renderdoc` Python 模块
- GPU 回放能力（用于提取纹理/RT）

**优势**:
- 完整的 Pipeline State
- 可提取纹理内容
- 可反编译 Shader

```python
class RDCParser:
    def __init__(self, cap: rd.CaptureFile, controller: rd.ReplayController):
        self.cap = cap
        self.controller = controller
    
    def parse(self) -> AnalysisContext:
        ctx = AnalysisContext()
        ctx.api = self.cap.DriverName()
        
        # 使用 ReplayController 获取详细信息
        ctx.events = self._parse_actions(self.controller.GetRootActions())
        ctx.textures = self._parse_textures(self.controller.GetTextures())
        ctx.shaders = self._parse_shaders(self.controller.GetShaders())
        
        return ctx
```

### 4.2 提取器 (Extractors)

#### 4.2.1 Texture Extractor

**输入**: `AnalysisContext` + 目标目录  
**输出**: PNG 文件 + 元数据映射

**实现策略**:

| 数据源 | 方法 | 质量 |
|--------|------|------|
| XML + ZIP | 解压 assets 目录 | ⭐⭐ 可能无缩略图 |
| RDC + Python API | `controller.GetTextureData()` | ⭐⭐⭐⭐⭐ 完整数据 |
| renderdoccmd export | 命令行批量导出 | ⭐⭐⭐⭐ 需要 GPU |

```python
class TextureExtractor:
    def extract(
        self, 
        ctx: AnalysisContext, 
        controller: Optional[rd.ReplayController],
        output_dir: Path
    ) -> dict[ResourceId, Path]:
        """
        提取纹理到 PNG 文件
        
        Returns:
            {resource_id: output_path} 映射
        """
        results = {}
        
        for tex in ctx.textures:
            if controller:
                # 优先使用 Python API
                data = controller.GetTextureData(tex.resource_id, ...)
                img_path = self._save_png(data, output_dir / f"{tex.resource_id}.png")
            else:
                # 回退：检查 ZIP 中是否有预导出的缩略图
                img_path = self._try_extract_from_zip(tex, output_dir)
            
            if img_path:
                results[tex.resource_id] = img_path
        
        return results
```

#### 4.2.2 Shader Extractor

**输入**: `AnalysisContext` + 目标目录  
**输出**: GLSL/HLSL/SPIR-V 源码文件

```python
class ShaderExtractor:
    def extract(
        self,
        ctx: AnalysisContext,
        controller: Optional[rd.ReplayController],
        output_dir: Path
    ) -> dict[ResourceId, ShaderSource]:
        results = {}
        
        for shader in ctx.shaders:
            if controller:
                # 获取反编译后的源码
                reflection = controller.GetShaderReflection(shader.resource_id)
                
                # 尝试多种输出格式
                for fmt in [rd.ShaderEncoding.GLSL, rd.ShaderEncoding.HLSL]:
                    source = controller.DisassembleShader(shader.resource_id, fmt)
                    if source:
                        self._save_shader(source, output_dir, shader, fmt)
                        results[shader.resource_id] = ShaderSource(
                            path=..., 
                            encoding=fmt,
                            entry_point=reflection.entryPoint
                        )
                        break
        
        return results
```

#### 4.2.3 RT Snapshot Extractor

**输入**: Event ID + `ReplayController`  
**输出**: Render Target 截图

**关键**: 需要在指定 Event 处"暂停"回放，然后读取当前绑定的 RT

```python
class RTSnapshotExtractor:
    def extract_at_event(
        self,
        controller: rd.ReplayController,
        event_id: int,
        output_dir: Path
    ) -> dict[str, Path]:
        """
        在指定 Event 处截取所有绑定的 Render Target
        
        Returns:
            {"color0": path, "color1": path, "depth": path, ...}
        """
        # 1. 移动回放位置到目标 Event
        controller.SetFrameEvent(event_id, False)
        
        # 2. 获取当前 Pipeline State
        state = controller.GetPipelineState()
        
        # 3. 读取所有 RT
        results = {}
        fb = state.GetFramebuffer()
        
        for i, rt in enumerate(fb.colorAttachments):
            if rt.resource != rd.ResourceId.Null():
                data = controller.GetTextureData(rt.resource, ...)
                path = output_dir / f"event_{event_id}_color{i}.png"
                self._save_png(data, path)
                results[f"color{i}"] = path
        
        # 深度缓冲
        if fb.depthAttachment.resource != rd.ResourceId.Null():
            # ... 类似处理
        
        return results
```

### 4.3 分析器 (Analyzers)

#### 4.3.1 性能分析器

**现有实现**: `scripts/rdc_analyzer/analyzers/performance_analyzer.py`

**规则类型**:

| 类别 | 规则示例 | 严重级别 |
|------|----------|----------|
| **纹理** | 大尺寸未压缩纹理 | Warning |
| **Draw Call** | 过多 Draw Call (>3000) | Critical |
| **Overdraw** | 大量全屏 Draw | Warning |
| **Shader** | 未使用的 Shader 绑定 | Info |
| **State** | 冗余状态切换 | Info |

#### 4.3.2 规则引擎设计

```python
@dataclass
class Rule:
    id: str
    name: str
    category: str  # "texture" | "drawcall" | "shader" | "state"
    severity: str  # "critical" | "warning" | "info"
    check: Callable[[AnalysisContext], list[Issue]]

class RuleEngine:
    def __init__(self):
        self.rules: list[Rule] = []
    
    def register(self, rule: Rule):
        self.rules.append(rule)
    
    def analyze(self, ctx: AnalysisContext) -> list[Issue]:
        issues = []
        for rule in self.rules:
            try:
                issues.extend(rule.check(ctx))
            except Exception as e:
                logger.warning(f"Rule {rule.id} failed: {e}")
        return issues
```

---

## 5. 数据模型设计

### 5.1 AnalysisContext (内部模型)

```python
@dataclass
class AnalysisContext:
    """解析后的捕获数据，与输入源解耦"""
    
    # 元数据
    api: str  # "Vulkan" | "D3D11" | "D3D12" | "OpenGL"
    driver_name: str
    capture_time: datetime
    
    # 事件数据
    events: list[EventInfo]
    
    # 资源数据
    textures: list[TextureInfo]
    buffers: list[BufferInfo]
    shaders: list[ShaderInfo]
    
    # 状态数据（可选，RDC 模式才有）
    blend_states: list[BlendState] = field(default_factory=list)
    depth_stencil_states: list[DepthStencilState] = field(default_factory=list)
    
    # 提取的资源（可选）
    texture_thumbnails: dict[ResourceId, Path] = field(default_factory=dict)
    shader_sources: dict[ResourceId, Path] = field(default_factory=dict)
    rt_snapshots: dict[int, dict[str, Path]] = field(default_factory=dict)  # event_id -> {color0: path}

@dataclass
class EventInfo:
    event_id: int
    name: str
    action_type: str  # "Draw" | "Dispatch" | "Clear" | "Copy" | ...
    
    # Draw Call 特有
    draw_index: Optional[int] = None
    vertex_count: int = 0
    instance_count: int = 1
    
    # 绑定资源
    bound_textures: list[ResourceId] = field(default_factory=list)
    bound_shaders: dict[str, ResourceId] = field(default_factory=dict)  # {"VS": id, "PS": id}
    
    # RT 快照（如果有）
    rt_snapshot: Optional[dict[str, Path]] = None

@dataclass
class TextureInfo:
    resource_id: ResourceId
    name: str
    width: int
    height: int
    depth: int = 1
    mip_levels: int = 1
    array_size: int = 1
    format: str
    memory_size: int  # bytes
    
    # 缩略图（如果已提取）
    thumbnail_path: Optional[Path] = None
```

### 5.2 AnalysisResult (输出模型)

```python
@dataclass
class AnalysisResult:
    """分析结果，可序列化为 JSON"""
    
    # 版本
    schema_version: str = "1.0.0"
    
    # 元数据
    metadata: CaptureMetadata
    
    # 统计摘要
    summary: AnalysisSummary
    
    # 检测到的问题
    issues: list[Issue]
    
    # 优化建议
    suggestions: list[Suggestion]
    
    # 资源清单
    assets: AssetManifest
    
    def to_json(self) -> dict:
        """序列化为 JSON 兼容格式"""
        return asdict(self)
    
    @classmethod
    def from_json(cls, data: dict) -> 'AnalysisResult':
        """从 JSON 反序列化"""
        return cls(**data)

@dataclass
class Issue:
    id: str
    rule_id: str
    severity: str  # "critical" | "warning" | "info"
    category: str
    title: str
    description: str
    affected_resources: list[ResourceId]
    affected_events: list[int]
    
    # 可选：修复建议
    fix_suggestion: Optional[str] = None

@dataclass
class Suggestion:
    id: str
    priority: int  # 1-10, 数字越小优先级越高
    category: str
    title: str
    description: str
    expected_impact: str  # "High" | "Medium" | "Low"
    
    # 验证方法（统一格式）
    verification: VerificationPlan

@dataclass
class VerificationPlan:
    """统一的验证计划格式"""
    method: str  # "visual_check" | "metric_compare" | "profiler" | "manual"
    steps: list[str]
    success_criteria: str
```

### 5.3 JSON Schema (输出文件格式)

```json
{
  "$schema": "https://renderdoc.org/schemas/rdc-analysis-v1.0.json",
  "schema_version": "1.0.0",
  
  "metadata": {
    "rdc_path": "D:/captures/scene.rdc",
    "api": "Vulkan",
    "driver": "NVIDIA GeForce RTX 4070 Ti",
    "capture_time": "2025-02-05T10:00:00Z",
    "analysis_time": "2025-02-05T10:05:00Z",
    "analyzer_version": "0.3.0"
  },
  
  "summary": {
    "draw_calls": 1423,
    "render_passes": 43,
    "total_events": 1479,
    "texture_count": 906,
    "texture_memory_mb": 1859.82,
    "shader_count": 362,
    "buffer_count": 2491,
    "score": 75,
    "issue_counts": {
      "critical": 0,
      "warning": 14,
      "info": 77
    }
  },
  
  "issues": [
    {
      "id": "issue-001",
      "rule_id": "TEX-001",
      "severity": "warning",
      "category": "texture",
      "title": "大尺寸未压缩纹理",
      "description": "发现 32 个 4K 纹理使用未压缩格式 (RGBA8)，建议使用 BC7 压缩",
      "affected_resources": ["ResourceId(123)", "ResourceId(456)"],
      "affected_events": [],
      "fix_suggestion": "使用 BC7 压缩可减少约 75% 显存占用"
    }
  ],
  
  "suggestions": [
    {
      "id": "sug-001",
      "priority": 2,
      "category": "texture",
      "title": "启用纹理压缩",
      "description": "将大尺寸纹理转换为 BC7 格式",
      "expected_impact": "High",
      "verification": {
        "method": "metric_compare",
        "steps": [
          "记录当前显存占用",
          "使用压缩工具转换纹理",
          "重新捕获并对比显存"
        ],
        "success_criteria": "显存占用下降 50% 以上"
      }
    }
  ],
  
  "assets": {
    "base_dir": "./",
    "thumbnails": {
      "dir": "thumbnails/",
      "count": 906,
      "format": "png"
    },
    "shaders": {
      "dir": "shaders/",
      "count": 362,
      "formats": ["glsl", "hlsl"]
    },
    "rt_snapshots": {
      "dir": "rt_snapshots/",
      "count": 43,
      "format": "png"
    }
  }
}
```

---

## 6. 输出适配器设计

### 6.1 HTML Bundle Exporter

**职责**: 将 `AnalysisResult` 渲染为可离线查看的 HTML 报告包

**输出结构**:

```
output/
├── index.html           # 总览仪表板
├── events.html          # 事件时间线
├── textures.html        # 纹理浏览器
├── shaders.html         # Shader 查看器
├── recommendations.html # 优化建议
├── data/
│   └── analysis.json    # 原始分析数据
├── assets/
│   ├── thumbnails/      # 纹理缩略图
│   ├── shaders/         # Shader 源码
│   └── rt_snapshots/    # RT 截图
├── css/
│   └── common.css       # 样式表
└── js/
    └── app.js           # 交互逻辑
```

**模板引擎**: Jinja2 / 原生字符串模板

### 6.2 EXE Panel (Qt Widget)

**两种实现方案**:

#### 方案 A: 嵌入 WebView

```cpp
class AnalysisPanelWebView : public QDockWidget
{
    Q_OBJECT
    
public:
    AnalysisPanelWebView(ICaptureContext &ctx);
    
    void LoadAnalysis(const QString &jsonPath);
    void LoadAnalysis(const QJsonObject &analysisResult);
    
private:
    QWebEngineView *m_webView;
    ICaptureContext &m_ctx;
    
    void setupUI();
    void injectBridge();  // JS ↔ C++ 桥接
};
```

**优点**: 复用 HTML 报告，开发成本低  
**缺点**: 需要 QtWebEngine，增加约 50MB 体积

#### 方案 B: 原生 Qt Widgets

```cpp
class AnalysisPanelNative : public QDockWidget
{
    Q_OBJECT
    
public:
    AnalysisPanelNative(ICaptureContext &ctx);
    
    void SetAnalysisResult(const AnalysisResult &result);
    
private:
    // 顶部摘要卡片
    QLabel *m_scoreLabel;
    QLabel *m_drawCallsLabel;
    QLabel *m_textureMemLabel;
    
    // 问题列表
    QTableWidget *m_issuesTable;
    
    // 建议列表
    QListWidget *m_suggestionsList;
    
    // 详情面板
    QStackedWidget *m_detailStack;
};
```

**优点**: 原生体验，无额外依赖  
**缺点**: 开发成本高，图表需要额外库（QtCharts）

#### 推荐方案: 混合模式

- 核心信息（问题列表、建议）使用原生 Qt
- 图表/可视化使用 QWebEngineView 嵌入轻量 HTML

### 6.3 JSON API Exporter

**用途**: CI/CD 集成、自动化测试

```python
class JSONExporter:
    def export(self, result: AnalysisResult, output_path: Path):
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result.to_json(), f, indent=2, ensure_ascii=False)
```

**CI/CD 集成示例**:

```yaml
# .github/workflows/rdc-analysis.yml
jobs:
  analyze:
    runs-on: windows-latest
    steps:
      - name: Analyze RDC
        run: |
          renderdoccmd analyze -f capture.rdc -o analysis.json
      
      - name: Check for critical issues
        run: |
          $result = Get-Content analysis.json | ConvertFrom-Json
          if ($result.summary.issue_counts.critical -gt 0) {
            exit 1
          }
```

---

## 7. 跨平台支持策略

### 7.1 移动端 RDC 兼容性

**现状**: 原版 RenderDoc 在 PC 上打开移动端 RDC 会因内存类型不匹配而失败

**解决方案**: 已在本仓库实现跨 GPU 回放补丁

| 补丁 | 位置 | 功能 |
|------|------|------|
| 内存类型重映射 | `vk_resource_funcs.cpp:337` | 根据 `propertyFlags` 查找兼容内存类型 |
| 内存对齐绕过 | `vk_resource_funcs.cpp:241` | 允许满足原设备对齐但不满足回放设备对齐 |

**详细文档**: `docs/analysis/CROSS_GPU_REPLAY_GUIDE.md`

### 7.2 API 兼容性矩阵

| 捕获 API | PC 回放 | 分析能力 |
|----------|---------|----------|
| **Vulkan (PC)** | ✅ 完整 | ✅ 完整 |
| **Vulkan (Android)** | ✅ 需跨 GPU 补丁 | ✅ 完整 |
| **D3D11** | ✅ 完整 | ✅ 完整 |
| **D3D12** | ✅ 完整 | ✅ 完整 |
| **OpenGL ES (Android)** | ⚠️ 部分 | ⚠️ 部分（扩展限制） |
| **Metal (iOS)** | ❌ 不支持 | ❌ 不支持 |

### 7.3 无 GPU 降级策略

当无法进行 GPU 回放时（如纯 CI/CD 环境）：

| 功能 | 有 GPU | 无 GPU |
|------|--------|--------|
| Draw Call 列表 | ✅ | ✅ (XML) |
| 纹理元数据 | ✅ | ✅ (XML) |
| 纹理内容 | ✅ | ❌ |
| Shader 元数据 | ✅ | ✅ (XML) |
| Shader 源码 | ✅ | ❌ |
| Pipeline State | ✅ | ⚠️ 部分 (XML) |
| RT 快照 | ✅ | ❌ |
| 性能分析 | ✅ | ✅ (基于元数据) |

---

## 8. 实施路线图

### Phase 1: 基础设施完善 (2 周)

**目标**: 统一数据模型，稳定 HTML 输出

| 任务 | 优先级 | 预估 |
|------|--------|------|
| 定义统一 JSON Schema | P0 | 2d |
| 重构 `AnalysisContext` 数据类 | P0 | 2d |
| 重构 `AnalysisResult` 数据类 | P0 | 1d |
| 完善纹理提取器 (RDC → PNG) | P0 | 3d |
| 添加 Shader 提取器 | P1 | 2d |
| 添加 RT 快照提取器 | P1 | 2d |

**交付物**:
- 完整的 JSON Schema 文档
- 纹理/Shader/RT 可正常导出

### Phase 2: CLI 工具打包 (1 周)

**目标**: 提供独立可执行的分析工具

| 任务 | 优先级 | 预估 |
|------|--------|------|
| 设计 CLI 接口 | P1 | 1d |
| PyInstaller 打包脚本 | P1 | 2d |
| 测试跨 Windows/Linux | P2 | 2d |

**交付物**:
- `rdc-analyzer.exe` 独立工具
- 使用文档

### Phase 3: RenderDoc 集成 (2 周)

**目标**: 在 RenderDoc 中添加分析面板

| 任务 | 优先级 | 预估 |
|------|--------|------|
| 设计 Panel UI 原型 | P1 | 2d |
| 实现 WebView 版本 | P2 | 5d |
| 添加"一键分析"按钮 | P2 | 2d |
| 集成测试 | P2 | 1d |

**交付物**:
- RenderDoc 内置分析面板
- 用户文档

### Phase 4: 高级功能 (按需)

| 功能 | 优先级 | 说明 |
|------|--------|------|
| 双帧对比增强 | P2 | 可视化差异 |
| Mali/Adreno 特定分析 | P3 | 移动端优化建议 |
| 性能计数器集成 | P3 | 需要 GPU 厂商 SDK |
| 远程分析服务 | P3 | WebSocket API |

---

## 9. 风险与缓解措施

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| **RenderDoc Python API 不稳定** | 中 | 高 | 锁定 RenderDoc 版本，编写兼容层 |
| **跨 GPU 补丁引入新 bug** | 中 | 中 | 保持原始行为作为 fallback |
| **EXE 打包体积过大** | 低 | 低 | 使用 PyInstaller 排除选项 |
| **Qt WebEngine 部署复杂** | 中 | 中 | 优先考虑原生 Qt 方案 |
| **移动端 RDC 兼容性问题** | 中 | 中 | 收集更多测试用例，持续修复 |

---

## 10. 附录

### 10.1 术语表

| 术语 | 定义 |
|------|------|
| **RDC** | RenderDoc Capture，帧捕获文件格式 |
| **Event** | 一次 GPU API 调用 |
| **Draw Call** | 触发 GPU 绘制的 API 调用 |
| **RT (Render Target)** | 渲染目标，即 GPU 写入的缓冲区 |
| **Pipeline State** | 当前 GPU 管线的完整配置 |

### 10.2 参考文档

- RenderDoc Python API: https://renderdoc.org/docs/python_api/
- Vulkan 规范: https://www.khronos.org/registry/vulkan/
- 跨 GPU 回放指南: `docs/analysis/CROSS_GPU_REPLAY_GUIDE.md`
- 项目索引: `docs/analysis/PROJECT_INDEX.md`

### 10.3 变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2025-02-05 | 初始版本 |

---

**文档结束**

> **下一步**: 请评审本文档，确认方向后开始 Phase 1 实施。
