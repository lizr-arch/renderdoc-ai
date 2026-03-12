# Data Richness Coverage Expand Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-02-01  
**Owner:** Codex01  
**Last Updated:** 2026-02-01  
**Plan File:** `plans/2026-02-01-203934-Codex01-Data-Richness-Expand.md`

---

## Goal
- 基于“数据丰富度基线”，在 `DATA_SOURCES_INDEX.md` 中新增“有/无/可扩充/需新增”清单，并指向现有 Python 入口。

## Scope
**In Scope**
- 追加 RenderDoc 对标字段清单（Action/Texture/PipeState）
- 标注 A/C 已覆盖 / 缺失字段
- 指向可扩充的 Python 入口脚本

**Out of Scope**
- 修改代码实现
- 运行 replay 或导出实际数据

## Assumptions
- 以 `2026-01-31-rdc-analyzer-data-richness-baseline.md` 为权威基线
- 缺失字段如无证据，必须标注“需要 replay/待新增”

## Repo / File List (line refs)
- Modify: `docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md:1`
- Reference: `docs/analysis/codex_rdc_analyzer/2026-01-31-rdc-analyzer-data-richness-baseline.md:1`
- Reference: `docs/analysis/codex_rdc_analyzer/README.md:137`

## Approach (Pseudo-code)
```
open data-richness-baseline doc
extract Action/Texture/PipeState coverage + gaps
append a new section in DATA_SOURCES_INDEX:
  - baseline summary
  - "已有/缺失/可扩充/需新增" tables
  - Python entrypoints mapping
verify with rg
```

## Impact Analysis
- 文档扩充，不影响功能
- 风险：字段遗漏 → 标注“待补充”

## Build/Test/Lint Quick Guide (record only)
- `rg -n "数据丰富度对标" docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`
- `rg -n "ActionDescription|TextureDescription|PipeState" docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`

---

## Task Checklist (2–5 min steps)

### Task 1: 新增“数据丰富度对标”章节
**Files:**  
- Modify: `docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`

**Step 1: 新章节结构**
```markdown
## 5. 数据丰富度对标（RenderDoc 基线）
### 5.1 对标基线（官方字段全集）
### 5.2 A/C 已覆盖（已有）
### 5.3 缺失字段（没有）
### 5.4 可扩充入口（已有代码）
### 5.5 需新增点（无代码）
```

### Task 2: 填充“已有/缺失/可扩充/需新增”
**Files:**  
- Modify: `docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`

**Step 1: 填入 Action/Texture/PipeState**
```markdown
- ActionDescription: outputs/copySource/... 缺失
- TextureDescription: resourceId/byteSize/... 缺失
- PipeState: API-specific 全量缺失
```

**Step 2: 绑定 Python 入口**
```markdown
rdc_to_html.py / analyze_rdc.py / analyze_xml_report.py / export_textures.py
```

---

## Risks & Blockers
- 字段全集未覆盖所有 API-specific 结构 → 标注“待补充”

## Verification / DoD
- 新增章节包含“已有/缺失/可扩充/需新增”四块
- 引用 data-richness-baseline 的证据行
- `rg` 可检索到关键字段

## Next Steps
- 等你确认后进入 `/do` 执行 Task 1–2

---

## Execution Log (2026-02-01)
- [x] Task 1: 新增“数据丰富度对标”章节
- [x] Task 2: 填充“已有/缺失/可扩充/需新增”

### Commands & Outputs
- `rg -n "数据丰富度对标|ActionDescription|TextureDescription|PipeState" docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`
