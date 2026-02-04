# Texture Thumbnail Mapping Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-02-04
**Owner:** Agent01
**Last Updated:** 2026-02-04
**Plan File:** `plans/2026-02-04-160900-Agent01-TextureThumbnail-Mapping.md`

## Goal
- 修复 bundle 纹理页不显示缩略图：确保 XML 纹理条目能映射到导出的 `tex_<resourceId>_<WxH>.png`

## Architecture
- 在 XML 路线补齐 `resource_id`，并让映射函数优先使用 `resource_id` 查找导出的 PNG
- 保留现有 `glob` fallback，不改动导出引擎

## Tech Stack
- Python 3.11
- RenderDoc RDC Analyzer (scripts/rdc_analyzer)
- pytest

## Success Criteria (measurable)
- `textures.html` 内出现至少 1 条 `"thumbnail": "textures/..."` 记录
- `map_exported_textures()` 映射成功数 > 0（在测试中验证）

## Acceptance Criteria
- 用户打开 `D:\backup\endfield_report\textures.html` 能看到缩略图

## Verification Commands
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k prefers_resource_id -v` (Expected: PASS)
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k load_textures_resource_id -v` (Expected: PASS)
- `py -3 scripts/rdc_analyzer/analyze_xml_report.py "D:\backup\endfield.zip.xml" -o "D:\backup\endfield_report" --ui-version bundle`
  then `rg -n "\"thumbnail\": \"textures/\" D:\backup\endfield_report\textures.html"` (Expected: hits > 0)

## Evidence
- 需记录：测试输出（pytest PASS）与 `textures.html` 中 thumbnail 命中行

## Estimation
- Effort: 1.5–2.0 hours
- Story Points: 2
- Original Estimate: 2h

## Risk Register
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| XML 未包含 `resourceId`，且 `id` 不可推断 | 缩略图仍无法匹配 | Medium | 增加 `tex_<num>` 解析 fallback；必要时从 XML 原文补抽取 |
| PNG 宽高与 XML 记录不一致 | 缩略图匹配失败 | Low | 保留 `glob` fallback，允许匹配任意 WxH |
| 纹理数量很大导致页面加载慢 | 体验变差 | Low | 本次不做虚拟化，后续优化 |

## Game Dev: Memory & Resource Budget (Leak Checks)
- 纹理 PNG 导出路径不增加常驻内存；仅关注导出时间与磁盘占用
- 若后续要回放导出，考虑 GPU 内存峰值监控（记录 export 前后显存）

## Game Dev: Asset Pipeline
- 资产来源：RenderDoc XML/ZIP（离线） → PNG 输出到 `output_dir/textures/`
- 输出路径需稳定（bundle 目录中相对路径 `textures/<file>.png`）

## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: 运行 `analyze_xml_report.py --ui-version bundle` 生成报告
- Dump/Core: (minidump | core dump) TBD
- Symbols: (PDB | dSYM | ELF | DWARF) TBD
- Build identity: (build id | commit hash | git commit) TBD

## Scope
In:
- `map_exported_textures()` 使用 `resource_id` 优先匹配
- `load_textures_if_available()` 补齐 `resource_id`（从 `resourceId` 字段或 `tex_123` 形式推断）

Out:
- UI 样式/布局调整
- 纹理导出引擎逻辑改动

## Assumptions
- `parse_rdc_xml.py` 已解析出 `resourceId` 字段（需 /do 验证）
- PNG 命名遵循 `tex_<resourceId>_<width>x<height>.png`

## Repo / File List (line-level)
- `scripts/rdc_analyzer/analyze_xml_report.py:1295` `load_textures_if_available(...)`
- `scripts/rdc_analyzer/analyze_xml_report.py:1469` `map_exported_textures(...)`
- `scripts/rdc_analyzer/exporters/texture_batch_exporter.py:224` PNG 命名（参考）
- `scripts/rdc_analyzer/tests/test_bundle_report_assets.py`（新增单测）

## Approach (Pseudo-code)
1) `load_textures_if_available()`：补齐 `resource_id`
```
resource_id = tex_info.get("resourceId") or tex_info.get("resource_id")
if not resource_id and isinstance(tex_id, str) and tex_id.startswith("tex_") and tex_id[4:].isdigit():
    resource_id = tex_id[4:]
```
2) `map_exported_textures()`：优先 `resource_id`
```
tex_id = tex.get("resource_id") or tex.get("resourceId") or tex.get("id")
```
3) 保留 `glob` fallback

## Action Items (TDD)
### Task 1: 新增失败测试（resource_id 优先）

**Files:**
- Modify: `scripts/rdc_analyzer/tests/test_bundle_report_assets.py`

**Step 1: Write the failing test**
```python
def test_map_exported_textures_prefers_resource_id(tmp_path):
    from analyze_xml_report import map_exported_textures
    textures = [{"id": "tex_0", "resource_id": "123", "width": 4, "height": 8, "thumbnail": ""}]
    export_dir = tmp_path / "textures"
    export_dir.mkdir()
    (export_dir / "tex_123_4x8.png").write_bytes(b"fake")
    mapped = map_exported_textures(textures, export_dir)
    assert mapped == 1
    assert textures[0]["thumbnail"] == "textures/tex_123_4x8.png"
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k prefers_resource_id -v`  
Expected: FAIL

**Status:** ✅ Completed  
**Tests:** `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k prefers_resource_id -v` (FAIL as expected)  

### Task 2: 实现最小修复（map_exported_textures + load_textures_if_available）

**Files:**
- Modify: `scripts/rdc_analyzer/analyze_xml_report.py:1295-1505`

**Step 3: Write minimal implementation**
```python
tex_id = tex.get("resource_id") or tex.get("resourceId") or tex.get("id")
```
```python
resource_id = tex_info.get("resourceId") or tex_info.get("resource_id")
if not resource_id and isinstance(tex_id, str) and tex_id.startswith("tex_") and tex_id[4:].isdigit():
    resource_id = tex_id[4:]
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k prefers_resource_id -v`  
Expected: PASS

**Status:** ✅ Completed  
**Tests:** `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k prefers_resource_id -v` (PASS)  

### Task 3: 新增失败测试（XML textures 读取 resourceId）

**Files:**
- Modify: `scripts/rdc_analyzer/tests/test_bundle_report_assets.py`

**Step 1: Write the failing test**
```python
def test_load_textures_resource_id():
    from analyze_xml_report import load_textures_if_available
    xml_data = {"textures": [{"resourceId": "321", "name": "T", "width": 1, "height": 1}]}
    textures = load_textures_if_available(None, xml_data)
    assert textures[0]["resource_id"] == "321"
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k load_textures_resource_id -v`  
Expected: FAIL

**Status:** ✅ Completed  
**Tests:** `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k load_textures_resource_id -v` (FAIL as expected)  

### Task 4: 实现最小修复（读取 resourceId）

**Files:**
- Modify: `scripts/rdc_analyzer/analyze_xml_report.py:1295-1445`

**Step 3: Write minimal implementation**
```python
resource_id = tex_info.get("resourceId") or tex_info.get("resource_id")
```

**Step 4: Run test to verify it passes**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k load_textures_resource_id -v`  
Expected: PASS

**Status:** ✅ Completed  
**Tests:** `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k load_textures_resource_id -v` (PASS)  

### Task 5: 运行真实数据验证（Endfield）

**Files:**
- None

**Step 1: Run**
`py -3 scripts/rdc_analyzer/analyze_xml_report.py "D:\backup\endfield.zip.xml" -o "D:\backup\endfield_report" --ui-version bundle`

**Step 2: Verify**
`rg -n "\"thumbnail\": \"textures/\" D:\backup\endfield_report\textures.html` → Expect hits > 0

**Status:** ✅ Completed  
**Tests/Evidence:** `textures.html` 更新时间 2026-02-04 22:21:22；`rg -n "thumbnail" D:\backup\endfield_report\textures.html` 命中并包含 `thumbnail: "textures/..."`。  

### Task 6: 提交

**Step 1: Commit**
```bash
git add scripts/rdc_analyzer/analyze_xml_report.py scripts/rdc_analyzer/tests/test_bundle_report_assets.py
git commit -m "fix(rdc-analyzer): map texture thumbnails by resource id"
```

**Status:** ✅ Completed  
**Notes:** commits: `a2ba856bb` (code/tests), `19fe140c5` (plan updates).  

## Next Steps
- 等待 /do 执行
