# UI Refactor Content Advance Plan (123)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-02-01  
**Owner:** Codex01  
**Last Updated:** 2026-02-01  
**Plan File:** `plans/2026-02-01-164636-Codex01-UI-Refactor-Content-Advance.md`

---

## Plan Metadata
- Version: 2026-02-01
- Owner: Codex01
- Last Updated: 2026-02-01
- Plan File: `plans/2026-02-01-164636-Codex01-UI-Refactor-Content-Advance.md`

## Goal
- 按顺序完成 1) 重写总结文档（逐条对照计划）、2) 加入索引、3) 推进内容（v2 UI 补齐 + A/C 报告回归）。

## Architecture
- 文档侧：单文件总结 + DOC_INDEX 索引。  
- 执行侧：A/C 样本导出 → v2 UI 生成 → 关键验收点记录。  

## Tech Stack
- Markdown  
- Mermaid  
- Python 3 (`scripts/rdc_analyzer`)  
- RenderDoc CLI (`renderdoccmd`)  

## Success Criteria (measurable)
- 总结文档包含“计划对照表 + 图示 + 责任表 + 验收要点 + 风险缺口”。  
- DOC_INDEX 新增条目。  
- 两个样本（大远景/战斗特写1）生成 v2 HTML 报告且可验证关键数据项（Issues/Events/Resources/Performance）。  

## Acceptance Criteria
- [ ] 文档严格映射计划条目  
- [ ] DOC_INDEX 有新条目  
- [ ] A/C 报告输出可验收  

## Verification Commands
- `rg -n '计划对照表|设计理念|框架图|流程图|代码调用图' docs/analysis/codex_rdc_analyzer/2026-02-01-ui-refactor-summary.md`  
- `rg -n 'UI 重构升级总结' docs/analysis/codex_rdc_analyzer/DOC_INDEX.md`  
- `py -3 scripts/rdc_analyzer/analyze_xml_report.py <xml> -o <report.html> --ui-version v2`  

## Evidence
- `plans/2026-02-01-155453-Codex01-UI-Refactor-Summary-Doc.md`  
- `scripts/rdc_analyzer/analyze_xml_report.py:1717-1737`  
- `scripts/rdc_analyzer/report_contract.py:24-132`  
- `scripts/rdc_analyzer/report_ui.py:747-820`  

## Estimation
- Effort: 1–2 days  
- Story Points: 3  
- Original Estimate: 1 day  

## Risk Register
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| v2 UI 数据缺失 | High | Medium | 在报告中标注缺失来源 |
| 回归样本导出失败 | High | Medium | 保留旧 XML 输出做兜底 |

## Game Dev: Memory & Resource Budget (Leak Checks)
- 关注大纹理列表渲染风险，必要时分页或折叠。  

## Game Dev: Asset Pipeline
- 纹理目录与 manifest 映射一致，避免资源错配。  

## Game Dev: Crash Repro + Dumps/Symbols
- 失败时记录 traceback + commit hash。  

---

## Scope
**In Scope**
- 重写总结文档  
- 更新索引  
- A/C 样本回归与 v2 UI 生成  

**Out of Scope**
- 新 UI 组件开发  
- Replay 路线  

## Assumptions
- 使用样本：`D:\backup\大远景.rdc`、`D:\backup\战斗特写1.rdc`  
- 输出目录：`D:\backup\rdc_reports\`  

## Repo / File List (line refs)
- `docs/analysis/codex_rdc_analyzer/2026-02-01-ui-refactor-summary.md`  
- `docs/analysis/codex_rdc_analyzer/DOC_INDEX.md`  
- `scripts/rdc_analyzer/analyze_xml_report.py:1717-1737`  

## Approach (Pseudo-code)
```
rewrite summary doc aligned to plan
update DOC_INDEX entry
export XML -> generate v2 HTML for two samples
record verification notes
```

## Impact Analysis
- 文档与回归验证不会改变功能，仅提供证据链与验收记录。  

## Build/Test/Lint Quick Guide (record only)
- `py -3 scripts/rdc_analyzer/analyze_xml_report.py <xml> -o <report.html> --ui-version v2`

---

## Task Checklist (2–5 min steps)

### Task 1: 重写总结文档（逐条对照计划）
**Files:**  
- Modify: `docs/analysis/codex_rdc_analyzer/2026-02-01-ui-refactor-summary.md`

**Step 1: 计划对照表**
```markdown
## 计划对照表（Plan → Summary）
| 计划条目 | 文档位置 | 说明 |
|---|---|---|
| Goal | 设计理念 / 目标与范围 | 对应“重构升级总结”目标 |
| Architecture | 框架图 / 代码调用图 | UI 四视图 + 数据契约链路 |
| Success Criteria | 验收要点 | 目标可检查点 |
| Evidence | 代码引用 | 文件/关键入口 |
| Risks | 风险与缺口 | 当前风险点 |
| Game Dev Addendum | 游戏开发注意点 | 资源、管线、崩溃记录 |
```

**Step 2: 完整重写正文（教学 + 汇报）**  
要求：包含“设计理念/目标与范围/框架图/流程图/调用图/模块职责/验收要点/风险与缺口/GameDev”。

**Step 3: Commit**
```bash
git add docs/analysis/codex_rdc_analyzer/2026-02-01-ui-refactor-summary.md
git commit -m "docs(rdc-analyzer): rewrite UI refactor summary aligned to plan"
```

### Task 2: 更新 DOC_INDEX
**Files:**  
- Modify: `docs/analysis/codex_rdc_analyzer/DOC_INDEX.md`

**Step 1: 新增条目**
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

### Task 3: A/C 回归（大远景）
**Files:**  
- Output: `D:\backup\rdc_reports\大远景\大远景.xml`  
- Output: `D:\backup\rdc_reports\大远景\大远景_report_v2.html`

**Step 1: 生成 XML**
```bash
renderdoccmd convert -f "D:\backup\大远景.rdc" -o "D:\backup\rdc_reports\大远景\大远景.xml" -c xml
```

**Step 2: 生成 v2 HTML**
```bash
py -3 scripts/rdc_analyzer/analyze_xml_report.py "D:\backup\rdc_reports\大远景\大远景.xml" -o "D:\backup\rdc_reports\大远景\大远景_report_v2.html" --ui-version v2
```

**Step 3: 验收记录（日志/截图）**
- Issues/Events/Resources/Performance 是否有数据  
- 若缺失，记录缺失字段  

### Task 4: A/C 回归（战斗特写1）
**Files:**  
- Output: `D:\backup\rdc_reports\战斗特写1\战斗特写1.xml`  
- Output: `D:\backup\rdc_reports\战斗特写1\战斗特写1_report_v2.html`

**Step 1: 生成 XML**
```bash
renderdoccmd convert -f "D:\backup\战斗特写1.rdc" -o "D:\backup\rdc_reports\战斗特写1\战斗特写1.xml" -c xml
```

**Step 2: 生成 v2 HTML**
```bash
py -3 scripts/rdc_analyzer/analyze_xml_report.py "D:\backup\rdc_reports\战斗特写1\战斗特写1.xml" -o "D:\backup\rdc_reports\战斗特写1\战斗特写1_report_v2.html" --ui-version v2
```

**Step 3: 验收记录（日志/截图）**
- Issues/Events/Resources/Performance 是否有数据  
- 若缺失，记录缺失字段  

---

## Next Steps
- [ ] 你确认后进入 `/do` 执行 Task 1–4。  

---

## Execution Log (2026-02-01)
- [x] Task 1: 重写总结文档（逐条对照计划）
- [x] Task 2: 更新 DOC_INDEX 索引条目
- [x] Task 3: A/C 回归（大远景）完成
- [x] Task 4: A/C 回归（战斗特写1）完成

### Commands & Outputs
- XML (大远景)：  
  - `C:\Program Files\RenderDoc\renderdoccmd.exe convert -f "D:\backup\大远景.rdc" -o "D:\backup\rdc_reports\大远景\大远景.xml" -c xml`
- HTML(v2)（大远景）：  
  - `py -3 scripts/rdc_analyzer/analyze_xml_report.py "D:\backup\rdc_reports\大远景\大远景.xml" -o "D:\backup\rdc_reports\大远景\大远景_report_v2.html" --ui-version v2`
- XML (战斗特写1)：  
  - `C:\Program Files\RenderDoc\renderdoccmd.exe convert -f "D:\backup\战斗特写1.rdc" -o "D:\backup\rdc_reports\战斗特写1\战斗特写1.xml" -c xml`
- HTML(v2)（战斗特写1）：  
  - `py -3 scripts/rdc_analyzer/analyze_xml_report.py "D:\backup\rdc_reports\战斗特写1\战斗特写1.xml" -o "D:\backup\rdc_reports\战斗特写1\战斗特写1_report_v2.html" --ui-version v2`

### Notes
- `renderdoccmd` 不在 PATH，使用绝对路径执行。  
- HTML 验收采用脚本统计标记（Issues/Resources/Performance 标签存在）。  
