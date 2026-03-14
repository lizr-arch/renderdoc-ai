# R2 Takeover Snapshot (2026-03-14 15:42:59)

## Frozen Baseline

- `renderdoc-ai/main`: `87c5a0b7a176a6fae40775b0b43d1e21c7740409`
- `codex/integration/renderdoc-ai-20260311`: `a961caccec5fef47f5d78cb165dc96347d5c0706`
- Root workspace: `D:\Code\git\renderdoc`
- Root branch/HEAD: `codex/local-clean-main` / `56fbce9b4327e91b7745dab8a6e045446a6defab`
- Root status: `## codex/local-clean-main...renderdoc-ai/main [ahead 2]`

## R2 Branch Governance

- Integration (R2): `codex/integration/renderdoc-ai-20260314-r2` (from `renderdoc-ai/main`)
- AgentD (R2): `codex/agentd/m5-android-regression-r2`
- AgentB (R2): `codex/agentb/m5-gui-snapshot-stability-r2`
- AgentC (R2): `codex/agentc/m6-compare-ci-r2`
- AgentA (R2): `codex/agenta/m5-skill-mvp-r2`

## Boundary Checklist (Hard Constraints)

- AgentD only: `qrenderdoc/Windows/MainWindow.cpp`, `qrenderdoc/Windows/MainWindow.h`
- AgentB only: `qrenderdoc/Code/Analyzer/*`, `qrenderdoc/Windows/AnalyzerReportViewer.cpp`, `qrenderdoc/Windows/AnalyzerReportViewer.h`
- AgentC only: `scripts/rdc_analyzer/*`
- AgentA only: `tools/mcp/*`, `scripts/rdc_analyzer/mcp_examples/*`

## Known Prohibitions

1. Second schema/template/report system
2. MCP/Skill cloning full report export capability
3. Validation artifacts (`test_output` etc.) entering integration/main
4. Historical ban: `d66d0f73b` must not be merged to integration/main

## Audit Evidence (Raw)

### Root 6-command audit

```text
codex/local-clean-main
56fbce9b4327e91b7745dab8a6e045446a6defab
## codex/local-clean-main...renderdoc-ai/main [ahead 2]

-- worktree list --
D:/Code/git/renderdoc                        56fbce9b4 [codex/local-clean-main]
D:/Code/git/renderdoc-agenta                 d66d0f73b [codex/agenta/mcp-skill-snapshot-consumer]
D:/Code/git/renderdoc-agenta-m5              87c5a0b7a [codex/agenta/m5-skill-mvp-r2]
D:/Code/git/renderdoc-agentb                 59d2502c8 [codex/agentb/gui-snapshot-v1]
D:/Code/git/renderdoc-agentb-m5              87c5a0b7a [codex/agentb/m5-gui-snapshot-stability-r2]
D:/Code/git/renderdoc-agentc                 9b5622d3a [codex/agentc/offline-snapshot-v1]
D:/Code/git/renderdoc-agentc-m6              87c5a0b7a [codex/agentc/m6-compare-ci-r2]
D:/Code/git/renderdoc-agentd                 9eaed79f9 [codex/agentd/m0c-android-launch]
D:/Code/git/renderdoc-agentd-m5              87c5a0b7a [codex/agentd/m5-android-regression-r2]
D:/Code/git/renderdoc-integration            87c5a0b7a [codex/integration/renderdoc-ai-20260314-r2]
D:/Code/git/renderdoc-main-merge             87c5a0b7a [codex/main-gate4-merge-20260313]
D:/Code/git/renderdoc-release-main-bootstrap 4b8002d75 [codex/integration/renderdoc-ai-20260311-linear-v2]

-- local refs --
codex/agenta/m5-skill-mvp eb0a548ec
codex/agenta/m5-skill-mvp-r2 87c5a0b7a
codex/agenta/mcp-skill-snapshot-consumer d66d0f73b
codex/agentb/gui-snapshot-v1 59d2502c8
codex/agentb/m5-gui-snapshot-stability 042fbfffb
codex/agentb/m5-gui-snapshot-stability-r2 87c5a0b7a
codex/agentc/m6-compare-ci 2d1fcfa47
codex/agentc/m6-compare-ci-r2 87c5a0b7a
codex/agentc/offline-snapshot-v1 9b5622d3a
codex/agentd/m0c-android-launch 9eaed79f9
codex/agentd/m5-android-regression 769ff9c01
codex/agentd/m5-android-regression-r2 87c5a0b7a
codex/integration/renderdoc-ai-20260311 a961cacce
codex/integration/renderdoc-ai-20260311-linear 2420da9cc
codex/integration/renderdoc-ai-20260311-linear-v2 4b8002d75
codex/integration/renderdoc-ai-20260314-r2 87c5a0b7a
codex/local-clean-main 56fbce9b4
codex/local-quarantine-20260314 27c51cae8
codex/local-quarantine-20260314-clean 0be3d62a0
codex/main-gate4-merge-20260313 87c5a0b7a
main 1a5a1b8b7
release/main-bootstrap f316f3d18
v1.x 1a5a1b8b7

-- remote refs --
lizr fb727636b
lizr/v1.x fb727636b
origin 74f895f65
origin/converter 38928667e
origin/v1.x 74f895f65
renderdoc-ai 87c5a0b7a
renderdoc-ai/codex/agenta/mcp-skill-snapshot-consumer d66d0f73b
renderdoc-ai/codex/agentd/m0c-android-launch 9eaed79f9
renderdoc-ai/codex/integration/renderdoc-ai-20260311 a961cacce
renderdoc-ai/codex/integration/renderdoc-ai-20260311-linear 2420da9cc
renderdoc-ai/codex/integration/renderdoc-ai-20260311-linear-v2 4b8002d75
renderdoc-ai/main 87c5a0b7a
```

### Workspace statuses

```text
integration: ## codex/integration/renderdoc-ai-20260314-r2...renderdoc-ai/main
agentd: ## codex/agentd/m5-android-regression-r2...renderdoc-ai/main
agentb: ## codex/agentb/m5-gui-snapshot-stability-r2...renderdoc-ai/main
agentc: ## codex/agentc/m6-compare-ci-r2...renderdoc-ai/main
agenta: ## codex/agenta/m5-skill-mvp-r2...renderdoc-ai/main
```
