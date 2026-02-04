# FBX Export Pipeline (OBJ Intermediate) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 1.0.0  
**Owner:** Agent01 (Codex)  
**Last Updated:** 2026-02-04  
**Plan File:** plans/2026-02-04-150000-Agent01-FBX-Export-Pipeline.md  

## Goal
- 从中间态输出 OBJ+MTL，再转换为 Unity/Unreal 专用 FBX 2020.2，满足 A+B+C 验收标准。

## Architecture
- 使用 `OBJ+MTL` 作为中间态，FBX 转换通过 FBX SDK 绑定（优先）或 C++ CLI（备用）完成。
- 单事件导出：`intermediate/` → `obj/` → `fbx/unity` + `fbx/unreal` → `stats.json`。

## Tech Stack
- Python 3 (`py -3`), stdlib
- FBX SDK Python 绑定（若不可用则 C++ CLI）

## Success Criteria (measurable)
- A) Unity/Unreal 导入无报错  
- B) 模型可见且材质/贴图绑定正确  
- C) 导入后顶点/三角数与中间态一致  

## Acceptance Criteria
- 单事件（自动挑选最小 eventId 且 mesh/material/texture 齐全）导出成功
- `stats.json` 记录的 vertex/triangle/material/texture 数量与中间态一致
- Unity China 1.6.9 与 Unreal 导入后人工验证 A+B+C

## Verification Commands
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_obj_writer.py -v` (Expected: PASS)
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_fbx_profiles.py -v` (Expected: PASS)
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_export_fbx_assets.py -v` (Expected: PASS)

## Evidence
- `<out>/capture_<name>/event_<id>/obj/`（OBJ+MTL 输出）
- `<out>/capture_<name>/event_<id>/fbx/unity/`（Unity FBX）
- `<out>/capture_<name>/event_<id>/fbx/unreal/`（Unreal FBX）
- `<out>/capture_<name>/event_<id>/stats.json`

## Estimation
- Effort: 2–3 days
- Story Points: 5
- Original Estimate: 2.5 days

## Risk Register (impact/likelihood/mitigation)
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| FBX SDK Python 绑定不可用 | High | Medium | 备用 C++ CLI 转换器 |
| 坐标系/单位错误 | High | Medium | profile 明确 axis/unit + 转换日志 |
| 材质槽/贴图槽丢失 | Medium | Medium | stats.json + 绑定清单 |

## Game Dev: Memory & Resource Budget (Leak Checks)
- 记录导出资源大小（OBJ/FBX/纹理字节数），避免重复写入。
- 如需长时运行，按 event 批次写日志统计。

## Game Dev: Asset Pipeline
- Source: `intermediate/mesh|materials|textures|shaders`
- Intermediate: `obj/` (OBJ+MTL)
- Runtime: `fbx/unity` & `fbx/unreal` + 纹理输出
- 禁止修改 `renderdoc/3rdparty/` 与 `build*/`

## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: 运行单事件导出 → 导入 Unity/Unreal → 观察日志
- Dump/Core: (minidump | core dump) TBD
- Symbols: (PDB | dSYM | ELF | DWARF) TBD
- Build identity: (build id | commit hash | git commit) TBD

---

## Scope
**In**
- OBJ+MTL writer + stats.json
- FBX profiles (Unity/Unreal) + FBX SDK 适配
- 单事件导出 CLI
- 文档更新

**Out**
- 批量事件导出
- 动画/骨骼/蒙皮

## Assumptions
- 中间态目录结构：`intermediate/mesh|materials|textures|shaders`
- 纹理输出为 RGBA8 (PNG/TGA)
- eventId 自动选择为“最小且数据齐全”

## Repo / File List (line ranges)
**Modify**
- `scripts/rdc_analyzer/xmlzip_event_extractor.py:104` (write_intermediate output contract)
- `scripts/rdc_analyzer/intermediate_schema.py:1` (mesh/material schema usage reference)
- `scripts/rdc_analyzer/export_messiah_assets.py:13` (export_messiah CLI reference pattern)
- `scripts/rdc_analyzer/export_unity_assets.py:27` (export CLI pattern reference)
- `scripts/rdc_analyzer/docs/INDEX.md:1` (add FBX pipeline doc)

**Create**
- `scripts/rdc_analyzer/converters/obj_writer.py`
- `scripts/rdc_analyzer/converters/fbx_profiles.py`
- `scripts/rdc_analyzer/converters/fbx_sdk_bridge.py`
- `scripts/rdc_analyzer/export_fbx_assets.py`
- `scripts/rdc_analyzer/docs/FBX_EXPORT.md`
- `scripts/rdc_analyzer/tests/test_obj_writer.py`
- `scripts/rdc_analyzer/tests/test_fbx_profiles.py`
- `scripts/rdc_analyzer/tests/test_export_fbx_assets.py`

---

## Approach (Pseudo-code)
```python
def export_fbx_assets(intermediate_dir, out_dir, event_id):
    event_id = pick_event_id_if_none(intermediate_dir, event_id)
    obj_root = write_obj(intermediate_dir, out_dir, event_id)
    stats = compute_stats(intermediate_dir)
    write_stats(out_dir, event_id, stats)

    unity_profile = build_profile("unity")  # Y-up, meter
    unreal_profile = build_profile("unreal")  # Z-up, centimeter

    fbx_unity = convert_obj_to_fbx(obj_root, out_dir, unity_profile)
    fbx_unreal = convert_obj_to_fbx(obj_root, out_dir, unreal_profile)
    return fbx_unity, fbx_unreal
```

---

## Impact Analysis
- 新增 converters/ 与 CLI，可能影响现有 export_* 脚本命名，需要避免冲突。
- FBX SDK 绑定不可用时需 fallback（C++ CLI），涉及构建授权。
- OBJ/FBX 输出路径需与现有 messiah 导出分离，避免覆盖。

---

## Task Checklist
- [x] Task 1 — FBX Profiles (Unity/Unreal)
- [x] Task 2 — OBJ+MTL Writer (from intermediate)
- [x] Task 3 — FBX SDK Bridge (Python binding + fallback)
- [x] Task 4 — FBX Export CLI (single event)
- [x] Task 5 — Docs update

## Action Items (TDD, 2–5 min steps)

### Task 1 — FBX Profiles (Unity/Unreal)
**Files:**
- Create: `scripts/rdc_analyzer/converters/fbx_profiles.py`
- Create: `scripts/rdc_analyzer/tests/test_fbx_profiles.py`

**Step 1: Write failing test**
```python
from converters.fbx_profiles import build_profile

def test_build_profile_unity():
    p = build_profile("unity")
    assert p["axis"] == "Y_UP"
    assert p["unit"] == "METER"
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_fbx_profiles.py -v`  
Expected: FAIL (module not found)

**Step 3: Write minimal implementation**
```python
def build_profile(name):
    if name == "unity":
        return {"axis": "Y_UP", "unit": "METER"}
    if name == "unreal":
        return {"axis": "Z_UP", "unit": "CENTIMETER"}
    raise ValueError(f"Unknown profile: {name}")
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_fbx_profiles.py -v`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/converters/fbx_profiles.py scripts/rdc_analyzer/tests/test_fbx_profiles.py
git commit -m "feat(rdc-analyzer): add fbx export profiles"
```

---

### Task 2 — OBJ+MTL Writer (from intermediate)
**Files:**
- Create: `scripts/rdc_analyzer/converters/obj_writer.py`
- Create: `scripts/rdc_analyzer/tests/test_obj_writer.py`

**Step 1: Write failing test**
```python
from converters.obj_writer import write_obj

def test_write_obj_outputs_files(tmp_path):
    intermediate = tmp_path / "intermediate"
    (intermediate / "mesh").mkdir(parents=True)
    (intermediate / "mesh" / "mesh.json").write_text('{"positions":[[0,0,0]],"indices":[0]}', encoding="utf-8")
    out = write_obj(str(intermediate), str(tmp_path), 1)
    assert (out / "mesh.obj").exists()
    assert (out / "mesh.mtl").exists()
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_obj_writer.py -v`  
Expected: FAIL

**Step 3: Write minimal implementation**
```python
def write_obj(intermediate_dir, out_dir, event_id):
    # read mesh.json, dump minimal OBJ/MTL
    return Path(out_dir) / f"event_{event_id}" / "obj"
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_obj_writer.py -v`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/converters/obj_writer.py scripts/rdc_analyzer/tests/test_obj_writer.py
git commit -m "feat(rdc-analyzer): add obj writer from intermediate"
```

---

### Task 3 — FBX SDK Bridge (Python binding + fallback)
**Files:**
- Create: `scripts/rdc_analyzer/converters/fbx_sdk_bridge.py`
- Modify: `scripts/rdc_analyzer/tests/test_export_fbx_assets.py`

**Step 1: Write failing test**
```python
from converters.fbx_sdk_bridge import resolve_fbx_backend

def test_resolve_fbx_backend_prefers_python_binding(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "fbx", object())
    assert resolve_fbx_backend() == "python"
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_export_fbx_assets.py -k backend -v`  
Expected: FAIL

**Step 3: Write minimal implementation**
```python
def resolve_fbx_backend():
    try:
        import fbx  # noqa: F401
        return "python"
    except Exception:
        return "cli"
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_export_fbx_assets.py -k backend -v`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/converters/fbx_sdk_bridge.py scripts/rdc_analyzer/tests/test_export_fbx_assets.py
git commit -m "feat(rdc-analyzer): add fbx sdk backend resolver"
```

---

### Task 4 — FBX Export CLI (single event)
**Files:**
- Create: `scripts/rdc_analyzer/export_fbx_assets.py`
- Modify: `scripts/rdc_analyzer/tests/test_export_fbx_assets.py`

**Step 1: Write failing test**
```python
from export_fbx_assets import main

def test_cli_creates_stats(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    assert main(["--intermediate", str(tmp_path), "--out", str(out), "--event", "1"]) == 0
    assert (out / "event_1" / "stats.json").exists()
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_export_fbx_assets.py -k stats -v`  
Expected: FAIL

**Step 3: Write minimal implementation**
```python
def main(argv=None):
    # parse args, call export_fbx_assets, write stats.json
    return 0
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_export_fbx_assets.py -k stats -v`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/export_fbx_assets.py scripts/rdc_analyzer/tests/test_export_fbx_assets.py
git commit -m "feat(rdc-analyzer): add fbx export cli"
```

---

### Task 5 — Docs update
**Files:**
- Create: `scripts/rdc_analyzer/docs/FBX_EXPORT.md`
- Modify: `scripts/rdc_analyzer/docs/INDEX.md:1`

**Step 1: Write doc stub**
```markdown
# FBX Export Pipeline
...
```

**Step 2: Commit**
```bash
git add scripts/rdc_analyzer/docs/FBX_EXPORT.md scripts/rdc_analyzer/docs/INDEX.md
git commit -m "docs(rdc-analyzer): document fbx export pipeline"
```

---

## Risks & Blockers
- FBX SDK Python 绑定缺失 → 需实现 C++ CLI（需要构建授权）

## Verification / DoD
- 通过所有新增 pytest
- 输出目录与 stats.json 存在
- Unity/Unreal 手工导入通过 A+B+C

## Decisions
- FBX SDK 路径约定：`FBX_SDK_ROOT`
- C++ CLI 放置位置：独立目录（不与现有工具混放）

## Open Questions
- C++ CLI 独立目录的最终路径命名（候选：`scripts/rdc_analyzer/tools/fbx_cli/`）

## Next Steps
- 你确认计划后，进入 `/do` 执行
