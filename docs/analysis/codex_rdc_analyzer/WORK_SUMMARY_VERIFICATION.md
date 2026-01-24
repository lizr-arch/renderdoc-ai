# WORK_SUMMARY_VERIFICATION — 真实性验证与使用方式

- WHAT: 真实性验证、覆盖率报告、本地配置与 CLI 用法。
- WHY: 保障分析结论可复现、可追溯。
- HOW: 汇总 DoD/验证步骤/示例命令与注意事项。

---

## 5. 数据质量保证（DoD-7.3）

### 5.1 Truthful Degradation 原则

**核心理念**：宁可数据显示为"缺失/估算"，也不造假。

```python
# coverage.details 的值域
class DataStatus(Enum):
    PRESENT = "present"      # 完整数据，来自真实 API 调用
    PARTIAL = "partial"      # 部分数据，有采样
    ESTIMATED = "estimated"  # 估算数据，使用启发式
    MISSING = "missing"      # 无数据
```

### 5.2 加权置信度算法

```python
# main.py:_build_coverage_report()
def _calculate_confidence(self, details: Dict[str, str]) -> str:
    """
    加权算法: present=1.0, partial=0.5, estimated=0.2, missing=0.0
    """
    weights = {
        'present': 1.0,
        'partial': 0.5,
        'estimated': 0.2,
        'missing': 0.0
    }
    
    total = 0
    weighted_sum = 0
    for key, status in details.items():
        total += 1
        weighted_sum += weights.get(status, 0)
    
    ratio = weighted_sum / total
    if ratio >= 0.8:
        return 'high'
    elif ratio >= 0.5:
        return 'medium'
    else:
        return 'low'
```

### 5.3 测试验证

`tests/test_dod_compliance.py::TestDOD73DataQuality` 包含真实断言：

```python
def test_weighted_confidence_algorithm():
    """验证加权算法正确性"""
    # 全 present → high
    details = {'textures': 'present', 'draw_calls': 'present'}
    assert calculate_confidence(details) == 'high'
    
    # 混合 → medium
    details = {'textures': 'present', 'pipeline': 'estimated', 'markers': 'missing'}
    assert calculate_confidence(details) == 'medium'
```

---


## 6. 测试样本支持（P1-NEW-1）

### 6.1 问题背景

大部分测试使用 mock 数据，跳过了需要真实 `.rdc` 文件的测试。

### 6.2 解决方案

**本地配置文件模式**：

1. 创建 `tests/conftest_local.py.example` 作为模板
2. 用户复制为 `tests/conftest_local.py`（已加入 .gitignore）
3. 配置本地样本路径

```python
# tests/conftest_local.py.example
"""
本地测试样本配置模板。

使用方法:
1. 复制本文件为 conftest_local.py
2. 修改下面的路径为你本地的真实样本路径
3. conftest_local.py 已在 .gitignore 中，不会被提交

示例样本（已验证可用）：
- Mali Pixel 9: D:\renderdoc\goog pixel-9\g145.rdc
"""

import pytest
from pathlib import Path

# ===== 本地样本路径配置 =====
LOCAL_RDC_SAMPLES = {
    'mali_pixel9': Path(r'D:\renderdoc\goog pixel-9\g145.rdc'),
}

# ===== Fixtures =====
@pytest.fixture(scope="session")
def local_mali_rdc():
    """提供 Mali GPU 的真实 RDC 样本路径"""
    path = LOCAL_RDC_SAMPLES.get('mali_pixel9')
    if path and path.exists():
        return path
    pytest.skip("Mali RDC 样本未配置或不存在")
```

---


## 8. CLI 使用示例

### 8.1 单帧分析

```bash
# 基础分析（XML 输入）
py -3 -m rdc_analyzer analyze capture.xml -o output/ --format html,json

# 带 Pipeline 采样（需要 RenderDoc 环境）
py -3 -m rdc_analyzer analyze capture.rdc -o output/ \
    --pipeline-samples 20 \
    --sampling-strategy diverse

# Mali GPU 专项分析
py -3 -m rdc_analyzer analyze capture.rdc -o output/ \
    --platform mali \
    --malioc-path /path/to/malioc
```

### 8.2 双帧对比

```bash
# 对比两个 RDC 文件
py -3 -m rdc_analyzer compare baseline.rdc target.rdc -o diff_report/

# 对比两个 JSON 分析结果（无需 RenderDoc）
py -3 -m rdc_analyzer compare baseline.json target.json \
    --html diff.html \
    --json diff.json

# 自定义回归阈值
py -3 -m rdc_analyzer compare baseline.json target.json \
    --triangle-threshold 10 \
    --draw-call-threshold 5
```

### 8.3 测试命令

```bash
# 全量测试
cd scripts/rdc_analyzer
py -3 -m pytest tests -q -rs
# 预期: 466 passed, 8 skipped, 5 warnings

# DoD 验收测试
py -3 -m pytest tests/test_dod_compliance.py -v

# Bridge 集成测试
py -3 -m pytest tests/test_schema_bridge_integration.py -v

# Pipeline 采样器测试
py -3 -m pytest tests/test_pipeline_sampler.py -v
```

---
