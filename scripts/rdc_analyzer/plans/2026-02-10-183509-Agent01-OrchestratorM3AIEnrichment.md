# Plan: Orchestrator M3 AI Enrichment Sidecar

- Time: 2026-02-10 18:35:09
- Agent: Agent01
- Scope: vent_asset_orchestrator.py add optional AI enrichment sidecar (non-blocking), extend rtifact_index schema, add tests, update docs.

## Scope / Assumptions
- Keep existing M1/M2 behavior fully backward-compatible.
- AI sidecar is advisory only; export pipeline must not fail because enrichment fails.
- Output contract stays script-authoritative (AI does not rewrite mesh/material/shader outputs).

## Build/Test/Lint Quick Guide
- Unit test (orchestrator):
  - py -3 -m pytest scripts/rdc_analyzer/tests/test_event_asset_orchestrator.py -q
- Regression tests:
  - py -3 -m pytest scripts/rdc_analyzer/tests/test_export_event_import_bundle.py -q
  - py -3 -m pytest scripts/rdc_analyzer/tests/test_export_fbx_assets.py -q

## Task Checklist
- [x] T1: Add CLI options and runtime branch for AI sidecar generation (enable/disable + non-blocking failure handling).
- [x] T2: Generate vent_<id>/ai_enrichment.json with stable schema-like structure and provenance notes.
- [x] T3: Extend rtifact_index.json with optional i_enrichment summary block.
- [x] T4: Update rtifact_index.schema.json for new optional field (backward compatible).
- [x] T5: Add tests for enabled/disabled/degraded paths and schema validation behavior.
- [x] T6: Update docs (EVENT_ASSET_ORCHESTRATOR.md, SKILL_RDC_EVENT_ASSET_ORCHESTRATOR_SPEC.md, INDEX.md).
- [x] T7: Run tests and record results in this plan.

## Risks / Blockers
- Risk: malformed material payloads may break enrichment parser.
  - Mitigation: defensive parsing and fallback default values.
- Risk: schema mismatch on optional field.
  - Mitigation: keep i_enrichment optional in schema.

## Decisions
- Sidecar filename: vent_<id>/ai_enrichment.json
- rtifact_index.ai_enrichment fields: status, ile, generator, message
- Status set: 
ot_requested, ok, degraded_non_blocking

## Verification / DoD
- rtifact_index.json validates against schema with and without AI enabled.
- When AI enabled and successful: sidecar file exists and stage includes i_enrichment=ok.
- When AI enabled and enrichment throws: pipeline still succeeds and stage marks degraded_non_blocking.
- Regression tests for M1/M2 remain passing.

## Progress Log
- 2026-02-10 18:35: plan created.
- 2026-02-10 18:52: implemented M3 code + schema + tests + docs.
- 2026-02-10 18:53: py -3 -m py_compile scripts/rdc_analyzer/event_asset_orchestrator.py scripts/rdc_analyzer/tests/test_event_asset_orchestrator.py passed.
- 2026-02-10 18:54: py -3 -m pytest scripts/rdc_analyzer/tests/test_event_asset_orchestrator.py -q passed (6 tests).
- 2026-02-10 18:54: py -3 -m pytest scripts/rdc_analyzer/tests/test_export_event_import_bundle.py -q passed (8 tests).
- 2026-02-10 18:54: py -3 -m pytest scripts/rdc_analyzer/tests/test_export_fbx_assets.py -q passed (4 tests).
