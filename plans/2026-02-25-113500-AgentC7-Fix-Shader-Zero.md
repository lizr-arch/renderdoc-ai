# Fix shader=0 in WebUI bundle

## Scope / Assumptions
- Fix shader list & usage mapping when `analysis.json` includes `shaders` and `pipeline_samples` but `draw_calls[*].pipeline_state` is empty.
- No UI layout changes; only bridge/normalization logic + tests.
- Use existing `analysis_to_bundle` as single source for report data.

## File List (with line refs)
- `scripts/rdc_analyzer/bridge/analysis_to_bundle.py:20` (shader extraction helpers)  
- `scripts/rdc_analyzer/bridge/analysis_to_bundle.py:67` (analysis_to_bundle main flow)  
- `scripts/rdc_analyzer/tests/test_analysis_to_bundle.py:1` (add test case)

## Pseudo-code
```
def _parse_resource_id(value):
    if value is None: return None
    if isinstance(value, int): return value
    s = str(value)
    if s.startswith("ResourceId::"):
        s = s[len("ResourceId::"):]
    if s in ("Null()", "0", "0()"): return None or 0
    try: return int(s)
    except ValueError: return value

def _normalize_shader_ids(shader):
    rid = shader.get("id") or shader.get("resource_id") or shader.get("resourceId")
    rid = _parse_resource_id(rid)
    if rid is None: return None
    shader.setdefault("resource_id", rid)
    shader.setdefault("id", rid)
    return shader

def analysis_to_bundle(analysis):
    shaders = []
    shader_usage = {}
    # 1) existing draw_calls pipeline_state path (keep)
    # 2) merge analysis["shaders"] -> normalize ids -> add to shaders
    # 3) use pipeline_samples.samples to fill shader_usage (vertex/pixel/compute)
```

## Impact Analysis
- Shader list now populated even when `draw_calls` lack `pipeline_state`.
- Shader usage map built from `pipeline_samples` to support “used by” and jump targets.
- No changes to report generator/templates; relies on normalized `id/resource_id`.

## Task Checklist (2–5 min each)
- [x] TDD-1: Add test `test_analysis_to_bundle_shaders_from_list_and_samples` in `scripts/rdc_analyzer/tests/test_analysis_to_bundle.py` that:
  - Provides `analysis["shaders"]` with `resourceId="ResourceId::123"`.
  - Provides `pipeline_samples.samples` with `event_id=7`, `vertex_shader_id=123`.
  - Asserts `bundle.shaders[0]["id"] == 123` and `bundle.shader_usage["123"] == [7]`.
- [x] TDD-2: Run `py -3 -m pytest scripts/rdc_analyzer/tests/test_analysis_to_bundle.py -v` (expect fail before fix).
- [x] Step-1: Implement `_parse_resource_id` + `_normalize_shader_ids` helpers in `analysis_to_bundle.py`.
  - Code snippet:
```
def _parse_resource_id(value):
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value)
    if text.startswith("ResourceId::"):
        text = text[len("ResourceId::"):]
    if text in ("Null()", "0", "0()"):
        return None
    try:
        return int(text)
    except ValueError:
        return value
```
- [x] Step-2: In `analysis_to_bundle`, merge `analysis.get("shaders")`:
  - Normalize ids, append to `shaders`, and keep existing `seen_shaders` de-dupe.
- [x] Step-3: In `analysis_to_bundle`, add usage collection from `pipeline_samples`:
  - For each sample: `event_id`, `vertex_shader_id`, `pixel_shader_id`, `compute_shader_id`.
  - Normalize shader id, then `shader_usage[str(id)].append(event_id)`.
- [x] Step-4: Re-run tests; expect pass.

## Risks / Blockers
- `pipeline_samples` might be `None` or dict without `samples`; must guard.
- `ResourceId::Null()` or malformed ids; parsing should be defensive to avoid exceptions.

## Decisions
- Normalize shader ids in bridge layer instead of changing report generator/templates.
- Use pipeline_samples as authoritative for usage mapping when draw_calls lack pipeline_state.

## Verification / Acceptance
- `test_analysis_to_bundle_shaders_from_list_and_samples` passes.
- Shader list in WebUI is non-empty for the provided capture; shader count > 0.

## Next Steps
- Wait for /do approval.
