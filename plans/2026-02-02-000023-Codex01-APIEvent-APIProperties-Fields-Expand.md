# APIEvent/APIProperties Fields Expand Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-02-02  
**Owner:** Codex01  
**Last Updated:** 2026-02-02  
**Plan File:** `plans/2026-02-02-000023-Codex01-APIEvent-APIProperties-Fields-Expand.md`

**Goal:** 在 `DATA_SOURCES_INDEX.md` 中补充 APIEvent / APIProperties 字段清单，并标注 Python 入口与覆盖现状。

**Architecture:** 仅改文档索引：以 `renderdoc/api/replay/data_types.h` 为字段权威来源，用
`renderdoc/replay/replay_controller.h` 作为 Python 入口来源；将字段 + 入口 + 覆盖状态写入
`DATA_SOURCES_INDEX.md`，不改代码、不运行 replay。

**Tech Stack:** Markdown, rg

**Success Criteria (measurable):**
- `DATA_SOURCES_INDEX.md` 新增 APIEvent/APIProperties 字段清单
- 每个字段组标注 Python 入口或“无入口/需新增”
- `rg` 能检索到 APIEvent/APIProperties 字段名与入口说明

**Acceptance Criteria:**
- 文档出现 APIEvent 与 APIProperties 小节
- A/C 缺失、B 可获取的覆盖状态明确
- 字段名与入口描述可对齐源码符号

**Verification Commands:**
- `rg -n "APIEvent|APIProperties|GetAPIProperties|GetRootActions" docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`  
  (Expected: 命中新增字段与入口说明)

**Evidence:**
- `rg` 输出日志（终端）
- `git diff`（文档修改记录）

**Estimation:**
- Effort: 20–30 min
- Story Points: 1
- Original Estimate: 0.5 day

**Risk Register (impact/likelihood/mitigation):**
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| SWIG 导出差异导致 Python 字段缺失 | Medium | Medium | 标注“仅 C++/需新增”，不假设可用 |
| data_types.h 行号漂移 | Low | Medium | 用符号名定位，不硬依赖行号 |

---

## Scope
**In Scope**
- APIEvent 字段全集与 Python 获取入口
- APIProperties 字段全集与 Python 获取入口
- 标注 A/C 缺失、B 可获取

**Out of Scope**
- 修改代码
- 运行 replay

## Assumptions
- 字段来源以 `renderdoc/api/replay/data_types.h` 为权威

## Repo / File List (line refs)
- Modify: `docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md:160`
- Reference: `renderdoc/api/replay/data_types.h:922` (APIEvent)
- Reference: `renderdoc/api/replay/data_types.h:2186` (APIProperties)
- Reference: `renderdoc/replay/replay_controller.h:139` (GetAPIProperties)
- Reference: `renderdoc/replay/replay_controller.h:185` (GetRootActions)

## Approach (Pseudo-code)
```
append subsection under "数据丰富度对标":
  - APIEvent fields + Python入口
  - APIProperties fields + Python入口
mark A/C missing, B replay
verify with rg
```

## Impact Analysis
- 文档更新，不影响功能

## Build/Test/Lint Quick Guide (record only)
- `rg -n "APIEvent|APIProperties|GetAPIProperties|GetRootActions" docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`

---

## Game Dev: Memory & Resource Budget (Leak Checks)
- 本计划仅文档更新，不涉及运行时资源采集；记录为 N/A。

## Game Dev: Asset Pipeline
- 本计划不新增资产/管线；记录为 N/A。

## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: N/A（仅文档更新）
- Dump/Core: N/A
- Symbols: N/A
- Build identity: 记录当前 git commit（由执行时补充）

---

## Task Checklist (2–5 min steps)

- [x] Task 1: 新增 APIEvent 字段清单
- [x] Task 2: 新增 APIProperties 字段清单
- [x] Task 3: 自检与提交

### Task 1: 新增 APIEvent 字段清单
**Files:**  
- Modify: `docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`

**Step 1: 追加字段 + 入口（文档）**
```markdown
#### APIEvent（API 调用事件）
- **字段清单**: eventId, chunkIndex, fileOffset, annotations
- **Python 入口**: ReplayController.GetRootActions() -> ActionDescription.events
- **覆盖**: A/C 缺失（无 replay）｜B 可获取（replay）
```

**Step 2: 自检（局部）**
Run: `rg -n "APIEvent|GetRootActions" docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`  
Expected: 命中新增 APIEvent 小节与入口说明

### Task 2: 新增 APIProperties 字段清单
**Files:**  
- Modify: `docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`

**Step 1: 追加字段 + 入口（文档）**
```markdown
#### APIProperties（驱动/回放能力）
- **字段清单**: pipelineType, localRenderer, vendor, remoteReplay, degraded, shaderDebugging, pixelHistory, rgpCapture
- **Python 入口**: ReplayController.GetAPIProperties()
- **覆盖**: A/C 缺失（无 replay）｜B 可获取（replay）
```

**Step 2: 自检（局部）**
Run: `rg -n "APIProperties|GetAPIProperties" docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`  
Expected: 命中新增 APIProperties 小节与入口说明

### Task 3: 自检与提交
**Files:**  
- Modify: `docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`

**Step 1: 运行验证命令**
```
rg -n "APIEvent|APIProperties|GetAPIProperties|GetRootActions" docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md
```

**Step 2: 提交**
```
git add docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md
git commit -m "docs(rdc-analyzer): expand APIEvent/APIProperties fields

- document APIEvent/APIProperties field lists
- add Python entrypoints and coverage notes"
```

---

## Risks & Blockers
- SWIG 非导出字段不在 Python 层可见 → 标注“仅 C++”

## Verification / DoD
- 新增 APIEvent/APIProperties 字段小节
- 标注 Python 入口或“无入口”
- `rg` 可检索到关键字段名

## Next Steps
- 等你确认后进入 `/do` 执行 Task 1–3

## Execution Log
- 2026-02-02: Task 1–3 completed.
- Verification: `rg -n "APIEvent|APIProperties|GetAPIProperties|GetRootActions" docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`
