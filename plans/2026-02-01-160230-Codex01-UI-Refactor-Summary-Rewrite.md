# UI Refactor Summary Rewrite Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-02-01  
**Owner:** Codex01  
**Last Updated:** 2026-02-01  
**Plan File:** `plans/2026-02-01-160230-Codex01-UI-Refactor-Summary-Rewrite.md`

---

## Plan Metadata
- Version: 2026-02-01
- Owner: Codex01
- Last Updated: 2026-02-01
- Plan File: `plans/2026-02-01-160230-Codex01-UI-Refactor-Summary-Rewrite.md`

## Goal
- 按 `plans/2026-02-01-155453-Codex01-UI-Refactor-Summary-Doc.md` **逐条对应**重写总结文档，满足“新人教学 + 项目汇报”双用途。

## Architecture
- 单文件总结文档（≤800 行），结构与计划条目一一映射。
- 使用 Mermaid/ASCII 绘制框架图、流程图、调用图。
- 明确代码引用（文件/关键函数名）以保证可追溯性。

## Tech Stack
- Markdown
- Mermaid（graph/sequence）
- ASCII（必要时）

## Success Criteria (measurable)
- 文档包含：设计理念、框架图、流程图、代码调用图、模块职责（WHAT/WHY/HOW）。
- 文档加入“计划→文档对照表”，逐项对应计划条目。
- 文档不超过 800 行。
- 索引 DOC_INDEX 增加新条目。

## Acceptance Criteria
- [ ] 新人阅读可理解“入口→契约→UI”的链路
- [ ] 汇报可快速看到目标/范围/风险/缺口
- [ ] DOC_INDEX 增加新条目（简介+关键词+适用链路）

## Verification Commands
- `rg -n '设计理念|框架图|流程图|代码调用图' docs/analysis/codex_rdc_analyzer/2026-02-01-ui-refactor-summary.md` (Expected: 4 个标题都存在)
- `rg -n '计划对照表' docs/analysis/codex_rdc_analyzer/2026-02-01-ui-refactor-summary.md` (Expected: 存在)
- `rg -n 'analyze_xml_report.py|report_contract.py|report_ui.py' docs/analysis/codex_rdc_analyzer/2026-02-01-ui-refactor-summary.md` (Expected: 至少各出现一次)
- `rg -n 'UI 重构升级总结' docs/analysis/codex_rdc_analyzer/DOC_INDEX.md` (Expected: 新条目存在)

## Evidence
- v2 入口：`scripts/rdc_analyzer/analyze_xml_report.py:1717-1737`
- 数据契约：`scripts/rdc_analyzer/report_contract.py:24-132`
- UI 壳层：`scripts/rdc_analyzer/report_ui.py:747-820`
- Issue Detector：`scripts/rdc_analyzer/core/issue_detector.py:160-210`

## Estimation
- Effort: 2–4 hours
- Story Points: 2
- Original Estimate: 0.5 day

## Risk Register
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| 文档过长超 800 行 | Medium | Medium | 控制在单文件 + 表格精简 |
| 图示与代码不一致 | High | Low | 图内标注模块名与入口文件 |

## Game Dev: Memory & Resource Budget (Leak Checks)
- 文档强调“大纹理/超长列表”渲染风险与 UI 防护策略。

## Game Dev: Asset Pipeline
- 文档强调纹理导出目录与 Manifest 映射的一致性。

## Game Dev: Crash Repro + Dumps/Symbols
- 文档强调 UI 生成失败的 traceback + commit hash 记录。

---

## Scope
**In Scope**
- 重写 `2026-02-01-ui-refactor-summary.md` 并按计划逐条对应
- 更新 `DOC_INDEX.md` 增加新条目

**Out of Scope**
- 代码功能修改
- UI 组件实现扩展

## Assumptions
- 总结文档继续保存在 `docs/analysis/codex_rdc_analyzer/`

## Repo / File List (line refs)
- `docs/analysis/codex_rdc_analyzer/2026-02-01-ui-refactor-summary.md` (rewrite)
- `docs/analysis/codex_rdc_analyzer/DOC_INDEX.md`
- `plans/2026-02-01-155453-Codex01-UI-Refactor-Summary-Doc.md`

## Approach (Pseudo-code)
```
load plan -> create plan-to-doc mapping table
rewrite summary doc sections aligned to plan
insert diagrams (framework/flow/call)
add responsibilities table + risks
update DOC_INDEX entry
verify headings + references
```

## Impact Analysis
- 仅文档改动，不影响运行逻辑；需要保证与代码一致。

## Build/Test/Lint Quick Guide (record only)
- 无需构建或测试（仅文档）。

---

## Task Checklist (2–5 min steps)

### Task 1: 重写总结文档（逐条对照计划）
**Files:**
- Modify: `docs/analysis/codex_rdc_analyzer/2026-02-01-ui-refactor-summary.md`

**Step 1: 写“计划 → 文档对照表”**
```markdown
## 计划对照表（Plan → Summary）
| 计划条目 | 文档位置 |
|---|---|
| Goal | 本文“设计理念”与“范围” |
| Architecture | “框架图”与“调用图” |
| Success Criteria | “验收要点” |
| Evidence | “代码引用” |
```

**Step 2: 重写正文（教学 + 汇报双视角）**
```markdown
## 设计理念（WHY）
...（新人视角 + 汇报视角）

## 框架图（WHAT / Architecture）
```mermaid
graph TD
  A[analyze_xml_report.py] --> B[ReportDataContract]
  B --> C[build_manifest()]
  B --> D[render_report_shell]
  D --> E[Issues/Events/Resources/Performance]
```
```

**Step 3: 加入“验收要点 & 风险”**
```markdown
## 验收要点
- ...

## 风险与缺口
- ...
```

**Step 4: Commit**
```bash
git add docs/analysis/codex_rdc_analyzer/2026-02-01-ui-refactor-summary.md
git commit -m "docs(rdc-analyzer): rewrite UI refactor summary aligned to plan"
```

### Task 2: 更新 DOC_INDEX 索引条目
**Files:**
- Modify: `docs/analysis/codex_rdc_analyzer/DOC_INDEX.md`

**Step 1: 添加条目**
```markdown
### 2026-02-01-ui-refactor-summary（UI 重构升级总结）
- 简介：按计划逐条对照，解释 v2 UI 架构、流程与调用链。
- 关键词：ui refactor, contract, manifest, shell
- 适用链路：A/C
- 路径：`docs/analysis/codex_rdc_analyzer/2026-02-01-ui-refactor-summary.md`
```

**Step 2: Commit**
```bash
git add docs/analysis/codex_rdc_analyzer/DOC_INDEX.md
git commit -m "docs(index): add UI refactor summary entry"
```

---

## Next Steps
- [ ] 你确认后进入 `/do` 执行 Task 1–2。  
