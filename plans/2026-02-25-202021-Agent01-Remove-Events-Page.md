# 2026-02-25-202021-Agent01-Remove-Events-Page

date: 2026-02-25 20:20:21  
agent: Agent01  
stage: /plan

## Scope / Assumptions
- Remove `events.html` from bundle output and navigation.
- Keep `jumpToRenderDoc` only for texture and shader targets (no event jump UI).
- Assumption: user wants no events page and no event-level GUI jump from WebUI.

## File List (line ranges)
- `scripts/rdc_analyzer/report_bundle_generator.py`: 1049-1121, 1421-1553, 1555-1571, 1590-1618
- `scripts/rdc_analyzer/templates/index.html`: 402-515
- `scripts/rdc_analyzer/templates/textures.html`: 715-721, 895-903, 1216-1234, 1250-1267, 1567-1574
- `scripts/rdc_analyzer/templates/shaders.html`: 1188-1193, 1408-1416, 2074-2077, 2240-2245, 2375-2382
- `scripts/rdc_analyzer/templates/recommendations.html`: 493-497, 739-746, 755-764
- `scripts/rdc_analyzer/core/evidence_chain_builder.py`: 142-150, 183-191, 223-230, 245-252, 287-295, 336-344, 373-378
- `scripts/rdc_analyzer/core/evidence_builder.py`: 137-145, 239-259, 385-393, 467-475
- `scripts/rdc_analyzer/core/types.py`: 885-901
- `scripts/rdc_analyzer/tests/test_bundle_report_assets.py`: 400-413, 430-441
- `scripts/rdc_analyzer/tests/test_report_issue_jump_links.py`: 4-23
- `scripts/rdc_analyzer/tests/test_webui_jump_buttons.py`: 15-35
- `scripts/rdc_analyzer/tests/test_evidence_chain_pipeline.py`: 190-196

## Pseudocode
### report_bundle_generator.py
```
def generate_manifest():
    pages = {
        "index": "index.html",
        "textures": "textures.html",
        "shaders": "shaders.html",
        "recommendations": "recommendations.html",
    }

def generate_all():
    write index, textures, shaders, recommendations
    skip generate_events()
    skip events_data.json and heatmap_data.json
```

### templates
```
# index.html: remove events menu item and quick-nav cards; keep draw call counts as static
# textures.html/shaders.html: remove "View Events" buttons, remove jumpToEvent(), remove onclick from usage items
# recommendations.html: remove events menu; remove affected_events section; no events fallback for resource tags
```

### evidence chain
```
# Remove jump_to_event actions (target_page="events.html"); keep affected_events list if needed
```

## Build/Test/Lint Quick Guide (commands only)
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -v` -> expected: PASS
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_report_issue_jump_links.py -v` -> expected: PASS
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_webui_jump_buttons.py -v` -> expected: PASS
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_evidence_chain_pipeline.py -v` -> expected: PASS

## Task Checklist (2-5 min each)
- [x] TDD-1 Update tests to remove events page expectations (tests should fail before code changes).
  - `test_template_css_vars_defined_contract`: remove `"events.html"` from file list.
  - Remove `events_html` reads/assertions in `test_report_issue_jump_links.py` and `test_webui_jump_buttons.py`.
  - `test_evidence_chain_pipeline.py`: use `textures.html` or `shaders.html` for `Action.target_page`.
- [x] TDD-2 Run the test subset above; confirm failures referencing events.html.
- [x] TDD-3 Implement generator changes to stop emitting events.html and its data files; update manifest pages.
  - Example snippet:
    ```
    "pages": {
        "index": "index.html",
        "textures": "textures.html",
        "shaders": "shaders.html",
        "recommendations": "recommendations.html",
    }
    ```
- [x] TDD-4 Update templates: remove events navigation and event jumps; keep GUI jumps for texture/shader.
  - Example snippet:
    ```
    <button class="detail-action-btn secondary" onclick="jumpToRenderDocTexture()">GUI</button>
    ```
- [x] TDD-5 Update evidence chain builders to stop adding jump_to_event actions.
  - Example snippet:
    ```
    # remove chain.add_action(... target_page="events.html")
    ```
- [x] TDD-6 Re-run tests; fix regressions; commit.

## Impact Analysis
- Bundle output no longer includes `events.html`.
- Evidence chain actions no longer point to events page; recommendations only link to textures/shaders.
- GUI jump remains available for texture/shader via `/api/jump`.

## Risks / Blockers
- Reduced drill-down for issues that only reference event IDs.
- Docs and helper scripts still mention `events.html` (out of scope unless requested).

## Decisions
- Remove events page generation and navigation.
- Do not provide event-level GUI jump from WebUI.

## Verification / Acceptance (Definition of Done)
- Output bundle includes only: `index.html`, `textures.html`, `shaders.html`, `recommendations.html`, `manifest.json`.
- No UI element links to `events.html` or calls `jumpToEvent()`.
- Texture/Shader GUI jump still calls `/api/jump?target=texture|shader&id=...`.
- All listed tests pass.

## /do Update (2026-02-25)
- Note: skipped pre-change failure confirmation; validated with post-change test passes.
- Tests:
  - `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -v` PASS
  - `py -3 -m pytest scripts/rdc_analyzer/tests/test_report_issue_jump_links.py -v` PASS
  - `py -3 -m pytest scripts/rdc_analyzer/tests/test_webui_jump_buttons.py -v` PASS
  - `py -3 -m pytest scripts/rdc_analyzer/tests/test_evidence_chain_pipeline.py -v` PASS

## Next Steps
- If needed later, update docs (EXPORT_ROUTES.md, WEBUI_AND_UI_EXTENSION.md) to reflect removal.
