# RDC Analyzer 输出口径：对比两个 RDC（输入/输出 Schema 说明）

> 覆盖范围：`scripts/rdc_analyzer/compare_rdc.py`  
> 目标：把“compare 需要什么输入、会输出什么、当前为什么不可信”讲清楚（WHAT / WHY / HOW）。  
> 更新时间：2025-01-20

---

## 0) WHY：为什么 compare 的 Schema 是“目标 2 的地基”？

你的目标 2 是：**对比两个 RDC，全方位，并给出结论**。  

这里的“全方位 + 结论”要求两点：
1) 对比输入必须同口径（同一个 schema、同一个单位、同一个统计范围）  
2) 结论必须可追溯（能解释“为什么认为回归”，最好还能指向根因）

当前仓库最大的问题是：compare 在兼容多种输入（Phase1 列表/Phase2 字典）时，会出现“补 0/空列表”的情况，直接导致结论失真。

---

## 1) compare 的输入：`load_json_data()`（Phase1 -> Phase2 的兼容转换）

### WHAT
- compare 目前主要输入是“JSON 文件”（不是直接对比两个 `.rdc`）。  
- 它支持两种输入格式：
  1) Phase2 字典格式：`{summary, textures, shaders, buffers, draw_calls, events, statistics, ...}`  
  2) Phase1 列表格式：`[{summary, shaders, textures}]`

### WHY（为什么这是风险点）
- 如果输入是 Phase1 列表格式，转换时会把很多关键指标写成 0 或空列表：  
  - `total_vertices/total_triangles = 0`  
  - `textures/shaders/buffers/draw_calls/events = []`  
- 结果：DiffEngine/RegressionDetector 的对比会变成“拿真实数据 vs 拿空数据”，结论必然不可信。

### HOW（当前实现怎么做的）
- 实现位置：`scripts/rdc_analyzer/compare_rdc.py` 的 `load_json_data()`  
- 关键行为：当 `data` 是 list 时，取第 0 项并构造“Phase2 期望的 dict”：
  - 从 `phase1_summary` 读取 `total_draw_events/total_textures/total_shaders`
  - 其余多项补 0 / 补空列表（这是 compare 结果“看起来能跑，但不可信”的根源之一）

---

## 2) compare 的输出 JSON：`export_json_diff()`

### 2.1 WHAT：输出顶层结构是什么？

实现位置：`scripts/rdc_analyzer/compare_rdc.py` 的 `export_json_diff()`  

抽象骨架如下：

```json
{
  "metadata": {
    "generated_at": "…",
    "baseline_file": "…",
    "target_file": "…",
    "tool_version": "1.0.0"
  },
  "summary": {
    "draw_calls": { "baseline": 0, "target": 0, "delta": 0, "delta_percent": 0 },
    "triangles":  { "baseline": 0, "target": 0, "delta": 0, "delta_percent": 0 },
    "vertices":   { "baseline": 0, "target": 0, "delta": 0, "delta_percent": 0 },
    "texture_memory_bytes": { "baseline": 0, "target": 0, "delta": 0, "delta_percent": 0 },
    "buffer_memory_bytes":  { "baseline": 0, "target": 0, "delta": 0, "delta_percent": 0 }
  },
  "regressions": {
    "has_critical": false,
    "has_warning": false,
    "issues": [
      {
        "rule_id": "REG001",
        "severity": "critical|warning|info",
        "message": "…",
        "baseline_value": 0,
        "target_value": 0,
        "delta_percent": 0
      }
    ]
  },
  "resource_changes": {
    "textures": { "added": 0, "removed": 0, "modified": 0 },
    "shaders":  { "added": 0, "removed": 0, "modified": 0 },
    "buffers":  { "added": 0, "removed": 0, "modified": 0 },
    "draw_calls": { "added": 0, "removed": 0, "modified": 0 }
  }
}
```

### 2.2 WHY：它的优点与限制是什么？

优点：
- 输出结构已经能形成“对比摘要 + 回归结论 + 资源变化计数”的闭环；
- 对于 CI/自动化很友好（机器可读）。

限制（会影响你说的“全方位”）：
- 它目前更像“汇总级 diff”，缺少：
  - 哪些具体 draw/资源导致回归（根因证据链）
  - state/binding/pass 级差异的可视化结构
- 如果输入数据不完整（Phase1 -> 补 0），那 summary 和 regressions 都会失真。

### 2.3 HOW：字段含义简表（WHAT/WHY/HOW）

#### `summary.*`
- WHAT：核心指标的 baseline/target/delta。
- WHY：这是人类读报告的第一屏，也是回归判断的基础。
- HOW：来自 `DiffResult.summary.*`（DiffEngine 的统计汇总）。

#### `regressions.*`
- WHAT：回归检测器输出的“规则化结论”列表。
- WHY：把“差异”提升成“可解释结论”（例如“draw_calls 增长 > 15% => warning”）。
- HOW：来自 `RegressionDetector`（`scripts/rdc_analyzer/diff/regression_detector.py`）与 `regression_types.py` 的规则定义。

#### `resource_changes.*`
- WHAT：新增/删除/修改的数量统计（textures/shaders/buffers/draw_calls）。
- WHY：帮助你判断“是内容回归（资产变了）还是渲染路径回归（draw/state 变了）”。
- HOW：来自 `DiffResult` 的聚合字段（added/removed/modified 计数）。

---

## 3) 我认为 compare 现在“为什么重要但不可信”（对照当前项目）

### WHAT（现象）
- compare 能跑出结果，但输入 schema 不稳定时会出现大量“0/空列表”的兼容数据。

### WHY（影响）
- 你会得到“形式正确、实质错误”的回归结论：  
  - delta_percent 可能被人为放大/缩小；  
  - modified/added 的统计缺乏真实依据；  
  - 结论无法说服人（你要求的 WHAT/HOW/WHY 也就无法成立）。

### HOW（根因）
- compare 缺一个“唯一权威输入 schema”（canonical single analysis JSON）。  
- DiffEngine/RegressionDetector 需要稳定的统计与资源列表；而当前输入兼容层会补 0。

---

## 4) 推荐的对比输入契约（与 P0-4 对齐）

如果你要把目标 2 做成“全方位 + 可信结论”，我建议：

1) compare 的唯一输入：`analysis.json`（canonical schema，带 `schema_version`）  
2) compare 的唯一输出：`diff.json`（你现在这份结构可以保留，但要确保来源可信）  
3) 禁止 Phase1/Phase2 混用：旧格式要么迁移，要么 fail-fast 给出错误提示

这样你才有资格在报告里说：
- WHAT：我发现了哪些回归  
- WHY：为什么它是回归（阈值/预算/证据链）  
- HOW：怎么修（定位到具体 draw/pass/resource 的变化）

