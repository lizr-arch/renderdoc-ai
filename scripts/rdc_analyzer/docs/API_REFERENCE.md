# RDC Analyzer API 参考手册

> **版本**: 1.0.0  
> **更新日期**: 2025-02-06

本文档描述 `rdc_analyzer` 模块的公开 API 接口，供二次开发和集成使用。

---

## 📖 目录

1. [核心模块](#核心模块)
2. [统计分析模块 (stats)](#统计分析模块-stats)
3. [差异对比模块 (diff)](#差异对比模块-diff)
4. [规则引擎 (rules)](#规则引擎-rules)
5. [数据类型 (types)](#数据类型-types)
6. [CLI 命令](#cli-命令)

---

## 核心模块

### `rdc_analyzer.main`

主分析入口，提供端到端的 RDC 文件分析。

#### `analyze_rdc(rdc_path, output_dir, **options)`

分析单个 RDC 文件并生成报告。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `rdc_path` | `Path` | RDC 文件路径 |
| `output_dir` | `Path` | 输出目录 |
| `platform` | `str` | 平台类型 (`"pc"` / `"mobile"`) |
| `verbose` | `bool` | 详细输出模式 |

**返回值**: `AnalysisResult` 对象

**示例**:
```python
from rdc_analyzer.main import analyze_rdc
from pathlib import Path

result = analyze_rdc(
    rdc_path=Path("capture.rdc"),
    output_dir=Path("output/"),
    platform="mobile"
)
print(f"发现 {len(result.issues)} 个问题")
```

---

### `rdc_analyzer.compare_rdc`

双帧对比分析模块。

#### `run_comparison(baseline_data, target_data, baseline_name, target_name, custom_thresholds=None, align_strategy="signature")`

执行两个分析结果的对比。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `baseline_data` | `Dict[str, Any]` | 基准帧 JSON 数据 |
| `target_data` | `Dict[str, Any]` | 目标帧 JSON 数据 |
| `baseline_name` | `str` | 基准帧名称 |
| `target_name` | `str` | 目标帧名称 |
| `custom_thresholds` | `Dict[RegressionRuleId, float]` | 自定义回归阈值 |
| `align_strategy` | `str` | 对齐策略 (`"order"` / `"signature"` / `"marker"`) |

**返回值**: `Tuple[DiffResult, RegressionReport]`

**示例**:
```python
from rdc_analyzer.compare_rdc import run_comparison
import json

with open("baseline.json") as f:
    baseline = json.load(f)
with open("target.json") as f:
    target = json.load(f)

diff_result, regression_report = run_comparison(
    baseline_data=baseline,
    target_data=target,
    baseline_name="v1.0",
    target_name="v1.1",
    align_strategy="marker"
)

print(f"检测到 {len(regression_report.regressions)} 个回归")
```

---

## 统计分析模块 (stats)

位于 `rdc_analyzer.stats` 包下。

### `stats.sampler.MetricStatistics`

多帧采样统计结果的数据类。

```python
@dataclass
class MetricStatistics:
    mean: float          # 算术平均值
    median: float        # 中位数
    std: float           # 标准差
    min_val: float       # 最小值
    max_val: float       # 最大值
    p95: float           # 95 分位数
    p99: float           # 99 分位数
    sample_count: int    # 采样数量
```

**方法**:
- `to_dict() -> Dict[str, Any]`: 转换为字典
- `from_samples(samples: List[float]) -> MetricStatistics`: 从样本列表创建

---

### `stats.sampler.MultiFrameSampler`

多帧采样器，用于收集和聚合多帧数据。

#### `__init__(sample_count: int = 5)`

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `sample_count` | `int` | 目标采样帧数 |

#### `add_sample(frame_data: Dict[str, Any])`

添加一帧的分析数据。

#### `get_statistics() -> Dict[str, MetricStatistics]`

获取所有指标的统计结果。

**示例**:
```python
from rdc_analyzer.stats.sampler import MultiFrameSampler

sampler = MultiFrameSampler(sample_count=5)

for frame_file in frame_files:
    with open(frame_file) as f:
        sampler.add_sample(json.load(f))

stats = sampler.get_statistics()
print(f"Draw Call 均值: {stats['draw_call_count'].mean}")
print(f"Draw Call 标准差: {stats['draw_call_count'].std}")
```

---

### `stats.summary.StatisticalSummary`

统计显著性分析类。

#### `compare(baseline_stats: MetricStatistics, target_stats: MetricStatistics, confidence_level: float = 0.95) -> SignificanceResult`

比较两组统计数据的显著性。

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `baseline_stats` | `MetricStatistics` | 基准组统计 |
| `target_stats` | `MetricStatistics` | 目标组统计 |
| `confidence_level` | `float` | 置信度 (0.90 / 0.95 / 0.99) |

**返回值**: `SignificanceResult`

```python
@dataclass
class SignificanceResult:
    z_score: float           # Welch's t-test 统计量
    p_value: float           # P 值
    cohens_d: float          # Cohen's d 效应量
    significance: str        # "HIGH" / "MEDIUM" / "LOW"
    baseline_mean: float
    target_mean: float
    change_percent: float    # 变化百分比
```

**示例**:
```python
from rdc_analyzer.stats.summary import StatisticalSummary

summary = StatisticalSummary()
result = summary.compare(
    baseline_stats=baseline_draw_calls,
    target_stats=target_draw_calls,
    confidence_level=0.95
)

if result.significance == "HIGH":
    print(f"⚠️ 显著回归: {result.change_percent:.1f}%")
```

---

### `stats.junit_reporter.JUnitReporter`

JUnit XML 报告生成器。

#### `__init__(test_suite_name: str = "performance_comparison")`

#### `add_result(metric_name: str, significance_result: SignificanceResult, is_regression: bool)`

添加一个测试结果。

#### `generate_xml() -> str`

生成 JUnit XML 格式的报告字符串。

#### `save(filepath: Path)`

保存 XML 到文件。

**示例**:
```python
from rdc_analyzer.stats.junit_reporter import JUnitReporter

reporter = JUnitReporter("RDC Perf Test")

for metric, result in comparison_results.items():
    reporter.add_result(
        metric_name=metric,
        significance_result=result,
        is_regression=(result.significance == "HIGH")
    )

reporter.save(Path("results.xml"))
```

---

## 差异对比模块 (diff)

位于 `rdc_analyzer.diff` 包下。

### `diff.diff_engine.DiffEngine`

结构化差异计算引擎。

#### `__init__(align_strategy: str = "signature")`

**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `align_strategy` | `str` | 对齐策略 |

可选值:
- `"order"`: 按事件 ID 顺序对齐
- `"signature"`: 按 Pipeline Hash 对齐
- `"marker"`: 按 RenderDoc 调试标记对齐

#### `compare(baseline: Dict, target: Dict) -> DiffResult`

执行差异计算。

**返回值**: `DiffResult`

```python
@dataclass
class DiffResult:
    added_events: List[EventInfo]       # 新增的事件
    removed_events: List[EventInfo]     # 删除的事件
    modified_events: List[EventDiff]    # 修改的事件
    metric_changes: Dict[str, MetricChange]  # 指标变化
    summary: DiffSummary                # 汇总信息
```

---

### `diff.regression_detector.RegressionDetector`

回归检测器。

#### `detect(diff_result: DiffResult, thresholds: Dict[str, float] = None) -> RegressionReport`

从差异结果中检测回归。

**返回值**: `RegressionReport`

```python
@dataclass
class RegressionReport:
    regressions: List[Regression]       # 检测到的回归列表
    warnings: List[Warning]             # 警告列表
    passed: bool                        # 是否通过（无严重回归）
    summary: str                        # 文本摘要
```

---

## 规则引擎 (rules)

位于 `rdc_analyzer.rules` 包下。

### `rules.runner.RuleRunner`

规则执行器，管理和运行所有分析规则。

#### `__init__(platform: str = "pc")`

#### `run_all(context: AnalysisContext) -> List[Issue]`

执行所有已注册规则。

#### `run_rule(rule_id: str, context: AnalysisContext) -> List[Issue]`

执行指定规则。

**示例**:
```python
from rdc_analyzer.rules.runner import RuleRunner
from rdc_analyzer.core.types import AnalysisContext

runner = RuleRunner(platform="mobile")
issues = runner.run_all(analysis_context)

for issue in issues:
    print(f"[{issue.severity}] {issue.rule_id}: {issue.message}")
```

### 可用规则 ID

| 规则 ID | 说明 |
|---------|------|
| `RD_DC_001` | Draw Call 数量过多 |
| `RD_DC_002` | 冗余状态切换 |
| `RD_DC_003` | 小批次绘制 |
| `RD_TEX_001` | 纹理尺寸过大 |
| `RD_TEX_002` | 未使用 Mipmap |
| `RD_TEX_003` | 纹理格式不当 |
| `RD_BUF_001` | 缓冲区过大 |
| `RD_BUF_002` | 频繁缓冲区更新 |
| `RD_SHADER_001` | Shader 复杂度过高 |
| `RD_SHADER_002` | 分支过多 |
| ... | (共 36 条规则) |

---

## 数据类型 (types)

位于 `rdc_analyzer.core.types` 模块。

### `AnalysisContext`

分析上下文，包含所有解析后的数据。

```python
@dataclass
class AnalysisContext:
    events: List[EventInfo]             # 事件列表
    textures: List[TextureInfo]         # 纹理列表
    buffers: List[BufferInfo]           # 缓冲区列表
    shaders: List[ShaderInfo]           # Shader 列表
    render_targets: List[RenderTarget]  # 渲染目标
    pipeline_states: List[PipelineState] # Pipeline 状态
    markers: List[MarkerInfo]           # 调试标记
    metadata: CaptureMetadata           # 捕获元数据
```

### `Issue`

问题/警告条目。

```python
@dataclass
class Issue:
    rule_id: str                    # 规则 ID
    severity: str                   # "error" / "warning" / "info"
    message: str                    # 描述信息
    evidence: Dict[str, Any]        # 证据数据
    event_ids: List[int]            # 关联的事件 ID
    resource_ids: List[str]         # 关联的资源 ID
    suggestion: Optional[str]       # 优化建议
```

### `CanonicalIssue`

标准化问题格式（用于输出）。

```python
@dataclass
class CanonicalIssue:
    id: str
    rule_id: str
    severity: str
    title: str
    description: str
    evidence_chain: List[Dict]
    affected_resources: List[str]
    optimization_steps: List[str]
    expected_impact: str
    verification_plan: str
```

---

## CLI 命令

### `analyze` - 单帧分析

```bash
py -3 -m rdc_analyzer analyze <input> [options]

位置参数:
  input                 输入文件 (.rdc / .xml / .json)

选项:
  -o, --output DIR      输出目录
  -p, --platform {pc,mobile}  平台类型
  -v, --verbose         详细输出
  --format {html,json,both}   输出格式
```

### `compare` - 双帧对比

```bash
py -3 -m rdc_analyzer compare <baseline> <target> [options]

位置参数:
  baseline              基准帧文件
  target                目标帧文件

选项:
  -o, --output FILE     输出文件
  --samples N           多帧采样数
  --confidence-level {90,95,99}  置信度
  --align-strategy {order,signature,marker}  对齐策略
  --threshold RULE=VAL  自定义阈值
  --junit-xml FILE      JUnit XML 输出
```

### `report` - 生成报告

```bash
py -3 -m rdc_analyzer report <input> [options]

位置参数:
  input                 分析结果 JSON 文件

选项:
  -o, --output DIR      输出目录
  --template {bundle,single,minimal}  报告模板
```

---

## 扩展开发

### 自定义规则

```python
from rdc_analyzer.rules.base import BaseRule, RuleSeverity
from rdc_analyzer.core.types import AnalysisContext, Issue

class MyCustomRule(BaseRule):
    rule_id = "CUSTOM_001"
    name = "自定义检测规则"
    description = "检测特定问题..."
    severity = RuleSeverity.WARNING
    
    def check(self, context: AnalysisContext) -> List[Issue]:
        issues = []
        # 自定义检测逻辑
        for event in context.events:
            if self._is_problematic(event):
                issues.append(Issue(
                    rule_id=self.rule_id,
                    severity=self.severity.value,
                    message=f"检测到问题: {event.name}",
                    event_ids=[event.id]
                ))
        return issues
    
    def _is_problematic(self, event) -> bool:
        # 实现检测逻辑
        pass

# 注册规则
from rdc_analyzer.rules.runner import RuleRunner
RuleRunner.register_rule(MyCustomRule)
```

---

## 相关文档

- [多帧统计使用指南](./MULTI_FRAME_GUIDE.md)
- [开发里程碑](../../docs/analysis/codex_rdc_analyzer/DEVELOPMENT_MILESTONES.md)
- [任务追踪表](../../docs/analysis/codex_rdc_analyzer/TASK_TRACKER.md)
