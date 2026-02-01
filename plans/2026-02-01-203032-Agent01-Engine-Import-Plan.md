# Engine Import (Messiah → Unity → Unreal) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 1.0.1  
**Owner:** Agent01 (Codex)  
**Last Updated:** 2026-02-01  
**Plan File:** plans/2026-02-01-203032-Agent01-Engine-Import-Plan.md  

## Goal
- Build engine importers that consume the existing intermediate export and emit **engine‑ready assets**, with **Messiah first**, then **Unity China 1.6.9**, then **Unreal**.

## Architecture
- Treat the intermediate output (`intermediate/mesh|materials|shaders|textures`) as the **single source of truth**.
- Implement per‑engine exporters under `scripts/rdc_analyzer/exporters/`, each writing a dedicated output tree without touching RenderDoc core.
- Use **deterministic hash GUIDs** for Messiah; output a minimal **Mesh + Texture + Material + Model** loop to render in engine.

## Tech Stack
- Python 3 (`py -3`), stdlib only
- Existing intermediate schema + decoder output in `scripts/rdc_analyzer/`

## Success Criteria (measurable)
- For one eventId, Messiah exporter writes a valid repository under:
  `.../messiah/Package/Repository/rdc_event_<eventId>.local/`
- GUID generation is deterministic for identical inputs.
- Unity/Unreal exporters generate importable asset stubs (OBJ/ShaderLab and FBX/Interchange inputs respectively).

## Acceptance Criteria
- Messiah: Mesh + Texture + Material + Model are generated with correct GUID linkage and load in editor.
- Unity: Assets import into Unity China 1.6.9 and can be manually assembled.
- Unreal: Assets import via FBX/Interchange pipeline without re-reading zip.xml.

## Verification Commands
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_messiah_guid_determinism.py` (Expected: PASS)
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_messiah_repository_layout.py` (Expected: PASS)
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_messiah_material_mapping.py` (Expected: PASS)

## Evidence
- `<out>/capture_<name>/event_<id>/messiah/Package/Repository/rdc_event_<eventId>.local/resource.repository`
- `<out>/capture_<name>/event_<id>/messiah/.../Mesh/<prefix>/<guid>/resource.xml`
- `<out>/capture_<name>/event_<id>/messiah/.../Model/<prefix>/<guid>/resource.xml`

## Estimation
- Effort: 2–3 days
- Story Points: 5
- Original Estimate: 2.5 days

## Risk Register
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Messiah XML schema mismatch | High | Medium | Follow official templates; add layout tests |
| Shader→material mapping incomplete | Medium | Medium | Unlit fallback + explicit mapping table |
| Intermediate lacks tangents/skin | Medium | Medium | Document unsupported semantics |

## Game Dev: Memory & Resource Budget (Leak Checks)
- Log bytes written per resource; verify no duplicate writes on same GUID in a single run.

## Game Dev: Asset Pipeline
- Keep engine outputs in a separate `messiah/` folder under event root.
- Use deterministic GUIDs to make re‑export idempotent.

## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: run exporter on one eventId, load repository in editor.
- Dump/Core: (minidump | core dump) TBD
- Symbols: (PDB | dSYM | ELF | DWARF) TBD
- Build identity: (build id | commit hash | git commit) TBD

---

## Scope
**In**
- Messiah exporter end‑to‑end (repository + resources + minimal model)
- Unity/Unreal exporter stubs + doc scaffolding

**Out**
- Full runtime integration (editor launch/import automation)
- D3D12/GLES targets

---

## Assumptions
- Intermediate output already exists per event under `<out>/.../intermediate/`
- Textures are RGBA8 or already decoded
- Shader disassembly is available for material mapping

---

## Repo / File List (line ranges)
**Modify**
- `scripts/rdc_analyzer/docs/INTERMEDIATE_FORMAT.md:1` (add Messiah/Unity/Unreal import notes + output structure)
- `scripts/rdc_analyzer/docs/INDEX.md:1` (add new import docs)

**Create**
- `scripts/rdc_analyzer/export_messiah_assets.py` (CLI entry)
- `scripts/rdc_analyzer/exporters/messiah_exporter.py` (core conversion)
- `scripts/rdc_analyzer/exporters/engine_guid.py` (hash GUID helper)
- `scripts/rdc_analyzer/docs/MESSIAH_IMPORT.md`
- `scripts/rdc_analyzer/docs/UNITY_IMPORT.md`
- `scripts/rdc_analyzer/docs/UNREAL_IMPORT.md`
- `scripts/rdc_analyzer/tests/test_messiah_repository_layout.py`
- `scripts/rdc_analyzer/tests/test_messiah_guid_determinism.py`
- `scripts/rdc_analyzer/tests/test_messiah_material_mapping.py`

---

## Output Layout (Messiah)
```
<out>/capture_<name>/event_<id>/
  messiah/
    Package/Repository/rdc_event_<eventId>.local/
      resource.repository
      Mesh/<prefix2>/<guid>/resource.xml
      Mesh/<prefix2>/<guid>/resource.data
      Texture/<prefix2>/<guid>/texture.xml
      Texture/<prefix2>/<guid>/resource.data
      Material/<prefix2>/<guid>/resource.xml
      Model/<prefix2>/<guid>/resource.xml
```

---

## Task Checklist (TDD‑style, 2–5 min steps)

### Task 1 — Deterministic GUID helper
**Files:**
- Create: `scripts/rdc_analyzer/exporters/engine_guid.py`
- Create: `scripts/rdc_analyzer/tests/test_messiah_guid_determinism.py`

**Step 1: Write failing test**
```python
def test_guid_hash_is_deterministic():
    from exporters.engine_guid import hash_guid
    assert hash_guid("Mesh", 100, "vb0") == hash_guid("Mesh", 100, "vb0")
```
**Step 2: Run test to verify it fails**  
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_messiah_guid_determinism.py -k deterministic`  
Expected: FAIL

**Step 3: Write minimal implementation**
```python
def hash_guid(kind, event_id, key):
    # uuid5 with fixed namespace + f"{kind}:{event_id}:{key}"
```
**Step 4: Run test to verify it passes**  
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_messiah_guid_determinism.py -k deterministic`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/exporters/engine_guid.py scripts/rdc_analyzer/tests/test_messiah_guid_determinism.py
git commit -m "feat(rdc-analyzer): add deterministic guid helper"
```

---

### Task 2 — Repository skeleton writer
**Files:**
- Create: `scripts/rdc_analyzer/exporters/messiah_exporter.py`
- Create: `scripts/rdc_analyzer/tests/test_messiah_repository_layout.py`

**Step 1: Write failing test**
```python
def test_repository_layout(tmp_path):
    from exporters.messiah_exporter import write_repo_skeleton
    root = write_repo_skeleton(tmp_path, event_id=100)
    assert (root / "resource.repository").exists()
```
**Step 2: Run test to verify it fails**  
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_messiah_repository_layout.py -k repository_layout`  
Expected: FAIL

**Step 3: Write minimal implementation**
```python
def write_repo_skeleton(out_dir, event_id):
    # create Package/Repository/rdc_event_<eventId>.local + resource.repository
```
**Step 4: Run test to verify it passes**  
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_messiah_repository_layout.py -k repository_layout`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/exporters/messiah_exporter.py scripts/rdc_analyzer/tests/test_messiah_repository_layout.py
git commit -m "feat(rdc-analyzer): add messiah repository skeleton"
```

---

### Task 3 — Material mapping (shader‑driven, Unlit fallback)
**Files:**
- Modify: `scripts/rdc_analyzer/exporters/messiah_exporter.py`
- Create: `scripts/rdc_analyzer/tests/test_messiah_material_mapping.py`

**Step 1: Write failing test**
```python
def test_material_follows_shader_or_fallback():
    from exporters.messiah_exporter import build_material_xml
    xml = build_material_xml(shader_kind="ps", fallback="unlit")
    assert "Unlit" in xml
```
**Step 2: Run test to verify it fails**  
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_messiah_material_mapping.py -k material`  
Expected: FAIL

**Step 3: Write minimal implementation**
```python
def build_material_xml(shader_kind, fallback):
    # map known shader to template; else fallback
```
**Step 4: Run test to verify it passes**  
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_messiah_material_mapping.py -k material`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/exporters/messiah_exporter.py scripts/rdc_analyzer/tests/test_messiah_material_mapping.py
git commit -m "feat(rdc-analyzer): add messiah material mapping"
```

---

### Task 4 — Messiah CLI entry (consume intermediate)
**Files:**
- Create: `scripts/rdc_analyzer/export_messiah_assets.py`
- Modify: `scripts/rdc_analyzer/exporters/messiah_exporter.py`

**Step 1: Write failing test**
```python
def test_cli_writes_repository(tmp_path):
    # call main() with intermediate path and check output repo
```
**Step 2: Run test to verify it fails**  
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_messiah_repository_layout.py -k cli`  
Expected: FAIL

**Step 3: Write minimal implementation**
```python
def main():
    # parse args, call export_messiah()
```
**Step 4: Run test to verify it passes**  
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_messiah_repository_layout.py -k cli`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/export_messiah_assets.py scripts/rdc_analyzer/exporters/messiah_exporter.py
git commit -m "feat(rdc-analyzer): add messiah export cli"
```

---

### Task 5 — Unity / Unreal import stubs (docs + scaffolding)
**Files:**
- Create: `scripts/rdc_analyzer/docs/UNITY_IMPORT.md`
- Create: `scripts/rdc_analyzer/docs/UNREAL_IMPORT.md`
- Modify: `scripts/rdc_analyzer/docs/INDEX.md`

**Step 1: Draft docs**
```markdown
# Unity Import
# Unreal Import
```
**Step 2: Commit**
```bash
git add scripts/rdc_analyzer/docs/UNITY_IMPORT.md scripts/rdc_analyzer/docs/UNREAL_IMPORT.md scripts/rdc_analyzer/docs/INDEX.md
git commit -m "docs(rdc-analyzer): add unity/unreal import stubs"
```

---

## Notes for Unity/Unreal (post‑Messiah)
- Unity: prefer OBJ/MTL + ShaderLab stub; map textures via material properties.
- Unreal: prefer FBX/Interchange inputs; avoid `.uasset` writes.

## Progress
- [x] Task 1 — Deterministic GUID helper
- [ ] Task 2 — Repository skeleton writer
- [ ] Task 3 — Material mapping (shader‑driven, Unlit fallback)
- [ ] Task 4 — Messiah CLI entry (consume intermediate)
- [ ] Task 5 — Unity / Unreal import stubs (docs + scaffolding)
