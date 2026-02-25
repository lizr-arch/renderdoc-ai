# Plan: WebUI ↔ GUI Jump (Issues + Event/Texture/Shader)

- Time: 2026-02-25 16:35:52
- Agent: AgentC7
- Scope: Make GUI-opened WebUI support jump-back to RenderDoc for issues/events/textures/shaders in both embedded and external WebUI modes.

## Scope / Assumptions
- `analysis.json` remains the SSOT for report generation.
- WebUI is opened from RenderDoc GUI (Tools -> RDC Analyzer -> Open WebUI).
- Embedded WebUI and external browser WebUI must both support jump-back.
- Report pages already expose jump buttons; only wiring/dispatch needs to be made consistent.
- No build steps; only Python + templates + UI extension changes.

## Build/Test/Lint Quick Guide (commands only, do not execute)
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_webui_server.py -v`
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_webui_jump_queue.py -v`
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_webui_jump_buttons.py -v`
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_report_issue_jump_links.py -v`

## File List (with line refs)
- `scripts/rdc_analyzer/webui/server.py:132` — `/api/jump` handler entry
- `scripts/rdc_analyzer/webui/server.py:137` — `_handle_jump` (target/id parsing)
- `scripts/rdc_analyzer/webui/server.py:177` — `_write_jump_request`
- `scripts/rdc_analyzer/webui/server.py:185` — `translate_path` (indentation bug)
- `scripts/rdc_analyzer/ui_extension/analyzer_extension.py:358` — `dispatch_jump`
- `scripts/rdc_analyzer/ui_extension/analyzer_extension.py:662` — `jump_handler` definition
- `scripts/rdc_analyzer/ui_extension/analyzer_extension.py:668` — `ensure_webui_server` wiring
- `scripts/rdc_analyzer/templates/navigation.js:284` — `jumpToRenderDoc` fetch
- `scripts/rdc_analyzer/templates/events.html:2157` — event jump button
- `scripts/rdc_analyzer/templates/textures.html:1222` — issue jump to GUI
- `scripts/rdc_analyzer/templates/shaders.html:2067` — issue jump to GUI
- `scripts/rdc_analyzer/report_bundle_generator.py:555` — issue jump button in index report
- `scripts/rdc_analyzer/tests/test_webui_server.py:144` — jump handler test

## Impact Analysis
- Embedded WebUI gains texture/shader jump (currently event-only).
- External WebUI continues to use jump queue with ack; no behavior regression.
- Fixing `translate_path` enables fallback to bundled WebUI assets when report pages missing.
- Minor test updates to match new jump handler signature.

## Risks / Blockers
- Jump handler signature change could break callers/tests if not updated.
- Some captures may not provide texture/shader IDs; jumps should fail gracefully.
- Embedded Python missing `_socket` still requires external WebUI; queue write must be permitted in output directory.

## Decisions
- Standardize `/api/jump` to pass a payload dict `{target, id, request_id, timestamp}` to `jump_handler`.
- Use `dispatch_jump` for all targets (event/texture/shader) in both embedded and external modes.
- Keep report templates unchanged unless a missing jump hook is found.

## Task Checklist (2–5 min steps)
- [x] T1: Fix `/api/jump` payload + translate_path
  - Update `WebUIRequestHandler._handle_jump` to call `jump_handler(payload)` and only fall back to queue when handler is absent.
  - Move `translate_path` into `WebUIRequestHandler` class (correct indentation) to enable report/asset fallback.
  - Code sketch:
    ```python
    # scripts/rdc_analyzer/webui/server.py
    def _handle_jump(self, parsed) -> None:
        qs = parse_qs(parsed.query)
        target = (qs.get("target") or ["event"])[0]
        id_str = (qs.get("id") or qs.get("eid") or [None])[0]
        if id_str is None: ...
        target_id = int(id_str)
        payload = {
            "request_id": int(time.time() * 1000),
            "timestamp": time.time(),
            "target": target,
            "id": target_id,
        }
        if self._jump_handler:
            self._jump_handler(payload)
        else:
            _write_jump_request(self._report_root, payload)
        _write_ok_json()

    def translate_path(self, path: str) -> str:
        mapped = map_request_path(path, self._analysis_file, self._report_root, self._assets_root)
        return str(mapped)
    ```
- [x] T2: Update GUI jump handler signature
  - Change `jump_handler` in `analyzer_extension.py` to accept a payload dict and pass it to `_dispatch_jump_on_ui_thread`.
  - Code sketch:
    ```python
    # scripts/rdc_analyzer/ui_extension/analyzer_extension.py
    def jump_handler(payload: dict):
        return _dispatch_jump_on_ui_thread(ctx, payload, mini_qt)
    ```
- [x] T3: Update tests for new handler contract
  - Adjust `test_webui_server.py` to expect payload dict (target/id).
  - Example update:
    ```python
    def jump_handler(payload):
        calls["target"] = payload.get("target")
        calls["id"] = payload.get("id")
    ...
    url = f"http://127.0.0.1:{port}/api/jump?target=texture&id=7"
    assert calls == {"target": "texture", "id": 7}
    ```
- [ ] T4: Verify issue jump coverage in templates
  - Confirm index/events/textures/shaders issue sections emit `jumpToRenderDoc(...)`.
  - If any page lacks a jump hook for issues, add `jumpToRenderDoc('event', eid)` or resource-specific target.
- [ ] T5: Docs update (if behavior changes need explicit note)
  - Update `scripts/rdc_analyzer/docs/WEBUI_AND_UI_EXTENSION.md` to state embedded mode supports event/texture/shader jumps via `/api/jump`.

## Verification / Acceptance (Definition of Done)
- GUI opens WebUI via Tools menu and loads report pages (index/events/textures/shaders).
- In embedded WebUI: clicking Jump on event/texture/shader changes GUI selection/viewer.
- In external WebUI: clicking Jump writes queue and GUI dispatches (ack file written).
- Tests in Quick Guide pass.

## Next Steps
- Proceed to `/do` after approval to implement T1–T5.

## Progress Log
- 2026-02-25 16:36: updated `/api/jump` payload handling and fixed `translate_path` placement in `webui/server.py`.
- 2026-02-25 16:38: updated GUI jump handler to accept payload dict (event/texture/shader).
- 2026-02-25 16:39: updated WebUI jump endpoint test to assert payload target/id.
