# RDC Report UI Fix Review Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-02-01  
**Owner:** Codex01 (Reviewer)  
**Last Updated:** 2026-02-01  
**Plan File:** `plans/2026-02-01-152721-Codex01-RDC-Report-UI-Fix-Review.md`

---

## Plan Metadata
- Version: 2026-02-01
- Owner: Codex01 (Reviewer)
- Last Updated: 2026-02-01
- Plan File: `plans/2026-02-01-152721-Codex01-RDC-Report-UI-Fix-Review.md`

## Goal
- 修复 v2 UI 路线的阻断问题（字段不匹配、导入错误、Manifest 字段不一致），保证 `--ui-version v2` 可运行并通过基础单测。

## Architecture
- 保持现有 `ReportDataContract` 作为唯一数据入口；修正 `analyze_xml_report.py` 与其字段对齐。  
- 统一 `report_ui.py` 的导入路径，保证“脚本直接执行”与“包内调用”都可用。  
- Manifest 使用单一字段 `coverage`（0–1）并在 UI 中做百分比展示。  

## Tech Stack
- Python 3 (`scripts/rdc_analyzer`)
- HTML/CSS/JS（report_ui.py 内联模板）
- JSON（Manifest 可选落盘）

## Success Criteria (measurable)
- `py -3 scripts/rdc_analyzer/analyze_xml_report.py <xml> --ui-version v2` 不报错并输出 HTML。  
- `scripts/rdc_analyzer/tests/test_report_contract.py` 与 `test_report_ui.py` 通过。  
- Manifest 覆盖率显示正确（按 0–1 计算，UI 显示为 %）。  

## Acceptance Criteria
- [ ] v2 UI 路线无 `TypeError/AttributeError/ModuleNotFoundError`  
- [ ] Manifest coverage 与 UI 显示一致  
- [ ] Issues 渲染可接受 `Issue` 与 dict（或测试与实现一致）  

## Verification Commands
- `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_contract.py` (Expected: PASS)  
- `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_ui.py` (Expected: PASS)  
- `py -3 -m unittest scripts/rdc_analyzer/tests/test_issue_detector.py` (Expected: PASS)  

## Evidence
- `scripts/rdc_analyzer/analyze_xml_report.py:1721` (ReportDataContract 构造不匹配字段)  
- `scripts/rdc_analyzer/report_contract.py:41,48` (contract 字段 meta/pipeline_states)  
- `scripts/rdc_analyzer/report_ui.py:19,20,229` (导入路径 + coverage_percent)  
- `scripts/rdc_analyzer/core/issue_detector.py:44` (Issue 字段定义)  

## Estimation
- Effort: 4–6 hours  
- Story Points: 3  
- Original Estimate: 0.5 day  

## Risk Register
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| 修复导入导致脚本模式不可用 | High | Medium | 采用双路径导入（local 优先） |
| Manifest 标准变动影响 UI | Medium | Medium | 保持 `coverage` 为唯一来源，UI 统一换算 |
| Issues 字段规范变动导致旧数据不兼容 | Medium | Low | _issues_to_dicts 做兼容映射 |

## Game Dev: Memory & Resource Budget (Leak Checks)
- 不引入新缓存；仅修复逻辑与字段一致性。  
- UI 渲染仍保持延迟/分页策略（不新增大规模 DOM）。  

## Game Dev: Asset Pipeline
- 纹理/资源字段保持原有结构，仅修复 UI 显示逻辑与字段映射。  

## Game Dev: Crash Repro + Dumps/Symbols
- Repro: 使用同一份 XML 执行 `--ui-version v2` 生成 HTML。  
- Dump/Core: N/A（Python traceback）。  
- Symbols: N/A  
- Build identity: 输出 git commit hash 到日志（可选）。  

---

## Scope
**In Scope**  
- 修复 v2 分支字段/导入/Manifest/Issues 映射  
- 对应单测更新  

**Out of Scope**  
- 新功能/UI 结构变更  
- Offline/V3 迁移  
- Compare Mode  

## Assumptions
- 入口仍采用 `py -3 scripts/rdc_analyzer/analyze_xml_report.py ...` 直接执行。  
- `ReportDataContract` 作为唯一数据契约。  

## Repo / File List (line refs)
- `scripts/rdc_analyzer/analyze_xml_report.py:1717-1735`  
- `scripts/rdc_analyzer/report_ui.py:19-20,229,717`  
- `scripts/rdc_analyzer/report_contract.py:41,113,132`  
- `scripts/rdc_analyzer/core/issue_detector.py:44-59`  
- `scripts/rdc_analyzer/tests/test_report_ui.py:90-110`  

## Approach (Pseudo-code)
```
contract = ReportDataContract(meta=..., textures=..., shaders=..., events=..., performance=...)
manifest = build_manifest(contract)
coverage_percent = manifest["coverage"] * 100
issues_dict = map_issue_objects_to_dicts(issues)
render_report_shell(contract)  # internal uses manifest + issues mapping
```

## Impact Analysis
- 修复字段不匹配属于向后兼容修正，不改变 UI 行为。  
- UI 导入调整只影响执行路径，需验证脚本直跑与包内运行均可用。  

## Build/Test/Lint Quick Guide (record only)
- `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_contract.py`
- `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_ui.py`
- `py -3 -m unittest scripts/rdc_analyzer/tests/test_issue_detector.py`

---

## Task Checklist (TDD, 2–5 min steps)

### Task 1: 修复 ReportDataContract 字段不匹配
**Files:**  
- Modify: `scripts/rdc_analyzer/analyze_xml_report.py:1717-1735`

**Step 1: Write failing test**
```python
# tests/test_feature_flag.py (新增)
def test_v2_contract_fields_match():
    source = Path(__file__).parent.parent / "analyze_xml_report.py"
    text = source.read_text(encoding="utf-8")
    assert "metadata=" not in text
    assert "passes=" not in text
```

**Step 2: Run test to verify it fails**  
Run: `py -3 -m unittest scripts/rdc_analyzer/tests/test_feature_flag.py`  
Expected: FAIL (metadata/passes 仍存在)

**Step 3: Write minimal implementation**
```python
# analyze_xml_report.py (v2 branch)
performance_data = convert_perf_report_to_html_data(perf_report, context, xml_data)
performance_data["passes"] = xml_data.get("passes", [])

contract = ReportDataContract(
    textures=textures,
    shaders=shader_data,
    events=xml_data.get("events", []),
    performance=performance_data,
    meta={
        "capture_name": xml_path.stem,
        "source": "xml",
        "xml_path": str(xml_path),
    },
)
```

**Step 4: Run test to verify it passes**  
Run: `py -3 -m unittest scripts/rdc_analyzer/tests/test_feature_flag.py`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/analyze_xml_report.py scripts/rdc_analyzer/tests/test_feature_flag.py
git commit -m "fix(rdc-analyzer): align v2 ReportDataContract fields

- use meta= instead of metadata=
- move passes into performance data"
```

### Task 2: 修复 report_ui 导入路径
**Files:**  
- Modify: `scripts/rdc_analyzer/report_ui.py:19-20`

**Step 1: Write failing test**
```python
# tests/test_report_ui.py (新增)
def test_report_ui_imports_local_modules(self):
    source = Path(__file__).parent.parent / "report_ui.py"
    text = source.read_text(encoding="utf-8")
    assert "scripts.rdc_analyzer" not in text
```

**Step 2: Run test to verify it fails**  
Run: `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_ui.py`  
Expected: FAIL

**Step 3: Write minimal implementation**
```python
# report_ui.py
from report_contract import ReportDataContract, build_manifest
from core.issue_detector import Issue, detect_all_issues
```

**Step 4: Run test to verify it passes**  
Run: `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_ui.py`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/report_ui.py scripts/rdc_analyzer/tests/test_report_ui.py
git commit -m "fix(rdc-analyzer): use local imports in report_ui"
```

### Task 3: 修复 Issues 字段映射
**Files:**  
- Modify: `scripts/rdc_analyzer/report_ui.py:717-725`

**Step 1: Write failing test**
```python
# tests/test_report_ui.py (新增)
def test_issue_mapping_uses_resource_id(self):
    from scripts.rdc_analyzer.core.issue_detector import Issue, Severity, Category
    issue = Issue(Severity.CRITICAL, Category.TEXTURE, "T", "D", resource_id="tex1")
    # ensure mapping doesn't access issue_id
```

**Step 2: Run test to verify it fails**  
Run: `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_ui.py`  
Expected: FAIL

**Step 3: Write minimal implementation**
```python
# report_ui.py _issues_to_dicts
result.append({
    "id": issue.resource_id or "",
    "title": issue.title,
    "severity": severity,
    "category": issue.category.value if hasattr(issue.category, "value") else "other",
    "description": issue.description,
    "details": issue.suggestion or "",
    "affected_resources": issue.metadata.get("affected_resources", []),
})
```

**Step 4: Run test to verify it passes**  
Run: `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_ui.py`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/report_ui.py scripts/rdc_analyzer/tests/test_report_ui.py
git commit -m "fix(rdc-analyzer): correct issue mapping fields"
```

### Task 4: Manifest coverage 字段统一
**Files:**  
- Modify: `scripts/rdc_analyzer/report_ui.py:229`  
- Modify: `scripts/rdc_analyzer/tests/test_report_ui.py:118`

**Step 1: Write failing test**
```python
# tests/test_report_ui.py (新增)
def test_manifest_coverage_uses_fraction(self):
    manifest = {"coverage": 0.85, "counts": {"textures": 1}}
    html = render_manifest_bar(manifest)
    assert "85.0" in html
```

**Step 2: Run test to verify it fails**  
Run: `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_ui.py`  
Expected: FAIL

**Step 3: Write minimal implementation**
```python
# report_ui.py
coverage = manifest.get("coverage", 0) * 100
```

**Step 4: Run test to verify it passes**  
Run: `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_ui.py`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/report_ui.py scripts/rdc_analyzer/tests/test_report_ui.py
git commit -m "fix(rdc-analyzer): normalize manifest coverage display"
```

### Task 5: 补齐 Manifest 校验工具（可选）
**Files:**  
- Create: `scripts/rdc_analyzer/tools/validate_manifest.py`

**Step 1: Write failing test**
```python
# tests/test_report_contract.py (新增)
def test_validate_manifest_tool_exists(self):
    path = Path(__file__).parent.parent / "tools" / "validate_manifest.py"
    self.assertTrue(path.exists())
```

**Step 2: Run test to verify it fails**  
Run: `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_contract.py`  
Expected: FAIL

**Step 3: Write minimal implementation**
```python
# tools/validate_manifest.py
import json
import sys

def main():
    path = sys.argv[1]
    data = json.load(open(path, "r", encoding="utf-8"))
    coverage = data.get("coverage", 0.0)
    print(f"coverage={coverage:.2f}")
    if coverage < 0.90:
        sys.exit(2)

if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**  
Run: `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_contract.py`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/tools/validate_manifest.py scripts/rdc_analyzer/tests/test_report_contract.py
git commit -m "feat(rdc-analyzer): add manifest validation tool"
```

---

## Risks & Blockers
- 如果你希望保持 `scripts.rdc_analyzer.*` 的绝对导入，请先确认入口改为模块执行（`python -m rdc_analyzer ...`）。  

## Next Steps
- [ ] 你确认后进入 `/do` 执行 Task 1–5。  

---

## Execution Log (2026-02-01)
- [x] Task 1: 修复 ReportDataContract 字段不匹配  
- [x] Task 2: 修复 report_ui 导入路径  
- [x] Task 3: 修复 Issues 字段映射  
- [x] Task 4: Manifest coverage 字段统一  
- [x] Task 5: 补齐 Manifest 校验工具  
- Tests:
  - `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_contract.py` ✅  
  - `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_ui.py` ✅  
  - `py -3 -m unittest scripts/rdc_analyzer/tests/test_issue_detector.py` ✅  
  - `py -3 -m unittest scripts/rdc_analyzer/tests/test_feature_flag.py` ✅  
