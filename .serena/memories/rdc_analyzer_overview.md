# scripts/rdc_analyzer（二次开发模块）概览

## 目标/定位
- `scripts/rdc_analyzer/` 是一个围绕 RenderDoc 捕获（.rdc）做“离线/半离线分析 + 报告生成”的 Python 工具集合。

## 主要使用路径（多条并行工作流）
1) RenderDoc API / Replay 驱动（需要 renderdoc 模块 + 通常需要可回放环境/GPU）
- CLI 入口：`scripts/rdc_analyzer/__main__.py:26`（`python -m rdc_analyzer analyze ...`）
- 新端到端管线：`scripts/rdc_analyzer/main.py:147`（`AnalysisPipeline`）
- 便捷入口：`scripts/rdc_analyzer/main.py:1124`（`analyze()`）

2) 纹理导出 + 100% 离线 HTML 纹理报告
- 纹理导出（RenderDoc API）：`scripts/rdc_analyzer/export_textures.py:40`（TextureExporter）/ `scripts/rdc_analyzer/export_textures.py:165`
- 离线报告生成器：`scripts/rdc_analyzer/generate_offline_report.py:65`（load_textures_from_export）/ `scripts/rdc_analyzer/generate_offline_report.py:133`（generate_offline_html）

3) XML 离线分析路径（从 RenderDoc 导出的 XML 解析）
- XML 解析：`scripts/rdc_analyzer/parse_rdc_xml.py:462`（parse_rdc_xml）
- XML -> AnalysisContext 桥：`scripts/rdc_analyzer/core/bridge.py:28`（XMLToContextBridge）

4) 纯二进制/离线解析（不依赖 renderdoc 模块，但能力有限/偏实验）
- RDC format spec：`scripts/rdc_analyzer/docs/rdc_format_spec.md:1`
- 主要离线解析器（Vulkan chunk/SPIR-V 为主）：`scripts/rdc_analyzer/rdc_parser.py:1`
- `parsers/binary_parser.py`：D3D11 chunk 映射 + LZ4 解压：`scripts/rdc_analyzer/parsers/binary_parser.py:289`

## 体系结构（可扩展点）
- 核心数据模型：`scripts/rdc_analyzer/core/types.py:235`（ParsedData 等），上下文：`scripts/rdc_analyzer/core/context.py:26`
- 分析器：`scripts/rdc_analyzer/analyzers/base.py:14`（BaseAnalyzer）+ `analyzers/*.py`
- 规则系统：`scripts/rdc_analyzer/rules/base.py:15`（BaseRule + RuleRegistry）、`scripts/rdc_analyzer/rules/runner.py:14`（RuleRunner），规则集合 `rules/*.py`
- 报告输出：
  - reporters：`scripts/rdc_analyzer/reporters/`（JSON/HTML/CSV/Markdown/Console）
  - exporters：`scripts/rdc_analyzer/exporters/html_exporter.py:1`（交互式 HTML，模板在 `exporters/templates/`）

## 维护性/风险提示
- 存在“旧管线/新管线/离线报告脚本”并行：`pipeline.py` 与 `main.py` 的职责有重叠。
- 大文件重构建议记录：`scripts/rdc_analyzer/docs/REFACTOR_ANALYSIS.md:1`（html_exporter.py / rdc_parser.py 等）。
- 测试框架：`scripts/rdc_analyzer/pytest.ini:1`，集成测试参考：`scripts/rdc_analyzer/tests/test_pipeline_integration.py:1`。
