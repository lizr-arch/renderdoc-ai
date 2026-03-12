# Data Richness Fields Expand Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-02-01  
**Owner:** Codex01  
**Last Updated:** 2026-02-01  
**Plan File:** `plans/2026-02-01-210216-Codex01-Data-Richness-Fields-Expand.md`

---

## Goal
- 在 `DATA_SOURCES_INDEX.md` 中追加 Buffers / DebugMessages / Counters / Descriptors 的字段级清单，并标注有/无/可扩充/需新增。

## Scope
**In Scope**
- 依据 RenderDoc `data_types.h` 字段定义，列出完整字段集
- 标注 A/C 的缺口与 Replay 依赖
- 绑定已有 Python 入口（可扩充）

**Out of Scope**
- 修改代码实现
- 实际 Replay 运行验证

## Assumptions
- 字段来源以 `renderdoc/api/replay/data_types.h` 为权威
- 若未在 A/C 输出中出现，一律标注为“缺失/需 replay”

## Repo / File List (line refs)
- Modify: `docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md:74`
- Reference: `renderdoc/api/replay/data_types.h:737` (BufferDescription)
- Reference: `renderdoc/api/replay/data_types.h:987` (DebugMessage)
- Reference: `renderdoc/api/replay/data_types.h:2329` (CounterDescription)
- Reference: `renderdoc/api/replay/data_types.h:693` (DescriptorStoreDescription)

## Approach (Pseudo-code)
```
extract Buffer/Debug/Counter/Descriptor field lists from data_types.h
append a new sub-section under "数据丰富度对标"
mark A/C coverage as missing
map to replay entrypoints
verify with rg
```

## Impact Analysis
- 文档扩充，不影响功能
- 风险：字段漏列 → 标注“待补充”

## Build/Test/Lint Quick Guide (record only)
- `rg -n "BufferDescription|DebugMessage|CounterDescription|DescriptorStoreDescription" docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`

---

## Task Checklist (2–5 min steps)

### Task 1: 新增字段级清单（Buffer/Debug/Counter/Descriptor）
**Files:**  
- Modify: `docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`

**Step 1: 追加子章节**
```markdown
### 5.6 字段级清单（Buffers/Debug/Counters/Descriptors）
```

**Step 2: 填入字段 + 缺口**
```markdown
- BufferDescription: resourceId, creationFlags, gpuAddress, length
- DebugMessage: eventId, category, severity, source, messageID, description
- CounterDescription: counter, name, category, description, resultType, resultByteWidth, unit, uuid
- DescriptorStoreDescription: firstDescriptorOffset, descriptorCount (+ 待补充)
```

### Task 2: 标注覆盖与可扩充入口
**Files:**  
- Modify: `docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`

**Step 1: 覆盖说明**
```markdown
- A/C：缺失
- B：ReplayController API 可获取
```

---

## Risks & Blockers
- Descriptor 细节字段仍需进一步补齐

## Verification / DoD
- 新增字段级清单小节
- 包含 Buffer/Debug/Counter/Descriptor 字段
- `rg` 可检索到关键字段名

## Next Steps
- 等你确认后进入 `/do` 执行 Task 1–2

---

## Execution Log (2026-02-01)
- [x] Task 1: 新增字段级清单（Buffer/Debug/Counter/Descriptor）
- [x] Task 2: 标注覆盖与可扩充入口

### Commands & Outputs
- `rg -n "BufferDescription|DebugMessage|CounterDescription|DescriptorStoreDescription" docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`
