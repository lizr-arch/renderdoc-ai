Scope / Assumptions
- Scope: Fix A-route HTML Event Browser data completeness (pipeline state, resource bindings, mesh info, API call params) for XML-driven reports like `D:\backup\rdc_reports\大远景\大远景_report.html`, and define a minimal eventPassData contract for A-route.
- Assumptions:
  - `parse_rdc_xml.py` already parses `params`, `meshInfo`, `pipelineState`, `resourceBindings` per event (see `scripts/rdc_analyzer/parse_rdc_xml.py:792,826-832`).
  - A-route uses `analyze_xml_report.py` → `convert_perf_report_to_html_data` to build `event_pass_data`, which currently omits those fields (`scripts/rdc_analyzer/analyze_xml_report.py:261,311`).
  - HTML template expects `event.params`, `event.meshInfo`, and `event.pipelineState.bindings` (see `scripts/rdc_analyzer/generate_offline_report.py:10269,10536,10906`).
  - Schema doc is in GB18030 (garbled when read as UTF-8); preserve original encoding when editing.

Evidence Snapshot (Why this plan exists)
- `D:\backup\rdc_reports\大远景\大远景_report.html` contains `const eventPassData = {summary, issues, events...}` but no `pipelineState/meshInfo/params` in events, so bindings/mesh/api tabs are empty.
- A-route generator only builds simplified event fields (draw counts + shader ids) and passes them directly to HTML.
- Full report generator (`generate_real_report.py`) supports pipeline/bindings/mesh/api data but uses different field names (apiCall/meshData) than the template expects.

File List (touch points with line refs)
- `scripts/rdc_analyzer/analyze_xml_report.py:261,311,482-498` (A-route event_pass_data assembly + HTML generation)
- `scripts/rdc_analyzer/parse_rdc_xml.py:792,826-832` (event contains params/meshInfo/pipelineState/resourceBindings)
- `scripts/rdc_analyzer/generate_offline_report.py:6819,10269,10536,10906` (HTML reads eventPassData; expects params/meshInfo/bindings)
- `scripts/rdc_analyzer/generate_real_report.py:572,606-673,625-657,668-717` (full-path conversion, bindings merge, meshData)
- `scripts/rdc_analyzer/analyze_rdc.py:2814-2860` (full html-mode path for reference)
- `docs/analysis/codex_rdc_analyzer/2026-01-20-rdc-analyzer-schema-single-analysis.md:35,41,47-54` (canonical single-analysis schema)
- `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_VERIFICATION.md:134-147` (verification currently only checks presence + counts)

Build/Test/Lint Quick Guide (commands only; do not run automatically)
- Generate XML from RDC (RenderDoc):
  - `renderdoccmd capture.rdc --export-xml capture.xml`
- A-route HTML:
  - `py -3 scripts/rdc_analyzer/analyze_xml_report.py capture.xml -o capture_report.html`
- EventPassData field check (HTML):
  - `py -3 -c "from pathlib import Path; t=Path(r'capture_report.html').read_text(encoding='utf-8',errors='ignore'); m='const eventPassData = '; s=t.find(m); e=t.find(';',s); j=t[s+len(m):e] if s!=-1 and e!=-1 else ''; print('has_pipelineState', 'pipelineState' in j, 'has_meshInfo', 'meshInfo' in j, 'has_params', 'params' in j)"`

Decisions
- Align A-route eventPassData to HTML template fields first (params/meshInfo/pipelineState.bindings), then document it as A-route Event Browser contract.
- Reuse parse_rdc_xml output as the authoritative source for event details (no new replay step).
- Keep full-path (`generate_real_report.py`) compatibility by optionally adding template fallbacks to `apiCall/meshData` if present.

Task Checklist (2–5 min granularity; include code snippets)
- [x] T1 — Baseline capture: parse `大远景_report.html` and log presence of `pipelineState/meshInfo/params` in eventPassData (proof of current gap).
- [x] T2 — Build XML event lookup by `eventId` in `convert_perf_report_to_html_data`:
  - Pseudocode:
    - `xml_events = {e["eventId"]: e for e in xml_data.get("events", [])}`
    - For each `dc` in `context.draw_calls`, merge:
      - `event["name"] = xml_event.get("name", event["name"])`
      - `event["params"] = xml_event.get("params", [])`
      - `event["meshInfo"] = xml_event.get("meshInfo")`
      - `event["pipelineState"] = xml_event.get("pipelineState")`
      - `event["resourceBindings"] = xml_event.get("resourceBindings")`
- [x] T3 — Ensure `pipelineState.bindings` exists for A-route:
  - Option A (preferred): port lightweight conversion from `generate_real_report.py` into a shared helper (e.g., `core/pipeline_bindings.py`) and call it here.
  - Option B (minimal): import `convert_resource_bindings_to_template_format` + `convert_pipeline_state_to_bindings` from `generate_real_report.py` and merge:
    ```
    bindings = convert_resource_bindings_to_template_format(resourceBindings)
    new_bindings = convert_pipeline_state_to_bindings(pipelineState)
    pipelineState["bindings"] = merge_bindings(bindings, new_bindings)
    ```
- [ ] T4 — Template compatibility fallback (optional safety):
  - In `renderEventApiCall`, if `event.params` missing but `event.apiCall` exists, render from `apiCall.params`.
  - In `renderEventMeshInfo`, if `event.meshInfo` missing but `event.meshData` exists, adapt to expected shape or display meshData directly.
- [x] T5 — Update A-route contract doc:
  - Add section to `2026-01-20-rdc-analyzer-schema-single-analysis.md` describing **eventPassData** and **Event Browser required fields** (WHAT/WHY/HOW).
  - Required fields (minimal): `events[].{eid,name,params,meshInfo,pipelineState{bindings}}`.
- [x] T6 — Update verification doc:
  - Add checks that `eventPassData.events` contains at least one event with `pipelineState.bindings`, `meshInfo`, and `params`.
  - Record any acceptable fallbacks (apiCall/meshData).
- [x] T7 — Regenerate A-route HTML for `大远景` and verify with the field-check command; update acceptance notes.

Impact Analysis
- A-route output becomes richer; Event Browser tabs should populate without switching to full HTML path.
- Potential CPU cost: building event lookup map and merging data (O(n)).
- Backward compatibility: template may need fallback to avoid breaking full report paths.

Risks / Blockers
- Encoding: schema doc appears GB18030; must preserve encoding on edit.
- Import coupling: importing `generate_real_report.py` inside A-route may create heavy dependencies; prefer extracting helpers if risk appears.
- Data size: eventPassData can be large; keep only needed fields.

Verification / Acceptance (Definition of Done)
- `大远景_report.html` contains eventPassData with:
  - `pipelineState` present in at least one event,
  - `meshInfo` present in at least one draw event,
  - `params` present for at least one event,
  - Event Browser tabs render non-empty content for a sampled event.
- Documentation updated with A-route Event Browser contract (WHAT/WHY/HOW).

Next Steps (post-approval)
- Execute tasks T1–T7 and update this plan with completion notes and any deviations.

Progress Notes
- T1: `大远景_report.html` 原始 eventPassData 未包含 `pipelineState/meshInfo/params`（Event Browser 空白）。
- T7: 重新运行 `analyze_xml_report.py` 后，field-check 显示 `pipelineState/meshInfo/params` 均存在。
- T4: 本次未改模板 fallback（A 路线已补齐字段，先观察是否仍有遗漏）。
