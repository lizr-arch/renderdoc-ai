# RDC Report Link & Data Consistency Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

## Plan Metadata
- Version: v1
- Owner: Codex01
- Last Updated: 2026-02-01
- Plan File: plans/2026-02-01-115623-Codex01-RDC-Report-Link-DataConsistency.md

## Goal
- 在不强行统一 UI 的前提下，让 V3 报告与离线纹理报告“数据口径可解释一致”，并支持双向跳转定位。

## Architecture
- 增加统一“事实层”清单（`rdc_manifest.json`）记录 capture_id、数据来源、统计口径与缺失原因。
- 在两类报告中嵌入同一跳转协议（URL hash + report_links.json），支持 event/resource/shader 定位。
- 引入一致性检查面板：跨报告对比 counts，差异必须显示原因。

## Tech Stack
- Python 3.11 (rdc_analyzer)
- 纯离线 HTML + JS（无外部依赖）
- 现有数据源：RDC chunk / XML / textures.json / replay（可选）

## Success Criteria (measurable)
- 同一 capture_id 的报告中：Event/Texture/Shader ID 命名规则一致（100%）。
- 资源计数差异可解释：差异项必须输出原因（100%）。
- 互跳成功率 ≥ 95%（样本：≥3 个 capture，随机 20 个 event/resource）。

## Acceptance Criteria
- V3 报告与纹理报告都显示“数据来源 + 差异原因”的一致性面板。
- 点击“跳转到另一报告”时能定位到同一 event/resource 或给出缺失原因。

## Verification Commands
- `py -3 scripts/rdc_analyzer/analyze_rdc.py "<rdc>" --output "<dir>/<name>_report.html"`  
  Expected: 生成 V3 报告并写入 manifest/link。
- `py -3 scripts/rdc_analyzer/analyze_xml_report.py "<xml>" -o "<dir>/<name>_report_xml.html"`  
  Expected: 生成离线纹理报告并写入 manifest/link。
- `py -3 scripts/_tmp_check_manifest_consistency.py "<dir>"`  
  Expected: 输出 counts + 差异原因，且无“unknown reason”。

## Evidence
- 报告输出路径：`<dir>/<capture>_report.html`、`<dir>/<capture>_report_xml.html`
- Manifest 输出：`<dir>/rdc_manifest.json`
- Link 映射：`<dir>/report_links.json`

## Estimation
- Effort: 1.5–2.5 天
- Story Points: 5
- Original Estimate: 2 天

## Risk Register
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| 报告间 ID 口径不一致 | 高 | 中 | 统一 ID 规则 + manifest 明示来源 |
| 跳转目标不存在 | 中 | 高 | 显示缺失原因 + fallback 视图 |
| HTML 体积变大 | 中 | 低 | 仅嵌入必要字段，其他走 manifest |

## Game Dev: Memory & Resource Budget (Leak Checks)
- 记录 GPU 资源数量 + 纹理总量，输出前后对比；若差异>阈值，显示原因。

## Game Dev: Asset Pipeline
- 资产导出链路明确：XML/manifest/replay 三源合并，优先级固定。

## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: 使用同一 capture_id 对比两份报告跳转。
- Dump/Core: minidump / core dump 记录（若发生浏览器崩溃）。
- Symbols: PDB / dSYM / ELF（如需渲染崩溃定位）。
- Build identity: commit hash + tool version。

---

## Repo / File List (精确到行号范围)
- `scripts/rdc_analyzer/analyze_rdc.py:690` V3 报告生成入口  
- `scripts/rdc_analyzer/analyze_rdc.py:708` V3 HTML 标题与模板  
- `scripts/rdc_analyzer/generate_offline_report.py:190` 离线纹理报告模板入口  
- `scripts/rdc_analyzer/generate_offline_report.py:6811` 离线报告 JS 数据注入  
- `scripts/rdc_analyzer/analyze_xml_report.py:590` XML 报告生成入口  
- 新增：`scripts/rdc_analyzer/schema/rdc_manifest.py`（manifest schema/写入）
- 新增：`scripts/rdc_analyzer/tools/report_linking.py`（跳转协议/写入）

---

## Approach (Pseudo-code)

### Manifest Schema (统一事实层)
```json
{
  "capture_id": "sha256:...",
  "source": "A|B|C",
  "counts": {
    "events": 668,
    "textures": 155,
    "shaders": 70
  },
  "count_reason": {
    "textures": "xml",
    "shaders": "xml",
    "events": "xml"
  },
  "missing_reason": [
    {"field": "texture.thumbnail", "reason": "no textures.json"}
  ],
  "report_links": {
    "v3": "xxx_report.html",
    "texture": "xxx_report_xml.html"
  }
}
```

### Jump Protocol
```
#event=123
#resource=456
#shader=abc
```
- 解析 hash → 在当前报告中定位  
- 若缺失 → 从 manifest 输出 “缺失原因”

---

## Feature Breakdown (WHAT / WHY / HOW)

### 1) 统一 Manifest
- WHAT：生成 `rdc_manifest.json`，记录来源与统计口径
- WHY：不同报告统计来源不一致，需要可解释对齐
- HOW：在报告生成入口写入 manifest

### 2) 一致性面板
- WHAT：显示 counts 对比与差异原因
- WHY：让“数据差异可接受”而不是误判为 bug
- HOW：读取 manifest + 当前报告 counts，输出差异表

### 3) 双向跳转
- WHAT：点击资源/事件跳到另一报告
- WHY：不同人群的报告互补，需要快速切换
- HOW：report_links.json + hash 协议

---

## Action Items (2-5 分钟粒度)

### Task 1: 新增 manifest schema + writer
**Files:**
- Create: `scripts/rdc_analyzer/schema/rdc_manifest.py`
- Test: `scripts/rdc_analyzer/tests/test_manifest_schema.py`

**Step 1: Write failing test**
```python
def test_manifest_requires_reason_for_missing():
    data = build_manifest(missing=[{"field": "x", "reason": ""}])
    assert data["missing_reason"][0]["reason"]
```

**Step 2: Run test (expect fail)**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_manifest_schema.py::test_manifest_requires_reason_for_missing -v`  
Expected: FAIL (manifest builder missing validation)

**Step 3: Minimal implementation**
```python
def build_manifest(...):
    for item in missing:
        if not item.get("reason"):
            raise ValueError("missing reason required")
```

**Step 4: Run test (expect pass)**
Run: same command  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/schema/rdc_manifest.py scripts/rdc_analyzer/tests/test_manifest_schema.py
git commit -m "feat(rdc-analyzer): add manifest schema"
```

---

### Task 2: V3 报告写入 manifest + link
**Files:**
- Modify: `scripts/rdc_analyzer/analyze_rdc.py:690`
- Create: `scripts/rdc_analyzer/tools/report_linking.py`
- Test: `scripts/rdc_analyzer/tests/test_v3_manifest.py`

**Step 1: Write failing test**
```python
def test_v3_report_writes_manifest(tmp_path):
    # stub minimal analysis_results
    # expect rdc_manifest.json created
```

**Step 2: Run test (expect fail)**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_v3_manifest.py::test_v3_report_writes_manifest -v`  
Expected: FAIL (no manifest)

**Step 3: Minimal implementation**
```python
write_manifest(output_dir, counts, reasons, links)
```

**Step 4: Run test (expect pass)**
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/analyze_rdc.py scripts/rdc_analyzer/tools/report_linking.py scripts/rdc_analyzer/tests/test_v3_manifest.py
git commit -m "feat(rdc-analyzer): write manifest + links in V3 report"
```

---

### Task 3: 离线纹理报告写入 manifest + link
**Files:**
- Modify: `scripts/rdc_analyzer/generate_offline_report.py:6811`
- Modify: `scripts/rdc_analyzer/analyze_xml_report.py:590`
- Test: `scripts/rdc_analyzer/tests/test_offline_manifest.py`

**Step 1: Write failing test**
```python
def test_offline_report_embeds_links():
    # expect report_links.json exists and hash jump anchors present
```

**Step 2: Run test (expect fail)**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_offline_manifest.py::test_offline_report_embeds_links -v`  
Expected: FAIL

**Step 3: Minimal implementation**
```python
inject_link_buttons(html, report_links)
```

**Step 4: Run test (expect pass)**
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/generate_offline_report.py scripts/rdc_analyzer/analyze_xml_report.py scripts/rdc_analyzer/tests/test_offline_manifest.py
git commit -m "feat(rdc-analyzer): offline report linking + manifest"
```

---

### Task 4: 一致性面板 + 跳转行为
**Files:**
- Modify: `scripts/rdc_analyzer/analyze_rdc.py:2310`
- Modify: `scripts/rdc_analyzer/generate_offline_report.py:6811`
- Test: `scripts/rdc_analyzer/tests/test_consistency_panel.py`

**Step 1: Write failing test**
```python
def test_consistency_panel_has_reason():
    # parse HTML and assert "reason" text exists
```

**Step 2: Run test (expect fail)**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_consistency_panel.py::test_consistency_panel_has_reason -v`  
Expected: FAIL

**Step 3: Minimal implementation**
```python
render_consistency_panel(counts, reasons)
```

**Step 4: Run test (expect pass)**
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/analyze_rdc.py scripts/rdc_analyzer/generate_offline_report.py scripts/rdc_analyzer/tests/test_consistency_panel.py
git commit -m "feat(rdc-analyzer): add consistency panel + jump"
```

---

## Execution Log
- 2026-02-01：完成 Task 1（新增 manifest schema + 测试），`test_manifest_schema.py` 通过。
- 2026-02-01：完成 Task 2（V3 报告写入 manifest/link），`test_v3_manifest.py` 通过。
- 2026-02-01：完成 Task 3（离线纹理报告写入 manifest/link），`test_offline_manifest.py` 通过。

## Verification / DoD
- 同一 capture 生成两份报告 → `rdc_manifest.json` / `report_links.json` 存在且字段完整。
- 互跳：至少 20 个 event/resource 跳转成功，失败必须显示原因。
- 一致性面板显示 counts 与原因，且不存在空原因。

---

## Open Questions
- 你要求的“数据一致”阈值是否固定为 0.90？还是按资源类型分开阈值？
- manifest 文件是否允许覆盖旧版本，还是必须版本化保留？

---

## Next Steps
- 等你批准 `/do` 后开始实现，并按 TDD + 分步提交。
