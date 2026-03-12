# Plan: 功能基线固化 + Skill 方案设计（防重复开发）

> Plan File: `plans/2026-02-09-235715-Agent01-RDC-FeatureBaseline-SkillDesign.md`
> Stage: `/plan`
> Author: Agent01
> Date: 2026-02-09

## Scope / Assumptions

- **目标**：
  1. 产出一份“当前已实现能力 + 成本/风险 + 去重建议”的基线文档，避免重复开发。
  2. 产出一份“RDC 事件资产编排 Skill”设计文档，明确 AI 与脚本边界、输入输出契约、失败恢复策略。
  3. 把以上文档挂到 `scripts/rdc_analyzer/docs/INDEX.md`，形成可检索入口。
- **不在本轮范围**：
  - 不新增业务算法（不改 Mesh/Shader/Texture 提取逻辑）。
  - 不直接实现可运行的 Codex Skill 文件（本轮先完成规范设计与文档化）。
- **事实来源（已确认）**：
  - 现有导出链路集中在 `extract_event_intermediate.py` 与 `export_fbx_assets.py`。
  - 文档入口集中在 `scripts/rdc_analyzer/docs/INDEX.md`。
  - 历史能力盘点存在于 `scripts/rdc_analyzer/.ai/FEATURE_INDEX.md`（作为输入，不直接替代本轮基线文档）。

## Build / Test / Lint Quick Guide（命令仅记录，不在 /plan 执行）

```bash
# 1) 文档关键字与链接入口检查
rg -n "FEATURE_COST_BASELINE|SKILL_RDC_EVENT_ASSET_ORCHESTRATOR_SPEC|AI_SCRIPT_BOUNDARY" scripts/rdc_analyzer/docs

# 2) 相关链路回归（仅抽样）
py -3 -m pytest scripts/rdc_analyzer/tests/test_export_fbx_assets.py -q
py -3 -m pytest scripts/rdc_analyzer/tests/test_dxbc_bridge.py -q
py -3 -m pytest scripts/rdc_analyzer/tests/test_spirv_cross_bridge.py -q

# 3) Schema 验证（若新增 schema 文档示例）
py -3 -m pytest scripts/rdc_analyzer/tests/test_intermediate_schemas.py -q
```

**预期输出（验收时）**：
- `rg` 至少命中新文档文件名和 INDEX 链接条目。
- pytest 用例通过（允许已有已知 skip，但不应出现新增 fail）。
- 文档中的路径均可在仓库中被定位。

## Task Checklist（2-5 分钟粒度）

- [x] T1. 收集能力证据：从脚本入口与文档索引抽取“已实现功能清单 + 负责模块 + 数据流阶段”。
- [x] T2. 产出 `FEATURE_COST_BASELINE.md` 初稿：按“功能 → 输入 → 输出 → 成本 → 重复风险 → 复用建议”结构落表。
- [x] T3. 产出 `AI_SCRIPT_BOUNDARY.md`：把“必须脚本化 / 适合 AI 增强 / 不应交给 AI”三类职责固化。
- [x] T4. 产出 `SKILL_RDC_EVENT_ASSET_ORCHESTRATOR_SPEC.md`：定义 skill 触发条件、参数契约、执行阶段、失败恢复、产物索引。
- [x] T5. 更新 `scripts/rdc_analyzer/docs/INDEX.md`：新增 3 份文档入口 + 关键词 + 使用场景。
- [x] T6. 自检：路径可达性检查 + 文档交叉引用检查 + 术语一致性（event/intermediate/import bundle/fbx）。

## File List（计划修改点 + 预计定位）

1. `scripts/rdc_analyzer/docs/FEATURE_COST_BASELINE.md`（新建）
   - 结构：
     - 背景与目标
     - 功能清单矩阵（含复杂度/运行成本/维护成本）
     - 重复开发高风险区域（Top N）
     - “先复用后开发”建议
2. `scripts/rdc_analyzer/docs/AI_SCRIPT_BOUNDARY.md`（新建）
   - 结构：
     - AI 与脚本职责边界
     - 典型工作流分工
     - 失败场景与人工介入点
3. `scripts/rdc_analyzer/docs/SKILL_RDC_EVENT_ASSET_ORCHESTRATOR_SPEC.md`（新建）
   - 结构：
     - Skill 目标
     - 输入契约（rdc/xml/zip/intermediate/eventid）
     - 阶段执行图（extract → bundle → fbx → verify）
     - 输出契约（`artifact_index.json`）
     - 扩展点（Unity/Unreal/Messiah）
4. `scripts/rdc_analyzer/docs/INDEX.md`（更新）
   - 预计插入区：`“📊 功能指南”`表格附近（当前已含 FBX/INTERMEDIATE/EVENT_IMPORT_BUNDLE 条目）。

## Pseudo-code / 文档落地骨架

```text
Doc FEATURE_COST_BASELINE:
  section1 = 当前范围 + 输入证据来源
  section2 = capability_matrix[]
    item = {
      feature_id,
      owner_script,
      inputs,
      outputs,
      implementation_cost,
      runtime_cost,
      maintenance_cost,
      duplication_risk,
      recommended_action
    }
  section3 = high_risk_duplicate_areas
  section4 = 下一步优先级

Doc AI_SCRIPT_BOUNDARY:
  must_be_script = deterministic extraction/conversion/schema validation
  ai_optional = semantic naming/material inference/confidence scoring
  must_be_human = final acceptance/engine-side artistic tuning

Doc SKILL_SPEC:
  triggers = ["导出某 event 可导入资源", "一键导出 unity/unreal 资产"]
  input_contract = event_id + (rdc | xml+zip | intermediate)
  stages = [S1_extract, S2_bundle, S3_fbx, S4_verify]
  output_contract = artifact_index.json + per-stage status
  failure_policy = retryable vs non-retryable + downgrade path
```

## Impact Analysis

- **正向影响**：
  - 减少功能重复建设（尤其是已存在链路：intermediate/bundle/fbx/shader bridge）。
  - 后续做 Skill 时有稳定输入输出契约，避免“AI 直接改业务逻辑”。
  - 新人可以按文档快速定位“已有实现在哪里、应复用什么”。
- **潜在影响**：
  - 文档新增后索引变长，需保持关键词可检索。
  - 若后续脚本演进较快，基线文档需周期更新（建议每里程碑维护一次）。

## Risks / Blockers

1. **风险**：现有文档与实现状态可能不一致（历史遗留）。
   - 缓解：基线文档优先引用代码入口函数，不仅引用旧文档描述。
2. **风险**：Skill 设计过大，导致实施周期不可控。
   - 缓解：Spec 中强制分阶段（先 orchestrator，后 AI enhancement）。
3. **风险**：用户后续目标扩展到 UE/Messiah 时契约字段不够。
   - 缓解：输出契约预留 `engine_targets[]` 与 `extension_fields`。

## Decisions

- D1. 本轮先做“文档与契约固化”，不改提取算法。
- D2. Skill 采用 **orchestrator-first**：编排现有脚本而非重写 pipeline。
- D3. AI 只做“语义增强与建议”，确定性导出保持脚本负责。

## Verification / Acceptance（Definition of Done）

- [ ] 新建 3 份文档，内容完整，且每份都有“输入/输出/边界/限制”。
- [ ] `scripts/rdc_analyzer/docs/INDEX.md` 已新增入口，关键词可检索。
- [ ] 文档中所有关键脚本路径在仓库存在。
- [ ] 文档中不出现与当前脚本能力冲突的断言（有不确定项时标注“假设（待验证）”）。

## Next Steps

1. 用户确认本计划后进入 `/do`。
2. `/do` 执行顺序：T1→T2→T3→T4→T5→T6。
3. 完成后回传：修改文件清单 + 验证命令结果 + 后续 skill 实施建议。


## /do 执行记录（2026-02-10）

### 已完成文件

- `scripts/rdc_analyzer/docs/FEATURE_COST_BASELINE.md`（新建）
- `scripts/rdc_analyzer/docs/AI_SCRIPT_BOUNDARY.md`（新建）
- `scripts/rdc_analyzer/docs/SKILL_RDC_EVENT_ASSET_ORCHESTRATOR_SPEC.md`（新建）
- `scripts/rdc_analyzer/docs/INDEX.md`（更新）

### 验证命令与结果

- `rg -n "FEATURE_COST_BASELINE|AI_SCRIPT_BOUNDARY|SKILL_RDC_EVENT_ASSET_ORCHESTRATOR_SPEC" scripts/rdc_analyzer/docs/INDEX.md` ✅ 命中新增入口
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_intermediate_schemas.py -q` ✅ 6 passed
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_export_fbx_assets.py -q` ✅ 4 passed
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_dxbc_bridge.py -q` ✅ 3 passed
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_spirv_cross_bridge.py -q` ✅ 6 passed

### 偏差与阻塞

- 无功能性阻塞。
- 说明：`codemap` 在 `scripts/rdc_analyzer/docs/*` 的直接文件命中不稳定，本轮使用 Serena/`rg` 补充证据链。
