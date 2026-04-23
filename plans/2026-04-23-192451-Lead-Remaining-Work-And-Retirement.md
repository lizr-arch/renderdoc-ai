# Plan: Lead / Remaining Work And R3 Retirement

Time: 2026-04-23 19:24:51 | Owner: Lead

## Scope / Assumptions

- Goal:
  - freeze the current post-merge project status against the product charter,
  - list only the remaining work needed to claim full charter closure,
  - define a safe retirement procedure for the old `D/B/C/A` `r3` source worktrees.
- Current released mainline is `renderdoc-ai/main@cae519d0d814dc2da24843408768fbb8d22e8673`.
- Historical control reference remains `codex/integration/renderdoc-ai-20260311@a961caccec5fef47f5d78cb165dc96347d5c0706`.
- `D` real-device verification is paused because no Android device is currently attached.
- This document is control-only. No merge, push, reset, clean, branch delete, or worktree removal is executed here.

## Mainline / Contract Guardrails

- Contract guardrails stay unchanged:
  - `snapshot.v1`
  - `template.v1`
  - `mcp-query.v1`
- No second schema/template/report/protocol may be introduced.
- Future business work must start from a fresh worktree based on `renderdoc-ai/main@cae519d0d814dc2da24843408768fbb8d22e8673`.
- Old `r3` source worktrees are now audit objects, not active development baselines.

## Charter Progress Snapshot

- `M0` Total charter and contract freeze: done.
  - Evidence:
    - `D:\Code\git\renderdoc\docs\product\development_charter.md`
    - `D:\Code\git\renderdoc\docs\product\snapshot_schema_v1.md`
    - `D:\Code\git\renderdoc\docs\product\template_contract_v1.md`
    - `D:\Code\git\renderdoc\docs\product\mcp_query_contract_v1.md`
- `M1` Foundation availability and compatibility baseline: partially done.
  - Done:
    - Android launch failure taxonomy and UI handling landed in the historical `D` line.
    - Completed real-device closure:
      - success `Launch + Capture`
      - `AndroidAPKInstallFailed`
      - `InjectionFailed(timeout)`
      - `InjectionFailed(non-timeout)`
  - Remaining:
    - `JDWPFailure`
    - `AndroidLayerConfFailed`
  - Current blocker:
    - no attached Android device.
- `M2` Unified snapshot and template: done for the current mainline contract surface.
- `M3` Report product line stabilization: done for the current single-frame GUI export path.
  - `Analyzer Report` -> auto-export -> `snapshot.v1.json` / `analysis.json` / `capture_context.json` is verified on mainline.
- `M4` MCP stabilization: done for the current local-desktop query path.
  - `mcp-query.v1` remains single-envelope and stable on mainline.
- `M5` Skill MVP: done for the current mainline scope.
  - `run_query.py` + `snapshot_consume.py --execute` complete successfully against a real loaded capture.
- `M6` Compare and CI system: current-cycle functional recert is complete on current mainline.
  - Repo assets exist for compare/diff/regression.
  - `baseline/target + JSON/JUnit/exit-code/golden` recertification is now archived for the current control cycle.
  - Remaining `M6` work is reduced to broad compare-suite hygiene, not compare-core behavior.

## Remaining Work Only

- `R1`: `D` line device evidence closure
  - Required outcome:
    - reproduce and capture fresh evidence for:
      - `JDWPFailure`
      - `AndroidLayerConfFailed`
  - Exit condition:
    - the `D` plan can move from "partial real-device closure" to "full planned real-device closure".
  - Not blocked by code implementation.
  - Blocked only by device availability.

- `R2`: compare-suite hygiene
  - Required outcome:
    - keep `M6` recert commands targeted and explicit,
    - optionally clean broad filtered pytest collection so unrelated import errors no longer appear during compare-focused sweeps.
  - Evidence status:
    - current mainline-era compare/CI behavior is already re-certified and archived.
  - Exit condition:
    - broad compare-related pytest invocation no longer surfaces unrelated import-collection failures.

- `R3`: retire legacy `r3` source worktrees
  - Required outcome:
    - preserve them as traceable history until explicit cleanup approval,
    - stop treating them as active dev branches,
    - move future work to fresh worktrees from released main.
  - Exit condition:
    - cleanup instructions are approved and executed, or the worktrees are explicitly frozen in control docs.

## Current R3 Audit Snapshot

- `D:\Code\git\renderdoc-agentd-r3`
  - branch: `codex/agentd/m0c-android-regression-r3`
  - head: `87c5a0b7a176a6fae40775b0b43d1e21c7740409`
  - status: `behind 3`, plan file dirty
- `D:\Code\git\renderdoc-agentb-r3`
  - branch: `codex/agentb/m5-gui-snapshot-stability-r3`
  - head: `70ff751cd9756108dd085d24d38d9825d8b60421`
  - status: `ahead 1, behind 3`
- `D:\Code\git\renderdoc-agentc-r3`
  - branch: `codex/agentc/m6-compare-ci-r3`
  - head: `d508e23e6e2a0717b8db4f43fe5c5979489fea20`
  - status: `ahead 2, behind 3`
- `D:\Code\git\renderdoc-agenta-r3`
  - branch: `codex/agenta/m5-skill-mvp-r3`
  - head: `103b4e458da17ba15c43bd6638ca5677a5f790df`
  - status: `ahead 1, behind 3`, plan file dirty

## Safe Retirement Procedure (No Execution Yet)

- Phase A: freeze and label
  - record each `r3` worktree as `audit-only`.
  - stop opening new tasks against:
    - `D:\Code\git\renderdoc-agentd-r3`
    - `D:\Code\git\renderdoc-agentb-r3`
    - `D:\Code\git\renderdoc-agentc-r3`
    - `D:\Code\git\renderdoc-agenta-r3`
- Phase B: create future clean baseline
  - when new work is needed, create a fresh worktree from:
    - `renderdoc-ai/main@cae519d0d814dc2da24843408768fbb8d22e8673`
- Phase C: cleanup approval gate
  - only after explicit approval:
    - optionally commit or archive plan-file edits that must be preserved,
    - re-run status/worktree audit,
    - remove or archive old worktrees,
    - optionally delete retired local branches if no longer needed.

## Non-Destructive Audit Commands

- Mainline status:
  - `git -C D:\Code\git\renderdoc ls-remote renderdoc-ai refs/heads/main`
  - `git -C D:\Code\git\renderdoc-main-merge rev-parse HEAD`
  - `git -C D:\Code\git\renderdoc-main-merge status --porcelain=v1 -b`
- Charter anchors:
  - `rg -n "### M0|### M1|### M2|### M3|### M4|### M5|### M6" D:\Code\git\renderdoc\docs\product\development_charter.md`
- `D` line remaining gap:
  - `rg -n "已完成真机闭环|未完成真机闭环|JDWPFailure|AndroidLayerConfFailed" D:\Code\git\renderdoc-agentd-r3\plans\2026-03-11-170659-AgentD-M0C-Android-Launch-Diagnose.md`
  - `adb devices -l`
- `r3` retirement audit:
  - `git -C D:\Code\git\renderdoc worktree list --porcelain`
  - `git -C D:\Code\git\renderdoc-agentd-r3 status --porcelain=v1 -b`
  - `git -C D:\Code\git\renderdoc-agentb-r3 status --porcelain=v1 -b`
  - `git -C D:\Code\git\renderdoc-agentc-r3 status --porcelain=v1 -b`
  - `git -C D:\Code\git\renderdoc-agenta-r3 status --porcelain=v1 -b`

## Task Checklist

- [x] T1: restate current charter stage against the released mainline.
- [x] T2: isolate only the remaining closure work.
- [x] T3: freeze `D` as "device evidence pending".
- [x] T4: record current `r3` worktree states.
- [x] T5: define a safe retirement procedure without destructive execution.

## Risks / Blockers

- Without a device, `M1` cannot be declared fully closed.
- Without a fresh compare/CI recertification run, `M6` should stay "in progress".
- Retiring old worktrees without explicit approval risks losing useful audit context in local plan-file edits.

## Verification / Acceptance

- Definition of Done for this control plan:
  - [x] Remaining work is reduced to a short explicit list.
  - [x] `D` is explicitly frozen as pending device evidence.
  - [x] `r3` worktrees are reclassified as audit-only sources.
  - [x] No destructive cleanup command is executed.

## 2026-04-23 Execution Update

- Retirement execution was completed after explicit `/do` approval.
- Archived local plan-only diffs before cleanup:
  - `D:\Code\git\renderdoc\docs\debug\session_archives\2026-04-23-r3-retirement\agentd-r3-plan.diff`
  - `D:\Code\git\renderdoc\docs\debug\session_archives\2026-04-23-r3-retirement\agenta-r3-plan.diff`
- Restored the recorded dirty plan files in:
  - `D:\Code\git\renderdoc-agentd-r3\plans\2026-03-11-170659-AgentD-M0C-Android-Launch-Diagnose.md`
  - `D:\Code\git\renderdoc-agenta-r3\plans\2026-03-13-155741-AgentA-M5-Skill-MVP.md`
- Removed retired `r3` worktrees from the root worktree registry:
  - `D:\Code\git\renderdoc-agentd-r3`
  - `D:\Code\git\renderdoc-agentb-r3`
  - `D:\Code\git\renderdoc-agentc-r3`
  - `D:\Code\git\renderdoc-agenta-r3`
- Audit note:
  - branch refs were intentionally preserved for traceability,
  - only worktree registrations were removed.
- Command evidence:
  - `git -C D:\Code\git\renderdoc worktree list --porcelain`
    - no longer lists the four `*-r3` worktrees above
  - `git -C D:\Code\git\renderdoc branch --contains d66d0f73b68596c7bc6e656b072ac93ff172f80c`
    - still returns `codex/agenta/mcp-skill-snapshot-consumer`
    - this confirms the banned legacy line still exists only as a historical branch ref, not as an active `r3` candidate worktree
