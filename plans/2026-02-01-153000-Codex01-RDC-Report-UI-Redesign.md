# RDC Report UI Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-02-01  
**Owner:** Codex01  
**Last Updated:** 2026-02-01

**Goal:** 统一当前三套 HTML 报告的“信息架构 + 视觉层级 + 数据入口”，让 A/C 路线输出的报告在一个页面内完成主诊断、资源检索与事件跳转，并为未来 B 路线的回放数据对齐提供稳定壳层。  
**Architecture:** 以“Report Data Contract + Manifest + Shared UI Shell”为核心，数据层（解析/规则/统计）与展示层（HTML/CSS/JS）解耦；所有页面只换数据、不换页面结构。  
**Tech Stack:** Python 3 (scripts/rdc_analyzer), HTML/CSS/JS (inline templates), RenderDoc CLI (renderdoccmd), JSON.

---

## Plan Metadata
- Version: 2026-02-01
- Owner: Codex01
- Last Updated: 2026-02-01
- Plan File: plans/2026-02-01-153000-Codex01-RDC-Report-UI-Redesign.md

## Goal
- 在不引入新依赖的前提下，将当前 V3 报告与 Offline 报告合并为**同一套页面壳层**，实现单帧与对比数据的**一致展示逻辑**与**双向跳转**。

## Architecture
- 新增 `report_contract.py` 定义 Report Data Contract + Manifest（统一数据口径）。
- 新增 `report_ui.py` 输出统一 UI Shell（顶栏/左侧导航/主体区域/事件浏览）。
- A 路线（analyze_xml_report）与 V3/Offline 路线统一调用 `render_report_shell(...)`，仅提供数据差异。
- 所有模块通过 Section IDs 交叉跳转（资源 → 事件、Shader → Pipeline、对比 → 单帧）。

## Tech Stack
- Python 3 (rdc_analyzer scripts)
- HTML/CSS/JS（内嵌模板）
- JSON（report + manifest）
- RenderDoc CLI (`renderdoccmd convert`/`renderdoccmd export`)

## Success Criteria (measurable)
- 生成的单帧 HTML 报告在同一页面包含：Summary、Event Browser、Textures、Shaders、Pipeline/State、Resources。  
- 同一份数据在 V3/Offline 输出中 **Section ID 与导航一致**（跳转无断链）。  
- 若 XML 数据含 `textures`/`shaders`，HTML 对应列表 **非空**（空则必须标注“无数据来源”）。  
- A/C 路线报告均含 `report_manifest.json`，字段覆盖率 ≥ 0.90。  

## Acceptance Criteria
- 用户可以在“网格视图/事件视图/主视图”之间切换，但**只是一套页面壳层**的模式切换。  
- 报告顶部显示 capture 名称 + 数据源（A/C/B），并能跳转到“对比报告入口”。  
- 两份报告可在页面内相互跳转（单帧 ↔ 对比）；跳转保留当前 tab。  

## Verification Commands
- `py -3 scripts/rdc_analyzer/analyze_xml_report.py <capture.xml> -o <report.html>` (Expected: 生成 HTML 且包含 `ReportManifest` 字段)  
- `py -3 scripts/rdc_analyzer/analyze_xml_report.py <capture.xml> --texture-dir <dir>` (Expected: HTML 中纹理数量 > 0 或注明无数据)  
- `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_manifest.py` (Expected: PASS)  

## Evidence
- `scripts/rdc_analyzer/analyze_rdc.py:778,795`（V3 报告入口与标题）  
- `scripts/rdc_analyzer/generate_offline_report.py:6058,6066,6531`（Offline 页面壳层与 Event Browser）  
- `scripts/rdc_analyzer/analyze_xml_report.py:25,1797`（XML→HTML 用法）  

## Estimation
- Effort: 3-5 days
- Story Points: 8
- Original Estimate: 4 days

## Risk Register
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| HTML 模板耦合过深导致回归 | High | Medium | 先抽壳层，保持旧函数存在并开 Feature Flag |
| 数据字段缺失导致“空列表” | High | Medium | Manifest+Coverage 校验，空则标注“无数据来源” |
| 事件跳转跨视图失效 | Medium | Medium | 统一 Section ID + hash 跳转测试 |

## Game Dev: Memory & Resource Budget (Leak Checks)
- HTML 生成阶段不引入新缓存；对大纹理列表使用懒加载，避免一次性渲染上万条。  
- 报告生成时统计 JSON 大小与纹理总数，超过阈值在报告顶部提示（避免 OOM）。  

## Game Dev: Asset Pipeline
- 统一资源路径策略（纹理导出目录 → Manifest 映射 → HTML 引用）。  
- 约定 `report_manifest.json` 为 HTML 的**唯一入口**，避免多份 JSON 口径分裂。  

## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: 使用同一份 RDC/同一导出目录重跑 HTML，记录 hash 与时间戳。  
- Dump/Core: N/A（Python 级异常以 traceback 记录）  
- Symbols: N/A  
- Build identity: 记录 git commit hash（导出日志中输出）。

---

## Scope
- **In:** 统一 V3 报告 + Offline 报告 + A 路线 XML 报告的 UI 壳层与跳转逻辑。  
- **Out:** B 路线（Replay/设备回放）与新增渲染功能。  

## Assumptions
- A/C 路线可生成 XML/JSON 且字段稳定；空字段必须标注来源缺失。  
- 当前脚本以单文件 HTML 输出为主，不引入新前端构建链。  

## Design Summary (WHAT / WHY / HOW)
- **Summary / Health**  
  - WHAT: 首屏显示关键指标、规则命中与结论。  
  - WHY: 快速决策是否值得继续深挖。  
  - HOW: 从 `analysis_summary` + `issues` 聚合渲染。  
- **Timeline & Event Browser**  
  - WHAT: 按 EID/Pass/DrawCall 浏览事件链路。  
  - WHY: 所有性能分析需要可追溯到具体调用。  
  - HOW: `event_pass_data` + `event_list` → 统一表格/筛选器。  
- **Resource Explorer (Textures/Buffers)**  
  - WHAT: 资源列表 + 缩略图 + 绑定位置。  
  - WHY: 纹理/缓冲是性能瓶颈的主要载体。  
  - HOW: `resources.textures/buffers` + manifest 统计。  
- **Shaders & Pipeline**  
  - WHAT: Shader 详情 + Pipeline state。  
  - WHY: 关键瓶颈常在 Shader 与管线配置。  
  - HOW: `shaders` + `pipelineState` → 详情面板。  
- **Compare Mode**  
  - WHAT: baseline vs target 对比视图。  
  - WHY: 真实优化需要差异验证。  
  - HOW: `diff_report.json` 以相同 UI 组件渲染。  

## Design References (5) + 采用点
- **Chrome DevTools Performance**：时间线 + flame chart + 事件跳转启发“事件↔资源”双向关联。citeturn0search3  
- **Unity Profiler**：Timeline/Hierarchy 切换启发“同数据不同视角”。citeturn0search4  
- **Grafana Best Practices**：仪表板要“讲故事、降低认知负担”。citeturn1search3  
- **Grafana Dashboard Layout**：Auto grid/Custom 布局启发“网格视图/自由视图”切换。citeturn1search2  
- **Datadog Dashboards**：Dashboard/Timeboard 两类布局与可折叠分组启发“按任务折叠”。citeturn2search10turn2search1  
- **New Relic Dashboards**：强调高密度可视化与跨数据源关联。citeturn1search0  

## Repo / File List (with line refs)
- `scripts/rdc_analyzer/analyze_rdc.py:778,795,2110` (V3 HTML 生成与纹理视图)  
- `scripts/rdc_analyzer/generate_offline_report.py:231,6066,6531` (Offline UI 壳层与 Event Browser)  
- `scripts/rdc_analyzer/analyze_xml_report.py:25,1797` (XML → HTML 入口用法)  
- `scripts/rdc_analyzer/analyze_xml_report.py:1767,1953` (main 入口)  

## Approach (Pseudo-code)
```
report = build_report_data(source)           # A/C pipeline
manifest = build_manifest(report)
html = render_report_shell(report, manifest, mode="single|compare")
write_html(html)
write_json(manifest, "report_manifest.json")
```

## Impact Analysis
- HTML 结构统一会影响旧报告的 CSS/JS 选择器，需保持旧 ID 或映射。  
- 事件跳转逻辑集中后，需确保各数据源字段一致；否则需显式标注缺失原因。  

## Build/Test/Lint Quick Guide (record only)
- `py -3 scripts/rdc_analyzer/analyze_xml_report.py <capture.xml> -o <report.html>`
- `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_manifest.py`

---

## P0 Task List (WHAT / WHY / HOW)
- **P0-1: Report Data Contract + Manifest**  
  - WHAT: 统一所有报告的数据入口与字段覆盖统计。  
  - WHY: 数据不一致导致 UI 空洞与跳转失败。  
  - HOW: 新增 `report_contract.py` + `build_manifest()`。  
- **P0-2: Shared UI Shell**  
  - WHAT: 一套 HTML 壳层覆盖 V3/Offline/XML。  
  - WHY: 维护三套 UI 成本过高且体验割裂。  
  - HOW: 抽出 `render_report_shell()` 并统一 Section IDs。  
- **P0-3: Cross-Link Navigation**  
  - WHAT: 资源/Shader/事件互跳。  
  - WHY: 性能诊断必须可追溯。  
  - HOW: Anchor IDs + `jumpToEvent(eid)` 统一实现。  
- **P0-4: Coverage Gate**  
  - WHAT: 生成报告时校验关键字段覆盖率 ≥ 0.90。  
  - WHY: 防止“看似完整但空数据”的报告。  
  - HOW: Manifest + unittest 校验。  

---

## Task Checklist (2–5 min steps, TDD)

### Task 1: Report Contract + Manifest
**Files:**  
- Create: `scripts/rdc_analyzer/report_contract.py`  
- Create: `scripts/rdc_analyzer/tests/test_report_manifest.py`

**Step 1: Write failing test**
```python
import unittest
from rdc_analyzer.report_contract import build_manifest

class TestManifest(unittest.TestCase):
    def test_manifest_counts(self):
        report = {"textures": [{"name": "t0"}], "shaders": [{"name": "s0"}]}
        manifest = build_manifest(report)
        self.assertEqual(manifest["counts"]["textures"], 1)
        self.assertEqual(manifest["counts"]["shaders"], 1)
```

**Step 2: Run test to verify it fails**  
Run: `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_manifest.py`  
Expected: FAIL (ImportError or missing function).

**Step 3: Write minimal implementation**
```python
def build_manifest(report):
    return {
        "counts": {
            "textures": len(report.get("textures", [])),
            "shaders": len(report.get("shaders", [])),
        }
    }
```

**Step 4: Run test to verify it passes**  
Run: `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_manifest.py`  
Expected: PASS.

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/report_contract.py scripts/rdc_analyzer/tests/test_report_manifest.py
git commit -m "feat(rdc-analyzer): add report manifest contract

- add minimal manifest builder
- add unit test for manifest counts"
```

### Task 2: Shared UI Shell (Header/Nav/Section IDs)
**Files:**  
- Create: `scripts/rdc_analyzer/report_ui.py`  
- Modify: `scripts/rdc_analyzer/analyze_xml_report.py:1767`

**Step 1: Write failing test**
```python
from rdc_analyzer.report_ui import render_report_shell

def test_shell_contains_sections():
    html = render_report_shell({"textures": [], "shaders": []}, {"counts": {}}, mode="single")
    assert "id=\"section-textures\"" in html
    assert "id=\"section-shaders\"" in html
```

**Step 2: Run test to verify it fails**  
Run: `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_manifest.py`  
Expected: FAIL (missing render_report_shell).

**Step 3: Write minimal implementation**
```python
def render_report_shell(report, manifest, mode):
    return (
        "<div id=\"section-textures\"></div>"
        "<div id=\"section-shaders\"></div>"
    )
```

**Step 4: Run test to verify it passes**  
Run: `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_manifest.py`  
Expected: PASS.

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/report_ui.py scripts/rdc_analyzer/analyze_xml_report.py
git commit -m "feat(rdc-analyzer): add shared report shell skeleton

- add render_report_shell entrypoint
- prepare XML report integration"
```

### Task 3: Wire A-route (XML → HTML)
**Files:**  
- Modify: `scripts/rdc_analyzer/analyze_xml_report.py:1767,1797`

**Step 1: Write failing test**
```python
def test_manifest_embedded():
    html = render_report_shell({"textures": []}, {"counts": {"textures": 0}}, "single")
    assert "reportManifest" in html
```

**Step 2: Run test to verify it fails**  
Run: `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_manifest.py`  
Expected: FAIL (manifest not embedded).

**Step 3: Write minimal implementation**
```python
manifest = build_manifest(report_data)
html = render_report_shell(report_data, manifest, mode="single")
```

**Step 4: Run test to verify it passes**  
Run: `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_manifest.py`  
Expected: PASS.

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/analyze_xml_report.py
git commit -m "feat(rdc-analyzer): unify XML report with shared UI shell

- embed manifest in HTML
- keep XML pipeline unchanged"
```

### Task 4: Wire V3 + Offline Reports
**Files:**  
- Modify: `scripts/rdc_analyzer/analyze_rdc.py:778,795`  
- Modify: `scripts/rdc_analyzer/generate_offline_report.py:6058,6066,6531`

**Step 1: Write failing test**
```python
def test_section_ids_consistent():
    html = render_report_shell({}, {"counts": {}}, "single")
    assert "section-textures" in html and "section-shaders" in html
```

**Step 2: Run test to verify it fails**  
Run: `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_manifest.py`  
Expected: FAIL (IDs mismatch).

**Step 3: Write minimal implementation**
```python
# Replace legacy section IDs with shared IDs in V3/Offline templates
```

**Step 4: Run test to verify it passes**  
Run: `py -3 -m unittest scripts/rdc_analyzer/tests/test_report_manifest.py`  
Expected: PASS.

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/analyze_rdc.py scripts/rdc_analyzer/generate_offline_report.py
git commit -m "refactor(rdc-analyzer): align V3/offline report sections

- unify section ids
- keep legacy styles intact"
```

---

## Risks / Blockers
- Serena 对 `scripts/rdc_analyzer` 目录访问被限制（需继续用 codemap/rg 取行号）。  
- 若 HTML 结构差异过大，可能需要短期保留旧模板并设置 `--ui-version` 兼容选项。  

## Decisions
- 不引入前端框架，不增加新依赖。  
- 以 Manifest 为唯一数据入口，避免多份 JSON 口径并存。  

## Verification / Acceptance (Definition of Done)
- 报告页面包含所有核心模块且可跳转。  
- A/C 路线 HTML 报告内容一致（仅数据不同）。  
- Manifest 通过覆盖率校验且无“空表”。  

## Next Steps
- 等你 /do 批准后执行。  
