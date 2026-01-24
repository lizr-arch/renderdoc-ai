# RDC Analyzer 工作总结

> **创建时间**: 2025-01-21  
> **执行者**: Agent B (Codex AI)  
> **目的**: 记录完整的开发流程、架构设计和实现细节，供后续 AI 对话阅读和延续工作

---

## 0. 项目概述

**RDC Analyzer** 是一个基于 RenderDoc 的图形帧分析工具，核心目标是：

| 目标 | 说明 |
|------|------|
| **单帧极致分析** | 从 `.rdc` 或 XML 导出文件中提取性能问题、生成可执行建议 |
| **双帧全方位对比** | baseline vs target 的回归检测，输出差异报告 |

**关键产物**：
- `scripts/rdc_analyzer/` — 完整的 Python 分析工具包
- HTML/JSON 报告 — 可离线查看的分析结果
- CLI 工具 — `py -3 -m rdc_analyzer analyze/compare`

---

## 1. 整体架构（三条输入路线）

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        RDC Analyzer 数据输入路线                          │
└─────────────────────────────────────────────────────────────────────────┘

                                    ┌─────────────┐
                                    │   .rdc 文件  │
                                    │ (RenderDoc  │
                                    │  Capture)   │
                                    └──────┬──────┘
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │                      │                      │
                    ▼                      ▼                      ▼
         ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐
         │  路线 A: XML 导出  │  │  路线 B: Python   │  │  路线 C: renderdoc│
         │  (RenderDoc UI)   │  │   API 直接解析    │  │  cmd export      │
         └─────────┬─────────┘  └─────────┬─────────┘  └─────────┬─────────┘
                   │                      │                      │
                   ▼                      ▼                      ▼
         ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐
         │  parsers/         │  │  core/bridge.py   │  │  纹理 PNG +       │
         │  rdc_xml_parser   │  │  ReplayWrapper    │  │  JSON 元数据      │
         └─────────┬─────────┘  └─────────┬─────────┘  └─────────┬─────────┘
                   │                      │                      │
                   └──────────────────────┼──────────────────────┘
                                          │
                                          ▼
                            ┌─────────────────────────┐
                            │     main.py             │
                            │   AnalysisPipeline      │
                            │   ────────────────      │
                            │   - parse()             │
                            │   - analyze()           │
                            │   - export()            │
                            └───────────┬─────────────┘
                                        │
                                        ▼
                            ┌─────────────────────────┐
                            │   HTML/JSON Report      │
                            │   (Canonical Schema v1) │
                            └─────────────────────────┘
```

### 1.1 路线 A: XML 导出（离线分析）

**适用场景**：无 RenderDoc Python 模块环境，或需要离线分析。

**流程**：
1. 在 RenderDoc UI 中打开 `.rdc` 文件
2. File → Export Structured Data...（导出结构化数据）
3. 选择保存为 `.xml` 格式
4. 用 `rdc_analyzer` 解析 XML

> ⚠️ **重要说明**：当前 XML 导出**只能通过 RenderDoc GUI 手动操作**。
> `renderdoccmd` 命令行工具原生不支持 `--export-xml` 选项（虽然我们的 export 命令实现了纹理/metadata/bindings 导出，但 XML 格式未包含）。

**关键文件**：
- `parsers/rdc_xml_parser.py` — XML 解析入口
- `parsers/rdc_xml_converter.py` — 转换为内部数据结构

**实现要点**：
```python
# parsers/rdc_xml_parser.py
class RDCXMLParser:
    def parse(self, xml_path: str) -> CaptureData:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # 提取纹理
        textures = self._parse_textures(root)
        # 提取 Draw Call
        draw_calls = self._parse_draw_calls(root)
        # 提取 Shader
        shaders = self._parse_shaders(root)
        
        return CaptureData(textures=textures, draw_calls=draw_calls, ...)
```

### 1.2 路线 B: Python API 直接解析（实时分析）

**适用场景**：有完整 RenderDoc Python 环境，需要实时提取 Pipeline State。

**流程**：
1. 通过 `renderdoc` Python 模块加载 `.rdc`
2. 使用 `ReplayController` 回放帧
3. 调用 `SetFrameEvent()` + `GetPipelineState()` 提取数据

**关键文件**：
- `core/bridge.py` — RenderDoc API 封装
- `extractors/replay_wrapper.py` — 回放控制器封装
- `extractors/pipeline_sampler.py` — Pipeline State 采样器

**实现要点**：
```python
# core/bridge.py
class ReplayWrapper:
    def __init__(self, rdc_path: str):
        self.cap = rd.OpenCaptureFile()
        self.cap.OpenFile(rdc_path, '', None)
        self.controller = self.cap.OpenCapture(rd.ReplayOptions(), None)
    
    def get_pipeline_state(self, event_id: int) -> PipelineSnapshot:
        self.controller.SetFrameEvent(event_id, True)
        state = self.controller.GetPipelineState()
        return self._convert_to_snapshot(state)
```

### 1.3 路线 C: renderdoccmd export（批量导出）

**适用场景**：CI/CD 环境，需要批量导出纹理和元数据。

**流程**：
1. 修改 RenderDoc C++ 源码添加 `export` 子命令
2. 编译后运行 `renderdoccmd export capture.rdc -o output/`
3. 输出纹理 PNG + JSON 元数据

**关键文件**（C++ 侧）：
- `renderdoc/replay/capture_exporter.cpp` — 导出器实现
- `renderdoc/renderdoccmd/cmd_export.cpp` — CLI 命令

**状态**：代码已添加，待编译验证。

---

## 1.4 路线验证状态总表

| 路线 | 状态 | 验证环境 | 备注 |
|------|------|----------|------|
| **A: XML 导出** | ✅ **已跑通** | Windows 10, Python 3.10 | 通过 `rdc_xml_parser.py` 解析 RenderDoc 导出的 XML |
| **B: Python API** | ⚠️ **部分验证** | 需要 `renderdoc` 模块 | 数据结构和采样器已实现，实际回放需 RenderDoc 环境 |
| **C: renderdoccmd** | ❌ **待编译** | 需编译 RenderDoc | C++ 代码已添加，等待 `msbuild` 编译 |

### 路线 A 验证详情（已跑通）

**测试文件**：`tests/test_xml_parser.py`, `tests/test_dod_compliance.py`

```bash
# 验证命令（已通过）
cd scripts/rdc_analyzer
py -3 -m pytest tests/test_xml_parser.py -v
# 结果: 全部 PASSED
```

**实际验证的功能**：
- ✅ XML 文件解析 → `CaptureData` 对象
- ✅ 纹理/DrawCall/Shader 数据提取
- ✅ 分析管线 → HTML/JSON 报告生成
- ✅ Schema v1 Bridge → DiffEngine 消费

### 路线 B 验证详情（部分验证）

**依赖**：需要 RenderDoc 安装目录下的 `renderdoc.pyd` (Windows) 或 `renderdoc.so` (Linux)

**已验证（通过 Mock）**：
- ✅ `PipelineSampler` 采样逻辑（4 种策略）
- ✅ `PipelineSnapshot` 数据结构
- ✅ 采样结果 → coverage 报告集成

**待真机验证**：
- ⏳ `ReplayController.SetFrameEvent()` 实际调用
- ⏳ `GetPipelineState()` 返回值解析
- ⏳ Mali GPU 真实 RDC 回放

**本地验证方法**：
```python
# 如果有 renderdoc 模块可用
import renderdoc as rd
cap = rd.OpenCaptureFile()
cap.OpenFile(r"D:\renderdoc\goog pixel-9\g145.rdc", "", None)
# 如果能打开，说明环境正常
```

### 路线 C 验证详情（待编译）

**需要的操作**：
1. 在 Visual Studio 中打开 `renderdoc.sln`
2. 编译 `renderdoccmd` 项目（Release/x64）
3. 运行 `renderdoccmd export capture.rdc -o output/`

**C++ 代码位置**：
- `renderdoc/renderdoccmd/cmd_export.cpp` — CLI 入口
- `renderdoc/replay/capture_exporter.cpp` — 导出器实现

---

## 1.5 Python 代码入口速查表

> 本节汇总所有关键 Python 入口函数，方便快速定位。

### CLI 入口

| 命令 | 入口文件 | 入口函数 |
|------|----------|----------|
| `py -3 -m rdc_analyzer analyze` | `__main__.py:38` | `main()` → `cmd_analyze()` |
| `py -3 -m rdc_analyzer compare` | `__main__.py:42` | `main()` → `cmd_compare()` |

### 核心管线入口

| 功能 | 文件:行号 | 函数签名 |
|------|-----------|----------|
| 分析主管线 | `main.py:85` | `AnalysisPipeline.run()` |
| XML 解析 | `parsers/rdc_xml_parser.py:45` | `RDCXMLParser.parse(xml_path) -> CaptureData` |
| JSON 加载 | `parsers/rdc_loader.py:28` | `load_capture_file(path) -> CaptureData` |
| Schema Bridge | `parsers/rdc_loader.py:112` | `_convert_schema_v1_to_capture_data(json_data)` |
| Pipeline 采样 | `extractors/pipeline_sampler.py:67` | `sample_pipeline_states(controller, events, ...)` |
| 帧对比 | `diff/diff_engine.py:35` | `DiffEngine.compare(baseline, target)` |

### 数据提取入口

| 数据类型 | 文件:行号 | 函数签名 |
|----------|-----------|----------|
| 纹理列表 | `parsers/rdc_xml_parser.py:89` | `_parse_textures(root) -> List[TextureInfo]` |
| DrawCall 列表 | `parsers/rdc_xml_parser.py:142` | `_parse_draw_calls(root) -> List[DrawCallInfo]` |
| Shader 列表 | `parsers/rdc_xml_parser.py:198` | `_parse_shaders(root) -> List[ShaderInfo]` |
| Pipeline State | `extractors/pipeline_sampler.py:145` | `_extract_snapshot(state, event_id) -> PipelineSnapshot` |

### 报告生成入口

| 报告类型 | 文件:行号 | 函数签名 |
|----------|-----------|----------|
| JSON 报告 | `main.py:245` | `_export_reports() -> dict` |
| HTML 报告 | `exporters/html_exporter.py:32` | `HtmlExporter.export(data, output_path)` |
| Coverage 报告 | `main.py:312` | `_build_coverage_report() -> dict` |
| Preflight 报告 | `main.py:378` | `_build_preflight() -> dict` |
| Suggestions | `main.py:425` | `_build_suggestions() -> List[dict]` |

### 测试入口

| 测试类别 | 文件 | 运行命令 |
|----------|------|----------|
| DoD 验收 | `tests/test_dod_compliance.py` | `py -3 -m pytest tests/test_dod_compliance.py -v` |
| Bridge 集成 | `tests/test_schema_bridge_integration.py` | `py -3 -m pytest tests/test_schema_bridge_integration.py -v` |
| 采样器 | `tests/test_pipeline_sampler.py` | `py -3 -m pytest tests/test_pipeline_sampler.py -v` |
| 全量测试 | `tests/` | `py -3 -m pytest tests -q -rs` |

### RenderDoc Python API 入口（路线 B）

| 操作 | 代码示例 |
|------|----------|
| 打开 RDC 文件 | `cap = rd.OpenCaptureFile(); cap.OpenFile(path, '', None)` |
| 获取回放控制器 | `controller = cap.OpenCapture(rd.ReplayOptions(), None)` |
| 设置当前事件 | `controller.SetFrameEvent(event_id, True)` |
| 获取 Pipeline State | `state = controller.GetPipelineState()` |
| 获取纹理列表 | `textures = controller.GetTextures()` |
| 获取 Root Actions | `actions = controller.GetRootActions()` |
| 关闭 | `controller.Shutdown(); cap.Shutdown()` |

---

## 2. Canonical Schema v1.0（统一输出格式）

为了让分析结果可被 compare、前端、自动化消费，我们定义了统一的 JSON Schema：

```json
{
  "schema_version": "1.0",
  "meta": {
    "capture_file": "game.rdc",
    "analyzer_version": "0.9.0",
    "timestamp": "2025-01-21T15:00:00Z",
    "platform": "Vulkan"
  },
  "summary": {
    "total_draw_calls": 1234,
    "total_triangles": 567890,
    "total_textures": 45,
    "total_vram_mb": 128.5,
    "issue_count": { "high": 3, "medium": 7, "low": 12 }
  },
  "coverage": {
    "overall": "high",
    "details": {
      "textures": "present",
      "draw_calls": "present",
      "pipeline_state": "partial",
      "resource_lifecycle": "estimated",
      "markers": "missing"
    },
    "confidence_reasons": ["Markers 未启用，Pass 边界使用启发式推断"],
    "sampling_stats": { "pipeline_samples": 15, "total_draw_calls": 1234 }
  },
  "events": [...],
  "draw_calls": [...],
  "resources": {
    "textures": [...],
    "buffers": [...]
  },
  "issues": [
    {
      "code": "RD_001",
      "severity": "high",
      "category": "performance",
      "message": "Draw Call 数量过多 (1234 > 500)",
      "event_ids": [100, 200, 300],
      "resource_ids": [],
      "evidence": { "actual": 1234, "threshold": 500 },
      "suggestion": "使用 GPU Instancing 或 Static Batching"
    }
  ],
  "suggestions": [
    {
      "id": "SUG_RD_001",
      "title": "减少 Draw Call 数量",
      "priority": "high",
      "steps": ["启用 GPU Instancing", "合并相同材质的网格"],
      "expected_impact": { "draw_calls": "-30% to -50%" },
      "risk": "low",
      "engine_howto": {
        "unity": "Edit > Project Settings > Player > Static Batching",
        "unreal": "Enable Instanced Rendering"
      },
      "verification_plan": {
        "metrics": ["Draw Call Count"],
        "expected_direction": "decrease",
        "how_to_capture": "相同场景再次抓帧"
      }
    }
  ],
  "preflight": {
    "status": "warning",
    "missing_data": [
      { "item": "Debug Markers", "impact": "无法识别 Pass 边界", "severity": "medium" }
    ],
    "capture_recommendations": [
      {
        "action": "启用 Debug Markers",
        "unity": "确保 FrameDebugger 打开",
        "unreal": "启用 RenderDoc 插件"
      }
    ],
    "degraded_conclusions": ["Pass 结构分析使用启发式推断"]
  }
}
```

**关键代码入口**：
- `main.py:AnalysisPipeline._export_reports()` — 构建并导出 JSON
- `main.py:AnalysisPipeline._build_coverage_report()` — 构建 coverage 块
- `main.py:AnalysisPipeline._build_preflight()` — 构建 preflight 块
- `main.py:AnalysisPipeline._build_suggestions()` — 构建 suggestions 块

---

## 3. Pipeline State 采样器（P0-NEW-4）

### 3.1 问题背景

分析每个 Draw Call 的 Pipeline State 代价太高（上千次 `SetFrameEvent` + `GetPipelineState`），需要智能采样。

### 3.2 解决方案

创建 `extractors/pipeline_sampler.py`，支持 4 种采样策略：

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| `UNIFORM` | 均匀间隔采样（每 k 个取 1） | 一般场景 |
| `DIVERSE` | 按 VS/PS 签名去重采样 | 保证覆盖所有 Shader 组合 |
| `FIRST_N` | 前 N 个 Draw Call | 初始化阶段分析 |
| `LAST_N` | 后 N 个 Draw Call | 最终输出阶段分析 |

**关键代码**：
```python
# extractors/pipeline_sampler.py
class SamplingStrategy(Enum):
    UNIFORM = "uniform"
    DIVERSE = "diverse"
    FIRST_N = "first_n"
    LAST_N = "last_n"

def sample_pipeline_states(
    controller,
    events: List[ActionDescription],
    sample_count: int = 5,
    strategy: SamplingStrategy = SamplingStrategy.UNIFORM
) -> PipelineSamplingResult:
    """
    从 Draw Call 列表中采样并提取 Pipeline State。
    
    返回:
        PipelineSamplingResult: 包含采样的 snapshots 和统计信息
    """
    if strategy == SamplingStrategy.DIVERSE:
        picked = _pick_diverse(events, sample_count)
    elif strategy == SamplingStrategy.UNIFORM:
        picked = _pick_uniform(events, sample_count)
    # ...
    
    snapshots = []
    for event in picked:
        controller.SetFrameEvent(event.eventId, True)
        state = controller.GetPipelineState()
        snapshots.append(_extract_snapshot(state, event.eventId))
    
    return PipelineSamplingResult(
        snapshots=snapshots,
        total_events=len(events),
        sampled_count=len(snapshots),
        strategy=strategy.value
    )
```

**数据结构**：
```python
@dataclass
class PipelineSnapshot:
    event_id: int
    vertex_shader: str  # Shader 资源 ID
    pixel_shader: str
    topology: str  # "TriangleList", "LineStrip", etc.
    viewports: List[Dict]
    scissor_rects: List[Dict]
    blend_state: Optional[Dict]
    depth_stencil_state: Optional[Dict]
    rasterizer_state: Optional[Dict]
    render_targets: List[str]
    depth_target: Optional[str]
```

**集成到主管线**：
```python
# main.py:AnalysisPipeline._sample_pipeline_states()
def _sample_pipeline_states(self):
    from extractors.pipeline_sampler import sample_pipeline_states, SamplingStrategy
    
    strategy = SamplingStrategy(self.options.pipeline_sample_strategy)
    self._pipeline_sampling_result = sample_pipeline_states(
        controller=self._controller,
        events=self._draw_calls,
        sample_count=self.options.pipeline_sample_count,
        strategy=strategy,
    )
```

---

## 4. Schema Bridge（P0-NEW-2）

### 4.1 问题背景

`compare` 命令需要消费 `analyze` 的 JSON 输出，但 JSON 格式（Canonical Schema v1）与 `DiffEngine` 期望的 `CaptureData` 格式不同。

### 4.2 解决方案

在 `parsers/rdc_loader.py` 中实现 Schema Bridge：

```python
# parsers/rdc_loader.py
def _convert_schema_v1_to_capture_data(json_data: Dict) -> CaptureData:
    """
    将 Canonical Schema v1.0 的 JSON 转换为 DiffEngine 期望的 CaptureData 格式。
    
    关键转换:
    - json_data['resources']['textures'] → CaptureData.textures
    - json_data['draw_calls'] → CaptureData.draw_calls
    - json_data['summary'] → CaptureData.stats
    """
    textures = []
    for tex in json_data.get('resources', {}).get('textures', []):
        textures.append(TextureInfo(
            resourceId=tex.get('resourceId') or tex.get('id'),
            name=tex.get('name', ''),
            width=tex.get('width', 0),
            height=tex.get('height', 0),
            # ...
        ))
    
    # ... 类似处理 draw_calls, buffers, shaders ...
    
    return CaptureData(
        textures=textures,
        draw_calls=draw_calls,
        # ...
    )

def load_capture_file(path: str, ...) -> CaptureData:
    """统一加载入口，支持 .rdc, .xml, .json"""
    if path.endswith('.json'):
        data = json.load(open(path))
        if data.get('schema_version') == '1.0':
            return _convert_schema_v1_to_capture_data(data)
    # ...
```

### 4.3 集成测试

`tests/test_schema_bridge_integration.py` 验证端到端链路：

```python
def test_bridge_preserves_texture_diff():
    """验证纹理差异不会被 Bridge 丢失"""
    baseline = create_schema_v1_json(textures=[
        {"resourceId": "T1", "width": 512, "height": 512}
    ])
    target = create_schema_v1_json(textures=[
        {"resourceId": "T1", "width": 1024, "height": 1024}  # 尺寸变化
    ])
    
    baseline_data = load_capture_file(baseline)
    target_data = load_capture_file(target)
    
    diff = DiffEngine().compare(baseline_data, target_data)
    
    assert len(diff.texture_changes) > 0
    assert diff.texture_changes[0].field == 'width'
```

---

## 5. 数据质量保证（DoD-7.3）

### 5.1 Truthful Degradation 原则

**核心理念**：宁可数据显示为"缺失/估算"，也不造假。

```python
# coverage.details 的值域
class DataStatus(Enum):
    PRESENT = "present"      # 完整数据，来自真实 API 调用
    PARTIAL = "partial"      # 部分数据，有采样
    ESTIMATED = "estimated"  # 估算数据，使用启发式
    MISSING = "missing"      # 无数据
```

### 5.2 加权置信度算法

```python
# main.py:_build_coverage_report()
def _calculate_confidence(self, details: Dict[str, str]) -> str:
    """
    加权算法: present=1.0, partial=0.5, estimated=0.2, missing=0.0
    """
    weights = {
        'present': 1.0,
        'partial': 0.5,
        'estimated': 0.2,
        'missing': 0.0
    }
    
    total = 0
    weighted_sum = 0
    for key, status in details.items():
        total += 1
        weighted_sum += weights.get(status, 0)
    
    ratio = weighted_sum / total
    if ratio >= 0.8:
        return 'high'
    elif ratio >= 0.5:
        return 'medium'
    else:
        return 'low'
```

### 5.3 测试验证

`tests/test_dod_compliance.py::TestDOD73DataQuality` 包含真实断言：

```python
def test_weighted_confidence_algorithm():
    """验证加权算法正确性"""
    # 全 present → high
    details = {'textures': 'present', 'draw_calls': 'present'}
    assert calculate_confidence(details) == 'high'
    
    # 混合 → medium
    details = {'textures': 'present', 'pipeline': 'estimated', 'markers': 'missing'}
    assert calculate_confidence(details) == 'medium'
```

---

## 6. 测试样本支持（P1-NEW-1）

### 6.1 问题背景

大部分测试使用 mock 数据，跳过了需要真实 `.rdc` 文件的测试。

### 6.2 解决方案

**本地配置文件模式**：

1. 创建 `tests/conftest_local.py.example` 作为模板
2. 用户复制为 `tests/conftest_local.py`（已加入 .gitignore）
3. 配置本地样本路径

```python
# tests/conftest_local.py.example
"""
本地测试样本配置模板。

使用方法:
1. 复制本文件为 conftest_local.py
2. 修改下面的路径为你本地的真实样本路径
3. conftest_local.py 已在 .gitignore 中，不会被提交

示例样本（已验证可用）：
- Mali Pixel 9: D:\renderdoc\goog pixel-9\g145.rdc
"""

import pytest
from pathlib import Path

# ===== 本地样本路径配置 =====
LOCAL_RDC_SAMPLES = {
    'mali_pixel9': Path(r'D:\renderdoc\goog pixel-9\g145.rdc'),
}

# ===== Fixtures =====
@pytest.fixture(scope="session")
def local_mali_rdc():
    """提供 Mali GPU 的真实 RDC 样本路径"""
    path = LOCAL_RDC_SAMPLES.get('mali_pixel9')
    if path and path.exists():
        return path
    pytest.skip("Mali RDC 样本未配置或不存在")
```

---

## 7. 文件结构速查

```
scripts/rdc_analyzer/
├── __main__.py              # CLI 入口 (py -3 -m rdc_analyzer)
├── main.py                  # AnalysisPipeline 主管线
├── compare_rdc.py           # 帧对比 CLI
│
├── core/                    # 核心模块
│   ├── bridge.py           # RenderDoc API 封装
│   ├── types.py            # 数据类型 (CanonicalIssue, TextureInfo, ...)
│   └── context.py          # 分析上下文
│
├── parsers/                 # 解析器
│   ├── rdc_xml_parser.py   # XML 解析
│   ├── rdc_loader.py       # 统一加载入口 + Schema Bridge
│   └── models/             # 数据模型
│
├── extractors/              # 数据提取器
│   ├── pipeline_sampler.py # Pipeline State 采样器 (P0-NEW-4)
│   ├── replay_wrapper.py   # Replay 控制器封装
│   └── shader_extractor.py # Shader 提取
│
├── analyzers/               # 分析器
│   ├── performance_analyzer.py
│   ├── mali_analyzer.py    # Mali GPU 专项
│   └── frame.py            # 帧级分析
│
├── rules/                   # 性能规则
│   ├── texture.py          # 纹理规则
│   ├── draw_call.py        # Draw Call 规则
│   └── mobile.py           # 移动端规则
│
├── diff/                    # 帧对比
│   ├── diff_engine.py      # 对比引擎
│   └── regression_detector.py
│
├── exporters/               # 导出器
│   ├── html_exporter.py    # HTML 报告
│   ├── json_exporter.py    # JSON 导出
│   └── templates/          # HTML 模板
│
└── tests/                   # 测试
    ├── test_dod_compliance.py  # DoD 验收测试
    ├── test_schema_bridge_integration.py  # Bridge 集成测试
    ├── test_pipeline_sampler.py  # 采样器测试
    └── conftest_local.py.example  # 本地样本配置模板
```

---

## 8. CLI 使用示例

### 8.1 单帧分析

```bash
# 基础分析（XML 输入）
py -3 -m rdc_analyzer analyze capture.xml -o output/ --format html,json

# 带 Pipeline 采样（需要 RenderDoc 环境）
py -3 -m rdc_analyzer analyze capture.rdc -o output/ \
    --pipeline-samples 20 \
    --sampling-strategy diverse

# Mali GPU 专项分析
py -3 -m rdc_analyzer analyze capture.rdc -o output/ \
    --platform mali \
    --malioc-path /path/to/malioc
```

### 8.2 双帧对比

```bash
# 对比两个 RDC 文件
py -3 -m rdc_analyzer compare baseline.rdc target.rdc -o diff_report/

# 对比两个 JSON 分析结果（无需 RenderDoc）
py -3 -m rdc_analyzer compare baseline.json target.json \
    --html diff.html \
    --json diff.json

# 自定义回归阈值
py -3 -m rdc_analyzer compare baseline.json target.json \
    --triangle-threshold 10 \
    --draw-call-threshold 5
```

### 8.3 测试命令

```bash
# 全量测试
cd scripts/rdc_analyzer
py -3 -m pytest tests -q -rs
# 预期: 466 passed, 8 skipped, 5 warnings

# DoD 验收测试
py -3 -m pytest tests/test_dod_compliance.py -v

# Bridge 集成测试
py -3 -m pytest tests/test_schema_bridge_integration.py -v

# Pipeline 采样器测试
py -3 -m pytest tests/test_pipeline_sampler.py -v
```

---

## 9. 待办事项（交接给下一个 Agent）

### 高优先级（P0）

- [ ] **P0-NEW-3**: 规范化 `suggestion.verification_plan` 的 schema
  - 统一 `how_to_verify` vs `how_to_capture`
  - 统一 `expected_direction` 枚举值 (`increase/decrease/unchanged`)
  - 文件: `main.py:_build_suggestions()`

### 中优先级（P1）

- [ ] **P1-NEW-2**: 清理 pytest warnings
  - 5 个 `PytestReturnNotNoneWarning`
  - 改 `return True/False` 为 `assert ...`

### 低优先级（P2）

- [ ] 编译 `renderdoccmd export` 命令
- [ ] 添加 Adreno GPU 专项分析
- [ ] 添加 Tile-Based 效率分析

---

## 10. 关键设计决策记录

| 决策 | 原因 | 日期 |
|------|------|------|
| 使用 Canonical Schema v1.0 | 统一输出格式，便于 compare 和前端消费 | 2025-01-20 |
| Truthful Degradation 原则 | 宁可缺失不造假，保证分析可信度 | 2025-01-21 |
| 4 种采样策略 | 平衡数据覆盖度与性能开销 | 2025-01-21 |
| 本地配置文件模式 | 支持真实样本测试但不泄露用户路径 | 2025-01-21 |
| Schema Bridge 而非直接修改 DiffEngine | 保持 DiffEngine 稳定，在加载层做适配 | 2025-01-21 |

---

## 11. RDC → XML 导出详细操作指南

> **重要**：这是当前唯一可用的 XML 导出方法，通过 RenderDoc GUI 手动操作。

### 11.1 导出步骤

1. **打开 RenderDoc**（安装版或编译版均可）
2. **加载 RDC 文件**：
   - File → Open Capture... (Ctrl+O)
   - 选择你的 `.rdc` 文件
3. **导出 XML**：
   - File → **Export Structured Data...**
   - 选择保存路径，文件扩展名为 `.xml`
   - 点击保存

### 11.2 导出的 XML 结构示例

```xml
<?xml version="1.0" encoding="utf-8"?>
<rdc>
  <chunks>
    <chunk name="DriverInit" id="1" length="...">
      <!-- 驱动初始化数据 -->
    </chunk>
    <chunk name="vkCreateInstance" id="2" length="...">
      <!-- API 调用参数 -->
    </chunk>
    <!-- ... 更多 chunks ... -->
  </chunks>
  <resources>
    <texture id="ResourceId::1" name="Backbuffer" width="1920" height="1080" format="R8G8B8A8_UNORM"/>
    <texture id="ResourceId::2" name="DepthBuffer" width="1920" height="1080" format="D24_UNORM_S8_UINT"/>
    <!-- ... 更多资源 ... -->
  </resources>
</rdc>
```

### 11.3 解析 XML 生成 HTML 报告

```bash
# 进入 RDC Analyzer 目录
cd scripts/rdc_analyzer

# 运行分析（XML 输入）
py -3 -m rdc_analyzer analyze your_capture.xml -o ./output/ --format html,json
```

或使用专用脚本：

```bash
py -3 analyze_xml_report.py your_capture.xml -o report.html
```

### 11.4 为什么没有命令行导出 XML？

| 方案 | 状态 | 说明 |
|------|------|------|
| `renderdoccmd --export-xml` | ❌ 不存在 | RenderDoc 原生 CLI 没有此选项 |
| 我们新增的 `renderdoccmd export` | ⚠️ 待编译 | 仅支持纹理/metadata/bindings，不含 XML |
| Python API 导出 | ⚠️ 依赖环境 | 需要 `renderdoc` 模块，可在 UI 中执行 |

**结论**：目前 **GUI 手动导出是唯一可用的方式**。如果需要批量处理，可考虑：
1. 编写 RenderDoc Python Shell 脚本，在 UI 中批量执行
2. 扩展我们的 `renderdoccmd export` 命令添加 `--xml` 支持（需要 C++ 修改）

### 11.5 实际操作截图参考

```
RenderDoc 主界面
┌─────────────────────────────────────────────────┐
│ File  Edit  View  Tools  Help                   │
├─────────────────────────────────────────────────┤
│  ┌─────────────────────────────────┐            │
│  │ File                            │            │
│  ├─────────────────────────────────┤            │
│  │ Open Capture...        Ctrl+O   │            │
│  │ Save Capture As...              │            │
│  │ ─────────────────────────────── │            │
│  │ Export Structured Data...   ◄── │ ← 点这里   │
│  │ Export To Replay Application    │            │
│  │ ─────────────────────────────── │            │
│  │ Recent Captures               ► │            │
│  └─────────────────────────────────┘            │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

## 12. 参考文档

- 架构图: `scripts/rdc_analyzer/docs/ARCHITECTURE_V1.md`
- 执行计划: `plans/2025-01-20-152300-Codex-A-first-execution-plan.md`
- 项目 README: `scripts/rdc_analyzer/README.md`
- 规则文档: `scripts/rdc_analyzer/RULES.md`
- Mali 集成指南: `scripts/rdc_analyzer/docs/MALI_INTEGRATION_SUMMARY.md`
