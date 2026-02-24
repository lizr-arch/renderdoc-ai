# WebUI Report Unification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-02-24
**Owner:** Agent01
**Last Updated:** 2026-02-24

**Goal:** Make WebUI serve the same report pages (index/events/textures/shaders) as the offline bundle and enable one-click GUI jump to an event (EID).

**Architecture:** Generate or derive the report bundle from canonical `analysis.json`, write the standard report pages to the WebUI output directory, and serve them via the existing WebUI server. Add a local HTTP endpoint (`/api/jump`) that calls `CaptureContext::SetEventID` through the UI extension so WebUI clicks can jump to GUI.

**Tech Stack:** Python (rdc_analyzer), Qt/PySide2 in RenderDoc UI extension, SimpleHTTPRequestHandler, HTML/JS/CSS templates.

**Success Criteria (measurable):**
- WebUI opens to `index.html` identical to offline report (same templates + `common.css` + `navigation.js`).
- WebUI events page can trigger GUI jump to the corresponding EID.
- Offline bundle generation still works unchanged.

**Acceptance Criteria:**
- Tools -> RDC Analyzer -> Open WebUI shows index/events/textures/shaders pages identical to offline report.
- Clicking “Jump to RenderDoc” on an event changes RenderDoc’s selected event.
- If report generation fails, WebUI falls back to the current minimal viewer.

**Verification Commands:**
- `py -3 -m pytest scripts/rdc_analyzer/tests -v --tb=short` (Expected: PASS)

**Evidence:**
- WebUI URL loads `index.html` with `common.css` and `navigation.js` in DevTools.
- Console/log shows `/api/jump?eid=...` success and GUI event selection changes.
- Output folder contains `index.html`, `events.html`, `textures.html`, `shaders.html`, `common.css`, `navigation.js`.

**Estimation:**
- Effort: 2-3 days
- Story Points: 5
- Original Estimate: 3 days

**Risk Register (impact/likelihood/mitigation):**
- Report generation time increases on WebUI open | Medium | Medium | Cache bundle output and reuse when analysis.json unchanged.
- analysis.json lacks data needed for some report sections | Medium | Medium | Add graceful fallbacks/placeholders.
- QtWebEngine absent on some setups | Low | High | Keep external browser fallback intact.

---

## Scope
- In scope: WebUI serves report bundle pages; add `/api/jump` endpoint; unify WebUI styling with offline templates; analysis.json as SSOT.
- Out of scope: texture/shader deep-link selection in GUI; multi-capture diff UI; large refactor of analyzer pipeline.

## Assumptions
- `analysis.json` is the canonical analysis output for a single capture.
- Report bundle can be generated from `analysis.json` via a bridge without needing extra replay data.
- WebUI server runs in the RenderDoc UI extension process (so it can call GUI APIs).

## Repo / File List (expected edits)
- Modify: `scripts/rdc_analyzer/ui_extension/analyzer_extension.py:150` (call report generation before serving WebUI)
- Modify: `scripts/rdc_analyzer/webui/server.py:41` (add `/api/jump` handler + serve report root)
- Modify: `scripts/rdc_analyzer/templates/events.html:7` (add “Jump to RenderDoc” UI hooks)
- Modify: `scripts/rdc_analyzer/templates/navigation.js:2` (add `jumpToRenderDoc(eid)` helper)
- Modify: `scripts/rdc_analyzer/report_bundle_generator.py:1417` (optional helper for report generation from analysis data)
- Create: `scripts/rdc_analyzer/bridge/analysis_to_bundle.py` (analysis.json -> bundle model)
- Create: `scripts/rdc_analyzer/report_from_analysis.py` (generate bundle output from analysis.json)
- Create: `scripts/rdc_analyzer/tests/test_analysis_to_bundle.py`
- Update docs: `scripts/rdc_analyzer/docs/WEBUI_AND_UI_EXTENSION.md:16`

## Approach (Pseudo-code)
```python
# bridge/analysis_to_bundle.py

def analysis_to_bundle(analysis: dict) -> BundleData:
    # Extract: stats, issues, events, textures, shaders
    # Provide defaults if missing to keep templates stable.
    return BundleData(events=..., textures=..., shaders=..., stats=...)

# report_from_analysis.py

def generate_report_from_analysis(analysis_path: Path, output_dir: Path, capture_name: str):
    data = json.load(open(analysis_path, 'r', encoding='utf-8'))
    bundle = analysis_to_bundle(data)
    gen = ReportBundleGenerator(str(output_dir), capture_name)
    gen.set_events(bundle.events)
    gen.set_textures(bundle.textures)
    gen.set_shaders(bundle.shaders, mali_data=None, usage_map=bundle.shader_usage)
    gen.stats.update(bundle.stats)
    gen.generate_all()

# webui/server.py
class WebUIRequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/api/jump'):
            eid = parse_eid(self.path)
            self.server.jump_handler(eid)  # provided by UI extension
            return json_ok()
        return super().do_GET()

# ui_extension/analyzer_extension.py
analysis_file = run_analysis(...)
try:
    generate_report_from_analysis(analysis_file, output_dir, capture_name)
    url = ensure_report_server(output_dir, analysis_file)
except Exception:
    url = ensure_webui_server(output_dir, analysis_file)
```

## Impact Analysis
- Adds report generation step to WebUI open; increases latency but yields unified UI.
- Adds local HTTP endpoint for GUI jump; ensure local-only (127.0.0.1).
- Maintains fallback to minimal WebUI when report generation fails.

## Build/Test/Lint Quick Guide (commands only, do not execute)
- Unit tests: `py -3 -m pytest scripts/rdc_analyzer/tests -v --tb=short`
- Manual WebUI: open capture -> Tools -> RDC Analyzer -> Open WebUI
- Manual jump: click “Jump to RenderDoc” on an event in WebUI

## Decisions
- SSOT = `analysis.json` (canonical output).
- WebUI serves report bundle pages identical to offline report.
- Jump-to-GUI implemented via local HTTP endpoint + `SetEventID`.

## Verification / Acceptance (Definition of Done)
- WebUI shows `index/events/textures/shaders` identical to offline report.
- `common.css` and `navigation.js` loaded in WebUI.
- `/api/jump?eid=...` triggers GUI event selection.
- All tests pass.

## Next Steps
- If event jump is stable, consider texture/shader jump API.
- Optionally cache report output to reduce open latency.

## Risks / Blockers
- Missing fields in `analysis.json` for report templates.
- Jump endpoint needs GUI thread safety (may require UI thread invoke).

## Game Dev: Memory & Resource Budget (Leak Checks)
- Check report generation memory growth by opening same capture 10x; track output size + RSS.

## Game Dev: Asset Pipeline
- Thumbnails/shader sources may need separate assets; ensure placeholders when missing.

## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: Open capture -> Open WebUI -> click jump link.
- Dump/Core: (minidump | core dump) TBD
- Symbols: (PDB | dSYM | ELF | DWARF) TBD
- Build identity: (build id | commit hash | git commit) TBD

## Task Checklist
- [x] Task 1: Add analysis.json -> bundle bridge + unit test
- [x] Task 2: Add report generation helper from analysis.json
- [x] Task 3: Update WebUI open flow to generate report + serve report root
- [x] Task 4: Add `/api/jump` endpoint and JS hook
- [x] Task 5: Update docs + manual verification notes

### Task 1: analysis.json -> bundle bridge
**Files:**
- Create: `scripts/rdc_analyzer/bridge/analysis_to_bundle.py`
- Create: `scripts/rdc_analyzer/tests/test_analysis_to_bundle.py`

**Step 1: Write the failing test**
```python
# scripts/rdc_analyzer/tests/test_analysis_to_bundle.py
from rdc_analyzer.bridge.analysis_to_bundle import analysis_to_bundle

def test_analysis_to_bundle_minimal():
    analysis = {"summary": {"draw_calls": 1}, "events": [{"eid": 7, "name": "Draw"}]}
    bundle = analysis_to_bundle(analysis)
    assert len(bundle.events) == 1
    assert bundle.stats["draw_calls"] == 1
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_analysis_to_bundle.py -v`
Expected: FAIL (module/function not found)

**Step 3: Write minimal implementation**
```python
# scripts/rdc_analyzer/bridge/analysis_to_bundle.py
from dataclasses import dataclass

@dataclass
class BundleData:
    events: list
    textures: list
    shaders: list
    stats: dict
    shader_usage: dict

def analysis_to_bundle(analysis: dict) -> BundleData:
    events = analysis.get("events", [])
    textures = analysis.get("textures", [])
    shaders = analysis.get("shaders", [])
    stats = analysis.get("summary", {})
    return BundleData(events, textures, shaders, stats, {})
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_analysis_to_bundle.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/bridge/analysis_to_bundle.py scripts/rdc_analyzer/tests/test_analysis_to_bundle.py
git commit -m "feat(rdc-analyzer): add analysis-to-bundle bridge"
```

### Task 2: Report generation helper from analysis.json
**Files:**
- Create: `scripts/rdc_analyzer/report_from_analysis.py`

**Step 1: Write the failing test**
```python
# scripts/rdc_analyzer/tests/test_report_from_analysis.py
from rdc_analyzer.report_from_analysis import generate_report_from_analysis

def test_generate_report_from_analysis(tmp_path):
    analysis = tmp_path / "analysis.json"
    analysis.write_text("{}", encoding="utf-8")
    generate_report_from_analysis(analysis, tmp_path, "capture")
    assert (tmp_path / "index.html").exists()
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_report_from_analysis.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**
```python
# scripts/rdc_analyzer/report_from_analysis.py
import json
from pathlib import Path
from rdc_analyzer.bridge.analysis_to_bundle import analysis_to_bundle
from rdc_analyzer.report_bundle_generator import ReportBundleGenerator

def generate_report_from_analysis(analysis_path: Path, output_dir: Path, capture_name: str):
    data = json.loads(Path(analysis_path).read_text(encoding="utf-8"))
    bundle = analysis_to_bundle(data)
    gen = ReportBundleGenerator(str(output_dir), capture_name)
    gen.set_events(bundle.events)
    gen.set_textures(bundle.textures)
    gen.set_shaders(bundle.shaders, mali_data=None, usage_map=bundle.shader_usage)
    gen.stats.update(bundle.stats)
    gen.generate_all()
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_report_from_analysis.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/report_from_analysis.py scripts/rdc_analyzer/tests/test_report_from_analysis.py
git commit -m "feat(rdc-analyzer): generate report from analysis.json"
```

### Task 3: WebUI uses report bundle output
**Files:**
- Modify: `scripts/rdc_analyzer/ui_extension/analyzer_extension.py:150`
- Modify: `scripts/rdc_analyzer/webui/server.py:41`

**Step 1: Write the failing test**
```python
# scripts/rdc_analyzer/tests/test_webui_report_root.py
# Placeholder: verify server serves index.html from report root
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_webui_report_root.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**
```python
# ui_extension/analyzer_extension.py (pseudo patch)
from rdc_analyzer.report_from_analysis import generate_report_from_analysis

analysis_file = run_analysis(capture, output_dir)
try:
    generate_report_from_analysis(analysis_file, output_dir, Path(capture).name)
    url = ensure_webui_server(output_dir, analysis_file)  # serves report root
except Exception:
    url = ensure_webui_server(output_dir, analysis_file)  # fallback current viewer
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_webui_report_root.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/ui_extension/analyzer_extension.py scripts/rdc_analyzer/webui/server.py
git commit -m "feat(rdc-analyzer): serve report bundle in WebUI"
```

### Task 4: WebUI -> GUI jump endpoint
**Files:**
- Modify: `scripts/rdc_analyzer/webui/server.py:41`
- Modify: `scripts/rdc_analyzer/templates/navigation.js:2`
- Modify: `scripts/rdc_analyzer/templates/events.html:7`

**Step 1: Write the failing test**
```python
# scripts/rdc_analyzer/tests/test_webui_jump_endpoint.py
# Placeholder: call /api/jump?eid=7 and expect 200
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_webui_jump_endpoint.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**
```js
// templates/navigation.js
async function jumpToRenderDoc(eid) {
  try { await fetch(`/api/jump?eid=${eid}`); } catch (e) {}
}
```
```html
<!-- templates/events.html: add button/link per event -->
<button onclick="jumpToRenderDoc({{EVENT_ID}})">Jump to RenderDoc</button>
```
```python
# webui/server.py: add /api/jump handler calling jump_handler(eid)
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_webui_jump_endpoint.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/webui/server.py scripts/rdc_analyzer/templates/navigation.js scripts/rdc_analyzer/templates/events.html
git commit -m "feat(rdc-analyzer): add WebUI jump to GUI"
```

### Task 5: Documentation + manual verification
**Files:**
- Modify: `scripts/rdc_analyzer/docs/WEBUI_AND_UI_EXTENSION.md:16`

**Step 1: Update docs**
Add: WebUI now serves report bundle pages and supports `/api/jump` for EID.

**Step 2: Manual verification**
- Open capture -> Tools -> RDC Analyzer -> Open WebUI
- Navigate to events page and click Jump
- Expect GUI selection changes to that EID

**Step 3: Commit**
```bash
git add scripts/rdc_analyzer/docs/WEBUI_AND_UI_EXTENSION.md
git commit -m "docs(rdc-analyzer): document WebUI report + jump"
```
