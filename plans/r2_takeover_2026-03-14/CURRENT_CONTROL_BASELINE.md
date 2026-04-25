# Current Control Baseline (2026-03-14)

## Active Baseline

- `renderdoc-ai/main`: `87c5a0b7a176a6fae40775b0b43d1e21c7740409`
- `codex/integration/renderdoc-ai-20260314-r2`: `87c5a0b7a176a6fae40775b0b43d1e21c7740409`
- `codex/local-clean-main`: `b8db8b4525f416549ec3c89682864c8024806aca`
  - Use only for docs/control notes.
  - Do not use as a business merge source.

## Root Dirty-Tree Isolation

- Root repo `D:\Code\git\renderdoc` is a control surface only.
- Root repo must not be treated as a business merge source.
- Any business candidate must come from an R3 worktree or an explicit SHA, never from the root repo HEAD or a floating branch tip.

### Current Dirty-Tree Grouping

As of this snapshot, the root dirty tree clusters into three top-level groups:

- `plans/`
  - Control docs and takeover notes.
- `qrenderdoc/`
  - GUI implementation spillover.
- `renderdoc/android/`
  - Android implementation spillover.

The grouping is used only for audit and isolation. It is not a permission to merge from the root repo.

### Audit Method

1. Capture the full root status from `D:\Code\git\renderdoc`.
2. Group paths by first directory component.
3. Separate `plans/` control notes from business code changes.
4. Treat every non-`plans/` group as dirty business spillover that must stay out of control-only handling.

### Future Audit Commands

```powershell
git -C D:\Code\git\renderdoc status --short --branch --untracked-files=all
git -C D:\Code\git\renderdoc status --short --untracked-files=all
git -C D:\Code\git\renderdoc diff --name-only
git -C D:\Code\git\renderdoc diff --name-only --cached
git -C D:\Code\git\renderdoc worktree list --porcelain
```

- Use the status output to re-group dirty paths by top-level directory.
- Use the worktree list to confirm the root repo stays in the control lane and that R3 candidates remain isolated in their own worktrees.

## Historical Reference Only

- `codex/integration/renderdoc-ai-20260311`: `a961caccec5fef47f5d78cb165dc96347d5c0706`
- `codex/agenta/mcp-skill-snapshot-consumer`: `d66d0f73b68596c7bc6e656b072ac93ff172f80c`
  - Frozen audit object.
  - Historical ban remains active: never merge this line into integration/main.

## Branch/Worktree Status

- Frozen baseline worktrees:
  - `D:\Code\git\renderdoc-agentd-m5`
  - `D:\Code\git\renderdoc-agentb-m5`
  - `D:\Code\git\renderdoc-agentc-m6`
  - `D:\Code\git\renderdoc-agenta-m5`
- Historical absorbed worktrees:
  - `D:\Code\git\renderdoc-agentd`
  - `D:\Code\git\renderdoc-agentb`
  - `D:\Code\git\renderdoc-agentc`
- Active candidate worktrees for R3 parallel execution:
  - `D:\Code\git\renderdoc-agentd-r3`
    - Branch: `codex/agentd/m0c-android-regression-r3`
    - Base: `renderdoc-ai/main@87c5a0b7a176a6fae40775b0b43d1e21c7740409`
  - `D:\Code\git\renderdoc-agentb-r3`
    - Branch: `codex/agentb/m5-gui-snapshot-stability-r3`
    - Base: `renderdoc-ai/main@87c5a0b7a176a6fae40775b0b43d1e21c7740409`
  - `D:\Code\git\renderdoc-agentc-r3`
    - Branch: `codex/agentc/m6-compare-ci-r3`
    - Base: `renderdoc-ai/main@87c5a0b7a176a6fae40775b0b43d1e21c7740409`
  - `D:\Code\git\renderdoc-agenta-r3`
    - Branch: `codex/agenta/m5-skill-mvp-r3`
    - Base: `renderdoc-ai/main@87c5a0b7a176a6fae40775b0b43d1e21c7740409`

## Operational Rules

1. D/B/C old active lines are read-only audit objects.
2. A old line `d66d0f73b` is banned and cannot become a candidate again.
3. Current active R3 candidates are `D-r3 / B-r3 / C-r3 / A-r3`.
4. All new development branches must start from `87c5a0b7a176a6fae40775b0b43d1e21c7740409`.
5. Candidate evaluation must use explicit SHA, not floating branch heads.
6. `FREEZE_SNAPSHOT.md` remains a historical snapshot, not the current execution baseline.
