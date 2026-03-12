# Plan: Orchestrator M2（engine_targets 差异字段扩展）

> Plan File: `plans/2026-02-10-173824-Agent01-Orchestrator-M2-EngineTargets.md`
> Stage: `/do`（基于你已批准 M2 方向直接执行）
> Date: 2026-02-10

## Scope

- 扩展 `artifact_index`，加入多引擎目标差异信息：`engine_targets[]` + `engines{unity,unreal,messiah}`。
- 扩展 orchestrator 参数：`--engine-targets`。
- 增加测试覆盖：`intermediate` 分支与 `xml+zip` 分支均可生成新增字段。
- 更新文档：编排器文档 + skill 规范文档。

## Task Checklist

- [x] T1. 扩展 `event_asset_orchestrator.py` 支持 `engine_targets` 参数与 per-engine 状态输出
- [x] T2. 扩展 `artifact_index.schema.json`：新增字段并保持 M1 兼容
- [x] T3. 更新 `test_event_asset_orchestrator.py` 覆盖 engine_targets 行为
- [x] T4. 更新文档（`EVENT_ASSET_ORCHESTRATOR.md` / `SKILL_RDC_EVENT_ASSET_ORCHESTRATOR_SPEC.md`）
- [x] T5. 运行测试与 dry-run 验证
- [x] T6. 提交变更（Conventional Commit）

## Verification / Acceptance

- [x] 生成的 `artifact_index.json` 含 `engine_targets` 与 `engines`。
- [x] `messiah` 目标可表达为 `not_implemented`（非阻断）。
- [x] 现有 M1 测试不回归，新增测试通过。


## /do 执行记录（2026-02-10）

### 已修改文件
- `scripts/rdc_analyzer/event_asset_orchestrator.py`
- `scripts/rdc_analyzer/schema/artifact_index.schema.json`
- `scripts/rdc_analyzer/tests/test_event_asset_orchestrator.py`
- `scripts/rdc_analyzer/docs/EVENT_ASSET_ORCHESTRATOR.md`
- `scripts/rdc_analyzer/docs/SKILL_RDC_EVENT_ASSET_ORCHESTRATOR_SPEC.md`
- `scripts/rdc_analyzer/docs/INDEX.md`

### 验证结果
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_event_asset_orchestrator.py -q` ✅ 4 passed
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_export_event_import_bundle.py -q` ✅ 8 passed
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_export_fbx_assets.py -q` ✅ 4 passed
- dry-run：`--engine-targets messiah` ✅ 阶段状态 `skipped_no_fbx_targets`，`engines.messiah.status=not_implemented`
