# 计划：AgentC / Offline `snapshot.v1` Builder + Shared Renderer（/do 主执行）

时间：2026-03-11 19:30:48 | 负责人：AgentC

## Scope / Assumptions

- 本计划为本轮 `/do` 主执行文档；旧计划并行保留：`plans/2026-03-09-165704-AgentC-Offline-Snapshot-Bridge.md`。
- 只在 `scripts/rdc_analyzer/*` 开发，不触碰 `qrenderdoc` C++ GUI。
- 保留 legacy bundle fallback；`renderer-mode=legacy` 作为默认兼容行为。
- 新增 shared renderer 只消费 `snapshot.v1`，不直接读取 XML 私有结构。

## File List

- `scripts/rdc_analyzer/providers/__init__.py`（新建）
- `scripts/rdc_analyzer/providers/offline_snapshot_builder.py`（新建）
- `scripts/rdc_analyzer/providers/snapshot_template_renderer.py`（新建）
- `scripts/rdc_analyzer/xml_to_bundle.py`
- `scripts/rdc_analyzer/report_bundle_generator.py`
- `scripts/rdc_analyzer/tests/test_offline_snapshot_builder.py`（新建）
- `scripts/rdc_analyzer/tests/test_snapshot_template_renderer.py`（新建）

## Build / Test / Lint Quick Guide

- `py -3 -m pytest D:\Code\git\renderdoc-agentc\scripts\rdc_analyzer\tests\test_offline_snapshot_builder.py -q`
- `py -3 -m pytest D:\Code\git\renderdoc-agentc\scripts\rdc_analyzer\tests\test_snapshot_template_renderer.py -q`
- `py -3 D:\Code\git\renderdoc-agentc\scripts\rdc_analyzer\xml_to_bundle.py D:\Code\git\renderdoc-agentc\scripts\rdc_analyzer\g145_capture.xml -o D:\Code\git\renderdoc-agentc\test_output\snapshot_renderer --emit-snapshot-v1 --renderer-mode snapshot`
- `py -3 D:\Code\git\renderdoc-agentc\scripts\rdc_analyzer\xml_to_bundle.py D:\Code\git\renderdoc-agentc\scripts\rdc_analyzer\g145_capture.xml -o D:\Code\git\renderdoc-agentc\test_output\legacy_renderer --renderer-mode legacy`

## Task Checklist

- [x] 实现 `OfflineSnapshotBuilder`，输出 `snapshot.v1` 顶层必需字段。
- [x] 实现 `SnapshotTemplateRenderer`，产出 `index/events/textures/shaders/recommendations/manifest`。
- [x] 在 `xml_to_bundle.py` 新增 `--emit-snapshot-v1` 与 `--renderer-mode {snapshot,legacy}`。
- [x] `xml_to_bundle.py` 先 build snapshot，再按 renderer mode 分流。
- [x] legacy `ReportBundleGenerator` 标注 fallback/compat 职责，不扩展产品主路径。
- [x] 新增 builder/renderer 单元测试并通过。
- [x] 运行 snapshot 集成验证并检查 `snapshot.v1.json` 最小完整性。
- [x] 运行 legacy 路径验证并确认兼容。

## Risks / Blockers

- `xml_to_bundle.py` 的 `query_layer` 缺失风险已通过本地降级导入处理（无该模块时不过滤 draw_calls）。
- `snapshot_schema_v1` 与旧 bundle 字段口径存在差异，首批以 required top-level 为验收底线。
- legacy 输出仍存在历史行为：当前不生成 `events.html`（本轮保持 fallback 不扩功能）。

## Verification / Acceptance

- [x] `snapshot.v1.json` 存在且 `schema_version == "snapshot.v1"`。
- [x] `meta/preflight/overview/actions/resources/findings/recommendations/availability` 八个顶层键存在且类型正确。
- [x] `availability` 含离线路径 `partial` 及 MCP 补数提示。
- [x] `renderer-mode=snapshot` 产出最小页面集合与 `manifest.json`。
- [x] `renderer-mode=legacy` 仍可生成 legacy bundle。
