# Git Hygiene & Workspace Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

## Plan Metadata
- Version: 2026.01.25
- Owner: Codex
- Last Updated: 2026-01-25
- Plan File: plans/2026-01-25-203050-Codex-GitCleanup.md

## Goal
- 在 `feature/export-textures-command` 分支内完成一次性 Git 清理治理：统一忽略本地生成物、移除误跟踪产物、确保工作区可持续开发。

## Architecture
- 采用“**先盘点 → 再忽略 → 再解除跟踪 → 分步提交**”流程，避免误删本地数据。所有移除只做 `--cached`，不删除磁盘文件。

## Tech Stack
- Git（status / check-ignore / rm --cached / add / commit）
- PowerShell 7（只读命令）
- Python 3（仅用于统计）

## Success Criteria (measurable)
- `git status -sb` 显示工作区干净（或仅剩明确保留的未跟踪本地文件且被 ignore）。
- `git ls-files -ci --exclude-standard` 无输出（已忽略项不被跟踪）。

## Acceptance Criteria
- 继续在当前分支开发不受脏工作区影响。
- 本地日志/缓存/测试输出不再进入 git 状态。
- 不删除任何本地文件内容（仅取消跟踪）。

## Verification Commands
- `git status -sb` (Expected: 工作区干净)
- `git ls-files -ci --exclude-standard` (Expected: 无输出)
- `git status --ignored -sb` (Expected: 本地生成物显示为 ignored)

## Evidence
- 记录 `git status -sb` 和 `git status --ignored -sb` 输出（保存到本计划“Evidence”段落或会话记录）。

## Estimation
- Effort: 1-2 hours
- Story Points: 3
- Original Estimate: N/A

## Risk Register
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| 忽略规则过宽导致误忽略有效源码 | 中 | 中 | 先盘点清单，逐条确认，保留 exceptions |
| 误取消跟踪重要文件 | 高 | 低 | 仅对“生成物/缓存/日志”执行 `--cached`，提交前复核 diff |
| 清理后仍有脏文件 | 低 | 中 | 用 `git status --ignored -sb` 验证并补充 ignore |

## Game Dev: Memory & Resource Budget (Leak Checks)
- 无运行时/内存改动，本计划仅处理 Git 目录状态。

## Game Dev: Asset Pipeline
- 不触碰资产管线，仅忽略本地导出/报告产物。

## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: N/A（非运行时变更）
- Dump/Core: (minidump | core dump) N/A
- Symbols: (PDB | dSYM | ELF | DWARF) N/A
- Build identity: (build id | commit hash | git commit) N/A

## Build/Test/Lint Quick Guide
- Build: 无
- Test: 无
- Lint: 无

## Repo / File List (line-specific)
- Modify: `.gitignore:51-66`（本地生成物忽略规则与例外）
- Create: `plans/2026-01-25-203050-Codex-GitCleanup.md`（本计划）
- Remove from index: 待盘点的生成物路径清单（见 Task 1 输出）

## Approach (Pseudo-code)
```
inventory = git status --porcelain
ignored = git status --ignored -sb
decide ignore patterns (logs/, __pycache__/, .pytest_cache/, output/, html reports, test_output)
update .gitignore with minimal, scoped rules + keep exceptions
git rm --cached <generated paths>
commit ignore rules
commit untracked removal
verify clean status
```

## Impact Analysis
- 对仓库无功能影响；仅改变 git 跟踪范围。
- 清理后大幅降低噪音，提升后续提交可读性。

## Action Items (checkbox)

- [x] Task 1: 盘点当前脏文件并分类（生成物/日志/缓存/真实源码）
  - Commands:
    - `git status -sb`
    - `git status --porcelain`
    - `git status --ignored -sb`
    - `git ls-files -ci --exclude-standard`
  - Output: 生成“需忽略/需取消跟踪/需保留”的三类清单

- [x] Task 2: 确认并补齐 .gitignore 规则（最小覆盖）
  - Files: `.gitignore:51-66`
  - Rules candidate (需人工确认):
    - `logs/`
    - `scripts/rdc_analyzer/output/`
    - `scripts/rdc_analyzer/test_output/`
    - `scripts/rdc_analyzer/test_output_d3d12/`
    - `scripts/rdc_analyzer/*.html`
    - `scripts/rdc_analyzer/*.json`
    - `scripts/rdc_analyzer/__pycache__/`
    - `scripts/rdc_analyzer/.pytest_cache/`
  - Guardrails:
    - 保留 `!scripts/rdc_analyzer/tests/**/*.py` 例外

- [x] Task 3: 提交忽略规则
  - Command:
    - `git add .gitignore`
    - `git commit -m "chore(repo): ignore local artifacts"`

- [x] Task 4: 取消跟踪已误纳入的生成物（不删除文件）
  - Command template (基于 Task 1 结果填充):
    - `git rm --cached <path1> <path2> ...`
  - Safety: 不使用 `git clean` / `git reset --hard`

- [x] Task 5: 提交“取消跟踪”变更
  - Command:
    - `git add -A`
    - `git commit -m "chore(repo): untrack generated artifacts"`

- [x] Task 6: 验证清理结果
  - Commands:
    - `git status -sb` (Expected: clean)
    - `git ls-files -ci --exclude-standard` (Expected: no output)
  - Note: `git ls-files -ci` 仍包含受保护的 3rdparty/ 与 `scripts/rdc_analyzer/test_captures/test_game.rdc`（忽略但保持跟踪）

## Open Questions
- 是否允许在 `.gitignore` 中增加 `scripts/rdc_analyzer/*.html` / `*.json` 的通用忽略？
- logs/ 目录是否全部视为本地产物，可统一忽略？
