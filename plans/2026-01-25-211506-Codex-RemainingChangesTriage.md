# Remaining Changes Triage Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

## Plan Metadata
- Version: 2026.01.25
- Owner: Codex
- Last Updated: 2026-01-25
- Plan File: plans/2026-01-25-211506-Codex-RemainingChangesTriage.md

## Goal
- 对当前分支剩余未提交的文件进行分组、确认保留范围，并形成有序提交（或丢弃）以恢复干净工作区。

## Architecture
- 先按“来源/用途”分组（配置/工具/索引/实验输出/计划文档），每组单独确认与提交；不清理未知来源文件，需用户确认后处理。

## Tech Stack
- Git（status / restore / add / commit）
- PowerShell 7（只读命令）
- Python 3（仅用于清单）

## Success Criteria (measurable)
- `git status -sb` 仅保留明确允许的本地文件，或完全干净。
- 每组提交均有清晰 Conventional Commits 备注。

## Acceptance Criteria
- 不误提交实验产物或本地临时文件。
- 核心源码改动与文档/索引变更分离提交。

## Verification Commands
- `git status -sb` (Expected: clean or only approved local files)

## Evidence
- 提交日志 + `git status -sb` 输出。

## Estimation
- Effort: 1-2 hours
- Story Points: 3
- Original Estimate: N/A

## Risk Register
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| 误提交本地产物 | 中 | 中 | 每组提交前列出文件清单并确认 |
| 丢失重要改动 | 高 | 低 | 仅在用户确认“丢弃”后执行 restore |
| 计划文档过多 | 低 | 中 | 仅提交认可的 plan，其他保留为 untracked |

## Game Dev: Memory & Resource Budget (Leak Checks)
- 无运行时改动，本计划仅处理 Git 状态。

## Game Dev: Asset Pipeline
- 不触碰资产，仅处理源码与文档。

## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: N/A
- Dump/Core: (minidump | core dump) N/A
- Symbols: (PDB | dSYM | ELF | DWARF) N/A
- Build identity: (build id | commit hash | git commit) N/A

## Build/Test/Lint Quick Guide
- Build: 无
- Test: 无
- Lint: 无

## Repo / File List (line-specific)
- Modify: `Agents.md:1`
- Modify: `docs/conf.py:1`
- Modify: `plans/2025-01-20-phase1-performance-integration.md:1`
- Add: `plans/2025-01-21-AgentB-AuditFix-3-4.md`
- Add: `plans/2026-01-24-193124-Agent01-ExportCompile-Codemap.md`
- Modify: `scripts/rdc_analyzer/.ai/FEATURE_INDEX.md:1`
- Modify: `scripts/rdc_analyzer/.ai/INDEX.md:1`
- Modify: `scripts/rdc_analyzer/.ai/tasks/2026-01-19.md:1`
- Modify: `scripts/rdc_analyzer/core/bridge.py:1`
- Modify: `scripts/rdc_analyzer/core/optimization_standalone.py:1`
- Modify: `scripts/rdc_analyzer/core/rt_tracker.py:1`
- Modify: `scripts/rdc_analyzer/core/types.py:1`
- Modify: `scripts/rdc_analyzer/extract_pipeline_state.py:1`
- Modify: `scripts/rdc_analyzer/generate_real_report.py:1`
- Modify: `scripts/rdc_analyzer/test_texture_extract.py:1`
- Add: `scripts/rdc_analyzer/_test_regex.js`
- Add: `scripts/rdc_analyzer/g145_with_shaders.json`
- Add: `scripts/rdc_analyzer/test_captures/export_output/bindings_with_shaders.json`

## Approach (Pseudo-code)
```
group files by purpose
for each group:
  show list -> user confirm keep or discard
  if keep: stage + commit with clear message
  if discard: git restore / git clean (only with confirmation)
verify git status clean
```

## Impact Analysis
- 无功能改动本身；仅整理现有改动与计划文件。

## Action Items (checkbox)

- [x] Task 1: 核心源码改动分组确认（scripts/rdc_analyzer/*.py）
  - Files: core/*, extract_pipeline_state.py, generate_real_report.py, test_texture_extract.py
  - Confirm: 需要保留？若保留 → `git add` → `feat|fix` 提交

- [x] Task 2: 构建/文档配置变动确认
  - Files: `Agents.md`, `docs/conf.py`
  - Confirm: 是否为本次需求改动？若否 → restore

- [x] Task 3: 计划/索引类文件确认
  - Files: plans/*, scripts/rdc_analyzer/.ai/*
  - Confirm: 是否归档保留？若保留 → `docs(plans)` 或 `docs(ai)` 提交

- [x] Task 4: 追加计划文档提交
  - Files: `plans/2026-01-25-213500-Agent01-HTML-Metrics-Alignment.md`
  - Commit: `docs(plans): add html metrics alignment plan`

- [x] Task 5: 样本/实验文件提交
  - Files:
    - `example_d3d12.obj`
    - `scripts/rdc_analyzer/_test_regex.js`
    - `scripts/rdc_analyzer/g145_with_shaders.json`
    - `scripts/rdc_analyzer/test_captures/export_output/bindings_with_shaders.json`
  - Commit: `chore(samples): add local sample artifacts`

- [ ] Task 6: 清理与验证
  - Run: `git status -sb` (Expected: clean or approved files only)

## Open Questions
- 是否确认提交样本/实验文件（已在 Task 5 列出）？
