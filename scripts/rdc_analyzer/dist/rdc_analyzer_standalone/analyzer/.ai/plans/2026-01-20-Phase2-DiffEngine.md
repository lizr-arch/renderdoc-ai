# Phase 2: RDC 对比分析 (DiffEngine) 实施计划

> **Version**: 1.0.0 | **Created**: 2026-01-20 | **Agent**: Flux0120
> 
> **目标**: 实现 RDC 文件对比分析系统，支持识别性能回归和资源变化

---

## 1. 需求分析

### 1.1 现有资源

| 文件 | 描述 | 可复用程度 |
|------|------|-----------|
| `compare_test.py` | Shader Cycle 对比原型 | **高** - 对比逻辑可提取 |
| `core/types.py` | 数据结构定义 | **高** - TextureInfo, DrawCallInfo 等 |
| `core/context.py` | AnalysisContext | **高** - 作为对比输入 |
| `exporters/html_exporter.py` | HTML 报告生成 | **中** - 需扩展 Diff 视图 |

### 1.2 输入依赖

**Phase 1 输出 (由其他 AI 负责)**:
- `XMLToContextBridge` → 将 XML/JSON 数据转换为 `AnalysisContext`
- 每个 RDC 生成一个 `AnalysisContext` 对象

**Phase 2 输入**:
- `baseline: AnalysisContext` — 基准捕获
- `current: AnalysisContext` — 当前捕获

### 1.3 对比维度

| 维度 | 数据源 | 对比方式 |
|------|--------|----------|
| Draw Call 数量 | `frame_summary.draw_call_count` | 数值差异 + 百分比 |
| 纹理内存 | `frame_summary.total_texture_memory` | 数值差异 (MB) |
| 唯一 Shader 数量 | `len(shaders)` | 数值差异 |
| 状态切换次数 | `frame_summary.shader_changes` 等 | 数值差异 |
| 资源列表 | `textures`, `shaders` | 新增/删除/修改 |

---

## 2. 架构设计

### 2.1 模块结构

```
scripts/rdc_analyzer/
├── core/
│   ├── diff_engine.py       # [新增] DiffEngine 核心类
│   ├── diff_types.py        # [新增] Diff 结果数据结构
│   └── regression_detector.py # [新增] 回归检测器
├── exporters/
│   └── diff_html_exporter.py # [新增] Diff HTML 报告
├── compare_rdc.py            # [新增] CLI 入口
└── tests/
    └── test_diff_engine.py   # [新增] 单元测试
```

### 2.2 类图

```
┌─────────────────────────────────────────────────────────────┐
│                       DiffEngine                             │
├─────────────────────────────────────────────────────────────┤
│ + compare(baseline, current) -> DiffResult                   │
│ - _compare_summary(b, c) -> SummaryDiff                      │
│ - _compare_textures(b, c) -> List[ResourceDiff]              │
│ - _compare_shaders(b, c) -> List[ResourceDiff]               │
│ - _compare_draw_calls(b, c) -> List[DrawCallDiff]            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     DiffResult                               │
├─────────────────────────────────────────────────────────────┤
│ + baseline_file: str                                         │
│ + current_file: str                                          │
│ + summary: SummaryDiff                                       │
│ + textures: ResourceListDiff                                 │
│ + shaders: ResourceListDiff                                  │
│ + draw_calls: DrawCallListDiff                               │
│ + regressions: List[RegressionWarning]                       │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  RegressionDetector                          │
├─────────────────────────────────────────────────────────────┤
│ + detect(diff: DiffResult) -> List[RegressionWarning]        │
│ - _check_draw_call_increase(diff) -> Optional[Warning]       │
│ - _check_memory_increase(diff) -> Optional[Warning]          │
│ - _check_state_change_increase(diff) -> Optional[Warning]    │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 数据结构

```python
# core/diff_types.py

@dataclass
class MetricDiff:
    """单个指标的差异"""
    name: str
    baseline: float
    current: float
    diff: float           # current - baseline
    diff_percent: float   # (diff / baseline) * 100
    unit: str = ""        # "count", "MB", "ms"

@dataclass
class ResourceDiff:
    """资源差异 (纹理/Shader/缓冲区)"""
    resource_id: str
    name: str
    status: str           # "added" | "removed" | "modified" | "unchanged"
    baseline_data: Optional[Dict] = None
    current_data: Optional[Dict] = None
    changes: List[str] = field(default_factory=list)  # 变更描述

@dataclass
class ResourceListDiff:
    """资源列表差异汇总"""
    added: List[ResourceDiff]
    removed: List[ResourceDiff]
    modified: List[ResourceDiff]
    unchanged_count: int

@dataclass
class SummaryDiff:
    """帧摘要对比"""
    draw_calls: MetricDiff
    dispatches: MetricDiff
    triangles: MetricDiff
    texture_memory_mb: MetricDiff
    buffer_memory_mb: MetricDiff
    shader_changes: MetricDiff
    rt_switches: MetricDiff
    blend_state_changes: MetricDiff

@dataclass
class RegressionWarning:
    """回归警告"""
    rule_id: str          # REG001, REG002, ...
    severity: str         # "critical" | "warning" | "info"
    category: str         # "draw_call" | "memory" | "state" | "resource"
    title: str
    message: str
    metric: MetricDiff
    threshold: float      # 触发阈值
    suggestion: str = ""

@dataclass
class DiffResult:
    """完整对比结果"""
    baseline_file: str
    current_file: str
    timestamp: str
    
    # 汇总对比
    summary: SummaryDiff
    
    # 资源对比
    textures: ResourceListDiff
    shaders: ResourceListDiff
    buffers: ResourceListDiff
    
    # 回归检测
    regressions: List[RegressionWarning]
    
    # 元数据
    baseline_api: str
    current_api: str
```

---

## 3. 实施任务

### 3.1 TASK-010: DiffEngine 实现

**文件**: `scripts/rdc_analyzer/core/diff_engine.py`

```python
# 伪代码

class DiffEngine:
    def compare(self, baseline: AnalysisContext, current: AnalysisContext) -> DiffResult:
        summary = self._compare_summary(baseline.frame_summary, current.frame_summary)
        textures = self._compare_resources(baseline.textures, current.textures, key='resource_id')
        shaders = self._compare_resources(baseline.shaders, current.shaders, key='resource_id')
        buffers = self._compare_resources(baseline.buffers, current.buffers, key='resource_id')
        
        return DiffResult(
            baseline_file=baseline.parsed.file_path,
            current_file=current.parsed.file_path,
            summary=summary,
            textures=textures,
            shaders=shaders,
            buffers=buffers,
            regressions=[],  # 由 RegressionDetector 填充
        )
    
    def _compare_summary(self, b: FrameSummary, c: FrameSummary) -> SummaryDiff:
        return SummaryDiff(
            draw_calls=self._metric_diff("Draw Calls", b.draw_call_count, c.draw_call_count, "count"),
            texture_memory_mb=self._metric_diff("Texture Memory", b.total_texture_memory/1024/1024, ...),
            # ...
        )
    
    def _metric_diff(self, name: str, base: float, curr: float, unit: str) -> MetricDiff:
        diff = curr - base
        pct = (diff / base * 100) if base > 0 else 0
        return MetricDiff(name=name, baseline=base, current=curr, diff=diff, diff_percent=pct, unit=unit)
    
    def _compare_resources(self, base_list, curr_list, key: str) -> ResourceListDiff:
        base_map = {getattr(r, key): r for r in base_list}
        curr_map = {getattr(r, key): r for r in curr_list}
        
        added = [ResourceDiff(id, name, "added", ...) for id in curr_map if id not in base_map]
        removed = [ResourceDiff(id, name, "removed", ...) for id in base_map if id not in curr_map]
        modified = [... for id in base_map if id in curr_map and has_changes(...)]
        
        return ResourceListDiff(added=added, removed=removed, modified=modified, unchanged_count=...)
```

**工时**: 2小时

**验证**:
```bash
py -3 -m pytest scripts/rdc_analyzer/tests/test_diff_engine.py -v
```

---

### 3.2 TASK-011: RegressionDetector 实现

**文件**: `scripts/rdc_analyzer/core/regression_detector.py`

**回归规则定义**:

| Rule ID | 名称 | 阈值 | 严重度 |
|---------|------|------|--------|
| REG001 | Draw Call 增加 | >10% | warning |
| REG002 | 纹理内存增加 | >20MB | warning |
| REG003 | 缓冲区内存增加 | >10MB | info |
| REG004 | Shader 切换增加 | >20% | warning |
| REG005 | RT 切换增加 | >15% | info |
| REG006 | 新增大纹理 | >4096x4096 | warning |
| REG007 | 新增未压缩纹理 | - | info |

```python
# 伪代码

class RegressionDetector:
    RULES = [
        {"id": "REG001", "name": "Draw Call 增加", "threshold": 0.10, "severity": "warning"},
        {"id": "REG002", "name": "纹理内存增加", "threshold": 20.0, "unit": "MB", "severity": "warning"},
        # ...
    ]
    
    def detect(self, diff: DiffResult) -> List[RegressionWarning]:
        warnings = []
        
        # REG001: Draw Call
        if diff.summary.draw_calls.diff_percent > 10:
            warnings.append(RegressionWarning(
                rule_id="REG001",
                severity="warning",
                category="draw_call",
                title="Draw Call 数量增加",
                message=f"Draw Call 从 {diff.summary.draw_calls.baseline} 增加到 {diff.summary.draw_calls.current} (+{diff.summary.draw_calls.diff_percent:.1f}%)",
                metric=diff.summary.draw_calls,
                threshold=10.0,
                suggestion="检查是否有不必要的绘制，考虑合批或实例化"
            ))
        
        # REG002: 纹理内存
        if diff.summary.texture_memory_mb.diff > 20:
            warnings.append(...)
        
        # REG006: 检查新增大纹理
        for tex in diff.textures.added:
            if tex.current_data and tex.current_data.get('width', 0) > 4096:
                warnings.append(...)
        
        return warnings
```

**工时**: 1.5小时

---

### 3.3 TASK-012: Diff HTML 报告

**文件**: `scripts/rdc_analyzer/exporters/diff_html_exporter.py`

**UI 设计**:

```
┌──────────────────────────────────────────────────────────────────┐
│  🔄 RDC Comparison Report                                        │
├──────────────────────────────────────────────────────────────────┤
│  Baseline: g145.rdc          Current: g145-battle-2.rdc          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ⚠️ Regressions (3)                                              │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ [REG001] Draw Call +15% (1200 → 1380)                      │  │
│  │ [REG002] Texture Memory +25MB (120MB → 145MB)              │  │
│  │ [REG006] New 8192x8192 texture added                       │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  📊 Summary Comparison                                           │
│  ┌─────────────────┬───────────┬───────────┬─────────┐          │
│  │ Metric          │ Baseline  │ Current   │ Change  │          │
│  ├─────────────────┼───────────┼───────────┼─────────┤          │
│  │ Draw Calls      │ 1,200     │ 1,380     │ +15% ⚠  │          │
│  │ Triangles       │ 2.5M      │ 2.8M      │ +12%    │          │
│  │ Texture Memory  │ 120 MB    │ 145 MB    │ +25 MB ⚠│          │
│  │ Shader Changes  │ 45        │ 52        │ +15%    │          │
│  └─────────────────┴───────────┴───────────┴─────────┘          │
│                                                                  │
│  📦 Resource Changes                                             │
│  [Textures] [Shaders] [Buffers]                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ ➕ Added (5)                                                │  │
│  │   • diffuse_hero_8k.dds (8192x8192, 256MB)                 │  │
│  │   • normal_detail.dds (2048x2048, 16MB)                    │  │
│  │ ➖ Removed (2)                                              │  │
│  │   • old_texture.dds                                        │  │
│  │ 🔄 Modified (3)                                             │  │
│  │   • ui_atlas.dds: 2048x2048 → 4096x4096                    │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

**工时**: 2小时

---

### 3.4 TASK-013: CLI 入口 & 批量对比

**文件**: `scripts/rdc_analyzer/compare_rdc.py`

```bash
# 单文件对比
py -3 scripts/rdc_analyzer/compare_rdc.py \
    --baseline output/baseline/context.json \
    --current output/current/context.json \
    --output diff_report.html

# 批量对比 (目录)
py -3 scripts/rdc_analyzer/compare_rdc.py \
    --baseline-dir captures/v1.0/ \
    --current-dir captures/v1.1/ \
    --output-dir diff_reports/

# CI 模式 (返回退出码)
py -3 scripts/rdc_analyzer/compare_rdc.py \
    --baseline ... --current ... \
    --ci --fail-on-regression
```

**工时**: 1.5小时

---

## 4. 任务 Checklist

| # | 任务 | 文件 | 工时 | 状态 |
|---|------|------|------|------|
| 1 | 创建 `diff_types.py` 数据结构 | `core/diff_types.py` | 30min | 🔲 |
| 2 | 实现 `DiffEngine.compare()` | `core/diff_engine.py` | 60min | 🔲 |
| 3 | 实现 `DiffEngine._compare_summary()` | `core/diff_engine.py` | 30min | 🔲 |
| 4 | 实现 `DiffEngine._compare_resources()` | `core/diff_engine.py` | 30min | 🔲 |
| 5 | 编写 DiffEngine 单元测试 | `tests/test_diff_engine.py` | 30min | 🔲 |
| 6 | 实现 `RegressionDetector` | `core/regression_detector.py` | 60min | 🔲 |
| 7 | 编写 RegressionDetector 测试 | `tests/test_regression.py` | 20min | 🔲 |
| 8 | 创建 Diff HTML 模板 | `exporters/diff_html_exporter.py` | 90min | 🔲 |
| 9 | 实现 CLI 入口 | `compare_rdc.py` | 60min | 🔲 |
| 10 | 端到端测试 | - | 30min | 🔲 |

**总工时预估**: 7-8 小时

---

## 5. 风险与阻塞

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Phase 1 未完成 | 无法获取 AnalysisContext | 创建 Mock 数据进行开发 |
| 资源 ID 不匹配 | 对比失败 | 支持按 name/hash 多种匹配策略 |
| 大文件性能 | 对比慢 | 增量对比 + 缓存 |

---

## 6. 验收标准 (Definition of Done)

- [ ] `DiffEngine.compare()` 能正确对比两个 AnalysisContext
- [ ] `RegressionDetector.detect()` 能识别 REG001-REG007 回归
- [ ] Diff HTML 报告可读、信息完整
- [ ] CLI 支持单文件和批量模式
- [ ] 所有单元测试通过
- [ ] 代码已提交 Git

---

## 7. 下一步

等待用户确认此计划，然后进入 `/do` 阶段开始实现。

**优先顺序**:
1. TASK-010: DiffEngine (核心)
2. TASK-011: RegressionDetector
3. TASK-012: Diff HTML 报告
4. TASK-013: CLI 批量对比
