# Data Sources Index Plan (Mutual Index)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-02-01  
**Owner:** Codex01  
**Last Updated:** 2026-02-01  
**Plan File:** `plans/2026-02-01-174533-Codex01-Data-Sources-Index.md`

---

## Goal
- 新增“数据来源方式总表”独立文档，并与 `REPORT_ARCHITECTURE.md` 互相索引。

## Scope
**In Scope**
- 新建数据来源分类文档（可持续补充）
- 在 `REPORT_ARCHITECTURE.md` 增加链接回指
- 在 `DOC_INDEX.md` 增加入口条目

**Out of Scope**
- 修改分析代码逻辑
- 引入新的数据源实现

## Assumptions
- 数据来源以 A/C 离线链路为主，Replay/Mali 仅做“来源说明”
- 文档行数 < 800 行

## Repo / File List (line refs)
- Add: `docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`
- Modify: `scripts/rdc_analyzer/docs/REPORT_ARCHITECTURE.md` (新增“数据来源索引”链接)
- Modify: `docs/analysis/codex_rdc_analyzer/DOC_INDEX.md` (新增入口)

## Approach (Pseudo-code)
```
create DATA_SOURCES_INDEX.md:
  sections: 分类表 + 说明 + 更新规则 + 关联文档
add backlink in REPORT_ARCHITECTURE.md
add entry in DOC_INDEX.md
verify links with rg
```

## Impact Analysis
- 文档新增/链接更新，不影响现有代码功能
- 风险：索引不一致 → 通过双向链接消除

## Build/Test/Lint Quick Guide (record only)
- `rg -n "DATA_SOURCES_INDEX" scripts/rdc_analyzer/docs/REPORT_ARCHITECTURE.md`
- `rg -n "DATA_SOURCES_INDEX" docs/analysis/codex_rdc_analyzer/DOC_INDEX.md`
- `rg -n "数据来源方式总表" docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`

---

## Task Checklist (2–5 min steps)

### Task 1: 新建数据来源索引文档
**Files:**  
- Add: `docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`

**Step 1: 文档结构**
```markdown
# 数据来源方式总表（可持续补充）
## 1. 分类总表（WHAT/WHY/HOW）
## 2. 补充规则（新增来源时填哪些字段）
## 3. 已关联文档索引
```

**Step 2: 互相引用**
- 链接 `REPORT_ARCHITECTURE.md`
- 链接 `README.md`（如有需要）

### Task 2: REPORT_ARCHITECTURE 增加回指
**Files:**  
- Modify: `scripts/rdc_analyzer/docs/REPORT_ARCHITECTURE.md`

**Step 1: 新增索引段**
```markdown
## 4.5 数据来源方式总表（索引）
- 路径：`docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`
- 说明：统一维护数据来源分类与可用性
```

### Task 3: DOC_INDEX 增加入口
**Files:**  
- Modify: `docs/analysis/codex_rdc_analyzer/DOC_INDEX.md`

**Step 1: 新增条目**
```markdown
### DATA_SOURCES_INDEX（数据来源方式总表）
- 简介：统一记录数据来源分类与可用性（可持续补充）
- 关键词：data sources, xml, json, replay, mali
- 路径：`docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`
```

---

## Risks & Blockers
- 数据来源列表可能随链路更新 → 通过“补充规则”保持可扩展

## Verification / DoD
- [x] `DATA_SOURCES_INDEX.md` 存在，且包含 WHAT/WHY/HOW 分类表
- [x] `REPORT_ARCHITECTURE.md` 与新文档双向链接
- [x] `DOC_INDEX.md` 入口可定位

## Next Steps
- 等你确认后进入 `/do` 执行 Task 1–3

---

## Execution Log (2026-02-01)
- [x] Task 1: 新建数据来源索引文档
- [x] Task 2: REPORT_ARCHITECTURE 增加回指
- [x] Task 3: DOC_INDEX 增加入口

### Commands & Outputs
- `rg -n "DATA_SOURCES_INDEX" scripts/rdc_analyzer/docs/REPORT_ARCHITECTURE.md`
- `rg -n "DATA_SOURCES_INDEX" docs/analysis/codex_rdc_analyzer/DOC_INDEX.md`
- `rg -n "数据来源方式总表" docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`
