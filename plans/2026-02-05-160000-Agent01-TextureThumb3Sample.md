# Renderdoccmd Export Evaluation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

## Plan Metadata
- Version: 2026-02-06.v1
- Owner: Agent01 (Codex)
- Last Updated: 2026-02-06
- Plan File: `plans/2026-02-05-160000-Agent01-TextureThumb3Sample.md`

## Goal
- 评估并集成 `renderdoccmd export` 路径，作为 Vulkan 缩略图的可行输出方案（无 GUI），并只保留 3 张缩略图。

## Architecture
- 使用 `renderdoccmd export` 生成 PNG + `textures.json`（必须带 `--metadata`）。
- 解析 `textures.json`，按面积排序只保留 3 张缩略图，写回报告映射。
- 不修改 RenderDoc C++ 逻辑，仅在 Python 侧做后处理。

## Tech Stack
- Python 3 (`py -3`)
- RenderDoc CLI (`renderdoccmd.exe`)
- `scripts/rdc_analyzer` 报告生成链路

## Success Criteria (measurable)
- 对 `D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc`，输出目录仅保留 3 张可读 PNG。
- `textures.html` 中能看到 3 张缩略图。
- 日志明确记录 renderdoccmd export 被调用与筛选结果。

## Acceptance Criteria
- 无 GUI，单次命令可完成导出与 HTML 生成。
- 缩略图数量受 `RDC_TEX_EXPORT_LIMIT` 控制（默认 3）。
- renderdoccmd 不可用时，给出清晰日志提示。

## Verification Commands
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_texture_row_pitch.py -v --tb=short`
  - Expected: `1 passed`
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_renderdoccmd_export_select.py -v --tb=short`
  - Expected: `1 passed`
- `cmd /c "set RDC_TEX_EXPORT_LIMIT=3&& set RDC_TEX_EXPORT_SOURCE=renderdoccmd&& py -3 -m rdc_analyzer analyze \"D:\\backup\\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc\" -o D:\\backup\\endfield_report_test --format html"`
  - Expected: log 包含 `renderdoccmd export` + `Done: 3/3`，目录仅有 3 张 PNG。

## Evidence
- `D:\backup\endfield_report_test\textures\*.png`
- `D:\backup\endfield_report_test\textures.html`

## Estimation
- Effort: 0.5 day
- Story Points: 2
- Original Estimate: 1 day

## Risk Register
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| renderdoccmd 不存在或不可用 | 高 | 中 | `_resolve_renderdoccmd` + 环境变量 RENDERDOCCMD + 清晰日志 |
| export 输出过大 | 中 | 中 | 先导出后筛选，仅保留 3 张 |
| 软件渲染不可用 | 中 | 中 | 允许手动设置 `--software-render`（后续扩展） |

## Game Dev: Memory & Resource Budget (Leak Checks)
- 关注 renderdoccmd 导出过程的峰值内存（纹理全量导出）。

## Game Dev: Asset Pipeline
- 输入为 `.rdc`，输出为 `textures.json + PNG`（renderdoccmd export 标准产物）。

## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: 运行验证命令并保留日志。
- Dump/Core: 无（若崩溃保留 renderdoccmd 输出日志）。
- Symbols: 若需调试，使用 RenderDoc 安装路径 PDB。
- Build identity: 记录 renderdoccmd 版本与 repo commit。

## Assumptions
- `renderdoccmd.exe` 可由 `_resolve_renderdoccmd()` 找到（已验证安装路径）。
- 本阶段仅评估 renderdoccmd export 路径，不改 C++。
- MCP 文档检索无结果（search_docs=0），结论以源码为准。

## Repo / File List (line ranges)
- `renderdoccmd/renderdoccmd.cpp:656-930` (ExportCommand 参数与 textures.json 输出)
- `scripts/rdc_analyzer/analyze_xml_report.py:120-260` (renderdoccmd 路径解析函数)
- `scripts/rdc_analyzer/analyze_xml_report.py:1990-2060` (纹理导出逻辑插入点)
- `scripts/rdc_analyzer/exporters/texture_batch_exporter.py:60-220` (TextureInfo/导出辅助)
- `scripts/rdc_analyzer/tests/test_texture_row_pitch.py` (已有 failing test)
- `scripts/rdc_analyzer/tests/test_renderdoccmd_export_select.py` (new)

## Approach (Pseudo-code)

```python
# exporters/renderdoccmd_exporter.py (new)

def load_textures_json(path: Path) -> list[dict]:
    data = json.load(path.open('r', encoding='utf-8'))
    return data.get('textures', [])


def select_textures(entries: list[dict], limit: int) -> list[dict]:
    ordered = sorted(entries, key=lambda e: (-(e.get('width', 0) * e.get('height', 0)), e.get('id', 0)))
    return ordered[:limit]


def copy_selected(entries, src_dir: Path, dst_dir: Path) -> list[dict]:
    dst_dir.mkdir(parents=True, exist_ok=True)
    kept = []
    for e in entries:
        filename = e.get('file')
        if not filename:
            continue
        shutil.copy2(src_dir / filename, dst_dir / filename)
        kept.append(e)
    return kept
```

```python
# analyze_xml_report.py (renderdoccmd path)
if export_source == 'renderdoccmd':
    renderdoccmd = _resolve_renderdoccmd()
    run([renderdoccmd, 'export', rdc_path, '--out', tmp_dir, '--format', 'png', '--metadata'])
    entries = load_textures_json(tmp_dir / 'textures.json')
    selected = select_textures(entries, limit)
    copy_selected(selected, tmp_dir, output_dir / 'textures')
    map_thumbnails_by_id(textures, selected)
```

## Action Items (2–5 min each)

### Task 1: 收尾已有 rowPitch 测试（保证测试可用）
**Files:**
- Modify: `scripts/rdc_analyzer/exporters/texture_batch_exporter.py`
- Test: `scripts/rdc_analyzer/tests/test_texture_row_pitch.py`

**Step 1: Run test to verify it fails**
- [x] Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_texture_row_pitch.py -v --tb=short`
- [x] Expected: FAIL（helper 不存在）

**Step 2: Implement minimal helper**
```python
def tighten_rows_by_pitch(raw: bytes, width: int, height: int, row_pitch: int, fmt: str) -> bytes:
    row_bytes = int(width * 4)  # 最小实现，先支持 RGBA8
    return b''.join(raw[i * row_pitch : i * row_pitch + row_bytes] for i in range(height))
```
- [x] Implemented in `scripts/rdc_analyzer/exporters/texture_batch_exporter.py`

**Step 3: Run test to verify it passes**
- [x] Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_texture_row_pitch.py -v --tb=short`
- [x] Expected: PASS

**Step 4: Commit**
```bash
git add scripts/rdc_analyzer/exporters/texture_batch_exporter.py scripts/rdc_analyzer/tests/test_texture_row_pitch.py
git commit -m "fix(rdc-analyzer): add row-pitch tightening helper\n\n- add tighten_rows_by_pitch for RGBA8\n- pass row pitch unit test"
```
- [x] Commit: `aaf87acc2`

### Task 2: 新增 renderdoccmd export 选择器（TDD）
**Files:**
- Create: `scripts/rdc_analyzer/exporters/renderdoccmd_exporter.py`
- Test: `scripts/rdc_analyzer/tests/test_renderdoccmd_export_select.py`

**Step 1: Write failing test**
```python
def test_select_textures_by_area(tmp_path):
    entries = [
        {"id": 1, "width": 2, "height": 2, "file": "a.png"},
        {"id": 2, "width": 8, "height": 8, "file": "b.png"},
        {"id": 3, "width": 4, "height": 4, "file": "c.png"},
    ]
    selected = select_textures(entries, 2)
    assert [e["id"] for e in selected] == [2, 3]
```
- [x] Test file created: `scripts/rdc_analyzer/tests/test_renderdoccmd_export_select.py`

**Step 2: Run test to verify it fails**
- [x] Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_renderdoccmd_export_select.py -v --tb=short`
- [x] Expected: FAIL

**Step 3: Implement minimal code**
```python
def select_textures(entries, limit):
    ordered = sorted(entries, key=lambda e: (-(e.get('width', 0) * e.get('height', 0)), e.get('id', 0)))
    return ordered[:limit]
```
- [x] Implemented in `scripts/rdc_analyzer/exporters/renderdoccmd_exporter.py`

**Step 4: Run test to verify it passes**
- [x] Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_renderdoccmd_export_select.py -v --tb=short`
- [x] Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/exporters/renderdoccmd_exporter.py scripts/rdc_analyzer/tests/test_renderdoccmd_export_select.py
git commit -m "feat(rdc-analyzer): add renderdoccmd export selector\n\n- add textures.json selector for top-N by area\n- add unit test for selection logic"
```
- [x] Commit: `168d0a33f`

### Task 3: 集成 renderdoccmd export 到 analyze_xml_report.py
**Files:**
- Modify: `scripts/rdc_analyzer/analyze_xml_report.py`

- [x] Step 1 完成：新增 `RDC_TEX_EXPORT_SOURCE`/`RDC_TEX_EXPORT_LIMIT` 开关并默认 limit=3。
- [x] Step 2 完成：`renderdoccmd export --format png --metadata` 已接入，且仅选择支持 `export` 的二进制。
- [x] Step 3 完成：读取 `textures.json` 后按面积选择 Top-N，并修剪未选中的 PNG（保留 3 张）。
- [x] Step 4 完成：按 `resource_id/resourceId/id` 映射缩略图，日志输出 `Done: 3/3`。
- [x] 验证完成：`D:\backup\endfield_report_test\textures` 中仅 `3` 张 PNG + `textures.json`。

**Decisions / Notes (2026-02-06)**
- 系统安装版 `C:\Program Files\RenderDoc\renderdoccmd.exe` 无 `export` 子命令；导出路径必须使用源码版二进制（如 `x64/Development/renderdoccmd.exe`）。
- 当 `RDC_TEX_EXPORT_SOURCE=renderdoccmd` 时，跳过 XML/ZIP Base64 缩略图流程，避免重复工作与日志噪音。

**Step 1: Add env switch + command builder**
```python
export_source = os.getenv("RDC_TEX_EXPORT_SOURCE", "xmlzip")
limit_env = os.getenv("RDC_TEX_EXPORT_LIMIT", "")
limit = int(limit_env) if limit_env.isdigit() else 3
```

**Step 2: Call renderdoccmd export (metadata)**
```python
cmd = [str(renderdoccmd), "export", str(rdc_path), "--out", str(tmp_dir), "--format", "png", "--metadata"]
subprocess.run(cmd, check=False)
```

**Step 3: Load textures.json + copy top-N**
```python
entries = load_textures_json(tmp_dir / "textures.json")
selected = select_textures(entries, limit)
copy_selected(selected, tmp_dir, output_dir / "textures")
```

**Step 4: Map thumbnails by resource id**
```python
for tex in textures:
    rid = tex.get("resource_id") or tex.get("id")
    if rid in selected_ids:
        tex["thumbnail"] = f"textures/{file_name}"
```

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/analyze_xml_report.py
git commit -m "feat(rdc-analyzer): add renderdoccmd export path for thumbnails\n\n- run renderdoccmd export with metadata\n- select top-N textures and map thumbnails"
```

## Build/Test/Lint Quick Guide (do not run automatically)
- Tests:
  - `py -3 -m pytest scripts/rdc_analyzer/tests/test_texture_row_pitch.py -v --tb=short`
  - `py -3 -m pytest scripts/rdc_analyzer/tests/test_renderdoccmd_export_select.py -v --tb=short`

## Verification / DoD
- 3 张 PNG 缩略图可读。
- 日志明确记录 renderdoccmd export。
- HTML 显示对应缩略图。

## Open Questions
- 是否允许在 renderdoccmd export 后删除未选中的 PNG 以节省空间？

## Next Steps
- 等待 /do 执行批准。
