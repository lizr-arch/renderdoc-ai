# Plan: Orchestrator M3 AI Enrichment Sidecar

- Time: 2026-02-10 18:35:09
- Agent: Agent01
- Scope: add optional AI enrichment sidecar in event_asset_orchestrator, extend artifact index schema, add tests, and update docs.

## Scope / Assumptions
- Keep existing M1/M2 behavior backward-compatible.
- AI sidecar is advisory only; export pipeline does not fail if enrichment fails.
- Main mesh/material/shader outputs stay script-authoritative.

## Build/Test/Lint Quick Guide
- py -3 -m py_compile scripts/rdc_analyzer/event_asset_orchestrator.py scripts/rdc_analyzer/tests/test_event_asset_orchestrator.py
- py -3 -m pytest scripts/rdc_analyzer/tests/test_event_asset_orchestrator.py -q
- py -3 -m pytest scripts/rdc_analyzer/tests/test_export_event_import_bundle.py -q
- py -3 -m pytest scripts/rdc_analyzer/tests/test_export_fbx_assets.py -q

## Task Checklist
- [x] T1: Add CLI option and runtime branch for AI sidecar generation.
- [x] T2: Generate event_<id>/ai_enrichment.json with stable structure.
- [x] T3: Extend artifact_index with ai_enrichment summary block.
- [x] T4: Extend artifact_index schema with optional ai_enrichment fields.
- [x] T5: Add tests for enabled, disabled, and degraded paths.
- [x] T6: Update docs (EVENT_ASSET_ORCHESTRATOR, SKILL spec, INDEX).
- [x] T7: Run tests and record results.

## Risks / Blockers
- Risk: malformed material payload may break enrichment parser.
  - Mitigation: defensive parsing and defaults.
- Risk: schema mismatch for optional fields.
  - Mitigation: keep new fields optional in artifact index schema.

## Decisions
- Sidecar filename: event_<id>/ai_enrichment.json
- artifact_index.ai_enrichment fields: status, file, generator, message
- ai_enrichment status set: not_requested, ok, degraded_non_blocking

## Verification / DoD
- artifact_index validates with and without AI enabled.
- AI enabled success path writes sidecar and ai_enrichment stage status ok.
- AI enabled failure path remains non-blocking with degraded status.
- Regression tests for M1/M2 pass.

## Progress Log
- 2026-02-10 18:35: plan created.
- 2026-02-10 18:52: implemented M3 code, schema, tests, and docs.
- 2026-02-10 18:53: py_compile passed.
- 2026-02-10 18:54: test_event_asset_orchestrator passed (6 tests).
- 2026-02-10 18:54: test_export_event_import_bundle passed (8 tests).
- 2026-02-10 18:54: test_export_fbx_assets passed (4 tests).
- 2026-02-10 18:59: reran test_event_asset_orchestrator after schema cleanup; still passed.
