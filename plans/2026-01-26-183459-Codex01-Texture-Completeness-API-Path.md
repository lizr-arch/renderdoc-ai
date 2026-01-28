# Scope / Assumptions
- In scope: use **RenderDoc official Python API** as the **authoritative** texture source to raise completeness ratio ≥ 0.90.
- In scope: define **priority order** for texture metadata sources (manifest → replay API → chunk parse).
- Out of scope: building RenderDoc, modifying core C++ drivers, or changing 3rdparty/build outputs.
- Assumptions:
  - RenderDoc Python API is available **in UI shell or renderdoccmd** when needed.
  - If replay is unsupported locally, we must fall back gracefully and report gaps.

# Build / Test / Lint Quick Guide (record only)
- Unit tests:
  - `py -3 -m pytest scripts/rdc_analyzer/tests/test_texture_source_selection.py -v`
- Manual verification (texture export via official API):
  - `py -3 scripts/rdc_analyzer/export_textures.py "D:\renderdoc\goog pixel-9\g145-battle-2.rdc" -o "D:\renderdoc\goog pixel-9\g145-battle-2_textures"`
- Report regeneration:
  - `py -3 scripts/rdc_analyzer/analyze_rdc.py "D:\renderdoc\goog pixel-9\g145-battle-2.rdc" --output "D:\renderdoc\goog pixel-9\g145-battle-2_report.html"`

# Repo / File List (with line refs)
- `scripts/rdc_analyzer/analyze_rdc.py:299-520` (texture extraction + export manifest merge)
- `scripts/rdc_analyzer/rdc_parser.py:1795-1855` (chunk-based texture parse fallback)
- `scripts/rdc_analyzer/export_textures.py:54-232` (RenderDoc API texture export, replay controller path)
- `scripts/rdc_analyzer/main.py:404-420` (GetTextures usage reference)
- `scripts/rdc_analyzer/ui_resource_counts.py:1-84` (UI-side authoritative texture/resource counts)
- `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_VERIFICATION.md` (update verification record)
- `scripts/rdc_analyzer/tests/test_texture_source_selection.py` (new)

# Approach (Pseudo-code)
```python
def get_texture_metadata(rdc_path):
    # 1) manifest/textures.json (official export) → authoritative
    export = load_textures_from_export(rdc_path)
    if export.texture_list:
        return export.texture_list, "manifest"

    # 2) RenderDoc replay API (official, no image export)
    if renderdoc_available():
        meta = replay_get_textures(rdc_path)  # OpenCaptureFile → OpenCapture → GetTextures()
        if meta:
            return meta, "replay_api"

    # 3) Chunk parse fallback
    return extract_textures(rdc_path), "chunk_parse"

def compute_texture_ratio(parsed_count, ui_count=None, chunk_count=None):
    if ui_count is not None:
        return parsed_count / max(ui_count, 1)
    if chunk_count is not None:
        return parsed_count / max(chunk_count, 1)
    return 0.0
```

# Impact Analysis
- **Positive:** Texture list aligns with RenderDoc UI, completeness ratio becomes meaningful.
- **Risk:** Replay API requires compatible GPU; must handle `LocalReplaySupport != Supported`.
- **Edge:** Exported manifest may be stale; need to record source + timestamp in report.

# Action Items (2-5 min each; WHAT/WHY/HOW)
- [x] 1. TDD: add texture-source selection unit tests
  - WHAT: create `test_texture_source_selection.py` to validate priority order.
  - WHY: prevents regressions when multiple sources exist.
  - HOW:
    ```python
    result = choose_texture_source(manifest, replay, chunk)
    assert result.source == "manifest"
    ```
- [x] 2. Add replay‑API metadata path (no image export)
  - WHAT: new helper `replay_get_textures()` using `rd.OpenCaptureFile()` + `GetTextures()`.
  - WHY: official API is authoritative; avoids fragile chunk parsing.
  - HOW:
    ```python
    cap = rd.OpenCaptureFile()
    cap.OpenFile(rdc_path, "", None)
    status, controller = cap.OpenCapture(rd.ReplayOptions(), None)
    textures = controller.GetTextures()
    ```
- [x] 3. Integrate source selection into `analyze_rdc.py`
  - WHAT: choose texture metadata source in priority order and record `texture_source`.
  - WHY: makes completeness ratio meaningful and explainable.
  - HOW:
    ```python
    textures, source = get_texture_metadata(...)
    summary["texture_source"] = source
    ```
- [x] 4. Update completeness ratio to prefer UI counts
  - WHAT: ratio uses `ui_texture_count` when available; chunk ratio becomes diagnostic.
  - WHY: avoid false negatives from `vkCreateImage`.
  - HOW:
    ```python
    ratio = parsed / ui_count
    summary["texture_ratio_ui"] = ratio
    ```
- [ ] 5. Update verification log (blocked: no replay environment available)
  - WHAT: record source + ui counts + ratios.
  - WHY: evidence chain for acceptance.
  - HOW:
    ```markdown
    - texture_source: replay_api
    - ui_texture_count: N
    - texture_ratio_ui: 1.00
    ```

# Risks & Blockers
- RenderDoc replay not supported locally → must fall back and flag in report.
- Replay metadata path requires renderdoc module in runtime environment.
- Blocker: 当前无 Replay 环境，无法实测 `texture_source=manifest/replay_api` 与 `texture_ratio_ui`。

# Verification / DoD
- Unit tests for source selection pass.
- Report shows `texture_source` + `texture_ratio_ui`.
- For g145-battle-2, ratio_ui ≥ 0.90 or explicitly flagged with reason.

# Open Questions
- 是否允许在 `analyze_rdc.py` 中 **自动触发** replay API（需要 GPU），还是仅在用户手动导出后读取 manifest？

# Next Steps
- 补充 g145-battle-2 的 UI 计数 + 新 ratio 记录到验收日志。
