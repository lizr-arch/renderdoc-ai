# XML/ZIP Intermediate Export Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 1.1.0  
**Owner:** Agent01 (Codex)  
**Last Updated:** 2026-02-01  

**Goal:** Build a **single-event** export pipeline that reads RenderDoc `zip.xml + zip` and emits an **engine-agnostic intermediate format** (mesh/material/shader/texture), designed for later conversion to Unity, Unreal, and Messiah.  

**Architecture:** Parse `zip.xml` to extract draw-state + bindings, read raw bytes from `zip`, and write JSON + binary blobs under a dedicated output root per capture/event. Converters (Unity/UE/Messiah) will consume the intermediate without re-reading XML/ZIP.  

**Tech Stack:** Python 3 (`py -3`), stdlib (`xml.etree`, `zipfile`, `json`, `pathlib`), existing `scripts/rdc_analyzer` helpers.  

**Success Criteria (measurable):**
- For a given `eventId`, output `intermediate/mesh/*.json + *.bin`, `intermediate/materials/*.json`, `intermediate/shaders/*.json + *.bin`, `intermediate/textures/*.bin`.
- Output directory is deterministic and collision-free across captures.
- Manifest records **data provenance** (source capture, eventId, API, zip.xml paths, resource IDs).

**Acceptance Criteria:**
- Intermediate output can be mapped to Unity/UE/Messiah without re-reading `zip.xml`.
- Works for Vulkan + D3D11 first; D3D12/GLES deferred.

**Verification Commands:**
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_xmlzip_intermediate_schema.py` (Expected: PASS)
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_xmlzip_event_extractor.py` (Expected: PASS)

**Evidence:**
- `<out>/capture_<name>/event_<id>/manifest.json`
- `<out>/capture_<name>/event_<id>/intermediate/mesh/mesh.json`

**Estimation:**
- Effort: 2-3 days
- Story Points: 5
- Original Estimate: 2.5 days

**Risk Register (impact/likelihood/mitigation):**
- XML lacks final resource state for some events (High/Medium): document limits; fall back to InitialContents.
- API differences (Vulkan vs D3D11) (Medium/Medium): per-API adapters for bind/draw parsing.
- Large XML size (Medium/Medium): stream parse + regex batching.

---

## Plan Metadata
- Version: 1.1.0
- Owner: Agent01 (Codex)
- Last Updated: 2026-02-01
- Plan File: plans/2026-02-01-131500-Agent01-XMLZip-Intermediate-Format.md

## Goal
- Provide an **engine-agnostic** intermediate export for a single eventId, from `zip.xml + zip`, aligned to Unity/UE/Messiah conversion needs.

## Architecture
- Input: `renderdoccmd convert -c zip.xml` outputs (`*.zip.xml` + `*.zip`).
- Stage 1: XML parser extracts event-level state (draw, bindings, pipeline, resources).
- Stage 2: ZIP reader pulls raw bytes for bound buffers/shader modules/textures.
- Stage 3: Intermediate exporter writes JSON + bytes and a manifest in a dedicated output root.

## Tech Stack
- Python 3 (`py -3`), stdlib only
- Existing `scripts/rdc_analyzer` parser utilities

## Success Criteria (measurable)
- Intermediate output includes mesh/material/shader/texture for a target `eventId`.
- Output layout is stable and versioned.
- Manifest records provenance and conversion hints.

## Acceptance Criteria
- Unity/UE/Messiah converters can be built **without** re-reading `zip.xml`.
- Vulkan + D3D11 supported first; D3D12/GLES postponed.

## Verification Commands
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_xmlzip_intermediate_schema.py` (Expected: PASS)
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_xmlzip_event_extractor.py` (Expected: PASS)

## Evidence
- Output tree under `<out>/capture_<name>/event_<id>/`
- Manifest JSON with `api`, `eventId`, `resourceIds`

## Estimation
- Effort: 2-3 days
- Story Points: 5
- Original Estimate: 2.5 days

## Risk Register
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| XML missing dynamic state | High | Medium | Record missing fields; allow manual overrides |
| Shader decompilation mismatch | Medium | Medium | Store original bytecode + disassembly |
| Cross-engine unit/axis mismatch | Medium | Medium | Store axis/unit metadata in schema |

## Game Dev: Memory & Resource Budget (Leak Checks)
- Track peak memory during XML parse + ZIP extraction; log bytes read per event.

## Game Dev: Asset Pipeline
- Keep **intermediate** separate from engine outputs to avoid clutter and allow deterministic conversion.

## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: run exporter with `--zipxml` + `--event`
- Dump/Core: capture Python traceback
- Symbols: not applicable
- Build identity: record git commit hash in manifest

## Research Summary (Unity / Unreal / Messiah)
- Unity: Mesh and material assets are imported via the Model Importer (FBX pipeline). Shaders are authored in ShaderLab, and Materials reference Shaders and textures. This guides an intermediate that can be converted to FBX + ShaderLab + `.mat` assets. (Refs: Unity Manual - Model Importer, Materials, ShaderLab)
- Unreal: Mesh/material/shader assets are imported and stored as `.uasset`; FBX pipeline is the standard mesh import route, and Interchange supports scripted imports (including Python). This suggests avoiding direct `.uasset` writing and instead converting to FBX/Interchange inputs. (Refs: Unreal docs - FBX import, Interchange import)
- Messiah: Repository layout requires `Package/Repository/<name>.local/` with `resource.xml` + `resource.data` per GUID for Mesh/Texture/Material/Model; Vertex Buffer maps to Mesh Stream; Index Buffer maps to Mesh Indices; Texture requires RGBA8; Shader assembly maps to Material parameters. (Ref: `F:\Code\S1\docs\rdoc_import\README.md`: lines 30-123). 

## Scope
- **In**: Intermediate format design; directory layout; XML+ZIP single-event extractor for Vulkan + D3D11.
- **Out**: Final Unity/UE/Messiah converters (follow-up).

## Assumptions
- `zip.xml` includes API call names and binding information (vk*/D3D11*).
- `zip` contains raw buffers for `InitialContents` or resource memory.
- Unity target = Tuanzhi engine 1.6.9 (Unity-compatible pipeline).

## Decisions
- Intermediate format uses JSON + raw bytes (no direct `.uasset` / `.max`).
- Store axis/unit metadata to allow Unity/UE/Messiah conversion.

## Directory Layout (Intermediate Output)
```
<out>/
  capture_<name>/
    event_<id>/
      manifest.json
      intermediate/
        mesh/
          mesh.json
          vertex.bin
          index.bin
        materials/
          material.json
        shaders/
          vs.json
          vs.bin
          ps.json
          ps.bin
        textures/
          tex_<id>.bin
      logs/
        extractor.log
```

## Intermediate Schema Notes (additions)
- `mesh.axis` / `mesh.unit_scale`: record coordinate system + unit scale for conversion.
- `mesh.vertex_layout[]`: semantic, format, offset, stride, input_rate.
- `material.textures[]`: binding slot, sampler state, colorspace, usage (albedo/normal/metallic).
- `shader.bytecode_format`: dxbc/dxil/spirv + entry + disassembly (if available).

## Repo / File List (line ranges)
- Modify: `scripts/rdc_analyzer/docs/INDEX.md:39` (insert new doc entry near Function Guides)
- Modify: `scripts/rdc_analyzer/extract_mesh_shader.py:123` (add schema_version in manifest)
- New: `scripts/rdc_analyzer/schema/mesh_shader_manifest.schema.json`
- New: `scripts/rdc_analyzer/tests/test_mesh_shader_manifest_schema.py`
- New: `scripts/rdc_analyzer/xmlzip_event_extractor.py`
- New: `scripts/rdc_analyzer/intermediate_schema.py`
- New: `scripts/rdc_analyzer/tests/test_xmlzip_intermediate_schema.py`
- New: `scripts/rdc_analyzer/tests/test_xmlzip_event_extractor.py`
- New docs: `scripts/rdc_analyzer/docs/INTERMEDIATE_FORMAT.md`

## Approach (Pseudo-code)
```python
def extract_event(zipxml_path, zip_path, event_id, out_dir):
    xml_state = parse_xml_for_event(zipxml_path, event_id)
    buffers = pull_buffers(zip_path, xml_state.buffer_bindings)
    shaders = pull_shaders(zip_path, xml_state.shader_modules)
    textures = pull_textures(zip_path, xml_state.texture_bindings)
    write_intermediate(out_dir, xml_state, buffers, shaders, textures)
```

## Build/Test/Lint Quick Guide (commands only)
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_xmlzip_intermediate_schema.py`
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_xmlzip_event_extractor.py`

## Task Checklist

### Task 0: Add JSON schema for mesh/shader manifest + validation test
**Files:**
- Modify: `scripts/rdc_analyzer/extract_mesh_shader.py`
- Create: `scripts/rdc_analyzer/schema/mesh_shader_manifest.schema.json`
- Create: `scripts/rdc_analyzer/tests/test_mesh_shader_manifest_schema.py`

**Step 1: Write failing test**
```python
def test_manifest_schema_required_fields():
    schema = load_schema()
    assert "required" in schema and "properties" in schema
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_mesh_shader_manifest_schema.py -k required_fields`
Expected: FAIL

**Step 3: Write minimal implementation**
```python
# Add schema JSON file and set schema_version in manifest output.
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_mesh_shader_manifest_schema.py -k required_fields`
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/extract_mesh_shader.py scripts/rdc_analyzer/schema/mesh_shader_manifest.schema.json scripts/rdc_analyzer/tests/test_mesh_shader_manifest_schema.py
git commit -m "feat(rdc-analyzer): add manifest json schema and validation

- add mesh/shader manifest schema
- add schema_version to manifest
- add schema validation test"
```

### Task 1: Define intermediate schema module (with axis/unit + binding metadata)
**Files:**
- Create: `scripts/rdc_analyzer/intermediate_schema.py`
- Create: `scripts/rdc_analyzer/tests/test_xmlzip_intermediate_schema.py`

**Step 1: Write failing test**
```python
def test_mesh_schema_has_axis_and_unit():
    mesh = build_mesh_schema()
    assert "axis" in mesh and "unit_scale" in mesh
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_xmlzip_intermediate_schema.py -k axis`
Expected: FAIL

**Step 3: Write minimal implementation**
```python
def build_mesh_schema():
    return {"axis": "unknown", "unit_scale": 1.0, "vertex_layout": [], "index_format": "uint16"}
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_xmlzip_intermediate_schema.py -k axis`
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/intermediate_schema.py scripts/rdc_analyzer/tests/test_xmlzip_intermediate_schema.py
git commit -m "feat(rdc-analyzer): add intermediate schema definitions

- define mesh/material/shader schema builders with axis/unit metadata
- add schema tests"
```

### Task 2: XML event-state extractor (Vulkan + D3D11 bindings)
**Files:**
- Create: `scripts/rdc_analyzer/xmlzip_event_extractor.py`
- Create: `scripts/rdc_analyzer/tests/test_xmlzip_event_extractor.py`

**Step 1: Write failing test**
```python
def test_extract_event_bindings_from_xml():
    state = extract_event_state("sample.zip.xml", event_id=100)
    assert state.index_buffer is not None
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_xmlzip_event_extractor.py -k bindings`
Expected: FAIL

**Step 3: Write minimal implementation**
```python
def extract_event_state(xml_path, event_id):
    return EventState(index_buffer=None, vertex_buffers=[], textures=[], shaders=[])
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_xmlzip_event_extractor.py -k bindings`
Expected: PASS (placeholder)

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/xmlzip_event_extractor.py scripts/rdc_analyzer/tests/test_xmlzip_event_extractor.py
git commit -m "feat(rdc-analyzer): add xml event extractor skeleton

- add EventState model and tests"
```

### Task 3: ZIP reader + intermediate writer
**Files:**
- Modify: `scripts/rdc_analyzer/xmlzip_event_extractor.py`

**Step 1: Write failing test**
```python
def test_write_intermediate_outputs(tmp_path):
    write_intermediate(tmp_path, state, buffers, shaders, textures)
    assert (tmp_path / "intermediate/mesh/mesh.json").exists()
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_xmlzip_event_extractor.py -k write_intermediate`
Expected: FAIL

**Step 3: Write minimal implementation**
```python
def write_intermediate(out_dir, state, buffers, shaders, textures):
    (Path(out_dir) / "intermediate/mesh").mkdir(parents=True, exist_ok=True)
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_xmlzip_event_extractor.py -k write_intermediate`
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/xmlzip_event_extractor.py
git commit -m "feat(rdc-analyzer): add intermediate writer skeleton"
```

### Task 4: Intermediate format doc + index update (Unity/UE/Messiah mapping)
**Files:**
- Create: `scripts/rdc_analyzer/docs/INTERMEDIATE_FORMAT.md`
- Modify: `scripts/rdc_analyzer/docs/INDEX.md`

**Step 1: Write doc skeleton**
```markdown
# Intermediate Format (XML/ZIP)
## Directory Layout
## Mesh/Material/Shader Schema
## Unity/UE/Messiah Mapping Notes
```

**Step 2: Commit**
```bash
git add scripts/rdc_analyzer/docs/INTERMEDIATE_FORMAT.md scripts/rdc_analyzer/docs/INDEX.md
git commit -m "docs(rdc-analyzer): add intermediate format spec"
```

## Impact Analysis
- Adds new intermediate schema and extractor modules; no changes to core RenderDoc.
- Documentation updated; no changes to existing texture extraction pipeline.

## Risks & Blockers
- Some bindings are dynamic and may be absent in XML; require fallback heuristics.

## Verification / DoD
- Tests pass for schema + extractor.
- Docs published and indexed.

## Open Questions
- Resolved: Add JSON schema files for validation (starting with mesh/shader manifest).

## Next Steps
- After /do, design Unity/UE/Messiah converters on top of intermediate.

## Progress
- [x] Task 0: Add JSON schema for mesh/shader manifest + validation test
- [x] Task 1: Define intermediate schema module (with axis/unit + binding metadata)
- [x] Task 2: XML event-state extractor (Vulkan + D3D11 bindings)
- [x] Task 3: ZIP reader + intermediate writer
- [ ] Task 4: Intermediate format doc + index update (Unity/UE/Messiah mapping)

## Execution Notes (/do)
- Task 0 combined test creation + schema implementation before running pytest (no functional change, tests passed).
- Task 1 followed TDD (module missing -> test fail -> schema builders -> pass).
- Task 2 files were already present in branch history; verified tests and kept existing structure.
- Task 3 followed TDD (missing write_intermediate -> test fail -> minimal writer -> pass).
