# Textures UI Scroll & List Clarity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026.02.05
**Owner:** Agent01 (Codex)
**Last Updated:** 2026-02-05

**Goal:** Make textures.html readable and scrollable by fixing list styling, removing the 50-item cap, and ensuring right panel scroll works.

**Architecture:** Update the report generator to emit consistent class names + data attributes, and adjust textures.html template + layout to fixed-viewport scrolling. Keep changes localized to templates/generator/tests.

**Tech Stack:** Python (rdc_analyzer), HTML/CSS/JS templates, pytest.

**Success Criteria (measurable):**
- textures.html shows multiple list items with readable thumbnails and metadata (no "only one item" appearance).
- Right-side properties panel scrolls within the fixed viewport.
- Search/filter/sort works based on data-* attributes.
- Tests pass for new list markup and fixed viewport markers.

**Acceptance Criteria:**
- In `D:\backup\endfield_report\textures.html`, left list and right panel both scroll, thumbnails have proper sizing, and IDs show resource ids.
- No regressions in shaders.html or events.html layout.

**Verification Commands:**
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -v --tb=short` (Expected: all tests pass)
- `py -3 -m rdc_analyzer analyze "D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc" -o "D:\backup\endfield_report"` (Expected: textures.html regenerated with scrollable panels)

**Evidence:**
- `D:\backup\endfield_report\textures.html` (open to verify list + scroll)
- Pytest output showing new tests pass

**Estimation:**
- Effort: 1.5–2.5 hours
- Story Points: 2
- Original Estimate: 2 hours

**Risk Register (impact/likelihood/mitigation):**
- Large HTML size when removing list cap (Impact: Medium, Likelihood: Medium) → Mitigate by keeping markup light; revisit virtual scroll later.
- HTML attribute escaping (Impact: Low, Likelihood: Medium) → Mitigate by using safe formatting; keep attribute values simple.
- Layout regressions due to fixed viewport (Impact: Medium, Likelihood: Low) → Mitigate by scoping changes to textures.html only.

## Game Dev: Memory & Resource Budget (Leak Checks)
- No runtime change to GPU resources; HTML size may grow. Track output size and page load time for large captures.

## Game Dev: Asset Pipeline
- No asset pipeline changes; only report HTML/CSS/JS output is updated.

## Game Dev: Crash Repro + Dumps/Symbols
- Not applicable for HTML-only change; if native crash appears during analysis, capture repro steps and keep build id + log for triage.

## Scope
**In scope**
- Fix textures.html list readability (class names, thumbnails, metadata).
- Fix panel scrolling by enforcing fixed viewport layout.
- Ensure search/filter/sort uses data-* attributes.
- Remove hard 50-item list limit.

**Out of scope**
- Server-side on-demand texture generation.
- Shader page rework or events page changes.

## Assumptions
- `textures.html` is generated exclusively via `ReportBundleGenerator.generate_textures`.
- Existing CSS variables and theme should be preserved.

## Repo / File List (line ranges)
- `scripts/rdc_analyzer/report_bundle_generator.py:502-560` (generate_textures list markup)
- `scripts/rdc_analyzer/templates/textures.html:12-80` (body/app-container layout)
- `scripts/rdc_analyzer/templates/textures.html:591-650` (renderListThumbnails/selectTexture)
- `scripts/rdc_analyzer/templates/common.css:101-170` (fixed viewport + panel scroll)
- `scripts/rdc_analyzer/tests/test_bundle_report_assets.py:1-200` (new tests)

## Approach (Pseudo-code)
1) Emit list items with consistent class names + data-* attributes.
2) In JS, resolve textures via `textureMap` and normalize id/resource_id.
3) Enforce fixed viewport with body/app-container classes.
4) Update tests to validate list markup + fixed layout markers.

## Build/Test/Lint Quick Guide
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -v --tb=short`

## Decisions
- Prefer minimal HTML/CSS changes and keep Photoshop dark theme intact.
- Remove list cap for now; revisit virtual scroll later if performance becomes a concern.

## Task Checklist (2-5 min each, TDD)
- [x] Add failing test for textures list markup and fixed viewport.
  - Code (new test in `test_bundle_report_assets.py`):
    ```python
    def test_textures_list_item_has_dataset_and_thumb_class(tmp_path):
        gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
        gen.set_textures([{
            "id": "tex_0",
            "resource_id": "133",
            "name": "Image_133",
            "width": 4,
            "height": 4,
            "mips": 1,
            "vram": 16,
            "format": "VK_FORMAT_R8G8B8A8_UNORM",
            "thumbnail": "textures/tex_133_4x4.png",
            "issues": [{"level": "warn", "message": "x"}],
        }])
        outputs = gen.generate_all()
        html = Path(outputs["textures"]).read_text(encoding="utf-8")
        assert 'data-name="Image_133"' in html
        assert 'data-format="VK_FORMAT_R8G8B8A8_UNORM"' in html
        assert 'data-width="4"' in html
        assert 'data-height="4"' in html
        assert 'data-mip-levels="1"' in html
        assert 'data-vram="16"' in html
        assert 'data-has-issue="true"' in html
        assert 'texture-item-thumb' in html
        assert 'app-container fixed' in html
        assert 'fixed-viewport' in html
    ```
- [x] Run the new test to confirm it fails.
  - Command:
    ```bash
    py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -v --tb=short
    ```
- [x] Update `generate_textures` list markup to align classes + data-* attributes and remove list cap.
  - Code (replace list loop in `generate_textures`):
    ```python
    for tex in self.textures:
        tex_id = tex.get("id") or tex.get("resource_id", "")
        raw_name = tex.get("name", "")
        width = tex.get("width", 0)
        height = tex.get("height", 0)
        fmt = tex.get("format", "UNKNOWN")
        mips = tex.get("mips", 1)
        vram = tex.get("vram", 0)
        has_issue = bool(tex.get("issues"))
        thumb = self._normalize_thumbnail(tex.get("thumbnail", ""))
        display_name = self._format_texture_name(raw_name, tex_id, width, height)
        simple_fmt = self._simplify_format_name(fmt)
        thumb_html = "<div class='thumb-placeholder'>?</div>"
        if thumb:
            thumb_html = f'<img src="{thumb}" alt="">'
        texture_list_html += f'''
            <div class="texture-item"
                 data-id="{tex_id}"
                 data-name="{display_name}"
                 data-format="{fmt}"
                 data-width="{width}"
                 data-height="{height}"
                 data-mip-levels="{mips}"
                 data-vram="{vram}"
                 data-has-issue="{str(has_issue).lower()}"
                 onclick="selectTexture('{tex_id}')">
                <div class="texture-item-thumb">
                    {thumb_html}
                </div>
                <div class="texture-item-info">
                    <div class="texture-item-name">{display_name}{size_tag}</div>
                    <div class="texture-item-meta">
                        {width}×{height} • {simple_fmt}
                    </div>
                </div>
            </div>'''
    ```
- [ ] Update textures.html template layout to fixed viewport.
  - Code (top of `textures.html`):
    ```html
    <body class="fixed-viewport">
        <div class="app-container fixed">
    ```
- [ ] Update textures.html JS to resolve thumbnails and selection by id/resource_id.
  - Code (in `renderListThumbnails` + `selectTexture`):
    ```javascript
    function renderListThumbnails() {
        document.querySelectorAll('.texture-item').forEach(item => {
            const texId = String(item.dataset.id || "");
            const texture = textureMap.get(texId);
            const thumbEl = item.querySelector('.texture-item-thumb') || item.querySelector('.texture-thumb');
            if (!thumbEl) return;
            if (texture && texture.thumbnail) {
                thumbEl.innerHTML = `<img src="${texture.thumbnail}" alt="">`;
            } else {
                thumbEl.innerHTML = "<div class='thumb-placeholder'>?</div>";
            }
        });
    }

    function selectTexture(id) {
        const key = String(id);
        const texture = textureMap.get(key);
        if (!texture) return;
        currentTexture = texture;
        document.querySelectorAll('.texture-item').forEach(el => el.classList.remove('selected'));
        const item = document.querySelector(`.texture-item[data-id="${key}"]`);
        if (item) item.classList.add('selected');
        document.getElementById('propId').textContent = texture.resource_id || texture.id || '-';
        // other fields unchanged...
    }
    ```
- [ ] Run tests again and confirm pass.
  - Command:
    ```bash
    py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -v --tb=short
    ```
- [ ] Regenerate report and spot-check UI (user does visual check).
  - Command:
    ```bash
    py -3 -m rdc_analyzer analyze "D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc" -o "D:\backup\endfield_report"
    ```
- [ ] Commit (per task completion, Conventional Commits).
  - Example:
    ```bash
    git add scripts/rdc_analyzer/report_bundle_generator.py scripts/rdc_analyzer/templates/textures.html scripts/rdc_analyzer/tests/test_bundle_report_assets.py
    git commit -m "fix(rdc-analyzer): improve textures list styling and scroll behavior

    - align texture list class names with common.css
    - add data attributes for search/sort
    - enforce fixed viewport for panel scrolling"
    ```

## Verification / Acceptance (Definition of Done)
- Tests pass as listed.
- User confirms textures list readability + right panel scroll in the generated HTML.

## Next Steps
- If HTML size becomes heavy, implement virtual scroll for textures list.
- Optional: add small ID badge styles for quicker scan (after UI confirmation).
