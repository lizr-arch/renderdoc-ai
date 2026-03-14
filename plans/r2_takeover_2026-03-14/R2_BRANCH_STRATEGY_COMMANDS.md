# R2 Branch Strategy & Command Draft

## Strategy

- True mainline stays `renderdoc-ai/main`.
- Integration lane for R2: `codex/integration/renderdoc-ai-20260314-r2`.
- Execution lanes for R2:
  - `codex/agentd/m5-android-regression-r2`
  - `codex/agentb/m5-gui-snapshot-stability-r2`
  - `codex/agentc/m6-compare-ci-r2`
  - `codex/agenta/m5-skill-mvp-r2`
- Merge rule remains serial: `D -> B -> C -> A`.
- Merge target must be candidate SHA, never floating branch head.

## Command Draft (No Push/Merge)

```powershell
# Sync remotes
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc fetch --all --prune

# Integration worktree
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-integration switch -C codex/integration/renderdoc-ai-20260314-r2 renderdoc-ai/main
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-integration branch --set-upstream-to=renderdoc-ai/main codex/integration/renderdoc-ai-20260314-r2

# Agent worktrees
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-agentd-m5 switch -C codex/agentd/m5-android-regression-r2 renderdoc-ai/main
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-agentd-m5 branch --set-upstream-to=renderdoc-ai/main codex/agentd/m5-android-regression-r2

D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-agentb-m5 switch -C codex/agentb/m5-gui-snapshot-stability-r2 renderdoc-ai/main
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-agentb-m5 branch --set-upstream-to=renderdoc-ai/main codex/agentb/m5-gui-snapshot-stability-r2

D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-agentc-m6 switch -C codex/agentc/m6-compare-ci-r2 renderdoc-ai/main
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-agentc-m6 branch --set-upstream-to=renderdoc-ai/main codex/agentc/m6-compare-ci-r2

D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-agenta-m5 switch -C codex/agenta/m5-skill-mvp-r2 renderdoc-ai/main
D:\Program Files\Git\cmd\git.exe -C D:\Code\git\renderdoc-agenta-m5 branch --set-upstream-to=renderdoc-ai/main codex/agenta/m5-skill-mvp-r2
```

## Post-check

All five worktrees should report:

```text
## <r2-branch>...renderdoc-ai/main
```

No untracked `test_output` or transient artifact is allowed on integration/mainline worktrees.
