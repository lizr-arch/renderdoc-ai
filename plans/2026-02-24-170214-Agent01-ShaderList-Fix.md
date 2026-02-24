# Shader List Export Implementation Plan
#
> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or subagent-driven-development) to implement this plan task-by-task.
#
**Version:** 2026-02-24
**Owner:** Agent01
**Last Updated:** 2026-02-24
**Plan File:** `plans/2026-02-24-170214-Agent01-ShaderList-Fix.md`
#
**Goal:** Ensure `analysis.json` contains a non-empty `shaders` array for non-Mali captures by extracting shader info from pipeline samples.
#
**Architecture:** Add a shader-list builder in `AnalysisPipeline` that prefers Mali data, otherwise uses `pipeline_sampler` + `shader_extractor` over sampled events. Keep output schema stable and avoid GUI dependency.
#
**Tech Stack:** Python (rdc_analyzer), RenderDoc ReplayController API, pytest, WebUI (`analysis.json` viewer).
#
**Success Criteria (measurable):**
- `analysis.json` contains `shaders` array with length > 0 for capture with shaders.
- WebUI shows non-zero shader count for the sample capture.
- New unit test passes and guards regression.
#
**Acceptance Criteria:**
- For `D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc`, WebUI shows shader count > 0.
- No crash when Mali analysis is disabled.
#
**Verification Commands:**
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_shader_list_export.py -v` (Expected: PASS)
- `cmd /c "py -3 -c \"\"import json, pathlib; p=pathlib.Path(r'D:\backup\rdc_analyzer\EndfieldTBeta2_2025.12.18_14.36_frame42231\analysis.json'); data=json.load(open(p, 'r', encoding='utf-8')); print(len(data.get('shaders', [])))\"\""` (Expected: > 0 after running analysis)
#
**Evidence:**
- `D:\backup\rdc_analyzer\EndfieldTBeta2_2025.12.18_14.36_frame42231\analysis.json`
- `C:\Users\lizhirui01\AppData\Roaming\qrenderdoc\extensions\rdc_analyzer_ext\rdc_analyzer_latest.log`
#
**Estimation:**
- Effort: 0.5 day
- Story Points: 3
- Original Estimate: 4 hours
#
**Risk Register (impact/likelihood/mitigation):**
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Shader extraction too slow on large captures | Medium | Medium | Use pipeline samples only (already capped by sample_count) |
| RenderDoc module missing in unit tests | Low | High | Allow dependency injection/mocking for extractor/controller |
| Shader list fields inconsistent with UI | Low | Medium | Keep minimal fields (resourceId/name/type/stage) |
#
## Game Dev: Memory & Resource Budget (Leak Checks)
- Ensure shader extraction does not leak references; reuse one extractor and avoid caching large shader texts unless requested.
#
## Game Dev: Asset Pipeline
- Treat shader list as lightweight metadata only (no heavy source payload in JSON by default).
#
## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: run analysis on sample capture; confirm shader list populated.
- Dump/Core: N/A for Python path; if native crash, capture minidump.
- Symbols: PDB for `qrenderdoc.exe` if native crash appears.
- Build identity: record git commit hash and build config if needed.
#
## Scope
- In: Populate `analysis.json` `shaders` array for non-Mali captures using pipeline samples.
- Out: Full shader source export, HLSL conversion, or GUI rendering changes.
#
## Assumptions
- Pipeline sampling is enabled (default true).
- ReplayController is available when analysis runs via RenderDoc environment.
#
## Repo / File List
- Modify: `scripts/rdc_analyzer/main.py`
- Add: `scripts/rdc_analyzer/tests/test_shader_list_export.py`
- (Optional) Modify: `scripts/rdc_analyzer/docs/ARCHITECTURE_V1.md` if we document the new step.
#
## Approach (Pseudo-code)
```python
def _build_shader_list(self):
    shaders_list = []
    if self._mali_report and self._mali_report.get("shaders"):
        for shader in self._mali_report["shaders"]:
            shaders_list.append({
                "resourceId": str(shader.get("resourceId") or shader.get("hash") or shader.get("name") or ""),
                "name": shader.get("name", ""),
                "type": shader.get("type", ""),
            })
        return shaders_list

    if not self._controller or not self._pipeline_sampling_result:
        return shaders_list

    try:
        import renderdoc as rd
    except Exception:
        rd = None

    from .extractors.shader_extractor import create_shader_extractor
    extractor = create_shader_extractor(self._controller, rd)
    shader_map = {}
    for sample in self._pipeline_sampling_result.samples:
        try:
            self._controller.SetFrameEvent(sample.event_id, False)
            pipe_state = self._controller.GetPipelineState()
            result = extractor.extract_bound_shaders(pipe_state)
            for shader in result.shaders:
                shader_map[shader.resource_id] = shader
        except Exception as exc:
            logger.debug(f"Shader extract failed for event {sample.event_id}: {exc}")
    for shader in shader_map.values():
        shaders_list.append({
            "resourceId": str(shader.resource_id),
            "name": shader.name or f"Shader_{shader.resource_id}",
            "type": shader.type or shader.stage or "",
            "stage": shader.stage,
            "encoding": shader.encoding,
        })
    return shaders_list
```
#
## Impact Analysis
- Behavior: `analysis.json` gains shader metadata for non-Mali runs.
- Performance: bounded by pipeline sample count.
- Risk: some captures may not expose shader reflection at sampled events; list might be partial.
#
## Action Items (TDD, 2-5 min steps)
### [x] Task 1: Add failing unit test for shader list population
**Files:**
- Create: `scripts/rdc_analyzer/tests/test_shader_list_export.py`
#
**Step 1: Write the failing test**
```python
import types
from rdc_analyzer.main import AnalysisPipeline, AnalysisOptions
from rdc_analyzer.extractors.pipeline_sampler import PipelineSample, SamplingResult
from rdc_analyzer.core.types import ShaderInfo

class FakeController:
    def __init__(self):
        self.events = []
    def SetFrameEvent(self, event_id, _):
        self.events.append(event_id)
    def GetPipelineState(self):
        return object()

class FakeExtractor:
    def __init__(self, shaders):
        self._shaders = shaders
    def extract_bound_shaders(self, _):
        result = types.SimpleNamespace()
        result.shaders = self._shaders
        result.unique_shader_count = len(self._shaders)
        result.by_stage = {}
        result.warnings = []
        return result

def test_build_shader_list_from_samples_populates_entries(monkeypatch):
    pipeline = AnalysisPipeline("dummy.rdc", AnalysisOptions())
    pipeline._controller = FakeController()
    pipeline._pipeline_sampling_result = SamplingResult(
        samples=[PipelineSample(event_id=10, name="draw", draw_type=None, snapshot=None)]
    )
    shaders = [
        ShaderInfo(resource_id="0x1", name="VS_main", type="VS", stage="Vertex", encoding="DXIL"),
        ShaderInfo(resource_id="0x2", name="PS_main", type="PS", stage="Pixel", encoding="DXIL"),
    ]
    def fake_factory(controller, rd_module):
        return FakeExtractor(shaders)
    monkeypatch.setattr(pipeline, "_create_shader_extractor", fake_factory)

    shader_list = pipeline._build_shader_list()
    assert len(shader_list) == 2
    assert shader_list[0]["resourceId"] == "0x1"
```
#
**Step 2: Run test to verify it fails**
- Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_shader_list_export.py -v`
- Expected: FAIL (method `_build_shader_list` or `_create_shader_extractor` missing)
#
### [x] Task 2: Implement shader list builder in AnalysisPipeline
**Files:**
- Modify: `scripts/rdc_analyzer/main.py`
#
**Step 1: Add factory hook (for tests)**
```python
def _create_shader_extractor(self, controller, rd_module):
    from .extractors.shader_extractor import create_shader_extractor
    return create_shader_extractor(controller, rd_module)
```
#
**Step 2: Add `_build_shader_list` and wire into `_export_reports`**
```python
shaders_list = self._build_shader_list()
```
(Replace the current hardcoded Mali-only block)
#
**Step 3: Run tests**
- Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_shader_list_export.py -v`
- Expected: PASS
#
### [x] Task 3: Manual verification (user-run)
**Step 1: Run analysis**
- Use RenderDoc UI extension to run analysis for the sample capture.
#
**Step 2: Validate output**
- Check `analysis.json` with the verification command in this plan.
- Open WebUI and confirm shader count > 0.
#
### [ ] Task 4: Commit (only after user approval)
**Step 1: Ask for approval**
- Confirm with user before committing.
#
**Step 2: Commit**
```bash
git add scripts/rdc_analyzer/main.py scripts/rdc_analyzer/tests/test_shader_list_export.py
git commit -m "fix(rdc-analyzer): populate shader list from pipeline samples

- extract shader metadata via shader_extractor for sampled events
- add unit test for shader list population"
```
#
## Risks & Blockers
- If `draw_type` is required in `PipelineSample` construction, adjust the test to use a valid enum or mock.
#
## Verification / DoD
- Unit test passes.
- Sample capture shows shader count > 0 in WebUI.
#
## Open Questions
- Do we need full shader source (ASM/HLSL) in JSON, or keep metadata only?
#
## Next Steps
- Proceed to `/do` if this plan is approved.

## /do Log
- 2026-02-24: Added unit test, observed RED failure, implemented shader list builder, GREEN pass.
- Tests: `py -3 -m pytest scripts/rdc_analyzer/tests/test_shader_list_export.py -v` (PASS)
- 2026-02-24: Verified via qrenderdoc `--python` script (renderdoc_shell_analyze) -> `analysis.json` shaders=34.
