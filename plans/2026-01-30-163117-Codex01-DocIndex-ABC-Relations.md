# Doc Index + A/B/C 关系澄清 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-01-30  
**Owner:** Codex01  
**Last Updated:** 2026-01-30  
**Plan File:** plans/2026-01-30-163117-Codex01-DocIndex-ABC-Relations.md

**Goal:** 明确 A/B/C 三条链路关系（含 A+C 主路径定位），并提供“文档阅读入口索引”与 A+C 功能/缺口总结入口。

**Architecture:** 仅更新 Markdown 文档：在 `WORK_SUMMARY_ROUTES.md` 增加关系说明；新增文档索引页；在 `Agents.md` 中将索引设为必读入口。

**Tech Stack:** Markdown 文档。

**Success Criteria (measurable):**
- `WORK_SUMMARY_ROUTES.md` 明确写出 A/B/C 关系与 A+C 主路径定位（含 B 的依赖与边界）。
- 新增文档索引页包含简介 + 关键词 + 适用链路标记。
- `Agents.md` 将“阅读入口索引”列为规范必读入口。
- A+C 已完成/未完成要点有明确“文档入口指向”。

**Acceptance Criteria:**
- `rg -n "A\\+C|A/B/C|关系" docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROUTES.md` 有命中。  
- `docs/analysis/codex_rdc_analyzer/DOC_INDEX.md` 存在且含“简介/关键词/适用链路”。  
- `Agents.md` 的“索引文档”区块新增索引入口。  

**Verification Commands:**
- `rg -n "DOC_INDEX" Agents.md`
- `rg -n "A\\+C|A/B/C|关系" docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROUTES.md`
- `rg -n "关键词|Key|Tags" docs/analysis/codex_rdc_analyzer/DOC_INDEX.md`

**Evidence:**
- `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROUTES.md`
- `docs/analysis/codex_rdc_analyzer/DOC_INDEX.md`
- `Agents.md`

**Estimation:**
- Effort: 1–2 小时  
- Story Points: 2  
- Original Estimate: 1.5 小时

**Risk Register (impact/likelihood/mitigation):**
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| A/B/C 关系表述与既有文档不一致 | 中 | 中 | 使用原文术语 + 加“适用场景/依赖” |
| 索引页难维护 | 中 | 低 | 关键词+简介固定结构，便于新增 |

## Game Dev: Memory & Resource Budget (Leak Checks)
- 文档只描述“链路依赖与输出”，不引入额外内存测试步骤。

## Game Dev: Asset Pipeline
- 明确 A+C 组合在“导出资源 + 分析报告”的链路定位，强调离线可复制。

## Game Dev: Crash Repro + Dumps/Symbols
- 本任务为文档更新；如遇工具崩溃，仅记录复现场景与输入样本路径。

---

## Scope / Assumptions
- Scope：仅文档更新，不改代码逻辑。  
- Assumptions：A/C 链路术语沿用现有文档表述。

## Build/Test/Lint Quick Guide (仅记录，不执行)
- 无构建/测试需求，仅使用 `rg` 验证变更。

## File List (精确到行号范围)
- `Agents.md:12-17` — 索引文档入口位置  
- `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROUTES.md:55-186` — A/B/C 章节与验证表  
- `docs/analysis/codex_rdc_analyzer/README.md:17` — 可能补充索引入口（可选）  
- **新增** `docs/analysis/codex_rdc_analyzer/DOC_INDEX.md` — 文档阅读入口

## Approach (Pseudo-code)
```
1) 在 WORK_SUMMARY_ROUTES.md 增加“关系说明”小节
2) 新建 DOC_INDEX.md：简介 + 关键词 + 适用链路
3) Agents.md 索引文档区块加入 DOC_INDEX.md 入口
```

## Impact Analysis
- 文档结构更清晰；对代码无影响。

## Task Checklist
- [x] TASK-01: 明确 A/B/C 关系与 A+C 主路径（ROUTES 文档）
- [x] TASK-02: 新建文档阅读入口索引（DOC_INDEX）
- [x] TASK-03: Agents.md 增加阅读入口（规范必读）
- [x] TASK-04: 如有需要，补充 README 入口（可选）

---

### Task 1: A/B/C 关系澄清（ROUTES）

**WHAT**: 在 `WORK_SUMMARY_ROUTES.md` 增加“关系说明/集合关系”段落。  
**WHY**: 当前只分述 A/B/C，未强调 A+C 主路径与 B 的依赖边界。  
**HOW**: 增加短段落：A/C 互补、A+C 为离线主路径、B 需 Replay 环境。

**Files:**
- Modify: `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROUTES.md:55-186`

**Step 1: Write the doc change**
```
新增“关系说明”小节（2-4 段），包含 A+C 与 B 的集合/依赖关系。
```

**Step 2: Verify**
Run: `rg -n "A\\+C|关系|集合" docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROUTES.md`  
Expected: 命中新增说明段落

**Step 3: Commit**
```bash
git add docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROUTES.md
git commit -m "docs(routes): clarify A/B/C relationships"
```

---

### Task 2: 文档阅读入口索引（DOC_INDEX）

**WHAT**: 新增 `DOC_INDEX.md`，提供简介、关键词、适用链路标签。  
**WHY**: 解决“找不到/记不住文档”的问题，建立统一入口。  
**HOW**: 结构化索引列表（标题 + 简介 + 关键词 + 适用链路）。

**Files:**
- Create: `docs/analysis/codex_rdc_analyzer/DOC_INDEX.md`

**Step 1: Draft index**
```
每个文档条目：简介（1-2 行）+ 关键词 + 适用链路(A/B/C)。
```

**Step 2: Verify**
Run: `rg -n "关键词|Tags|适用链路" docs/analysis/codex_rdc_analyzer/DOC_INDEX.md`  
Expected: 命中索引结构字段

**Step 3: Commit**
```bash
git add docs/analysis/codex_rdc_analyzer/DOC_INDEX.md
git commit -m "docs(index): add doc entry index"
```

---

### Task 3: Agents.md 入口更新（规范必读）

**WHAT**: 将 DOC_INDEX.md 写入 `Agents.md` 的索引文档区块。  
**WHY**: 确保所有对话先读规范入口，再读索引文档。  
**HOW**: 在“索引文档”区块新增一条“文档阅读入口”。

**Files:**
- Modify: `Agents.md:12-17`

**Step 1: Update**
```
新增“文档阅读入口（必读）”条目，指向 DOC_INDEX.md。
```

**Step 2: Verify**
Run: `rg -n "DOC_INDEX" Agents.md`  
Expected: 命中新增入口

**Step 3: Commit**
```bash
git add Agents.md
git commit -m "docs(agents): add doc index entrypoint"
```

---

### Task 4: README 入口补充（可选）

**WHAT**: 在 `README.md` 增加 DOC_INDEX 入口。  
**WHY**: 提供第二入口（非强制）。  
**HOW**: 在阅读顺序列表添加一条索引入口。

**Files:**
- Modify: `docs/analysis/codex_rdc_analyzer/README.md:17`

**Step 1: Update**
```
加入 DOC_INDEX.md 入口（可选）。
```

**Step 2: Verify**
Run: `rg -n "DOC_INDEX" docs/analysis/codex_rdc_analyzer/README.md`  
Expected: 命中新增入口

**Step 3: Commit**
```bash
git add docs/analysis/codex_rdc_analyzer/README.md
git commit -m "docs(readme): add doc index entry"
```

---

## Decisions
- 将 “A+C 主路径 / B 依赖” 明确写入路线文档。
- 新增 DOC_INDEX 作为统一入口，并写入 Agents 规范。

## Verification / Acceptance (DoD)
- A/B/C 关系与 A+C 主路径在 ROUTES 文档可检索。
- DOC_INDEX 存在且包含简介/关键词/适用链路。
- Agents.md 已包含 DOC_INDEX 必读入口。

## Next Steps
- 等待 `/do` 执行该计划。

---

## Execution Log

### 2026-01-30

- TASK-01 完成：已在 `WORK_SUMMARY_ROUTES.md` 增加 A/B/C 关系与 A+C 主路径说明。
  - 验证：`rg -n "A\\+C|A/B/C|关系" docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROUTES.md`
- TASK-02 完成：新增 `DOC_INDEX.md`（简介/关键词/适用链路）。
  - 验证：`rg -n "关键词|Tags|适用链路" docs/analysis/codex_rdc_analyzer/DOC_INDEX.md`
- TASK-03 完成：`Agents.md` 增加 DOC_INDEX 必读入口。
  - 验证：`rg -n "DOC_INDEX" Agents.md`
- TASK-04 完成：`README.md` 增加 DOC_INDEX 入口（可选项已执行）。
  - 验证：`rg -n "DOC_INDEX" docs/analysis/codex_rdc_analyzer/README.md`

**Deviations:** 无。
