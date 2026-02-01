# Data Sources Auto-Expand Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-02-01  
**Owner:** Codex01  
**Last Updated:** 2026-02-01  
**Plan File:** `plans/2026-02-01-201019-Codex01-Data-Sources-Auto-Expand.md`

---

## Goal
- 自动补齐“数据来源方式总表”的来源项，并按分类 + WHAT/WHY/HOW 记录可用性与限制。

## Scope
**In Scope**
- 汇总现有链路中所有可确认的数据来源（A/B/C）
- 补齐 `DATA_SOURCES_INDEX.md` 表格行与说明

**Out of Scope**
- 新增/修改数据导出代码
- 构建 RenderDoc 或渲染 UI

## Assumptions
- 当前以文档/代码线索为事实来源
- 不做 replay 实测，只记录可用性与依赖

## Repo / File List (line refs)
- Modify: `docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md:1`
- Reference: `scripts/rdc_analyzer/analyze_xml_report.py:9`
- Reference: `scripts/rdc_analyzer/compare_rdc.py:118`
- Reference: `scripts/rdc_analyzer/compare_rdc.py:213`
- Reference: `scripts/rdc_analyzer/renderdoc_mali_shell.py:281`
- Reference: `docs/analysis/codex_rdc_analyzer/README.md:248`
- Reference: `scripts/rdc_analyzer/docs/REPORT_ARCHITECTURE.md:266`

## Approach (Pseudo-code)
```
collect sources from README / REPORT_ARCHITECTURE / compare_rdc / analyze_xml_report / renderdoc_mali_shell
map each source -> category + WHAT/WHY/HOW + availability (A/B/C)
append rows to DATA_SOURCES_INDEX table
add short “来源覆盖差异说明” section if needed
verify with rg that new entries exist
```

## Impact Analysis
- 文档更新，不影响功能
- 风险：来源描述不完整 → 标注“待补充”并写清限制

## Build/Test/Lint Quick Guide (record only)
- `rg -n "renderdoccmd|OpenCaptureFile|export_json_diff|load_json_data|mali" docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`
- `rg -n "DATA_SOURCES_INDEX" docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`

---

## Task Checklist (2–5 min steps)

### Task 1: 汇总 A/C 路线来源（XML/CLI）
**Files:**  
- Modify: `docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`

**Step 1: 新增来源行**
```markdown
| CLI 导出 | renderdoccmd convert XML | ... | ... | ... | A/C | ... |
| CLI 导出 | renderdoccmd export textures/metadata/bindings | ... | ... | ... | A/C | README |
```

**Step 2: 标注限制**
- “字段缺失/需要 replay”写入“可用性/限制”

### Task 2: 汇总 B 路线来源（Replay API）
**Files:**  
- Modify: `docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`

**Step 1: 新增来源行**
```markdown
| Replay API | RenderDoc Python API | ... | ... | renderdoc.OpenCaptureFile + ReplayController | B | python_api |
```

### Task 3: 汇总 Compare/JSON 输出来源
**Files:**  
- Modify: `docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`

**Step 1: 新增来源行**
```markdown
| 输出结构 | load_json_data (input) | ... | ... | compare_rdc.py | A/B | schema-compare |
| 输出结构 | export_json_diff (output) | ... | ... | compare_rdc.py | A/B | schema-compare |
```

### Task 4: 汇总 Mali/外部工具来源
**Files:**  
- Modify: `docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`

**Step 1: 新增来源行**
```markdown
| 外部工具 | Mali 分析 | ... | ... | renderdoc_mali_shell.py | B | REPORT_ARCHITECTURE |
```

---

## Risks & Blockers
- renderdoccmd 的 export 能力与版本差异 → 标注“可能缺失”
- Mali 工具链依赖外部环境 → 标注“可用性条件”

## Verification / DoD
- `DATA_SOURCES_INDEX.md` 表格新增 ≥4 行来源
- 新增行包含 WHAT/WHY/HOW + 可用性/限制
- `rg` 能检索到关键来源关键词

## Next Steps
- 等你确认后进入 `/do` 执行 Task 1–4

---

## Execution Log (2026-02-01)
- [x] Task 1: 汇总 A/C 路线来源（XML/CLI）
- [x] Task 2: 汇总 B 路线来源（Replay API）
- [x] Task 3: 汇总 Compare/JSON 输出来源
- [x] Task 4: 汇总 Mali/外部工具来源

### Commands & Outputs
- `rg -n "renderdoccmd|OpenCaptureFile|export_json_diff|load_json_data|mali" docs/analysis/codex_rdc_analyzer/DATA_SOURCES_INDEX.md`
