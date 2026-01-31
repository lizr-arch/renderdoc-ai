# Offline Texture Pixel Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-01-31
**Owner:** Codex Agent
**Last Updated:** 2026-01-31
**Plan File:** plans/2026-01-31-175557-Agent01-OfflineTexturePixels.md

**Goal:** Determine whether RDC stores texture pixel data that can be extracted without replay, and if feasible, implement an offline extractor for Vulkan captures.

**Architecture:** Reuse existing `rdc_parser` to locate InitialContents/texture resources in RDC sections, map resource -> format/layout, decode or emit DDS (raw) where possible, and produce a manifest for downstream Unity assembly.

**Tech Stack:** Python (`scripts/rdc_analyzer`), RenderDoc serialisation schema, RDC section/chunk parsing.

**Success Criteria (measurable):**
- For a Vulkan RDC, offline tool outputs at least 1 texture file (PNG or DDS) without opening a replay context.
- If pixel data is not present, tool outputs a manifest marking textures as “metadata-only” with explicit reason codes.

**Acceptance Criteria:**
- Offline run produces a deterministic output directory with manifest + extracted textures (or metadata-only entries).
- Logs clearly state whether pixel extraction succeeded or why it was skipped.

**Verification Commands:**
- `py -3 scripts/rdc_analyzer/offline_extract_textures.py "D:\\backup\\大远景.rdc" -o D:\\backup\\offline_tex`  
  Expected: `Extracted <n> textures` or `No pixel data available (metadata-only)`
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_offline_texture_extraction.py`  
  Expected: `= ... passed`

**Evidence:**
- Output dir: `D:\backup\offline_tex\`
- Manifest: `D:\backup\offline_tex\manifest.json`
- Payload sample: `D:\backup\offline_tex\textures\tex_00000001.bin`
- Vulkan InitialContents serialises `type` then `ResourceId` at chunk start (`vk_initstate.cpp:1110-1111`), so chunk → resource_id mapping is feasible.
- `VkResourceType` enum values: `eResDeviceMemory=5`, `eResImage=8` (`vk_resources.h:56-64`).

**Estimation:**
- Effort: 1–2 days
- Story Points: 3
- Original Estimate: 2 days

**Risk Register (impact/likelihood/mitigation):**
- Missing pixel data in RDC (High/Medium): detect and gracefully fallback to metadata-only.
- Unknown/tiling layouts for Vulkan images (High/High): prefer DDS output for raw blocks; document unsupported layouts.
- Compressed formats (ASTC/ETC/BC) (Medium/High): emit DDS/KTX2 if decoding not possible without new deps.
- Chunk layout ambiguity (High/Medium): accept only payloads where size matches chunk tail; otherwise mark as metadata-only.
- Repo hygiene (Low/Low): user approved committing docs; do not commit temp files; ignore unrelated untracked docs not created in this task.

---

## Game Dev: Memory & Resource Budget (Leak Checks)
- Track per-texture byte size from RDC metadata; warn if output total exceeds configured cap (e.g., 2–4 GB).
- If extraction creates large temporary buffers, ensure streaming/chunked reads and cleanup after each texture.

## Game Dev: Asset Pipeline
- Source: `.rdc` → offline extractor → `manifest.json` + `*.dds`/`*.png`.
- Output should be deterministic and Unity-importable (DDS preferred for compressed GPU blocks).
- Define a stable folder layout: `textures/`, `manifest.json`, `logs.txt`.

## Game Dev: Crash Repro + Dumps/Symbols
- Repro with `D:\backup\大远景.rdc` and record exact command.
- If native crash in parsing occurs, collect stack trace via Python traceback and store in log.

---

## Scope
### In
- Vulkan capture: scan RDC sections for InitialContents/texture resource payloads.
- Implement offline extraction pipeline or explicit “metadata-only” fallback.

### Out
- D3D12/GLES offline extraction.
- Full texture format conversion to Unity-native assets (beyond DDS/PNG).

## Assumptions
- `TEXTURE_EXTRACTION.md` is authoritative for existing extraction paths.
- If initial contents exist, they are stored in InitialContents chunks in RDC.
- No new dependencies unless explicitly approved.

## Repo / File List
- `scripts/rdc_analyzer/docs/TEXTURE_EXTRACTION.md` (append offline note)
- `scripts/rdc_analyzer/rdc_parser.py:1410-1495` (FrameCapture data + chunk parsing)
- `scripts/rdc_analyzer/offline_extract_textures.py:11-120` (offline CLI + payload parsing)
- `scripts/rdc_analyzer/tests/test_offline_texture_extraction.py:16-150` (unit tests)
- `renderdoc/driver/vulkan/vk_initstate.cpp:1105-1622` (InitialContents serialisation order)
- `renderdoc/driver/vulkan/vk_resources.h:54-72` (VkResourceType enum)
- `renderdoc/core/resource_manager.h:1050-1624` (InitialContents chunk emit)
- `docs/analysis/RDC_PARSING_INDEX.md:232-233` (SystemChunk mapping)

## Approach (Pseudo-code)
```python
def offline_extract_textures(rdc_path, out_dir):
    texture_meta = extract_textures(rdc_path)  # metadata path
    fc_data = get_frame_capture_data(rdc_path)
    chunks = parse_chunks(fc_data)

    payloads = {}
    for chunk in chunks:
        if chunk.chunk_id == SYSTEM_CHUNK_INITIAL_CONTENTS:
            blob = fc_data[chunk.data_offset:chunk.data_offset + chunk.length]
            parsed = parse_initial_contents_payload(blob)
            if parsed:
                res_id, payload = parsed
                payloads[res_id] = payload

    entries = build_manifest_entries(texture_meta, payloads, out_dir)
    write_payload_files(entries, payloads, out_dir)
    write_manifest(entries, out_dir)
```

## Build/Test/Lint Quick Guide (commands only, do not run)
- Unit tests: `py -3 -m pytest scripts/rdc_analyzer/tests/test_offline_texture_extraction.py`
  - Expected: `= ... passed`
- Manual run: `py -3 scripts/rdc_analyzer/offline_extract_textures.py "D:\\backup\\大远景.rdc" -o D:\\backup\\offline_tex`
  - Expected: `Extracted <n> textures` or `metadata-only`

## Action Items (2–5 min granularity)
- [x] Inspect `rdc_parser.extract_textures()` to confirm it only returns metadata.
- [x] Locate InitialContents section/chunk mapping in `docs/analysis/RDC_PARSING_INDEX.md`.
- [x] Trace `InitialContents` handling in `resource_manager.h` and Vulkan driver code to confirm payload format.
- [x] Review official texture export example to confirm it relies on replay support.
- [x] Define a minimal payload map: resource_id -> bytebuf slice.
- [x] Write failing test for “metadata-only when no payload”.
- [x] Draft `offline_extract_textures.py` CLI skeleton (no new deps).
- [x] Implement minimal payload parsing for InitialContents chunks (Vulkan only).
- [ ] Emit raw payload files (no decode) and update manifest status.
- [ ] Run tests; record output path in Evidence.
- [ ] Update `TEXTURE_EXTRACTION.md` with offline pixel extraction findings.

## Risks & Blockers
- Payload may be GPU-tiling or proprietary layout; offline decode may be infeasible.
- Large captures can exceed memory if not streamed; need chunked reads.
- Vulkan InitialContents serialises raw memory bytes (`ContentsSize`/`Contents`) for `eResImage` and `eResDeviceMemory`, but mapping to image layout/mip/subresource is not yet resolved.
- Official Python example saves textures via ReplayController and checks LocalReplaySupport; no documented offline texture export path.
- User approved committing docs; exclude any `tmp` files; ignore unrelated untracked docs not created in this task.

## Open Questions
- Does `InitialContents` include full pixel data for Vulkan images, or only resource handles?
- Are compressed formats stored in GPU-native blocks that can be wrapped to DDS without decode?
- Any existing tool in repo to decode ASTC/ETC/BC without new deps?

---

## Task Plan (Next Batch, TDD)

### Task 1: Parse InitialContents payloads (Vulkan only)

**Files:**
- Modify: `scripts/rdc_analyzer/offline_extract_textures.py:11-78`
- Modify: `scripts/rdc_analyzer/tests/test_offline_texture_extraction.py:32-80`

**Step 1: Write the failing test**

```python
def test_parse_initial_contents_payload_exact_tail():
    # type=eResImage(8), id=1, size=4, payload=b"DATA"
    blob = struct.pack("<IQQ", 8, 1, 4) + b"DATA"
    res_id, payload = oet.parse_initial_contents_payload(blob)
    assert res_id == 1
    assert payload == b"DATA"
```

**Step 2: Run test to verify it fails**

Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_offline_texture_extraction.py::test_parse_initial_contents_payload_exact_tail`  
Expected: FAIL with `AttributeError: module has no attribute parse_initial_contents_payload`

**Step 3: Write minimal implementation**

```python
def parse_initial_contents_payload(chunk_data: bytes) -> Optional[Tuple[int, bytes]]:
    if len(chunk_data) < 20:
        return None
    res_type = struct.unpack_from("<I", chunk_data, 0)[0]
    res_id = struct.unpack_from("<Q", chunk_data, 4)[0]
    if res_type not in (5, 8):
        return None
    for offset in (12, 16, 20, 24):
        if offset + 8 > len(chunk_data):
            continue
        size = struct.unpack_from("<Q", chunk_data, offset)[0]
        payload_start = offset + 8
        payload_end = payload_start + size
        if size > 0 and payload_end == len(chunk_data):
            return res_id, chunk_data[payload_start:payload_end]
    return None
```

**Step 4: Run test to verify it passes**

Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_offline_texture_extraction.py::test_parse_initial_contents_payload_exact_tail`  
Expected: PASS

**Step 5: Commit**

```bash
git add scripts/rdc_analyzer/offline_extract_textures.py scripts/rdc_analyzer/tests/test_offline_texture_extraction.py
git commit -m "feat(rdc-analyzer): parse InitialContents payloads for Vulkan

- add chunk payload parser for eResImage/eResDeviceMemory
- cover payload tail parsing in tests"
```

### Task 2: Wire payload parsing into offline extractor

**Files:**
- Modify: `scripts/rdc_analyzer/offline_extract_textures.py:11-78`
- Modify: `scripts/rdc_analyzer/tests/test_offline_texture_extraction.py:32-110`

**Step 1: Write the failing test**

```python
def test_payloads_mapped_to_manifest(tmp_path: Path):
    tex = _make_texture(resource_id=1)
    payloads = {1: b"DATA"}
    entries = oet.build_manifest_entries([tex], payloads, tmp_path)
    assert entries[0]["status"] == "payload_present"
```

**Step 2: Run test to verify it fails**

Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_offline_texture_extraction.py::test_payloads_mapped_to_manifest`  
Expected: FAIL with assertion mismatch (status still metadata_only)

**Step 3: Write minimal implementation**

```python
if tex.resource_id in payloads:
    entry["status"] = "payload_present"
    entry["reason"] = None
```

**Step 4: Run test to verify it passes**

Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_offline_texture_extraction.py::test_payloads_mapped_to_manifest`  
Expected: PASS

**Step 5: Commit**

```bash
git add scripts/rdc_analyzer/offline_extract_textures.py scripts/rdc_analyzer/tests/test_offline_texture_extraction.py
git commit -m "feat(rdc-analyzer): mark manifest entries with payload presence

- set status=payload_present when bytes are found
- add unit test for manifest mapping"
```

### Task 3: Save raw payloads (no decode) and update docs

**Files:**
- Modify: `scripts/rdc_analyzer/offline_extract_textures.py:11-120`
- Modify: `scripts/rdc_analyzer/tests/test_offline_texture_extraction.py:32-150`
- Modify: `scripts/rdc_analyzer/docs/TEXTURE_EXTRACTION.md` (append section)

**Step 1: Write the failing test**

```python
def test_payload_file_written(tmp_path: Path):
    tex = _make_texture(resource_id=1)
    entries = oet.build_manifest_entries([tex], {1: b"DATA"}, tmp_path)
    oet.write_payload_files(entries, {1: b"DATA"}, tmp_path)
    assert (tmp_path / "textures" / "tex_00000001.bin").exists()
```

**Step 2: Run test to verify it fails**

Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_offline_texture_extraction.py::test_payload_file_written`  
Expected: FAIL with `AttributeError: module has no attribute write_payload_files`

**Step 3: Write minimal implementation**

```python
def write_payload_files(entries: List[dict], payloads: Dict[int, bytes], out_dir: Path) -> None:
    tex_dir = out_dir / "textures"
    tex_dir.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        res_id = entry["resource_id"]
        if res_id in payloads:
            name = f"tex_{res_id:08x}.bin"
            (tex_dir / name).write_bytes(payloads[res_id])
            entry["file"] = f"textures/{name}"
```

**Step 4: Run test to verify it passes**

Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_offline_texture_extraction.py::test_payload_file_written`  
Expected: PASS

**Step 5: Commit**

```bash
git add scripts/rdc_analyzer/offline_extract_textures.py scripts/rdc_analyzer/tests/test_offline_texture_extraction.py scripts/rdc_analyzer/docs/TEXTURE_EXTRACTION.md
git commit -m "feat(rdc-analyzer): emit raw payload files offline

- write payload .bin files when bytes exist
- document offline payload output and limitations"
```

## Next Steps
- Proceed to `/do` once plan is approved.
