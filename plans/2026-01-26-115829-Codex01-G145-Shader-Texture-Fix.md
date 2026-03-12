# Scope / Assumptions
- In scope: fix empty Shader Details + Textures in `g145-battle-2_report.html`; produce an accurate report that explains data gaps; update acceptance so it detects empty lists.
- Out of scope: building RenderDoc or adding new dependencies.
- Assumptions: capture is Vulkan; shader extraction currently only uses `vkCreateShaderModule`; texture metadata is parsed from `vkCreateImage` or external manifest.

# Build / Test / Lint Quick Guide (record only)
- Unit tests (TDD): `py -3 -m pytest scripts/rdc_analyzer/tests/test_shader_object_extraction.py -v`
- Unit tests (acceptance checks): `py -3 -m pytest scripts/rdc_analyzer/tests/test_html_content_checks.py -v`
- Manual: regenerate HTML
  - `py -3 scripts/rdc_analyzer/analyze_rdc.py "D:\renderdoc\goog pixel-9\g145-battle-2.rdc" --output "D:\renderdoc\goog pixel-9\g145-battle-2_report.html"`
- Headless acceptance:
  - `powershell -ExecutionPolicy Bypass -File scripts/_tmp_html_ui_review_cdp.ps1 -Html "D:\renderdoc\goog pixel-9\g145-battle-2_report.html" -OutDir "docs/analysis/codex_rdc_analyzer/html_review" -LogFile edge_log`

# Repo / File List (with line refs)
- `scripts/rdc_analyzer/analyze_rdc.py:190` Vulkan shader extraction entry
- `scripts/rdc_analyzer/analyze_rdc.py:216` texture extraction entry
- `scripts/rdc_analyzer/analyze_rdc.py:358` shader_details assembly
- `scripts/rdc_analyzer/analyze_rdc.py:382` manifest / texture list merge
- `scripts/rdc_analyzer/rdc_parser.py:1575` `extract_vulkan_shaders`
- `scripts/rdc_analyzer/rdc_parser.py:1730` `extract_vulkan_textures`
- `scripts/_tmp_html_ui_review_cdp.ps1:159` headless UI checks
- `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_VERIFICATION.md` acceptance log

# Approach (Pseudo-code)
```python
# rdc_parser.py
def extract_vulkan_shaders(self):
    shaders = []
    for chunk in chunks:
        if chunk.chunk_id in (vkCreateShaderModule, vkCreateShadersEXT):
            shaders += extract_spirv_from_chunk(chunk)
    return dedupe_by_hash(shaders)

# analyze_rdc.py
if is_vulkan and not shaders:
    summary["shader_data_reason"] = "No vkCreateShaderModule found; capture may use vkCreateShadersEXT"
if not texture_details:
    summary["texture_data_reason"] = "No vkCreateImage parsed and no manifest.json/textures.json found"

# _tmp_html_ui_review_cdp.ps1
check shader_count > 0 AND texture_count > 0
write into review.json (fail if zero)
```

# Impact Analysis
- Shader extraction will now scan `vkCreateShadersEXT` chunks; possible false positives if SPIR-V blob detection is too loose.
- Texture extraction still depends on chunk layout; add explicit “why empty” reason in report to be accurate even if still empty.
- Headless acceptance will start failing when Shader/Texture lists are empty (desired).

# Action Items (2-5 min each; WHAT/WHY/HOW)
- [x] 1. TDD: add tests for shader-object chunk extraction
  - WHAT: new test file `test_shader_object_extraction.py` with a fake chunk containing SPIR-V magic.
  - WHY: verify parser can extract SPIR-V from `vkCreateShadersEXT` path.
  - HOW:
    ```python
    def test_extract_spirv_from_vkCreateShadersEXT():
        blob = b"\x03\x02\x23\x07" + b"\x00"*16  # SPIR-V header
        data = b"\x00"*64 + blob + b"\x00"*32
        shaders = extract_spirv_blobs_from_chunk(data)
        assert len(shaders) == 1
    ```
- [x] 2. Implement shader object extraction in `rdc_parser.py`
  - WHAT: include `vkCreateShadersEXT` in `extract_vulkan_shaders`, add helper to scan for SPIR-V magic and build `ShaderInfo`.
  - WHY: `g145-battle-2` appears to use shader objects, so shader list is empty.
  - HOW:
    ```python
    if chunk.chunk_id in (VulkanChunk.vkCreateShaderModule, VulkanChunk.vkCreateShadersEXT):
        shaders += self._extract_spirv_from_chunk(fc_data, chunk)
    ```
- [x] 3. Add explicit “data gap reason” in HTML (shader + texture)
  - WHAT: emit `summary["shader_data_reason"]` / `summary["texture_data_reason"]` and show in HTML when lists are empty.
  - WHY: make report accurate when data is missing.
  - HOW:
    ```python
    if not shaders: summary["shader_data_reason"] = "..."; 
    if not texture_details: summary["texture_data_reason"] = "..."
    ```
- [x] 4. TDD: add HTML acceptance checks for empty lists
  - WHAT: unit test that `analysisData` or DOM indicates non-empty shaders/textures.
  - WHY: current acceptance only checked “click”, missed empty content.
  - HOW:
    ```python
    assert "shaders" in html and "texture-grid" in html
    ```
- [x] 5. Update `_tmp_html_ui_review_cdp.ps1` to validate counts
  - WHAT: add JS that inspects `analysisData` and emits counts to review.json.
  - WHY: acceptance should fail when shader/texture lists are empty.
  - HOW:
    ```javascript
    const shaderCount = (analysisData?.[0]?.shaders||[]).length;
    const textureCount = (analysisData?.[0]?.textures||[]).length;
    ```
- [x] 6. Update verification log with new acceptance result
  - WHAT: append a new section in `WORK_SUMMARY_VERIFICATION.md` with shader/texture counts.
  - WHY: keep evidence chain accurate and reproducible.
  - HOW:
    ```markdown
    - shader_count: X
    - texture_count: Y
    - result: pass/fail
    ```

# Risks & Blockers
- Extracting SPIR-V from `vkCreateShadersEXT` is heuristic; may require more layout knowledge.
- Texture metadata parsing may still fail for new layouts without renderdoccmd export.

# Verification / DoD
- g145-battle-2 report shows non-empty Shader Details and Textures OR an explicit, accurate reason if not available.
- Headless acceptance fails when either list is empty, passes when both have content.
- Verification log updated with counts and command references.

# Open Questions
- Is `vkCreateShadersEXT` used in this capture? (Need chunk scan confirmation.)
- Do we accept “data missing but explained” as pass, or must always show lists?

# Next Steps
- Await /do approval.
