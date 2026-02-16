# Plan: Route-C Trusted Compare v1 (Schema Contract + Bridge Reliability)

- Time: 2026-02-16 13:15:41
- Agent: Agent02
- Spec source: conversation `/spec` on 2026-02-16
- Goal: make Route-C compare results trustworthy by enforcing one input contract, validating bridge behavior against production code, and aligning compare entrypoints.

## Scope / Assumptions

### In scope
- Harden compare input contract at entrypoint (dict-only, explicit error for legacy list payload).
- Ensure Canonical Schema v1 JSON is converted to DiffEngine-consumable CaptureData consistently.
- Align behavior between `compare_rdc.py` and `rdc_analyzer compare` command.
- Add production-backed tests for schema bridge and compare JSON output contract.

### Out of scope
- No Route-B replay work.
- No new DiffEngine algorithms or new regression rules.
- No RenderDoc C++ (`renderdoccmd`) changes.

### Key assumption
- Route-C user value depends more on data trustworthiness than new UI/report features; a strict contract with better tests yields highest ROI now.

## Navigation Evidence (Codemap First)

codemap queries (max 3):
1) `codemap "scripts/rdc_analyzer/compare_rdc.py load_json_data export_json_diff" -Num 20`
2) `codemap "rdc_loader.py load capture data compare" -Num 20`
3) `codemap "scripts/rdc_analyzer/diff/regression_detector.py detect RegressionRuleId" -Num 20`

candidate hits (>=3):
- [renderdoc] `scripts/rdc_analyzer/compare_rdc.py:118`
  - `def load_json_data(file_path: str) -> Dict[str, Any]:`
- [renderdoc] `scripts/rdc_analyzer/compare_rdc.py:215`
  - `def export_json_diff(...)`
- [renderdoc] `scripts/rdc_analyzer/compare_rdc.py:531`
  - `baseline_data = load_json_data(args.baseline)`
- [renderdoc] `scripts/rdc_analyzer/parsers/rdc_loader.py:227`
  - `def _convert_schema_v1_to_capture_data(data: Dict[str, Any]) -> Dict[str, Any]:`
- [renderdoc] `scripts/rdc_analyzer/parsers/rdc_loader.py:418`
  - `from ..compare_rdc import load_json_data` (cross-module dependency)

follow-ups (1-2) and why:
- `scripts/rdc_analyzer/compare_rdc.py:118-147` (input contract branch point and fail-fast behavior).
- `scripts/rdc_analyzer/parsers/rdc_loader.py:227-334, 413-423` (production schema bridge and JSON load path used by main compare CLI).

next step:
- OpenGrok xref:
  - http://127.0.0.1:8080/source/xref/renderdoc/scripts/rdc_analyzer/compare_rdc.py#118
  - http://127.0.0.1:8080/source/xref/renderdoc/scripts/rdc_analyzer/parsers/rdc_loader.py#227
- Then implement in /do with symbol-targeted edits + tests.

## File List (targets)

Modify:
- `scripts/rdc_analyzer/compare_rdc.py`
  - `load_json_data` input guards: ~118-147
  - main load path (replace JSON-only branch with unified loader): ~529-538
  - exception mapping for contract errors: ~589-599
- `scripts/rdc_analyzer/parsers/rdc_loader.py`
  - remove compare module back-reference (`from ..compare_rdc import load_json_data`): ~418-420
  - normalize JSON list rejection in loader itself: ~413-423
- `scripts/rdc_analyzer/tests/test_compare_rdc.py`
  - extend input contract tests: ~103-134
  - extend JSON output contract tests: ~213-233
- `scripts/rdc_analyzer/tests/test_rdc_loader.py`
  - add schema-v1 JSON conversion assertions in production loader path: ~140-199
- `scripts/rdc_analyzer/tests/test_schema_bridge.py`
  - replace local duplicated conversion function with import from production module: ~20-93

Optional (if drift cleanup included in same batch):
- `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_SCHEMA.md`
  - update mention of `tests/test_schema_bridge_integration.py` to current real test file(s): ~247-250

## Build/Test/Lint Quick Guide (record-only)

- Syntax check:
  - `py -3 -m py_compile scripts/rdc_analyzer/compare_rdc.py scripts/rdc_analyzer/parsers/rdc_loader.py`
- Focused tests:
  - `py -3 -m pytest scripts/rdc_analyzer/tests/test_compare_rdc.py -q`
  - `py -3 -m pytest scripts/rdc_analyzer/tests/test_rdc_loader.py -q`
  - `py -3 -m pytest scripts/rdc_analyzer/tests/test_schema_bridge.py -q`
- Optional broader safety check:
  - `py -3 -m pytest scripts/rdc_analyzer/tests/test_diff_engine.py -q`

Expected:
- Contract tests pass for valid dict input.
- Legacy list input fails with explicit ValueError.
- Schema v1 JSON path produces CaptureData with required keys (`resourceId`, `memorySize`, `size`).

## Task Checklist (2-5 minute granularity)

- [x] T1: Lock compare input contract behavior.
  - [x] Add explicit guard in `load_json_data`: reject non-dict JSON payloads.
  - [x] Keep fail-fast message for Phase1 list payload (no silent conversion).

- [x] T2: Remove compare-loader cross dependency.
  - [x] In `rdc_loader.load_capture_file`, replace `from ..compare_rdc import load_json_data` call path.
  - [x] Implement local list rejection with same message semantics.

- [x] T3: Align compare entrypoint behavior.
  - [x] In `compare_rdc.py`, switch `main()` loading path to unified loader (`load_capture_file`) so schema v1 conversion path matches `__main__.py` compare.
  - [x] Ensure `.json/.xml/.rdc` handling errors are surfaced as actionable messages.

- [x] T4: Strengthen compare contract tests.
  - [x] Add non-dict JSON rejection test (`{"a":1}` valid dict, but scalar/string/number invalid).
  - [x] Add schema-v1 JSON test proving no “empty list fallback” regression.
  - [x] Assert JSON output includes required top-level groups and key nested fields.

- [x] T5: Convert bridge tests to production-backed assertions.
  - [x] Replace local copied `_convert_schema_v1_to_capture_data` in `test_schema_bridge.py` with import from `rdc_loader`.
  - [x] Keep existing cases but assert production key names used by DiffEngine (`resourceId`, `memorySize`, `size`).

- [x] T6: Run and record verification.
  - [x] Run `py_compile` on modified files.
  - [x] Run targeted pytest files and capture pass counts.

- [x] T7: Update plan checklist + progress log and stop for feedback.

## Pseudo-code and concrete snippets

### 1) compare input guard

```python
# compare_rdc.py::load_json_data
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

if isinstance(data, list):
    raise ValueError("Phase1 list format is deprecated; use Canonical Schema dict input")

if not isinstance(data, dict):
    raise ValueError(f"Unsupported JSON payload type: {type(data).__name__}; expected object")

return data
```

### 2) loader-side rejection (remove cycle)

```python
# rdc_loader.py::load_capture_file for .json
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

if isinstance(data, list):
    raise ValueError("Phase1 list format is deprecated; use Canonical Schema dict input")

if data.get('schema_version') == '1.0':
    return _convert_schema_v1_to_capture_data(data)

return data
```

### 3) unify compare_rdc main loading path

```python
# compare_rdc.py::main
from parsers.rdc_loader import load_capture_file

baseline_data = load_capture_file(args.baseline, verbose=not args.quiet)
target_data = load_capture_file(args.target, verbose=not args.quiet)
```

### 4) production-backed schema bridge tests

```python
# test_schema_bridge.py
from parsers.rdc_loader import _convert_schema_v1_to_capture_data

result = _convert_schema_v1_to_capture_data(schema_v1_data)
assert result['textures'][0]['resourceId'] == 'tex-001'
assert result['textures'][0]['memorySize'] == 4194304
assert result['buffers'][0]['size'] == expected_size
```

## Impact Analysis

### Behavior changes
- Standalone `compare_rdc.py` gets consistent loader behavior with `rdc_analyzer compare`.
- Legacy JSON list input becomes explicit fail-fast at all compare entrances.
- Schema v1 inputs become reliably bridged before DiffEngine consumption.

### Risks
- Existing ad-hoc scripts still using old list payload may fail.
- Replacing load path in `compare_rdc.py` may alter legacy test fixtures if they rely on old lax behavior.

### Mitigations
- Keep error text explicit with migration hint.
- Add targeted tests before/after each behavior change.
- Restrict this batch to contract and bridge only; no diff algorithm edits.

## Risks / Blockers

- If any downstream internal automation still writes list-format JSON, migration is required.
- If loader import path changes create circular import in edge path, fallback is to keep compare standalone path JSON-only but still enforce dict schema + bridge helper in compare module.

## Decisions

- Decision A (recommended): Make contract strict now (fail-fast for list/non-dict).
- Decision B: Keep output structure stable (`metadata/summary/regressions/resource_changes`) to avoid breaking existing consumers.
- Decision C: Test production bridge implementation directly (no duplicate conversion logic in tests).

## Verification / Acceptance (Definition of Done)

- Contract:
  - `load_json_data()` rejects list and non-dict JSON with clear errors.
- Bridge:
  - schema v1 JSON input reaches DiffEngine with expected normalized keys.
- Consistency:
  - standalone `compare_rdc.py` and package CLI compare follow same load semantics.
- Tests:
  - targeted test files all pass.

Commands (to run in /do):
- `py -3 -m py_compile scripts/rdc_analyzer/compare_rdc.py scripts/rdc_analyzer/parsers/rdc_loader.py`
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_compare_rdc.py -q`
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_rdc_loader.py -q`
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_schema_bridge.py -q`

## Approval Required

Stop here after `/plan`. Wait for user approval before `/do` implementation.

## Progress Log
- 2026-02-16: Completed T1–T6 and verification.
  - py_compile: ok
  - pytest test_compare_rdc.py: 25 passed
  - pytest test_rdc_loader.py: 16 passed, 2 skipped
  - pytest test_schema_bridge.py: 15 passed
- Ready for feedback.
