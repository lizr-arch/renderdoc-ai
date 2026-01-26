# Scope / Assumptions
- In scope: add “completeness reconciliation” checks:
  1) Chunk-based counts (vkCreateShaderModule + vkCreateShadersEXT, vkCreateImage).
  2) RenderDoc UI counts (ReplayController.GetTextures / GetResources).
- Out of scope: compiling RenderDoc; any dependency installs.
- Assumptions: capture is Vulkan; we can read FrameCapture chunk list without replay; UI counts must be run inside RenderDoc UI Python Shell.

# Build / Test / Lint Quick Guide (record only)
- Unit test (chunk count): `py -3 -m pytest scripts/rdc_analyzer/tests/test_chunk_reconciliation.py -v`
- Manual: print chunk counts
  - `py -3 scripts/rdc_analyzer/rdc_parser.py "D:\renderdoc\goog pixel-9\g145-battle-2.rdc" --chunk-counts`
- RenderDoc UI counts (Python Shell):
  - `exec(open(r'D:\Code\git\renderdoc\scripts\rdc_analyzer\ui_resource_counts.py').read())`
  - Expected: prints `ui_texture_count`, `ui_resource_count`

# Repo / File List (with line refs)
- `scripts/rdc_analyzer/rdc_parser.py` add chunk count utility + CLI flag
- `scripts/rdc_analyzer/analyze_rdc.py` include reconciliation summary
- `scripts/rdc_analyzer/tests/test_chunk_reconciliation.py` (new)
- `scripts/rdc_analyzer/ui_resource_counts.py` (new helper for UI Shell)
- `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_VERIFICATION.md` record reconciliation results

# Approach (Pseudo-code)
```python
# rdc_parser.py
def count_chunks(data):
    counts = Counter(chunk.chunk_id for chunk in parse_chunks(data))
    return {
        "vkCreateShaderModule": counts[VulkanChunk.vkCreateShaderModule],
        "vkCreateShadersEXT": counts[VulkanChunk.vkCreateShadersEXT],
        "vkCreateImage": counts[VulkanChunk.vkCreateImage],
    }

# analyze_rdc.py
summary["reconcile_chunks"] = {
    "shader_chunk_total": shader_module + shader_object,
    "texture_chunk_total": image_count,
    "shader_count": len(shaders),
    "texture_count": len(texture_details),
    "shader_ratio": ratio(shader_count, shader_chunk_total),
    "texture_ratio": ratio(texture_count, texture_chunk_total),
}

# ui_resource_counts.py (RenderDoc UI)
cap = pyrenderdoc.OpenCaptureFile()
controller = cap.OpenCapture(...)
print(texture_count, resource_count)
```

# Impact Analysis
- Adds explicit “completeness ratio” to report; if ratio below threshold, report flags incomplete.
- UI-based reconciliation relies on RenderDoc UI shell; cannot be automated headless.

# Action Items (2-5 min each; WHAT/WHY/HOW)
- [x] 1. TDD: chunk reconciliation unit test
  - WHAT: test chunk count calculation with fake chunk list.
  - WHY: ensure ratios computed correctly.
  - HOW:
    ```python
    assert result["shader_ratio"] == 0.5
    ```
- [x] 2. Implement chunk count utility in `rdc_parser.py`
  - WHAT: add `count_vulkan_chunks()` + CLI `--chunk-counts`.
  - WHY: make chunk counts visible and reusable.
  - HOW:
    ```python
    def count_vulkan_chunks(self):
        counts = Counter(...)
        return {...}
    ```
- [x] 3. Add reconciliation section in HTML/summary
  - WHAT: embed counts & ratios in `summary`.
  - WHY: surface “completeness” in report output.
  - HOW:
    ```python
    summary["reconcile_chunks"] = {...}
    ```
- [x] 4. Add UI resource count helper
  - WHAT: `ui_resource_counts.py` to print UI counts.
  - WHY: align with authoritative RenderDoc resource totals.
  - HOW:
    ```python
    textures = controller.GetTextures()
    resources = controller.GetResources()
    ```
- [x] 5. Update verification log
  - WHAT: log chunk counts + UI counts + ratios.
  - WHY: accurate report evidence.
  - HOW:
    ```markdown
    - shader_chunk_total: N
    - shader_count: M
    - shader_ratio: ...
    - ui_texture_count: ...
    ```

# Risks & Blockers
- UI counts require running in RenderDoc UI; cannot be done headless.
- Chunk layout changes may still cause extraction differences; ratios are “sanity bounds,” not exact parity.

# Verification / DoD
- Chunk counts printed + ratio computed.
- UI counts captured in log. (待执行：RenderDoc UI Python Shell)
- Report shows reconciliation section and flags if ratio < threshold (0.9).
- If ratio < 0.9, list differences and mark “approval required”.

# Open Questions
- UI counts: should we compare GetTextures only, or GetResources too?

# Next Steps
- 运行 RenderDoc UI Python Shell 采集 UI 侧资源计数并补充到验收记录。
