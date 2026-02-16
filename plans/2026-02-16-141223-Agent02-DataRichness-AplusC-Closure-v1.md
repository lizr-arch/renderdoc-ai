# Plan: Data Richness A+C Closure v1 (Coverage Transparency + Schema Annotation)

- Time: 2026-02-16 14:12:23
- Agent: Agent02
- Spec source: conversation `/spec` on 2026-02-16
- Goal: 在不引入 Replay（B 路线）的前提下，让 A+C 的输出“数据丰富度”可度量、可解释、可回归验证。

## Scope / Assumptions

### In scope
- 在 Canonical Schema v1 输出中新增 `data_richness`（或同等命名）块，用于声明 A/C 覆盖度与缺口（基于基线文档的静态字段表）。
- 在 A 路线 HTML 报告中展示/附带 data_richness 摘要（可为简化文本/JSON 片段）。
- 补齐 DoD/Schema 相关测试：验证 `data_richness` 结构稳定且必需字段存在。
- 更新 Schema 文档：明确新增字段含义与来源边界。

### Out of scope
- 不改 RenderDoc C++ 或 renderdoccmd。
- 不实现 Replay（B 路线）字段抓取。
- 不扩展 DiffEngine 逻辑或新增规则算法。

### Assumptions
- `main.py::_export_reports()` 为 Canonical Schema v1 的单一输出口。
- `analyze_xml_report.py` 为 A 路线 XML→HTML 的独立入口。
- “数据丰富度基线”文档是权威缺口清单（缺失字段需标记为 requires replay 或 xml 扩展）。

## Navigation Evidence (Codemap First)

codemap queries (max 3):
1) `codemap "def _export_reports" -Num 20`
2) `codemap "analyze_xml_report" -Num 20`
3) `codemap "test_dod_compliance" -Num 20`

candidate hits (>=3):
- [renderdoc] `scripts/rdc_analyzer/main.py:1158`
  - `def _export_reports(self, output_dir: Path) -> List[str]:`
- [renderdoc] `scripts/rdc_analyzer/main.py:1495`
  - `def _build_coverage_report(self) -> Dict[str, Any]:`
- [renderdoc] `scripts/rdc_analyzer/main.py:1649`
  - `def _build_preflight(self, coverage: Dict[str, Any]) -> Dict[str, Any]:`
- [renderdoc] `scripts/rdc_analyzer/analyze_xml_report.py:9`
  - `py -3 analyze_xml_report.py capture.xml -o report.html`
- [renderdoc] `scripts/rdc_analyzer/tests/test_dod_compliance.py`
  - `scripts/rdc_analyzer/tests/test_dod_compliance.py`

follow-ups (1-2) and why:
- `scripts/rdc_analyzer/main.py:1158`：新增 `data_richness` 输出块的唯一入口。
- `scripts/rdc_analyzer/analyze_xml_report.py`：A 路线 HTML 输出需附带/展示 data_richness 摘要。

next step:
- OpenGrok xref:
  - http://127.0.0.1:8080/source/xref/renderdoc/scripts/rdc_analyzer/main.py#1158
  - http://127.0.0.1:8080/source/xref/renderdoc/scripts/rdc_analyzer/analyze_xml_report.py#9
- Then use Serena/LSP for precise symbol edits once /do starts.

## File List (targets)

Modify:
- `scripts/rdc_analyzer/main.py`
  - `_export_reports()`：注入 `data_richness` 块
  - `_build_coverage_report()` / `_build_preflight()`：关联 data_richness 的声明与提示
- `scripts/rdc_analyzer/analyze_xml_report.py`
  - HTML 中注入 data_richness 摘要（文本或 JSON 片段）
- `scripts/rdc_analyzer/tests/test_dod_compliance.py`
  - 新增 `data_richness` 结构断言（DoD-7.3 可信闭环）
- `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_SCHEMA.md`
  - 记录新增字段与用途
- `docs/analysis/codex_rdc_analyzer/2025-01-20-rdc-analyzer-schema-single-analysis.md`
  - 更新 Canonical Schema 顶层结构描述（若需要）

Optional:
- `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROUTES.md`
  - A+C 覆盖边界补充说明（若需要）

## Approach (Pseudo-code)

### 1) Canonical Schema 输出补齐 data_richness

```python
# main.py::_export_reports()
analysis_data = {
  "schema_version": "1.0",
  ...
  "coverage": self._build_coverage_report(),
  "preflight": self._build_preflight(coverage),
  "data_richness": self._build_data_richness(),  # new
}

def _build_data_richness(self) -> Dict[str, Any]:
    return {
        "baseline": {
            "events": ["eventId", "outputs", "copySource", "copyDestination", "children", ...],
            "textures": ["resourceId", "byteSize", "msSamp", "msQual", "creationFlags", ...],
            "pipeline_state": ["PipeState", "API-specific state", "descriptor sets", ...],
        },
        "routes": {
            "A": {
                "source": "xml",
                "coverage": "partial",
                "missing_fields": {"events": [...], "textures": [...], "pipeline_state": [...]},
                "requires_replay": ["events.outputs", "pipeline_state.full", ...],
            },
            "C": {
                "source": "compare",
                "coverage": "summary-only",
                "missing_fields": {"events": "full", "pipeline_state": "full", ...},
            },
        },
        "notes": [
            "缺失字段需 ReplayController 才可获得",
            "A+C 输出不伪造字段，仅声明缺口",
        ],
    }
```

### 2) A 路线 HTML 注入 data_richness 摘要

```python
# analyze_xml_report.py
report_meta = {"dataRichness": data_richness}
html = html.replace("/*__REPORT_META__*/", json.dumps(report_meta, ...))
```

### 3) DoD / Schema 测试最小化

```python
# tests/test_dod_compliance.py
assert "data_richness" in analysis_json
assert "routes" in analysis_json["data_richness"]
assert "A" in analysis_json["data_richness"]["routes"]
```

## Impact Analysis

- 正向影响：输出能“自解释覆盖度”，避免误用 A/C 结果冒充官方完整数据。
- 兼容性：新增字段为向后兼容（消费者可忽略）。
- 风险：新增字段可能被误读为“已补齐数据”；需在 notes/文档中明确“缺失原因与边界”。

## Risks / Blockers

- data_richness 的字段清单来源于文档基线，需保持与官方结构同步（后续维护成本）。
- A 路线 HTML 注入可能受模板结构影响（需确认插入点）。

## Verification / DoD

Record-only commands (do not execute in /plan):
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_dod_compliance.py::TestDOD73DataQuality -v`
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_dod_compliance.py -v`
- 如涉及 HTML：添加/更新最小断言或静态快照测试（若存在）

Expected:
- `data_richness` 出现在 Canonical JSON 输出。
- DoD 测试覆盖 data_richness 关键结构。

## Task Checklist (2–5 min each)

- [x] T1: 读取 `main.py::_export_reports()` 与 coverage/preflight 结构，确定插入点。
- [x] T2: 实现 `_build_data_richness()`（基于“数据丰富度基线”静态表）。
- [x] T3: 在 `_export_reports()` 输出加入 `data_richness`。
- [x] T4: A 路线 HTML 注入 data_richness 摘要（`analyze_xml_report.py`）。
- [x] T5: 更新 Schema 文档（WORK_SUMMARY_SCHEMA + 单帧 schema 说明）。
- [x] T6: 补充 DoD 测试断言（data_richness 必需字段）。
- [x] T7: 运行验证命令并记录结果。
- [x] T8: 更新本 plan 勾选与进度日志，提交代码。

## Progress Log

- 2026-02-16: 为 DoD-7.3 增加 data_richness 测试（RED），确认失败后实现 summarize_field_coverage / _build_data_richness / export 注入（GREEN）。
- 2026-02-16: A 路线 HTML 注入 data_richness 摘要；Schema 文档补齐 data_richness 顶层块。
- Verification:
  - `py -3 -m pytest scripts/rdc_analyzer/tests/test_dod_compliance.py::TestDOD73DataQuality -v` (pass)
  - `py -3 -m py_compile scripts/rdc_analyzer/main.py scripts/rdc_analyzer/schema/data_richness_baseline.py scripts/rdc_analyzer/analyze_xml_report.py` (pass)

## Open Questions

- data_richness 是否需要加入 compare 输出（diff.json）？若需要，将在 /do 中额外确认。
- A 路线 HTML 的展示形式：仅 JSON 注入，还是新增可视化模块？

## Next Steps

- 等待用户确认进入 `/do`。
