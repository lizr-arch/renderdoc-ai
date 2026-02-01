# Shader/Bindings Fields Expand Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-02-01  
**Owner:** Codex01  
**Last Updated:** 2026-02-01  
**Plan File:** `plans/2026-02-01-232822-Codex01-Shader-Bindings-Fields-Expand.md`

---

## Goal
- 在 `DATA_SOURCES_INDEX.md` 中补充 Shader/Bindings 字段级清单，并标注 A/C 缺失、B 可获取。

## Scope
**In Scope**
- ShaderReflection / SigParameter / ShaderResource / ShaderEntryPoint 字段清单
- DescriptorAccess / DescriptorStoreDescription 字段清单
- 覆盖现状（A/C 缺失，B Replay）

**Out of Scope**
- 修改代码
- 执行 replay 或导出

## Assumptions
- 字段来源以 `renderdoc/api/replay/shader_types.h` 与 `common_pipestate.h` 为权威

## Repo / File List (line refs)
- Modify: `docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md:120`
- Reference: `renderdoc/api/replay/shader_types.h:1087` (SigParameter)
- Reference: `renderdoc/api/replay/shader_types.h:1619` (ShaderResource)
- Reference: `renderdoc/api/replay/shader_types.h:1745` (ShaderEntryPoint)
- Reference: `renderdoc/api/replay/shader_types.h:1987` (ShaderReflection)
- Reference: `renderdoc/api/replay/common_pipestate.h:784` (DescriptorAccess)
- Reference: `renderdoc/api/replay/data_types.h:693` (DescriptorStoreDescription)

## Approach (Pseudo-code)
```
append new subsection under "数据丰富度对标":
  - ShaderReflection fields
  - SigParameter fields
  - ShaderResource fields
  - ShaderEntryPoint fields
  - DescriptorAccess fields
  - DescriptorStoreDescription fields
mark coverage: A/C missing, B replay
verify with rg
```

## Impact Analysis
- 文档更新，不影响功能

## Build/Test/Lint Quick Guide (record only)
- `rg -n "ShaderReflection|SigParameter|ShaderResource|ShaderEntryPoint|DescriptorAccess" docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`

---

## Task Checklist (2–5 min steps)

### Task 1: 新增 Shader 字段清单
**Files:**  
- Modify: `docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`

**Step 1: 追加子章节**
```markdown
### 5.7 字段级清单（Shader / Bindings）
```

**Step 2: 填入字段**
```markdown
SigParameter / ShaderResource / ShaderEntryPoint / ShaderReflection
```

### Task 2: 新增 DescriptorAccess / DescriptorStore 字段清单
**Files:**  
- Modify: `docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`

**Step 1: 填入字段**
```markdown
DescriptorAccess / DescriptorStoreDescription
```

### Task 3: 标注覆盖
**Files:**  
- Modify: `docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`

**Step 1: 覆盖说明**
```markdown
A/C：缺失；B：Replay 可获取
```

---

## Risks & Blockers
- DescriptorLogicalLocation 等细节字段仍待补充

## Verification / DoD
- 新增章节包含 Shader/Bindings 字段
- `rg` 可检索到关键字段名

## Next Steps
- 等你确认后进入 `/do` 执行 Task 1–3

---

## Execution Log (2026-02-01)
- [x] Task 1: 新增 Shader 字段清单
- [x] Task 2: 新增 DescriptorAccess / DescriptorStore 字段清单
- [x] Task 3: 标注覆盖

### Commands & Outputs
- `rg -n "ShaderReflection|SigParameter|ShaderResource|ShaderEntryPoint|DescriptorAccess" docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`
