# RDC Report UI Unified Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-02-01  
**Owner:** Codex01 + AI  
**Last Updated:** 2026-02-01  
**Plan File:** `plans/2026-02-01-143948-Codex01-RDC-Report-UI-Unified-Plan.md`  
**Derived From:** `plans/2025-01-21-RDC-Report-UI-Unified-Plan.md`

---

## Plan Metadata
- Version: 2026-02-01
- Owner: Codex01 + AI
- Last Updated: 2026-02-01
- Plan File: `plans/2026-02-01-143948-Codex01-RDC-Report-UI-Unified-Plan.md`

## Goal
- 统一 V3 / Offline / XML 三套 HTML 报告的**信息架构、数据入口与跳转逻辑**，并以 Feature Flag 渐进迁移。

## Architecture
- 数据层：`report_contract.py` 定义唯一数据契约 + Manifest，所有来源必须对齐该契约。  
- 展示层：`report_ui.py` 统一壳层 + 四视图切换（Issues/Events/Resources/Performance）。  
- 迁移策略：通过 `--ui-version=2` 开启新壳层，旧逻辑保留为 `ui-version=1`。  

## Tech Stack
- Python 3 (`scripts/rdc_analyzer`)
- HTML/CSS/JS（内嵌模板）
- JSON（Report Data + Manifest）
- RenderDoc CLI（`renderdoccmd`）

## Success Criteria (measurable)
- Manifest 字段覆盖率 ≥ 0.90。  
- 单页四视图可切换，且 Section IDs 一致（跨视图跳转不失败）。  
- 若 XML 数据含 `textures`/`shaders`，HTML 对应列表非空；否则必须显示“无数据来源”。  
- `--ui-version=1` 仍能生成旧版报告。  

## Acceptance Criteria
- [ ] Issues / Events / Resources / Performance 四视图可切换  
- [ ] 报告顶部显示 capture 名称 + 数据源（A/C/B）  
- [ ] Manifest 嵌入 HTML，并可导出 JSON  
- [ ] 空数据字段显示“无数据来源”  
- [ ] `--ui-version=1` 保留旧逻辑  

## Verification Commands
- `py -3 scripts/rdc_analyzer/analyze_xml_report.py <capture.xml> -o report.html --ui-version=2` (Expected: 新壳层 HTML 输出)  
- `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_manifest.py` (Expected: PASS)  
- `py -3 -m unittest scripts/rdc_analyzer/tests/test_issue_detector.py` (Expected: PASS)  
- `py -3 scripts/rdc_analyzer/tools/validate_manifest.py report_manifest.json` (Expected: Coverage ≥ 0.90)  

## Evidence
- V3 入口：`scripts/rdc_analyzer/analyze_rdc.py:778,795`  
- Offline 壳层与 Event Browser：`scripts/rdc_analyzer/generate_offline_report.py:6058,6066,6531`  
- XML → HTML 入口：`scripts/rdc_analyzer/analyze_xml_report.py:25,1797`  

## Estimation
- Effort: 3–5 days  
- Story Points: 8  
- Original Estimate: 4 days  

## Risk Register
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| HTML 模板耦合导致回归 | High | Medium | Feature Flag 渐进迁移 |
| 数据字段缺失导致空列表 | High | Medium | Manifest 覆盖率校验 + 空数据标注 |
| 事件跳转跨视图失效 | Medium | Medium | 统一 Section ID + hash 跳转测试 |
| Issue Detector 与 rules 重复 | Medium | Medium | 明确 Issue Detector 仅做聚合，不新增规则口径 |

## Game Dev: Memory & Resource Budget (Leak Checks)
- 纹理/资源列表采用懒加载；报告生成时统计 JSON 大小与纹理总数，超阈值提示。  
- 禁止一次性渲染上万行表格；分页或折叠分组。  

## Game Dev: Asset Pipeline
- 统一资源路径策略（纹理导出目录 → Manifest 映射 → HTML 引用）。  
- 约定 `report_manifest.json` 为唯一入口，避免多份 JSON 口径分裂。  

## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: 使用同一份 RDC / 同一导出目录重跑报告，记录 hash 与时间戳。  
- Dump/Core: N/A（Python 级异常记录 traceback）。  
- Symbols: N/A  
- Build identity: 输出 git commit hash 到报告 footer。  

---

## Scope
**In Scope**  
- 统一 V3 / Offline / XML 三套报告的 UI 壳层  
- Manifest 数据契约 + 覆盖率校验  
- 四视图切换 + 基础跳转  

**Out of Scope**  
- B 路线（Replay）  
- Compare Mode（Phase 3）  
- 引入前端构建链  

## Assumptions
- A/C 路线可生成 XML/JSON 且字段稳定  
- 报告仍保持单文件 HTML 输出  
- 纹理缩略图允许 base64 内嵌  

## Design Summary (WHAT / WHY / HOW)
- **Issues**  
  - WHAT：问题聚合视图  
  - WHY：快速定位性能瓶颈  
  - HOW：基于既有规则输出的 issues 统一渲染  
- **Events**  
  - WHAT：事件浏览与追溯  
  - WHY：所有结论需追踪到 EID  
  - HOW：`event_pass_data` + 统一表格  
- **Resources**  
  - WHAT：纹理/缓冲列表  
  - WHY：资源是性能瓶颈主载体  
  - HOW：Manifest + 纹理缩略图  
- **Performance**  
  - WHAT：统计指标 + Top N  
  - WHY：核心 KPI 直达  
  - HOW：现有统计 + Rule 归并  

## Repo / File List (line refs)
- `scripts/rdc_analyzer/analyze_rdc.py:778,795,2110`  
- `scripts/rdc_analyzer/generate_offline_report.py:231,6066,6531`  
- `scripts/rdc_analyzer/analyze_xml_report.py:25,1797,1767`  

## Build/Test/Lint Quick Guide (record only)
- `py -3 scripts/rdc_analyzer/analyze_xml_report.py <capture.xml> -o report.html --ui-version=2`
- `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_manifest.py`
- `py -3 -m unittest scripts/rdc_analyzer/tests/test_issue_detector.py`

---

## P0 Task List (WHAT / WHY / HOW)
- **P0-1: Report Contract + Manifest**  
  - WHAT：统一所有报告的数据入口与字段覆盖统计  
  - WHY：空列表/不一致根因在口径分裂  
  - HOW：`report_contract.py` + `build_manifest()`  
- **P0-2: Issue Detector 聚合器**  
  - WHAT：将已有规则输出聚合成 Issues 视图  
  - WHY：避免重复规则体系，确保可追溯  
  - HOW：`issue_detector.py` 只聚合不新增口径  
- **P0-3: Unified UI Shell**  
  - WHAT：四视图统一壳层  
  - WHY：减少维护成本与用户混乱  
  - HOW：`report_ui.py` 生成统一 HTML  
- **P0-4: Feature Flag 迁移**  
  - WHAT：支持 `--ui-version=2`  
  - WHY：降低迁移风险  
  - HOW：新增 CLI 参数，分支保留旧逻辑  

---

## Task Checklist (TDD, 2–5 min steps)

### Task 1: Report Contract + Manifest
**Files:**  
- Create: `scripts/rdc_analyzer/report_contract.py`  
- Create: `scripts/rdc_analyzer/tests/test_report_manifest.py`

**Step 1: Write failing test**
```python
# tests/test_report_manifest.py
import unittest
from rdc_analyzer.report_contract import build_manifest, ReportDataContract

class TestManifest(unittest.TestCase):
    def test_manifest_counts(self):
        report = ReportDataContract(
            textures=[{"name": "t0"}],
            shaders=[{"name": "s0"}],
            events=[{"eid": 1}],
        )
        manifest = build_manifest(report)
        self.assertEqual(manifest["counts"]["textures"], 1)
        self.assertEqual(manifest["counts"]["shaders"], 1)
        self.assertEqual(manifest["counts"]["events"], 1)
```

**Step 2: Run test to verify it fails**  
Run: `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_manifest.py`  
Expected: FAIL (ImportError / missing symbol)

**Step 3: Write minimal implementation**
```python
# report_contract.py
from dataclasses import dataclass, field
from typing import Dict, Any, List

@dataclass
class ReportDataContract:
    meta: Dict[str, Any] = field(default_factory=dict)
    textures: List[Dict[str, Any]] = field(default_factory=list)
    shaders: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    buffers: List[Dict[str, Any]] = field(default_factory=list)
    issues: List[Dict[str, Any]] = field(default_factory=list)
    performance: Dict[str, Any] = field(default_factory=dict)

def build_manifest(report: ReportDataContract) -> Dict[str, Any]:
    counts = {
        "textures": len(report.textures),
        "shaders": len(report.shaders),
        "events": len(report.events),
        "buffers": len(report.buffers),
        "issues": len(report.issues),
    }
    non_empty = sum(1 for v in counts.values() if v > 0)
    coverage = non_empty / len(counts) if counts else 0.0
    return {"version": "2.0", "counts": counts, "coverage": coverage}
```

**Step 4: Run test to verify it passes**  
Run: `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_manifest.py`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/report_contract.py scripts/rdc_analyzer/tests/test_report_manifest.py
git commit -m "feat(rdc-analyzer): add report data contract and manifest

- add ReportDataContract dataclass
- add build_manifest with coverage"
```

### Task 2: Issue Detector 聚合器
**Files:**  
- Create: `scripts/rdc_analyzer/core/issue_detector.py`  
- Create: `scripts/rdc_analyzer/tests/test_issue_detector.py`

**Step 1: Write failing test**
```python
# tests/test_issue_detector.py
import unittest
from rdc_analyzer.core.issue_detector import detect_texture_issues, Severity, Category

class TestIssueDetector(unittest.TestCase):
    def test_oversized_texture(self):
        textures = [{"name": "huge", "width": 8192, "height": 8192}]
        issues = detect_texture_issues(textures)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, Severity.CRITICAL)
        self.assertEqual(issues[0].category, Category.TEXTURE)
```

**Step 2: Run test to verify it fails**  
Run: `py -3 -m unittest scripts/rdc_analyzer/tests/test_issue_detector.py`  
Expected: FAIL (ImportError / missing symbol)

**Step 3: Write minimal implementation**
```python
# core/issue_detector.py
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, List

class Severity(Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    PASS = "pass"

class Category(Enum):
    TEXTURE = "texture"
    SHADER = "shader"
    PERFORMANCE = "performance"
    STATE = "state"
    RESOURCE = "resource"

@dataclass
class Issue:
    id: str
    severity: Severity
    category: Category
    title: str
    details: Dict[str, Any]
    suggestion: str
    resource_id: str = ""
    event_id: int = 0

def detect_texture_issues(textures: List[Dict[str, Any]]) -> List[Issue]:
    issues: List[Issue] = []
    for idx, tex in enumerate(textures):
        w = tex.get("width", 0)
        h = tex.get("height", 0)
        name = tex.get("name", f"texture_{idx}")
        if w > 4096 or h > 4096:
            issues.append(Issue(
                id=f"TEX-{idx:03d}-SIZE",
                severity=Severity.CRITICAL,
                category=Category.TEXTURE,
                title=f"纹理 '{name}' 超过 4096 限制",
                details={"width": w, "height": h},
                suggestion="降采样到 4096 或拆分纹理",
                resource_id=name,
            ))
    return issues
```

**Step 4: Run test to verify it passes**  
Run: `py -3 -m unittest scripts/rdc_analyzer/tests/test_issue_detector.py`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/core/issue_detector.py scripts/rdc_analyzer/tests/test_issue_detector.py
git commit -m "feat(rdc-analyzer): add issue detector aggregator

- add Severity/Category/Issue models
- add detect_texture_issues baseline"
```

### Task 3: Unified UI Shell 骨架
**Files:**  
- Create: `scripts/rdc_analyzer/report_ui.py`

**Step 1: Write failing test**
```python
# append to tests/test_report_manifest.py
def test_shell_contains_views(self):
    from rdc_analyzer.report_ui import render_report_shell
    from rdc_analyzer.report_contract import ReportDataContract, build_manifest
    report = ReportDataContract()
    manifest = build_manifest(report)
    html = render_report_shell(report, manifest, mode="single")
    self.assertIn('id="view-issues"', html)
    self.assertIn('id="view-events"', html)
    self.assertIn('id="view-resources"', html)
    self.assertIn('id="view-performance"', html)
```

**Step 2: Run test to verify it fails**  
Run: `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_manifest.py`  
Expected: FAIL (missing render_report_shell)

**Step 3: Write minimal implementation**
```python
# report_ui.py
from typing import Dict, Any
from .report_contract import ReportDataContract

def render_report_shell(report: ReportDataContract, manifest: Dict[str, Any], mode: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>RDC Report</title></head>
<body>
  <header>RDC Analyzer | {report.meta.get("capture_name", "Unknown")} | {mode}</header>
  <nav>
    <button data-view="issues">Issues</button>
    <button data-view="events">Events</button>
    <button data-view="resources">Resources</button>
    <button data-view="performance">Performance</button>
  </nav>
  <section id="view-issues"></section>
  <section id="view-events"></section>
  <section id="view-resources"></section>
  <section id="view-performance"></section>
  <footer>Coverage: {manifest.get("coverage", 0):.0%}</footer>
</body></html>
"""
```

**Step 4: Run test to verify it passes**  
Run: `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_manifest.py`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/report_ui.py
git commit -m "feat(rdc-analyzer): add unified report UI shell"
```

### Task 4: Feature Flag `--ui-version`
**Files:**  
- Modify: `scripts/rdc_analyzer/analyze_xml_report.py`

**Step 1: Add CLI arg**
```python
parser.add_argument('--ui-version', type=int, default=1, choices=[1, 2],
                    help='UI version: 1=legacy, 2=unified shell')
```

**Step 2: Add branch**
```python
if args.ui_version == 2:
    from rdc_analyzer.report_contract import ReportDataContract, build_manifest
    from rdc_analyzer.report_ui import render_report_shell
    report = ReportDataContract(meta={"capture_name": capture_name}, textures=textures, shaders=shaders, events=events)
    manifest = build_manifest(report)
    html = render_report_shell(report, manifest, mode="single")
else:
    html = generate_legacy_html(...)
```

**Step 3: Commit**
```bash
git add scripts/rdc_analyzer/analyze_xml_report.py
git commit -m "feat(rdc-analyzer): add --ui-version flag for unified shell"
```

### Task 5: Manifest 校验工具
**Files:**  
- Create: `scripts/rdc_analyzer/tools/validate_manifest.py`

**Step 1: Add tool**
```python
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

**Step 2: Commit**
```bash
git add scripts/rdc_analyzer/tools/validate_manifest.py
git commit -m "feat(rdc-analyzer): add manifest coverage validator"
```

---

## Deferred Work (Requires separate /plan to keep 2–5 min steps)
- **V3 / Offline 报告迁移到统一壳层**  
- **四视图完整实现（Issues/Events/Resources/Performance 细化）**  
- **Compare Mode**  

---

## Next Steps
- [ ] 你确认后进入 `/do`，按 Task 1–5 顺序执行。  
