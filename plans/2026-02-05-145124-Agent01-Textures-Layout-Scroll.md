# Plan: Textures UI center preview + list scroll

## Scope
- In: remove right-panel preview block; keep center preview; fix texture list scrolling.
- Out: no shader UI changes, no export logic changes, no layout redesign beyond required.

## Assumptions
- Bundle template scripts/rdc_analyzer/templates/textures.html is the source for report/textures.html.

## Repo / File List (line ranges)
- scripts/rdc_analyzer/templates/textures.html:12-239 (page CSS for body, texture-list, detail-preview)
- scripts/rdc_analyzer/templates/textures.html:336-519 (layout markup: app-container, left panel, main canvas, right panel)
- scripts/rdc_analyzer/templates/textures.html:610-661 (preview update logic)
- scripts/rdc_analyzer/templates/common.css:100-166 (app-container fixed + panel-left/right layout)

## Approach (Pseudo-code + code snippets)
1) Fix layout height to allow scroll
   - Change container to fixed height:
     HTML: <div class='app-container fixed'>
   - Ensure left panel can shrink:
     CSS:
       .panel-left {
         min-height: 0;
       }
   - Ensure list uses available height:
     CSS:
       .texture-list {
         flex: 1;
         min-height: 0;
       }

2) Remove right-panel preview section
   - Delete the prop-section block labeled Preview (the detailPreview container).

3) Simplify preview update to center-only
   - Update caller:
       const previewImg = document.getElementById('previewImg');
       const canvasEmpty = document.getElementById('canvasEmpty');
       updateTexturePreview(texture, previewImg, canvasEmpty);
   - Update function:
       function updateTexturePreview(texture, previewImg, canvasEmpty) {
         const imgEl = previewImg || document.getElementById('previewImg');
         const emptyEl = canvasEmpty || document.getElementById('canvasEmpty');
         if (texture.thumbnail) {
           imgEl.src = texture.thumbnail;
           imgEl.classList.remove('hidden');
           emptyEl.classList.add('hidden');
         } else {
           imgEl.classList.add('hidden');
           emptyEl.classList.remove('hidden');
         }
       }

## Impact Analysis
- Removes quick preview in property panel; reduces redundancy but aligns with request.
- Fixes list scroll by constraining layout height; should not affect other pages.
- Risk: if list still does not scroll, may need to wrap left panel content into panel-content or adjust flex rules.

## Action Items (2-5 min each)
- [x] Edit textures.html: change app-container class; remove preview block; adjust texture-list CSS min-height.
- [x] Edit common.css: add min-height: 0 to panel-left.
- [x] Edit textures.html JS: remove detailPreview usage; adjust updateTexturePreview signature.
- [ ] Regenerate bundle report for Endfield capture (headless).
- [ ] Visual verification in browser and record result.

## Risks & Blockers
- If list still does not scroll, investigate missing flex constraints and add a panel-content wrapper.
- Headless report regeneration was terminated after long runtime; output HTML patched directly as a fallback.

## Verification / DoD
- Command (headless, no GUI):
  py -3 scripts/rdc_analyzer/analyze_xml_report.py D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc --ui-version bundle -o D:\backup\endfield_report\report.html
  Expected: report saved under D:\backup\endfield_report\report\ and textures.html updated.
- Visual checks (user):
  - Left texture list scrolls with mouse wheel
  - Right panel has no preview block
  - Center preview shows selected texture

## Next Steps
- Wait for /do approval.
