# Phase 5: 多帧统计对比使用指南

> **目标**: 通过多帧采样和统计分析，区分"正常帧间波动"与"真实性能回归"
> 
> **适用场景**: CI/CD 回归门禁、版本对比、性能基准测试

---

## 📖 目录

1. [快速开始](#快速开始)
2. [多帧采样 (P5.1)](#多帧采样-p51)
3. [显著性检测 (P5.2)](#显著性检测-p52)
4. [对齐策略 (P5.3)](#对齐策略-p53)
5. [CI 集成 (P5.4)](#ci-集成-p54)
6. [最佳实践](#最佳实践)

---

## 快速开始

### 基础对比（单帧）

```bash
# 对比两个 JSON 分析结果
py -3 -m rdc_analyzer compare baseline.json target.json -o diff_report.html
```

### 多帧统计对比

```bash
# 采集 5 帧样本，使用 95% 置信度
py -3 -m rdc_analyzer compare baseline/ target/ \
    --samples 5 \
    --confidence-level 95 \
    --junit-xml results.xml
```

---

## 多帧采样 (P5.1)

### 原理

单帧数据容易受 GPU 状态、驱动缓存等因素影响，产生随机波动。多帧采样通过统计学方法降低噪声：

```
┌─────────────────────────────────────────────────┐
│  单帧采样              多帧采样 (N=5)            │
│  ┌───┐                ┌───┬───┬───┬───┬───┐     │
│  │ ? │  波动 ±15%     │ A │ B │ C │ D │ E │     │
│  └───┘                └───┴───┴───┴───┴───┘     │
│                       mean: 42.3ms  std: 2.1ms  │
│                       → 真实值: 42.3 ± 4.2ms    │
└─────────────────────────────────────────────────┘
```

### 输出指标

| 指标 | 说明 | 用途 |
|------|------|------|
| `mean` | 算术平均值 | 核心指标 |
| `median` | 中位数 | 抗离群值 |
| `std` | 标准差 | 衡量稳定性 |
| `min` / `max` | 极值 | 检测异常帧 |
| `p95` / `p99` | 分位数 | 性能保障线 |

### CLI 参数

```bash
--samples N      # 采样帧数，推荐 5-10 帧
```

### 数据结构

```python
@dataclass
class MetricStatistics:
    mean: float
    median: float
    std: float
    min_val: float
    max_val: float
    p95: float
    p99: float
    sample_count: int
```

---

## 显著性检测 (P5.2)

### 原理

当对比两组多帧数据时，仅看平均值差异不够——需要判断差异是否"统计显著"。

**使用的统计方法**:

1. **Welch's t-test (Z-score)**: 计算两组均值差异的置信区间
2. **Cohen's d (效应量)**: 衡量差异的实际大小

```
┌─────────────────────────────────────────────────┐
│  Baseline: mean=40ms, std=3ms                   │
│  Target:   mean=45ms, std=4ms                   │
│                                                 │
│  Welch's t-test → p-value < 0.05 → 显著        │
│  Cohen's d = 1.4 → 大效应 (> 0.8)              │
│                                                 │
│  结论: HIGH significance 回归                  │
└─────────────────────────────────────────────────┘
```

### 显著性级别

| 级别 | 条件 | 含义 |
|------|------|------|
| `HIGH` | p < 0.01 且 d > 0.8 | 确定性回归，必须修复 |
| `MEDIUM` | p < 0.05 且 d > 0.5 | 可能回归，建议关注 |
| `LOW` | p >= 0.05 或 d < 0.5 | 正常波动，可忽略 |

### CLI 参数

```bash
--confidence-level {90,95,99}   # 置信度，默认 95%
```

### 输出示例

```json
{
  "metric": "draw_call_count",
  "baseline": {"mean": 1200, "std": 50},
  "target": {"mean": 1450, "std": 60},
  "z_score": 5.2,
  "p_value": 0.00001,
  "cohens_d": 1.8,
  "significance": "HIGH"
}
```

---

## 对齐策略 (P5.3)

### 问题背景

当两次捕获的 Draw Call 数量不同（新增/删除渲染 Pass）时，按顺序对齐会导致错位：

```
Baseline: [A, B, C, D, E]
Target:   [A, B, X, C, D, E]  ← 新增了 X

按顺序对齐（错误）:
  A↔A, B↔B, C↔X, D↔C, E↔D  ← C 以后全部错位！

按语义对齐（正确）:
  A↔A, B↔B, [新增 X], C↔C, D↔D, E↔E
```

### 可用策略

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| `order` | 按事件 ID 顺序对齐 | Draw Call 数量完全相同 |
| `signature` | 按 Pipeline Hash 对齐 | Shader/状态相同的调用 |
| `marker` | 按 RenderDoc 调试标记对齐 | 有良好标记的捕获 |

### 4 阶段对齐算法

`DiffEngine` 使用递进式匹配：

```
阶段 1: marker + shader 完全匹配
    ↓ 未匹配项
阶段 2: 仅 marker 名称匹配
    ↓ 未匹配项
阶段 3: pipeline signature 匹配
    ↓ 未匹配项
阶段 4: 标记为 新增/删除
```

### CLI 参数

```bash
--align-strategy {order,signature,marker}   # 默认 signature
```

### 使用示例

```bash
# 有调试标记时使用 marker 策略
py -3 -m rdc_analyzer compare baseline.json target.json \
    --align-strategy marker

# 无标记时使用 signature
py -3 -m rdc_analyzer compare baseline.json target.json \
    --align-strategy signature
```

---

## CI 集成 (P5.4)

### JUnit XML 输出

生成标准 JUnit XML 格式，兼容主流 CI 系统：

```bash
py -3 -m rdc_analyzer compare baseline.json target.json \
    --junit-xml results.xml
```

### XML 结构

```xml
<?xml version="1.0" encoding="UTF-8"?>
<testsuites name="RDC Performance Regression">
  <testsuite name="performance_comparison" tests="8" failures="2">
    <testcase name="draw_call_count" classname="metrics">
      <failure message="Regression detected: +20.8% (HIGH significance)">
Baseline: 1200.0 ± 50.0
Target: 1450.0 ± 60.0
Change: +250.0 (+20.8%)
Z-score: 5.2
Cohen's d: 1.8
Significance: HIGH
      </failure>
    </testcase>
    <testcase name="texture_memory" classname="metrics"/>
  </testsuite>
</testsuites>
```

### Exit Code

| 代码 | 含义 |
|------|------|
| `0` | 无显著回归 |
| `1` | 检测到 HIGH significance 回归 |

### GitHub Actions 示例

```yaml
name: Performance Regression Check

on:
  pull_request:
    branches: [main]

jobs:
  perf-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -e scripts/rdc_analyzer
      
      - name: Download baseline
        uses: actions/download-artifact@v4
        with:
          name: perf-baseline
          path: baseline/
      
      - name: Run performance comparison
        run: |
          python -m rdc_analyzer compare \
            baseline/analysis.json \
            target/analysis.json \
            --samples 5 \
            --confidence-level 95 \
            --junit-xml perf-results.xml
      
      - name: Publish Test Results
        uses: dorny/test-reporter@v1
        if: always()
        with:
          name: Performance Tests
          path: perf-results.xml
          reporter: java-junit
```

### GitLab CI 示例

```yaml
performance_check:
  stage: test
  script:
    - python -m rdc_analyzer compare baseline.json target.json --junit-xml results.xml
  artifacts:
    reports:
      junit: results.xml
    when: always
```

---

## 最佳实践

### 1. 采样数量选择

| 场景 | 推荐采样数 | 原因 |
|------|-----------|------|
| 快速检查 | 3-5 帧 | 平衡速度与准确性 |
| 正式基准 | 10+ 帧 | 更可靠的统计结论 |
| 高噪声环境 | 20+ 帧 | 降低随机波动影响 |

### 2. 调试标记规范

良好的标记让对齐更精确：

```cpp
// RenderDoc API 示例
rdoc::BeginEvent("ShadowPass");
  RenderShadowMaps();
rdoc::EndEvent();

rdoc::BeginEvent("GBuffer");
  RenderGBuffer();
rdoc::EndEvent();
```

### 3. 阈值调整

可通过 `--threshold` 参数调整回归判定阈值：

```bash
# 更严格的阈值（适合关键路径）
py -3 -m rdc_analyzer compare ... --threshold draw_call_count=0.05

# 更宽松的阈值（适合实验性功能）
py -3 -m rdc_analyzer compare ... --threshold texture_memory=0.20
```

### 4. 忽略已知变化

使用 `--ignore` 跳过已知的预期变化：

```bash
py -3 -m rdc_analyzer compare ... --ignore "PostProcess/*"
```

---

## 故障排查

### Q: 为什么所有指标都显示 LOW significance？

**可能原因**:
1. 样本数太少（< 3）
2. 波动确实很大（std 接近 mean）
3. 变化本身很小

**解决方案**:
```bash
# 增加采样数
--samples 10

# 查看原始统计数据
--output-format json --verbose
```

### Q: 对齐失败，大量 Draw Call 标记为 "新增"

**可能原因**:
1. 缺少调试标记
2. Pipeline 状态变化太大

**解决方案**:
```bash
# 回退到顺序对齐
--align-strategy order

# 或检查标记覆盖率
py -3 -m rdc_analyzer analyze capture.rdc --check-markers
```

---

## 相关文档

- [CLI 完整参考](./CLI_REFERENCE.md)
- [API 参考手册](./API_REFERENCE.md)
- [开发里程碑](../../docs/analysis/codex_rdc_analyzer/DEVELOPMENT_MILESTONES.md)
