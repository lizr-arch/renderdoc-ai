# Analysis Report Schema + Extraction Map Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-02-24
**Owner:** Agent01
**Last Updated:** 2026-02-24

**Goal:** Define a single-frame analysis report spec (field contract + page structure + extraction paths) that covers shaders, textures/RT, render passes, pipeline state, and uniforms for Vulkan/D3D11/D3D12, with P1 Mali metrics and P2 placeholders.

**Architecture:** Use `analysis.json` as SSOT. Document a canonical schema with P0/P1/P2 tiers. Map each field to current extraction modules (rdc_analyzer pipeline + RenderDoc replay API) and record gaps. Report pages derive from the schema and are API-agnostic at the view layer.

**Tech Stack:** Python (rdc_analyzer), existing dataclasses in `scripts/rdc_analyzer/core/types.py`, Markdown docs, optional JSON schema for validation.

**Success Criteria (measurable):**
- A canonical field contract is written with P0/P1/P2 tiers and API coverage flags.
- Each report page lists required fields and fallback behavior.
- Each field has a source path (module/function) or a documented gap.

**Acceptance Criteria:**
- Stakeholders can answer "what data is shown, from where, and for which API" for every report section.
- The spec explicitly lists which fields depend on Mali Offline Compiler (P1) and which are deferred to P2.
- The spec is usable to implement WebUI without re-reading pipeline code.

**Verification Commands:**
- `py -3 -m pytest scripts/rdc_analyzer/tests -v --tb=short` (Expected: PASS)
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_analysis_schema_contract.py -v` (Expected: PASS)

**Evidence:**
- New spec doc path and commit hash.
- Schema contract table and extraction map in the doc.
- Test output confirming schema contract checks.

**Estimation:**
- Effort: 1.5-2 days
- Story Points: 3
- Original Estimate: 2 days

**Risk Register (impact/likelihood/mitigation):**
- Schema drifts from actual pipeline output | Medium | Medium | Add contract test and keep mapping table versioned.
- API coverage uneven across Vulkan/D3D11/D3D12 | Medium | High | Mark per-field API coverage and add TODO gaps.
- Mali metrics unavailable on some runs | Low | High | P1 optional section with graceful fallback.

## Game Dev: Memory & Resource Budget (Leak Checks)
- If schema validation adds caching or precomputation, verify no repeated open creates unbounded growth by running the same capture N times and tracking output size.

## Game Dev: Asset Pipeline
- If schema includes thumbnails or extracted assets, define stable output paths and a cache invalidation rule.

## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: open capture, run analyzer, generate analysis.json and spec check.
- Dump/Core: (minidump | core dump) TBD
- Symbols: (PDB | dSYM | ELF | DWARF) TBD
- Build identity: (build id | commit hash | git commit) TBD

## Scope
- In scope: single-frame report schema + page structure + extraction map; Vulkan/D3D11/D3D12; P1 Mali metrics.
- Out of scope: multi-frame diff (future); non-Mali hardware profilers (P2); GUI/WebUI implementation.

## Assumptions
- `analysis.json` remains the SSOT for report generation.
- Existing dataclasses (TextureInfo/ShaderInfo/PassInfo/DrawCallInfo) are still the best place to anchor field names.

## Repo / File List (expected edits)
- Create: `docs/analysis/codex_rdc_analyzer/analysis_report_schema_v1.md`
- Create: `scripts/rdc_analyzer/schema/analysis_schema_v1.json` (optional machine-checkable schema)
- Create: `scripts/rdc_analyzer/tests/test_analysis_schema_contract.py`
- Modify: `scripts/rdc_analyzer/docs/INDEX.md` (add spec link)
- Modify: `scripts/rdc_analyzer/docs/WEBUI_AND_UI_EXTENSION.md` (reference schema doc)

## Approach (Pseudo-code)
```python
# scripts/rdc_analyzer/tests/test_analysis_schema_contract.py

def test_analysis_schema_contract_minimal():
    # Load canonical schema or spec-derived required keys
    required = {"summary", "events", "textures", "shaders", "passes", "pipeline_state", "uniforms"}
    data = load_sample_analysis_json()
    missing = required - set(data.keys())
    assert not missing
```

```json
// scripts/rdc_analyzer/schema/analysis_schema_v1.json (sketch)
{
  "schema_version": "1.0",
  "summary": {"frame": "...", "api": "...", "draws": 0},
  "events": [{"eid": 0, "name": "...", "pass_id": "..."}],
  "textures": [{"id": "...", "format": "...", "size": "...", "usage": "..."}],
  "shaders": [{"id": "...", "stage": "VS", "entry": "...", "size": 0}],
  "passes": [{"id": "...", "rt": ["..."], "ds": "...", "draws": 0}],
  "pipeline_state": [{"eid": 0, "raster": {}, "blend": {}, "depth": {}}],
  "uniforms": [{"eid": 0, "cbuffers": [], "push_constants": []}]
}
```

## Impact Analysis
- Adds a formal contract that may reveal current data gaps.
- Enables WebUI/report work to proceed without re-reading pipeline code.
- Requires periodic sync with pipeline output as fields evolve.

## Action Items (Tasks)
- [x] Task 1: Inventory current data model and extraction entry points
- [x] Task 2: Write schema spec doc (field contract + P0/P1/P2 tiers)
- [x] Task 3: Add extraction map (field -> module/function -> API coverage)
- [x] Task 4: Define report page structure (P0/P1/P2 sections)
- [x] Task 5: Wire docs index references

### Task 1: Inventory current data model and extraction entry points
**Files:**
- Read: `scripts/rdc_analyzer/core/types.py:13` (TextureInfo)
- Read: `scripts/rdc_analyzer/core/types.py:93` (ShaderInfo)
- Read: `scripts/rdc_analyzer/core/types.py:148` (PassInfo)
- Read: `scripts/rdc_analyzer/analyzers/resource.py:79`
- Read: `scripts/rdc_analyzer/analyzers/pass_analyzer.py:65`

**Step 1: Write the failing test**
```python
def test_analysis_schema_contract_minimal():
    # placeholder: required keys expected to fail until schema doc exists
    required = {"summary", "events", "textures", "shaders", "passes"}
    data = {}
    missing = required - set(data.keys())
    assert not missing
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_analysis_schema_contract.py -v`
Expected: FAIL with "missing" keys

**Step 3: Write minimal implementation**
```python
# update test to load a real sample analysis.json once schema doc is created
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_analysis_schema_contract.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/tests/test_analysis_schema_contract.py
git commit -m "test(rdc-analyzer): add analysis schema contract checks"
```

### Task 2: Write schema spec doc (field contract + P0/P1/P2 tiers)
**Files:**
- Create: `docs/analysis/codex_rdc_analyzer/analysis_report_schema_v1.md`

**Step 1: Write the failing test**
```python
def test_schema_doc_exists():
    import pathlib
    assert pathlib.Path("docs/analysis/codex_rdc_analyzer/analysis_report_schema_v1.md").exists()
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_analysis_schema_contract.py::test_schema_doc_exists -v`
Expected: FAIL

**Step 3: Write minimal implementation**
```markdown
# Analysis Report Schema v1
## P0: summary/events/textures/shaders/passes/pipeline_state/uniforms
## P1: Mali metrics
## P2: External profilers
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_analysis_schema_contract.py::test_schema_doc_exists -v`
Expected: PASS

**Step 5: Commit**
```bash
git add docs/analysis/codex_rdc_analyzer/analysis_report_schema_v1.md
git commit -m "docs(rdc-analyzer): add analysis report schema v1"
```

### Task 3: Add extraction map (field -> module/function -> API coverage)
**Files:**
- Modify: `docs/analysis/codex_rdc_analyzer/analysis_report_schema_v1.md`

**Step 1: Write the failing test**
```python
def test_schema_doc_has_extraction_map():
    import pathlib
    text = pathlib.Path("docs/analysis/codex_rdc_analyzer/analysis_report_schema_v1.md").read_text(encoding="utf-8")
    assert "Extraction Map" in text
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_analysis_schema_contract.py::test_schema_doc_has_extraction_map -v`
Expected: FAIL

**Step 3: Write minimal implementation**
```markdown
## Extraction Map
| Field | Source | Vulkan | D3D11 | D3D12 | Notes |
| --- | --- | --- | --- | --- | --- |
| textures[] | analyzers/resource.py:_parse_texture_api | Y | Y | Y | uses replay controller |
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_analysis_schema_contract.py::test_schema_doc_has_extraction_map -v`
Expected: PASS

**Step 5: Commit**
```bash
git add docs/analysis/codex_rdc_analyzer/analysis_report_schema_v1.md
git commit -m "docs(rdc-analyzer): add extraction map to schema"
```

### Task 4: Define report page structure (P0/P1/P2 sections)
**Files:**
- Modify: `docs/analysis/codex_rdc_analyzer/analysis_report_schema_v1.md`

**Step 1: Write the failing test**
```python
def test_schema_doc_has_page_structure():
    import pathlib
    text = pathlib.Path("docs/analysis/codex_rdc_analyzer/analysis_report_schema_v1.md").read_text(encoding="utf-8")
    assert "Page Structure" in text
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_analysis_schema_contract.py::test_schema_doc_has_page_structure -v`
Expected: FAIL

**Step 3: Write minimal implementation**
```markdown
## Page Structure
- Overview (summary + top issues)
- Events/Passes (timeline + filters)
- Shaders (list + usage + Mali metrics)
- Textures/RT (format/size/usage)
- Pipeline State (raster/blend/depth)
- Uniforms (cbuffers/push constants)
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_analysis_schema_contract.py::test_schema_doc_has_page_structure -v`
Expected: PASS

**Step 5: Commit**
```bash
git add docs/analysis/codex_rdc_analyzer/analysis_report_schema_v1.md
git commit -m "docs(rdc-analyzer): add report page structure"
```

### Task 5: Wire docs index references
**Files:**
- Modify: `scripts/rdc_analyzer/docs/INDEX.md`
- Modify: `scripts/rdc_analyzer/docs/WEBUI_AND_UI_EXTENSION.md`

**Step 1: Write the failing test**
```python
def test_docs_index_links_schema():
    import pathlib
    text = pathlib.Path("scripts/rdc_analyzer/docs/INDEX.md").read_text(encoding="utf-8")
    assert "analysis_report_schema_v1.md" in text
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_analysis_schema_contract.py::test_docs_index_links_schema -v`
Expected: FAIL

**Step 3: Write minimal implementation**
```markdown
| [analysis_report_schema_v1.md](analysis_report_schema_v1.md) | Analysis report schema v1 | schema, analysis.json |
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_analysis_schema_contract.py::test_docs_index_links_schema -v`
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/docs/INDEX.md scripts/rdc_analyzer/docs/WEBUI_AND_UI_EXTENSION.md
git commit -m "docs(rdc-analyzer): link analysis report schema"
```

## Verification / DoD
- Schema doc exists and includes field contract, P0/P1/P2 tiers, extraction map, and page structure.
- Contract tests pass.
- Docs index references the schema.

## Open Questions
- Is there a canonical sample `analysis.json` to validate against?
- Should render pass be Vulkan-only or unified with D3D11/D3D12 "pass-like" grouping?

## Next Steps
- After approval, execute tasks in order and keep this plan updated.
