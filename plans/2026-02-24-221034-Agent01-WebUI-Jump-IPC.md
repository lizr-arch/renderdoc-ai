# WebUI Jump IPC (Event/Texture/Shader) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-02-24
**Owner:** Agent01
**Last Updated:** 2026-02-24

**Goal:** Make WebUI jump (event/texture/shader) work reliably for both embedded and external WebUI by adding an IPC jump queue and GUI-side dispatcher.

**Architecture:** Add a file-based jump queue in the WebUI output directory. `/api/jump` writes requests to the queue when no in-process GUI handler is available. The UI extension starts a lightweight polling loop that reads jump requests and invokes RenderDoc GUI APIs on the UI thread. Keep direct in-process jump for embedded WebUI, but always accept IPC as fallback.

**Tech Stack:** Python (rdc_analyzer), RenderDoc UI extension (qrenderdoc), SimpleHTTPRequestHandler, JSON file IPC, optional MiniQtHelper.

**Success Criteria (measurable):**
- WebUI jump works in **external WebUI mode** (missing `_socket`) for event jumps.
- Event/texture/shader jump requests are accepted and dispatched without crash.
- Jump requests are idempotent (no repeated jump on refresh).

**Acceptance Criteria:**
- External WebUI: clicking “↗ GUI” in events page selects the event in RenderDoc.
- Texture/Shader jump buttons appear when IDs exist and bring up corresponding viewers.
- Embedded WebUI still uses direct jump (no regression).

**Verification Commands:**
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_webui_server.py -k "jump" -v` (Expected: PASS)
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_ui_extension_config.py -k "jump" -v` (Expected: PASS)

**Evidence:**
- WebUI URL shows successful jump; GUI selection visibly updates.
- Output folder contains `rdc_analyzer_jump.json` + `rdc_analyzer_jump_ack.json` after a click.

**Estimation:**
- Effort: 1-2 days
- Story Points: 3
- Original Estimate: 1.5 days

**Risk Register (impact/likelihood/mitigation):**
- Jump queue races (duplicate requests) | Medium | Medium | Include request_id + ack file to dedupe.
- Shader/texture API mismatch | Medium | Medium | Validate with QRDInterface + PythonShell bindings before wiring.
- Polling overhead | Low | Medium | 250-500ms interval, stop when WebUI closes.

---

## Scope
- In scope: IPC jump queue, event/texture/shader jump dispatch, WebUI buttons, tests, docs.
- Out of scope: multi-capture routing, deep link syncing of selection state back to WebUI.

## Assumptions
- Output directory is stable per capture and writable.
- WebUI server can write into output_dir when running externally.
- RenderDoc GUI exposes enough APIs for texture/shader viewer selection.

## Repo / File List
- Modify: `scripts/rdc_analyzer/webui/server.py`
- Modify: `scripts/rdc_analyzer/ui_extension/analyzer_extension.py`
- Modify: `scripts/rdc_analyzer/templates/events.html`
- Modify: `scripts/rdc_analyzer/templates/textures.html`
- Modify: `scripts/rdc_analyzer/templates/shaders.html`
- Modify: `scripts/rdc_analyzer/templates/navigation.js`
- Modify: `scripts/rdc_analyzer/bridge/analysis_to_bundle.py` (ensure IDs)
- Add: `scripts/rdc_analyzer/tests/test_webui_jump_queue.py`
- Update: `scripts/rdc_analyzer/docs/WEBUI_AND_UI_EXTENSION.md`

## Approach (Pseudo-code)
```python
# webui/server.py
def _handle_jump(parsed):
    target = qs.get("target", "event")
    eid = int(qs["eid"])
    if self._jump_handler: self._jump_handler({...})
    else: write_jump_request(output_dir/"rdc_analyzer_jump.json", {...})

# analyzer_extension.py
def start_jump_watcher(output_dir):
    while not stop: 
        req = read_jump_request(...)
        if req and req_id != last_id:
            invoke_ui_thread(lambda: dispatch_jump(ctx, req))
            write_ack(...)

def dispatch_jump(ctx, req):
    if target == "event": ctx.SetEventID([], eid, eid)
    if target == "texture": ctx.ShowTextureViewer(); ctx.GetTextureViewer().SetSelectedTexture(tex_id)
    if target == "shader": ctx.ViewShader(shader_id, stage?) or open ShaderViewer
```

## Impact Analysis
- External WebUI gains GUI jump capability without `_socket`.
- Adds background polling thread; ensure clean stop on capture change.
- Requires verifying texture/shader viewer APIs.

## Build/Test/Lint Quick Guide (commands only, do not execute)
- Unit tests: `py -3 -m pytest scripts/rdc_analyzer/tests -v --tb=short`

## Task Checklist
- [x] Task 1: Define jump request schema + queue write in WebUI server
- [x] Task 2: Add GUI jump watcher + dispatcher
- [x] Task 3: Wire event/texture/shader buttons + navigation helper
- [ ] Task 4: Ensure bundle data contains needed IDs
- [ ] Task 5: Tests + docs update

### Task 1: Jump request schema + server writer
**Files:**
- Modify: `scripts/rdc_analyzer/webui/server.py`
- Add: `scripts/rdc_analyzer/tests/test_webui_jump_queue.py`

**Step 1: Write the failing test**
```python
def test_jump_queue_written_when_no_handler(tmp_path):
    # start server with jump_handler=None
    # request /api/jump?target=event&eid=7
    # assert jump file exists + json contains target/event/eid
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_webui_jump_queue.py -v`
Expected: FAIL (no jump file)

**Step 3: Write minimal implementation**
```python
def _write_jump_request(root, payload):
    tmp = root/"rdc_analyzer_jump.tmp"
    dst = root/"rdc_analyzer_jump.json"
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(dst)
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_webui_jump_queue.py -v`
Expected: PASS
Result: PASS (2026-02-24)
Result: PASS (2026-02-24)

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/webui/server.py scripts/rdc_analyzer/tests/test_webui_jump_queue.py
git commit -m "feat(rdc-analyzer): add WebUI jump queue writer"
```

### Task 2: GUI jump watcher + dispatcher
**Files:**
- Modify: `scripts/rdc_analyzer/ui_extension/analyzer_extension.py`
- Add: `scripts/rdc_analyzer/tests/test_webui_jump_queue.py` (extend)

**Step 1: Write the failing test**
```python
def test_dispatch_jump_event_calls_seteventid():
    # stub ctx with SetEventID
    # call dispatch_jump(ctx, {"target":"event","id":7})
    # assert called with eid 7
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_webui_jump_queue.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**
```python
def dispatch_jump(ctx, req):
    target = req.get("target")
    if target == "event": ctx.SetEventID([], eid, eid, True)
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_webui_jump_queue.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/ui_extension/analyzer_extension.py scripts/rdc_analyzer/tests/test_webui_jump_queue.py
git commit -m "feat(rdc-analyzer): add GUI jump dispatcher"
```

### Task 3: WebUI buttons + navigation helper
**Files:**
- Modify: `scripts/rdc_analyzer/templates/events.html`
- Modify: `scripts/rdc_analyzer/templates/textures.html`
- Modify: `scripts/rdc_analyzer/templates/shaders.html`
- Modify: `scripts/rdc_analyzer/templates/navigation.js`

**Step 1: Add JS helper**
```js
window.jumpToRenderDoc = (target, id) => fetch(`/api/jump?target=${target}&id=${id}`);
```

**Step 2: Wire buttons**
```html
<button onclick="jumpToRenderDoc('event', event.eid)">↗ GUI</button>
```

**Step 3: Commit**
```bash
git add scripts/rdc_analyzer/templates/navigation.js scripts/rdc_analyzer/templates/events.html scripts/rdc_analyzer/templates/textures.html scripts/rdc_analyzer/templates/shaders.html
git commit -m "feat(rdc-analyzer): add jump buttons for event/texture/shader"
```
Result: PASS (2026-02-24, test_webui_jump_buttons.py)

### Task 4: Ensure bundle data contains needed IDs
**Files:**
- Modify: `scripts/rdc_analyzer/bridge/analysis_to_bundle.py`

**Step 1: Add mapping**
```python
tex_id = tex.get("resourceId") or tex.get("id")
shader_id = shader.get("shader_resource_id") or shader.get("id")
```

**Step 2: Run tests**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_analysis_to_bundle.py -v`
Expected: PASS

**Step 3: Commit**
```bash
git add scripts/rdc_analyzer/bridge/analysis_to_bundle.py
git commit -m "fix(rdc-analyzer): ensure bundle IDs for jump"
```

### Task 5: Docs + manual verification
**Files:**
- Modify: `scripts/rdc_analyzer/docs/WEBUI_AND_UI_EXTENSION.md`

**Manual verification steps:**
- External WebUI (missing _socket): click ↗ GUI in events/texture/shader page → GUI jumps.

**Commit**
```bash
git add scripts/rdc_analyzer/docs/WEBUI_AND_UI_EXTENSION.md
git commit -m "docs(rdc-analyzer): document jump IPC flow"
```

## Decisions
- Use file-based IPC (`rdc_analyzer_jump.json`) for external WebUI.
- Keep direct handler for embedded WebUI, fallback to IPC.

## Verification / Acceptance (Definition of Done)
- External WebUI jump works for events.
- Texture/Shader jump buttons appear when IDs exist.
- No regression in embedded WebUI.

## Next Steps
- Add WebUI → GUI jump ack UI if needed (toast/indicator).

## Game Dev: Memory & Resource Budget (Leak Checks)
- Ensure watcher thread stops on capture change; no thread leaks after 10 open/close cycles.

## Game Dev: Asset Pipeline
- Jump queue files stored in output_dir; do not pollute capture root.

## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: Open capture → Open WebUI → click jump button
- Dump/Core: (minidump | core dump) TBD
- Symbols: (PDB | dSYM | ELF | DWARF) TBD
- Build identity: (build id | commit hash | git commit) TBD
