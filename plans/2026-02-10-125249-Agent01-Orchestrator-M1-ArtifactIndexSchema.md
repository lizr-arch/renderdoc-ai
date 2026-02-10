# Plan: Task5-M1 Orchestrator (artifact_index schema + 最小编排CLI)

> Plan File: `plans/2026-02-10-125249-Agent01-Orchestrator-M1-ArtifactIndexSchema.md`
> Stage: `/plan`
> Author: Agent01
> Date: 2026-02-10

## Scope / Assumptions

- **目标（M1）**：新增一个“最小可用 orchestrator CLI”，把既有脚本串起来，稳定产出 `artifact_index.json`，并对其做 schema 验证。
- **核心原则**：
  - 不重写 `extract_event_intermediate.py` / `export_event_import_bundle.py` / `export_fbx_assets.py` 的业务逻辑。
  - orchestrator 只负责：参数解析 → 调用已有函数/脚本 → 汇总状态 → 生成索引与验证。
- **输入三选一**（与 spec 文档一致）：
  - `--rdc <path>`（可选，M1 先不做，取决于 repo 是否已有 rdc→zip.xml 的统一入口）
  - `--xml <zip.xml> --zip <zip>`
  - `--intermediate <dir>`
- **输出**：`<out>/event_<id>/...`，并生成 `artifact_index.json`。

## Navigation Evidence（codemap-first）

> 说明：本仓库 codemap 对 `scripts/rdc_analyzer/*` 新文件直接命中不稳定，因此补充 `rg` 证据。

### codemap queries used (max 3)

1) `codemap "artifact_index schema" -Num 20 -Repo renderdoc` → no matches
2) `codemap "RDC Analyzer 功能索引" -Num 20 -Repo renderdoc` → hits in `.ai/FEATURE_INDEX.md`
3) `codemap "RDC Analyzer 文档索引" -Num 20 -Repo renderdoc` → hits in `docs/analysis/md_scan_summary.md`

### candidate hits (>=3)

- `[renderdoc] scripts/rdc_analyzer/.ai/FEATURE_INDEX.md:1` `# RDC Analyzer 功能索引`
- `[renderdoc] scripts/rdc_analyzer/docs/INDEX.md:53` `FBX_EXPORT.md ... OBJ 中间态 → Unity/Unreal`
- `[renderdoc] scripts/rdc_analyzer/docs/INDEX.md:59` `EVENT_IMPORT_BUNDLE.md ... single event 闭环`

### follow-up targets (1-2)

- `scripts/rdc_analyzer/extract_event_intermediate.py:714`（中间态提取入口）
- `scripts/rdc_analyzer/export_fbx_assets.py:365`（FBX 导出入口 + shader plan 状态聚合）

## Build / Test / Lint Quick Guide（命令仅记录，不在 /plan 执行）

```bash
# schema 单测（已有）
py -3 -m pytest scripts/rdc_analyzer/tests/test_intermediate_schemas.py -q

# orchestrator 新增单测（M1 需要新增）
py -3 -m pytest scripts/rdc_analyzer/tests/test_event_asset_orchestrator.py -q
```

## Repo / File List（精确到文件）

**新增**：
1. `scripts/rdc_analyzer/event_asset_orchestrator.py`
   - CLI：`py -3 scripts/rdc_analyzer/event_asset_orchestrator.py --xml ... --zip ... --event ... --out ...`
   - 内部复用：优先直接 import 并调用：
     - `extract_event_intermediate.extract_event_intermediate`
     - `export_event_import_bundle.export_event_import_bundle`
     - `export_fbx_assets.export_fbx_assets`
2. `scripts/rdc_analyzer/schema/artifact_index.schema.json`
   - 新增 schema，用于验证 `artifact_index.json`。
3. `scripts/rdc_analyzer/tests/test_event_asset_orchestrator.py`
   - 覆盖：
     - 生成的 `artifact_index.json` 必填字段
     - schema 验证通过
     - “降级策略”：无 FBX 后端时仍能生成索引并指向 import_bundle

**更新**：
4. `scripts/rdc_analyzer/docs/SKILL_RDC_EVENT_ASSET_ORCHESTRATOR_SPEC.md`
   - 把“建议新增 schema”改为“已新增 schema（M1）”
   - 补充 CLI 示例命令（可复制）
5. `scripts/rdc_analyzer/docs/INDEX.md`
   - 增加 orchestrator 文档入口或在现有条目中补充“CLI 编排器入口”

## Approach (Pseudo-code)

```python
# event_asset_orchestrator.py

args = parse_args()
# resolve event_id + paths

stage_results = []

if args.intermediate:
    intermediate_dir = args.intermediate
    stage_results.append({"name": "extract_intermediate", "status": "reused"})
else:
    intermediate_dir = extract_event_intermediate(xml=args.xml, zip=args.zip, event_id=args.event, out_dir=args.out)
    stage_results.append({"name": "extract_intermediate", "status": "ok"})

bundle_dir = export_event_import_bundle(intermediate_dir, event_id=args.event, out_dir=args.out, rgba_manifest=args.rgba_manifest)
stage_results.append({"name": "export_import_bundle", "status": "ok"})

fbx_result = export_fbx_assets(intermediate_dir, event_id=args.event, out_dir=args.out, allow_missing=args.allow_missing)
stage_results.append({"name": "export_fbx_assets", "status": fbx_result.status})

artifact_index = {
  "schema_version": "1.0",
  "schema_path": "schema/artifact_index.schema.json",
  "event_id": args.event,
  "api": read_api_from_intermediate_manifest(intermediate_dir),
  "stages": stage_results,
  "artifacts": {...},
  "status_counts": {"shader": read_shader_plan_counts(...), "texture": read_bundle_texture_counts(...)}
}

write_json(artifact_index_path)
validate_json_file(artifact_index_path, schema/artifact_index.schema.json)
```

## Task Checklist（2-5 分钟粒度）

- [x] T1. 设计 `artifact_index.schema.json`（字段、required、枚举、路径约束）
- [x] T2. 新增 `event_asset_orchestrator.py`：参数解析 + 三阶段调用 + index 汇总
- [x] T3. 新增单测 `test_event_asset_orchestrator.py`（mock 最小 intermediate/bundle/fbx 产物）
- [x] T4. 文档更新：Spec + INDEX 增补 orchestrator CLI 使用方式
- [x] T5. 验证：pytest 通过；手工用一份已存在 intermediate 做 dry-run（不需要真实 rdc）
- [x] T6. 提交：`feat(rdc-analyzer): 新增event资产编排器与artifact_index schema`

## Impact Analysis

- **新增价值**：
  - 把“手工执行多个脚本”升级为“一键编排 + 可审计索引”。
  - `artifact_index.json` 成为后续 Unity/Unreal/Messiah 导入器的 SSOT 入口。
- **风险**：
  - 需要决定“读哪些现有文件来汇总状态”（shader plan / bundle manifest / intermediate manifest）。
  - 现有脚本返回值/输出路径不一致时，orchestrator 可能需要更健壮的路径发现。

## Open Questions（需要你确认）

1) orchestrator 的 **最小输入** 你希望是：
   - A. 只支持 `--xml + --zip + --event`（推荐先落地）
   - B. 支持 `--intermediate + --event`（推荐也支持，方便离线复用）
   - C. 额外支持 `--rdc` 自动生成 zip.xml（若 repo 已有稳定转换入口）
2) 输出目录：是否严格固定为 `<out>/event_<id>/`（推荐）？

## Verification / Acceptance（Definition of Done）

- [x] `artifact_index.json` 可由 schema 验证通过。
- [x] 无 FBX 后端时（或 allow_missing），orchestrator 仍能输出可消费的 `import_bundle/` + `artifact_index.json`。
- [x] 单测覆盖最小路径与降级路径。

## Next Step

- 你确认本 plan 后，我进入 `/do` 实现 M1（schema + orchestrator + tests + docs）。


## /do 执行记录（2026-02-10）

### 已完成文件
- scripts/rdc_analyzer/event_asset_orchestrator.py（新建）
- scripts/rdc_analyzer/schema/artifact_index.schema.json（新建）
- scripts/rdc_analyzer/tests/test_event_asset_orchestrator.py（新建）
- scripts/rdc_analyzer/docs/EVENT_ASSET_ORCHESTRATOR.md（新建）
- scripts/rdc_analyzer/docs/INDEX.md（更新）
- scripts/rdc_analyzer/docs/SKILL_RDC_EVENT_ASSET_ORCHESTRATOR_SPEC.md（更新）

### 验证命令与结果
- py -3 -m pytest scripts/rdc_analyzer/tests/test_event_asset_orchestrator.py -q ✅ 3 passed
- py -3 -m pytest scripts/rdc_analyzer/tests/test_export_event_import_bundle.py -q ✅ 8 passed
- py -3 -m pytest scripts/rdc_analyzer/tests/test_export_fbx_assets.py -q ✅ 4 passed

### 说明
- FBX 后端缺失时通过 --allow-missing-fbx-backend 降级，仍生成 import_bundle + shader_import_plan + artifact_index。
- 手工 dry-run：py -3 scripts/rdc_analyzer/event_asset_orchestrator.py --intermediate ... --event 321 --out ... --allow-missing-fbx-backend 成功生成 artifact_index.json。
