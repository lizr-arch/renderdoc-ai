# RDC Report UI 统一重构计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2025-01-21  
**Owner:** Codex01 + AI  
**Status:** /plan Phase - 待审批

---

## 0. 设计融合说明

本文档合并了两份设计：
- **Codex01 设计** (`2026-02-01-153000-Codex01-RDC-Report-UI-Redesign.md`)：侧重数据契约 + Manifest + 统一 Shell
- **AI SPEC 设计** (`UI_REDESIGN_SPEC.md`)：侧重四视图架构 + 问题驱动 + 业界调研

### 融合决策

| 维度 | 采纳方案 | 来源 |
|------|---------|------|
| 数据层 | Report Contract + Manifest | Codex01 ✅ |
| 展示层 | 混合：`report_ui.py` Shell + `templates/` 组件 | 融合 ✅ |
| 信息架构 | 四视图 (Issues/Events/Resources/Performance) | AI SPEC ✅ |
| TDD 流程 | 5 步 TDD (失败测试→实现→验证→提交) | Codex01 ✅ |
| 对比报告 | Phase 3 (优先单帧分析) | 用户决策 ✅ |
| 兼容策略 | Feature Flag `--ui-version=2` | Codex01 ✅ |

---

## 1. Goal

统一当前三套 HTML 报告 (V3/Offline/XML) 的信息架构、视觉层级与数据入口，实现：
1. **单页面四视图切换**：Issues / Events / Resources / Performance
2. **数据与展示解耦**：Report Contract + Manifest 为唯一数据入口
3. **问题驱动首页**：自动检测问题，聚合展示
4. **跨模块跳转**：资源 ↔ 事件 ↔ Shader 互相跳转

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        数据层 (Python)                          │
├─────────────────────────────────────────────────────────────────┤
│  analyze_xml_report.py ──┐                                      │
│  analyze_rdc.py ─────────┼──→ report_contract.py ──→ Manifest   │
│  generate_offline.py ────┘      └──→ issue_detector.py          │
├─────────────────────────────────────────────────────────────────┤
│                        展示层 (HTML/JS)                         │
├─────────────────────────────────────────────────────────────────┤
│  report_ui.py ──→ render_report_shell()                         │
│       │                                                         │
│       ├──→ templates/views/issues.html                          │
│       ├──→ templates/views/events.html                          │
│       ├──→ templates/views/resources.html                       │
│       └──→ templates/views/performance.html                     │
└─────────────────────────────────────────────────────────────────┘
```

## 3. Tech Stack

- Python 3 (`scripts/rdc_analyzer`)
- HTML/CSS/JS (内嵌模板 + `templates/` 组件)
- JSON (Report Data + Manifest)
- RenderDoc CLI (`renderdoccmd`)

## 4. Success Criteria (可量化)

| 指标 | 阈值 | 验证方式 |
|------|------|---------|
| Manifest 字段覆盖率 | ≥ 0.90 | `test_report_manifest.py` |
| Section ID 一致性 | 100% | 跨视图跳转测试 |
| 四视图功能完整 | 全部 Tab 可切换 | 手动验收 |
| 空数据标注 | 无静默空列表 | 目视检查 |
| 问题检测数量 | ≥ 5 类规则 | Issue 类型枚举 |

## 5. Acceptance Criteria

- [ ] 用户可在 Issues/Events/Resources/Performance 四视图间切换
- [ ] 报告顶部显示 capture 名称 + 数据源 (A/C/B)
- [ ] Manifest 嵌入 HTML，可导出 JSON
- [ ] 空数据字段显示"无数据来源"提示
- [ ] `--ui-version=1` 可回退旧版

## 6. Verification Commands

```bash
# 生成 v2 报告
py -3 scripts/rdc_analyzer/analyze_xml_report.py <capture.xml> -o report.html --ui-version=2

# 运行单元测试
py -3 -m unittest scripts/rdc_analyzer/tests/test_report_manifest.py
py -3 -m unittest scripts/rdc_analyzer/tests/test_issue_detector.py

# 验证 Manifest 覆盖率
py -3 scripts/rdc_analyzer/tools/validate_manifest.py report_manifest.json
```

---

## 7. Scope

**In Scope:**
- 统一 V3 / Offline / XML 三套报告的 UI 壳层
- 四视图架构实现
- Report Contract + Manifest 机制
- Issue Detector 规则引擎
- 跨模块跳转 (Section IDs + `jumpToEvent()`)

**Out of Scope:**
- B 路线 (Replay 回放)
- Compare Mode (Phase 3)
- 新前端框架依赖

## 8. Assumptions

- A/C 路线可生成 XML/JSON 且字段稳定
- 保持单 HTML 文件输出，不引入构建链
- 纹理缩略图内嵌 base64

---

## 9. Risk Register

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| HTML 模板耦合过深导致回归 | High | Medium | Feature Flag `--ui-version` 兼容 |
| 数据字段缺失导致空列表 | High | Medium | Manifest 覆盖率校验 + 空数据标注 |
| 事件跳转跨视图失效 | Medium | Medium | 统一 Section ID + hash 跳转测试 |
| 12000 行迁移风险 | High | Medium | 渐进式：先 Shell，后逐步提取组件 |

---

## 10. 文件结构 (目标状态)

```
scripts/rdc_analyzer/
├── report_contract.py          # [NEW] 数据契约 + Manifest
├── report_ui.py                # [NEW] 统一 UI Shell 入口
├── core/
│   ├── issue_detector.py       # [NEW] 问题检测器
│   └── report_schema.py        # [NEW] 数据结构定义
├── templates/                  # [NEW] HTML 组件目录
│   ├── base/
│   │   ├── layout.html         # 基础布局框架
│   │   └── styles.css          # 公共样式
│   ├── views/
│   │   ├── issues.html         # Issues 视图
│   │   ├── events.html         # Events 视图
│   │   ├── resources.html      # Resources 视图
│   │   └── performance.html    # Performance 视图
│   └── components/
│       ├── header.html         # 顶部导航
│       ├── texture_card.html   # 纹理卡片
│       └── issue_card.html     # 问题卡片
├── tests/
│   ├── test_report_manifest.py # [NEW] Manifest 测试
│   └── test_issue_detector.py  # [NEW] Issue 检测测试
└── tools/
    └── validate_manifest.py    # [NEW] 覆盖率校验工具
```

---

## 11. Phase 划分

| Phase | 名称 | 预估工时 | 目标产物 |
|-------|------|---------|---------|
| **Phase 1** | 数据契约 + 基础架构 | 2 天 | Manifest + Shell 骨架 |
| **Phase 2** | 四视图实现 | 3-4 天 | 完整四视图 + 跳转 |
| **Phase 3** | 增强功能 | 2-3 天 | Compare Mode + 可视化 |

---

## 12. Task Checklist (TDD 格式)

### Phase 1: 数据契约 + 基础架构

#### Task 1.1: Report Contract + Manifest
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
            textures=[{"name": "t0", "width": 1024}],
            shaders=[{"name": "s0"}],
            events=[{"eid": 1}]
        )
        manifest = build_manifest(report)
        self.assertEqual(manifest["counts"]["textures"], 1)
        self.assertEqual(manifest["counts"]["shaders"], 1)
        self.assertEqual(manifest["counts"]["events"], 1)
    
    def test_coverage_calculation(self):
        report = ReportDataContract(textures=[], shaders=[])
        manifest = build_manifest(report)
        self.assertLess(manifest["coverage"], 0.5)  # 空数据覆盖率低
```

**Step 2: Run test (expect FAIL)**
```bash
py -3 -m unittest scripts/rdc_analyzer/tests/test_report_manifest.py
# Expected: ImportError
```

**Step 3: Write minimal implementation**
```python
# report_contract.py
from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class ReportDataContract:
    """统一的报告数据契约"""
    meta: Dict[str, Any] = field(default_factory=dict)
    textures: List[Dict] = field(default_factory=list)
    shaders: List[Dict] = field(default_factory=list)
    events: List[Dict] = field(default_factory=list)
    buffers: List[Dict] = field(default_factory=list)
    issues: List[Dict] = field(default_factory=list)
    performance: Dict[str, Any] = field(default_factory=dict)

def build_manifest(report: ReportDataContract) -> Dict[str, Any]:
    """构建 Manifest，统计字段覆盖率"""
    counts = {
        "textures": len(report.textures),
        "shaders": len(report.shaders),
        "events": len(report.events),
        "buffers": len(report.buffers),
        "issues": len(report.issues),
    }
    
    # 计算覆盖率：非空字段数 / 总字段数
    non_empty = sum(1 for v in counts.values() if v > 0)
    coverage = non_empty / len(counts) if counts else 0.0
    
    return {
        "version": "2.0",
        "counts": counts,
        "coverage": coverage,
        "generated_at": None,  # 填充时间戳
    }
```

**Step 4: Run test (expect PASS)**
```bash
py -3 -m unittest scripts/rdc_analyzer/tests/test_report_manifest.py
# Expected: OK
```

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/report_contract.py scripts/rdc_analyzer/tests/test_report_manifest.py
git commit -m "feat(rdc-analyzer): add report data contract and manifest

- add ReportDataContract dataclass
- add build_manifest() with coverage calculation
- add unit tests for manifest counts and coverage"
```

---

#### Task 1.2: Issue Detector 基础
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
        textures = [{"name": "huge_tex", "width": 8192, "height": 8192}]
        issues = detect_texture_issues(textures)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, Severity.CRITICAL)
        self.assertEqual(issues[0].category, Category.TEXTURE)
    
    def test_missing_mipmap(self):
        textures = [{"name": "no_mip", "width": 1024, "height": 1024, "mips": 1}]
        issues = detect_texture_issues(textures)
        self.assertTrue(any(i.severity == Severity.WARNING for i in issues))
```

**Step 2: Run test (expect FAIL)**
```bash
py -3 -m unittest scripts/rdc_analyzer/tests/test_issue_detector.py
# Expected: ImportError
```

**Step 3: Write minimal implementation**
```python
# core/issue_detector.py
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any

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
    resource_id: str = None
    event_id: int = None

def detect_texture_issues(textures: List[Dict]) -> List[Issue]:
    """检测纹理相关问题"""
    issues = []
    for i, tex in enumerate(textures):
        name = tex.get("name", f"texture_{i}")
        width = tex.get("width", 0)
        height = tex.get("height", 0)
        mips = tex.get("mips", 0)
        
        # 规则 1: 尺寸过大
        if width > 4096 or height > 4096:
            issues.append(Issue(
                id=f"TEX-{i:03d}-SIZE",
                severity=Severity.CRITICAL,
                category=Category.TEXTURE,
                title=f"纹理 '{name}' 超过 4096 限制",
                details={"width": width, "height": height},
                suggestion="降采样到 4096 或拆分纹理",
                resource_id=name
            ))
        
        # 规则 2: 缺少 mipmap
        if width >= 512 and mips <= 1:
            issues.append(Issue(
                id=f"TEX-{i:03d}-MIP",
                severity=Severity.WARNING,
                category=Category.TEXTURE,
                title=f"纹理 '{name}' 缺少 mipmap",
                details={"mips": mips},
                suggestion="生成完整 mipmap 链",
                resource_id=name
            ))
    
    return issues
```

**Step 4: Run test (expect PASS)**
```bash
py -3 -m unittest scripts/rdc_analyzer/tests/test_issue_detector.py
# Expected: OK
```

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/core/issue_detector.py scripts/rdc_analyzer/tests/test_issue_detector.py
git commit -m "feat(rdc-analyzer): add issue detector with texture rules

- add Severity and Category enums
- add Issue dataclass
- add detect_texture_issues() with size/mipmap rules
- add unit tests"
```

---

#### Task 1.3: Report UI Shell 骨架
**Files:**
- Create: `scripts/rdc_analyzer/report_ui.py`
- Create: `scripts/rdc_analyzer/templates/base/layout.html`

**Step 1: Write failing test**
```python
# 添加到 tests/test_report_manifest.py
def test_shell_contains_sections(self):
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

**Step 2: Run test (expect FAIL)**

**Step 3: Write minimal implementation**
```python
# report_ui.py
from pathlib import Path
from typing import Dict, Any
from .report_contract import ReportDataContract

TEMPLATES_DIR = Path(__file__).parent / "templates"

def load_template(name: str) -> str:
    """加载模板文件"""
    path = TEMPLATES_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return f"<!-- Template not found: {name} -->"

def render_report_shell(
    report: ReportDataContract,
    manifest: Dict[str, Any],
    mode: str = "single"
) -> str:
    """渲染统一的报告 Shell"""
    
    # 顶部导航
    header = f'''
    <header class="report-header">
        <h1>🎮 RDC Analyzer</h1>
        <span class="capture-name">{report.meta.get("capture_name", "Unknown")}</span>
        <span class="data-source">Source: {mode.upper()}</span>
    </header>
    '''
    
    # 四视图标签页
    tabs = '''
    <nav class="view-tabs">
        <button class="tab active" data-view="issues">🎯 Issues</button>
        <button class="tab" data-view="events">📁 Events</button>
        <button class="tab" data-view="resources">📦 Resources</button>
        <button class="tab" data-view="performance">⚡ Performance</button>
    </nav>
    '''
    
    # 视图容器
    views = '''
    <main class="view-container">
        <section id="view-issues" class="view active">
            <h2>Issues Dashboard</h2>
            <p>问题列表将在此显示</p>
        </section>
        <section id="view-events" class="view">
            <h2>Event Browser</h2>
            <p>事件列表将在此显示</p>
        </section>
        <section id="view-resources" class="view">
            <h2>Resource Explorer</h2>
            <p>资源列表将在此显示</p>
        </section>
        <section id="view-performance" class="view">
            <h2>Performance</h2>
            <p>性能数据将在此显示</p>
        </section>
    </main>
    '''
    
    # 底部状态栏
    footer = f'''
    <footer class="report-footer">
        <span>Textures: {manifest["counts"]["textures"]}</span>
        <span>Shaders: {manifest["counts"]["shaders"]}</span>
        <span>Events: {manifest["counts"]["events"]}</span>
        <span>Coverage: {manifest["coverage"]:.0%}</span>
    </footer>
    '''
    
    # 样式
    styles = '''
    <style>
        :root { --bg: #1e1e1e; --fg: #d4d4d4; --accent: #569cd6; }
        body { font-family: system-ui; background: var(--bg); color: var(--fg); margin: 0; }
        .report-header { padding: 1rem; background: #252526; display: flex; gap: 1rem; align-items: center; }
        .view-tabs { display: flex; gap: 0.5rem; padding: 0.5rem 1rem; background: #333; }
        .tab { padding: 0.5rem 1rem; border: none; background: transparent; color: var(--fg); cursor: pointer; }
        .tab.active { background: var(--accent); color: #fff; border-radius: 4px; }
        .view { display: none; padding: 1rem; }
        .view.active { display: block; }
        .report-footer { padding: 0.5rem 1rem; background: #252526; display: flex; gap: 2rem; font-size: 0.9rem; }
    </style>
    '''
    
    # 脚本
    scripts = '''
    <script>
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById('view-' + tab.dataset.view).classList.add('active');
            });
        });
    </script>
    '''
    
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>RDC Report</title>
    {styles}
</head>
<body>
    {header}
    {tabs}
    {views}
    {footer}
    {scripts}
</body>
</html>'''
```

**Step 4: Run test (expect PASS)**

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/report_ui.py
git commit -m "feat(rdc-analyzer): add unified report UI shell

- add render_report_shell() with 4-view tabs
- add dark theme CSS
- add view switching JS"
```

---

#### Task 1.4: Feature Flag 兼容
**Files:**
- Modify: `scripts/rdc_analyzer/analyze_xml_report.py`

**Step 1: 添加 CLI 参数**
```python
# 在 argparse 部分添加
parser.add_argument('--ui-version', type=int, default=1, choices=[1, 2],
                    help='UI version: 1=legacy, 2=unified shell')
```

**Step 2: 条件分支**
```python
if args.ui_version == 2:
    from .report_contract import ReportDataContract, build_manifest
    from .report_ui import render_report_shell
    
    report = ReportDataContract(...)
    manifest = build_manifest(report)
    html = render_report_shell(report, manifest, mode="single")
else:
    # 保留旧版生成逻辑
    html = generate_legacy_html(...)
```

**Step 3: Commit**
```bash
git commit -m "feat(rdc-analyzer): add --ui-version flag for gradual migration

- ui-version=1: legacy behavior (default)
- ui-version=2: new unified shell"
```

---

### Phase 2: 四视图实现

#### Task 2.1: Issues 视图完整实现
- [ ] 渲染问题统计卡片 (Critical/Warning/Info/Pass)
- [ ] 渲染问题列表 (含跳转按钮)
- [ ] 实现 `jumpToResource(id)` / `jumpToEvent(eid)`
- [ ] 添加过滤器 (按严重程度/类别)

#### Task 2.2: Events 视图完整实现
- [ ] 渲染事件树 (Pass 分组)
- [ ] 渲染详情面板 (Pipeline State)
- [ ] 迁移 `generate_offline_report.py` 中的 Event Browser 逻辑

#### Task 2.3: Resources 视图完整实现
- [ ] 渲染资源列表 (网格/列表切换)
- [ ] 渲染纹理详情 (通道分离)
- [ ] 迁移现有纹理查看器逻辑

#### Task 2.4: Performance 视图完整实现
- [ ] 渲染性能指标卡片
- [ ] 渲染 Top N 事件列表
- [ ] 可选：Mali GPU 建议

#### Task 2.5: 跨视图跳转测试
- [ ] 验证 Issues → Resources 跳转
- [ ] 验证 Issues → Events 跳转
- [ ] 验证 Resources → Events 跳转

---

### Phase 3: 增强功能 (待 Phase 2 完成后细化)

- [ ] Compare Mode 实现
- [ ] Timeline 可视化
- [ ] Dependency Graph
- [ ] 文档更新

---

## 13. Decisions Log

| 决策 | 理由 | 日期 |
|------|------|------|
| 采用混合模板方案 | 兼顾简单与可维护 | 2025-01-21 |
| Compare Mode 放 Phase 3 | 优先完成单帧分析 | 2025-01-21 |
| 使用 Feature Flag | 平滑迁移，降低风险 | 2025-01-21 |
| 四视图架构 | 问题驱动 + 角色适配 | 2025-01-21 |

---

## 14. Next Steps

- [ ] 用户审批本计划
- [ ] `/do` 开始执行 Task 1.1

---

## 附录 A: 四视图 ASCII 原型

### Issues Dashboard
```
┌─────────────────────────────────────────────────────────────┐
│ [🎯 Issues] [📁 Events] [📦 Resources] [⚡ Performance]     │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐            │
│ │🔴 3     │ │🟠 5     │ │🟡 4     │ │✅ 28    │            │
│ │Critical │ │Warning  │ │Info     │ │Pass     │            │
│ └─────────┘ └─────────┘ └─────────┘ └─────────┘            │
├─────────────────────────────────────────────────────────────┤
│ 🔴 [TEX-001] 纹理超过 4096 限制                            │
│    hero_diffuse | 8192x8192 | [→ 资源] [→ 事件]            │
├─────────────────────────────────────────────────────────────┤
│ 🟠 [TEX-002] 缺少 mipmap                                   │
│    env_skybox | mips=1 | [→ 资源]                          │
└─────────────────────────────────────────────────────────────┘
```

### Events View
```
┌──────────────────┬──────────────────────────────────────────┐
│ Event Tree       │ Details                                  │
├──────────────────┼──────────────────────────────────────────┤
│ 📁 Frame         │ Pipeline State                           │
│ ├─ 📁 GBuffer    │ ┌────────────────────────────────────────┤
│ │  ├─ EID 12    │ │ VS: model_vs.hlsl                      │
│ │  └─ EID 15    │ │ PS: pbr_ps.hlsl                        │
│ ├─ 📁 Lighting   │ │ Blend: SrcAlpha, OneMinusSrcAlpha      │
│ └─ 📁 PostFX     │ │ Depth: LessEqual                       │
└──────────────────┴──────────────────────────────────────────┘
```

## 附录 B: 数据契约 JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["meta", "textures", "events"],
  "properties": {
    "meta": {
      "type": "object",
      "properties": {
        "capture_name": { "type": "string" },
        "api": { "type": "string", "enum": ["D3D11", "D3D12", "Vulkan", "OpenGL"] },
        "generated_at": { "type": "string", "format": "date-time" }
      }
    },
    "textures": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "width": { "type": "integer" },
          "height": { "type": "integer" },
          "format": { "type": "string" },
          "mips": { "type": "integer" }
        }
      }
    },
    "issues": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": { "type": "string" },
          "severity": { "type": "string", "enum": ["critical", "warning", "info", "pass"] },
          "category": { "type": "string" },
          "title": { "type": "string" },
          "suggestion": { "type": "string" }
        }
      }
    }
  }
}
```
