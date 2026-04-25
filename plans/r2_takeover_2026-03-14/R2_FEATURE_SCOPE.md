# R2 Next Functional Scope

## AgentD (Regression Guard)

- No new feature by default.
- Validate Android launch failure paths for regression.
- Only minimal fix in `MainWindow.cpp/.h` when regression is proven.

## AgentB (M5 GUI Snapshot Stability)

- Stabilize exporter behavior and contract-level field consistency.
- Keep GUI/offline snapshot output aligned to frozen schema/template contracts.
- Hard block on introducing any second schema/template/report path.

## AgentC (M6 Compare/CI Hardening)

- Improve determinism and error model of compare/junit outputs.
- Keep docs/tests aligned with compare output behavior.
- Restrict changes to `scripts/rdc_analyzer/*`.

## AgentA (M5 Skill MVP Consolidation)

- Strengthen `snapshot_consumer` contract compliance and tests.
- Maintain MCP-query-consume chain consistency.
- No full report export duplication in MCP/Skill.

## Merge Model

- Parallel development allowed.
- Serial merge gate: `D -> B -> C -> A`.
- Merge by candidate SHA only (no floating branch heads).
