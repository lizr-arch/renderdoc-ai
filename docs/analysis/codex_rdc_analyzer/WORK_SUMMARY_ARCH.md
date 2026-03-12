# WORK_SUMMARY_ARCH — 架构与模块

- WHAT: 记录 RDC Analyzer 的架构、模块与文件结构。
- WHY: 快速理解系统组成与职责边界。
- HOW: 汇总架构描述、模块分布与目录结构，保持原文细节。

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
