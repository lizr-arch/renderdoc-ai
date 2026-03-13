# AgentC / M6 Compare + CI 最小闭环

## Scope / Assumptions

- 主线归属：报告产品线 / 离线 compare + CI 最小闭环。
- 主入口固定为 `D:\Code\git\renderdoc-agentc-m6\scripts\rdc_analyzer\compare_rdc.py`。
- 输入主路径固定为 `snapshot.v1.json`，兼容 `schema_version == "1.0"` 与既有 CaptureData-like JSON、`.rdc`、`.xml`。
- 不新增第二套 schema、第二套模板、第二套报告系统；HTML compare 仅保留现有兼容出口。
- `offline_snapshot_builder.py` 的别名漂移只在 compare 读取时兼容，不反写契约。

## Build / Test / Lint Quick Guide

- `/plan` 阶段只记录，不执行。
- `/do` 已执行：
  - `py -3 -m py_compile D:\Code\git\renderdoc-agentc-m6\scripts\rdc_analyzer\parsers\rdc_loader.py`
  - `py -3 -m py_compile D:\Code\git\renderdoc-agentc-m6\scripts\rdc_analyzer\compare_rdc.py`
  - `py -3 -m py_compile D:\Code\git\renderdoc-agentc-m6\scripts\rdc_analyzer\diff\junit_exporter.py`
  - `py -3 -m py_compile D:\Code\git\renderdoc-agentc-m6\scripts\rdc_analyzer\tests\test_snapshot_compare_adapter.py`
  - `py -3 -m py_compile D:\Code\git\renderdoc-agentc-m6\scripts\rdc_analyzer\tests\test_compare_rdc.py`
  - `py -3 -m py_compile D:\Code\git\renderdoc-agentc-m6\scripts\rdc_analyzer\tests\test_compare_ci.py`
  - `py -3 -m py_compile D:\Code\git\renderdoc-agentc-m6\scripts\rdc_analyzer\tests\test_junit_exporter.py`

## Task Checklist

- [x] 在 `scripts/rdc_analyzer/parsers/snapshot_compare_adapter.py` 实现 `snapshot.v1 -> CaptureData` 归一化层。
- [x] 在 `scripts/rdc_analyzer/parsers/rdc_loader.py` 接入 `snapshot.v1` / Canonical v1 兼容加载。
- [x] 扩展 `scripts/rdc_analyzer/compare_rdc.py`，保持单一 compare CLI 入口。
- [x] 增加结构化 CI verdict：阈值、退出码、stdout 摘要、扩展 JSON 输出。
- [x] 增加 `--junit` 并复用现有 `JUnitXMLExporter`。
- [x] 在 compare 主链补 `RegressionReport.results` 填充。
- [x] 修复 `scripts/rdc_analyzer/diff/junit_exporter.py` 对 `WARNING` 与 metric 映射的处理。
- [x] 增加 / 更新 pytest：
  - [x] `test_snapshot_compare_adapter.py`
  - [x] `test_compare_rdc.py`
  - [x] `test_compare_ci.py`
  - [x] `test_junit_exporter.py`
- [x] 更新 compare / CI 文档：
  - [x] `scripts/rdc_analyzer/docs/EXPORT_ROUTES.md`
  - [x] `scripts/rdc_analyzer/docs/E2E_WORKFLOW_GUIDE.md`
- [ ] 在本分支提交实现并记录 SHA。

## I/O Contract

### Inputs

- `baseline` / `target`:
  - `.json` + `schema_version == "snapshot.v1"` -> snapshot compare adapter
  - `.json` + `schema_version == "1.0"` -> Canonical v1 compat conversion
  - `.json` + CaptureData-like dict -> direct compare
  - `.rdc` / `.xml` -> existing loader path

### Internal normalized shape

```json
{
  "statistics": {},
  "events": [],
  "textures": [],
  "buffers": [],
  "shaders": [],
  "_source_schema": "snapshot.v1",
  "_snapshot_meta": {},
  "_snapshot_counts": {},
  "_snapshot_availability": {},
  "_snapshot_evidence_index": {}
}
```

### Outputs

- HTML: existing diff exporter only
- JSON:
  - `metadata`
  - `input`
  - `summary`
  - `snapshot_summary`
  - `regressions`
  - `ci`
  - `resource_changes`
- JUnit XML: `--junit <path>`
- Exit code:
  - `0` no gate regression
  - `1` warning gate regression
  - `2` critical gate regression
  - `3` compare execution error

## Decisions

- `snapshot.v1` 进入 compare 时只做归一化，不修改原始 snapshot 文档结构。
- `compare_rdc.py` 使用 `RegressionDetector` 产出的 `issues`，再补一层 `RegressionResult` 供 JUnit / CI 使用。
- `--texture-mem-threshold` 正式接入 CI gate；`--buffer-mem-threshold` 保持兼容并用于 buffer memory verdict synthesis。
- `passes / pipelines / availability` 只进 `snapshot_summary`，不进入默认 gate。

## Risks / Blockers

- 无代码级阻塞。
- `scripts/rdc_analyzer/tests/_m6_sample/` 为本轮样例执行生成目录，不纳入实现提交。

## Verification / Acceptance

- Pytest:
  - `test_snapshot_compare_adapter.py`: `3 passed`
  - `test_compare_ci.py`: `3 passed`
  - `test_compare_rdc.py`: `14 passed`
  - `test_junit_exporter.py`: `20 passed`
- 样例执行：
  - baseline: `draw_calls=10`, `triangles=12000`, `texture_memory=64MB`, `buffer_memory=8MB`
  - target: `draw_calls=12`, `triangles=15000`, `texture_memory=84MB`, `buffer_memory=8MB`
  - 结果：`status=critical`, `exit_code=2`
  - `failing_checks=draw_calls,triangles,texture_memory`
  - JSON `ci.thresholds`: `10.0 / 20.0 / 30.0 / 30.0`
- Definition of Done:
  - [x] `snapshot.v1` 可直接 compare
  - [x] JSON 输出包含 `input / snapshot_summary / ci`
  - [x] `--junit` 可落地 XML
  - [x] `RegressionReport.results` 被 compare 主链填充
  - [x] pytest 覆盖 compare / CI / adapter / JUnit
  - [ ] commit SHA 已记录

## Complexity / Runtime Estimate

- 纯 JSON compare 复杂度：`O(actions + textures + buffers + shaders + passes + pipelines)`
- 新增成本主要来自：
  - JSON 反序列化
  - shader hash 生成
  - 结构化摘要拼装
- 预计运行时：
  - `snapshot.v1.json` vs `snapshot.v1.json`：亚秒级到约 1 秒
  - `.rdc` 输入：耗时仍主要由既有 `renderdoccmd / analyze` 转换主导，不属于 M6 新增瓶颈

## Next

- 记录 commit SHA 并回报变更文件列表。
