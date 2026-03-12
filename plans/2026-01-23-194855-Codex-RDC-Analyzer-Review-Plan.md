# RDC Analyzer Review & A-first Sync (Autonomous)

## Objective
Deliver an updated A-first plan with new P0 fixes, a deep architecture/feature review of `scripts/rdc_analyzer`, and a clear A-stage status (done vs. remaining) with testing focus.

## Context
- User requests: sync fixes into existing plan, review rdc_analyzer architecture/coverage, identify redundancy, evaluate A-stage minimal loop, and produce a summary or implementation plan.
- Repo constraints: no destructive commands, no `renderdoc/3rdparty/` or `build*/` edits, docs under `docs/analysis/`, single doc <= 800 lines.

## Scope
- In scope:
  - Update `plans/2025-01-20-152300-Codex-A-first-execution-plan.md` with new P0 tasks and latest findings.
  - Create/update analysis docs under `docs/analysis/codex_rdc_analyzer/`.
  - Architecture/feature coverage review of `scripts/rdc_analyzer/` (Python).
  - A-stage completion assessment + test points or execution plan.
- Out of scope:
  - Modifying RenderDoc core C++ code.
  - Building/compiling binaries.
  - Deleting generated artifacts without explicit user request.

## Constraints
- Use `py -3` for Python.
- Keep documentation files under 800 lines each.
- Do not run destructive commands (e.g., `rm -rf`, `git clean -fd`).
- Use codemap-first; fallback to Serena when codemap has no matches.

## Verification (Definition of Done)
- Plan file updated with new P0 tasks and status.
- New/updated docs created in `docs/analysis/codex_rdc_analyzer/` covering:
  - Architecture review
  - Feature coverage comparison
  - Redundancy/overlap findings
  - A-stage completion assessment + test points or plan
- Cross-references added to `docs/analysis/codex_rdc_analyzer/README.md`.

## Task Checklist
- [x] Locate relevant docs and plan sections; capture evidence paths.
- [x] Update A-first plan with new P0 fixes and verification notes.
- [x] Produce architecture + feature coverage review doc.
- [x] Assess A-stage minimal loop completeness; add test points or execution plan.
- [x] Update docs index (README) to include new doc(s).

## Risks / Open Questions
- `game_mode_sel_v1.py` doc reference not found in this repo; needs user-provided path.
- Codemap does not index this repo (fallback to Serena evidence).

## Notes
- This plan is for autonomous execution (no stage-gate required).
