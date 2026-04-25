# R2 Branch Strategy & Command Draft

## Strategy

- True mainline stays `renderdoc-ai/main@87c5a0b7a176a6fae40775b0b43d1e21c7740409`.
- Active integration lane stays `codex/integration/renderdoc-ai-20260314-r2@87c5a0b7a176a6fae40775b0b43d1e21c7740409`.
- `codex/integration/renderdoc-ai-20260311@a961caccec5fef47f5d78cb165dc96347d5c0706` is historical only.
- `codex/local-clean-main@b8db8b4525f416549ec3c89682864c8024806aca` is docs/control only and not a business merge source.
- Root repo `D:\Code\git\renderdoc` is docs/control only. It is not a business merge source and must not be used to select candidate content.
- Historical absorbed lanes:
  - `codex/agentd/m0c-android-launch@9eaed79f90d6ad069b785fbe37dac83c5e555427`
  - `codex/agentb/gui-snapshot-v1@59d2502c8efad7aa5ebbe43be270033b39aeea2f`
  - `codex/agentc/offline-snapshot-v1@9b5622d3ad8d5a1447153b5ca88e2427b62d562e`
- Historical banned lane:
  - `codex/agenta/mcp-skill-snapshot-consumer@d66d0f73b68596c7bc6e656b072ac93ff172f80c`
- Active candidate lanes for the current parallel round:
  - `codex/agentd/m0c-android-regression-r3@87c5a0b7a176a6fae40775b0b43d1e21c7740409`
  - `codex/agentb/m5-gui-snapshot-stability-r3@87c5a0b7a176a6fae40775b0b43d1e21c7740409`
  - `codex/agentc/m6-compare-ci-r3@87c5a0b7a176a6fae40775b0b43d1e21c7740409`
  - `codex/agenta/m5-skill-mvp-r3@87c5a0b7a176a6fae40775b0b43d1e21c7740409`
  - Worktrees:
    - `D:\Code\git\renderdoc-agentd-r3`
    - `D:\Code\git\renderdoc-agentb-r3`
    - `D:\Code\git\renderdoc-agentc-r3`
    - `D:\Code\git\renderdoc-agenta-r3`
- Candidate sourcing rule:
  - Only read candidate content from the four R3 worktrees above or from an explicit SHA.
  - Never derive a candidate from the root repo dirty tree, from `codex/local-clean-main`, or from any floating branch head.
- Any future D/B/C/A work must start from `renderdoc-ai/main` in a new worktree.
- Merge target must be candidate SHA, never floating branch head.
- Root dirty-tree audit rule:
  - `plans/` entries are control notes only.
  - Any dirty path outside `plans/` is business spillover and must stay isolated from branch-strategy decisions.

## Command Draft (No Push/Merge)

```powershell
# Root audit
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc rev-parse --abbrev-ref HEAD
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc rev-parse HEAD
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc worktree list --porcelain
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc status --short --branch --untracked-files=all
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc branch --contains d66d0f73b
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc branch --merged renderdoc-ai/main

# R3 candidate audit
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-agentd-r3 status --short --branch
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-agentd-r3 merge-base HEAD renderdoc-ai/main
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-agentd-r3 diff --name-only renderdoc-ai/main...HEAD
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-agentd-r3 rev-parse HEAD

D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-agentb-r3 status --short --branch
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-agentb-r3 merge-base HEAD renderdoc-ai/main
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-agentb-r3 diff --name-only renderdoc-ai/main...HEAD
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-agentb-r3 rev-parse HEAD

D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-agentc-r3 status --short --branch
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-agentc-r3 merge-base HEAD renderdoc-ai/main
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-agentc-r3 diff --name-only renderdoc-ai/main...HEAD
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-agentc-r3 rev-parse HEAD

D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-agenta-r3 status --short --branch
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-agenta-r3 merge-base HEAD renderdoc-ai/main
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-agenta-r3 diff --name-only renderdoc-ai/main...HEAD
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-agenta-r3 rev-parse HEAD

# Legacy hygiene spot checks
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-agentd status --short --branch
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-agentc status --short --branch
```

## Post-check

Expected signals:

```text
## codex/agentd/m0c-android-regression-r3...renderdoc-ai/main
## codex/agentb/m5-gui-snapshot-stability-r3...renderdoc-ai/main
## codex/agentc/m6-compare-ci-r3...renderdoc-ai/main
## codex/agenta/m5-skill-mvp-r3...renderdoc-ai/main
87c5a0b7a176a6fae40775b0b43d1e21c7740409
```

Legacy worktrees `renderdoc-agentd` and `renderdoc-agentc` should be clean after artifact cleanup.

`codex/agenta/mcp-skill-snapshot-consumer` may still appear in `git branch --contains d66d0f73b`, but it is frozen and must never be treated as a merge candidate.
