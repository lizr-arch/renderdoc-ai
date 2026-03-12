# 待评分任务队列

> **说明**: 此文件记录所有待评分的任务
> 
> ⚠️ **规则**:
> - 任务完成后，完成者**自动添加**一条待评分记录到此文件
> - 其他 Agent **认领**评分任务进行评审（不能自评）
> - 评分完成后，将记录**移动**到对应日期的评分文档

---

## 📋 待评分任务

<!-- 
格式说明:
- task_id: 原任务 ID
- title: 任务标题
- completed_by: 完成者 Agent 名字
- completed_at: 完成时间
- files_changed: 修改的文件列表
- commit: Git commit hash 或信息
-->

### [TASK-010] DiffEngine 核心实现
- **完成者**: Flux-0119
- **完成时间**: 2026-01-19 21:00
- **修改文件**:
  - `diff/diff_engine.py` (新建, +350 行) - 核心对比引擎
  - `diff/__init__.py` (新建, +10 行) - 模块初始化
  - `diff/models.py` (新建, +150 行) - DiffReport/DiffSummary 数据模型
- **Commit**: `feat(diff): implement DiffEngine core comparison`
- **自评摘要**: 
  - 实现了完整的对比引擎，支持 Draw Call、纹理、Buffer、Shader、状态差异检测
  - 支持两种 Phase 1 输出格式（legacy list + modern dict）
  - 添加内存估算算法处理缺失的 size_bytes 字段
- **评分状态**: 🟡 待认领
- **评审者**: -

---

### [TASK-011] 差异可视化 HTML
- **完成者**: Flux-0119
- **完成时间**: 2026-01-19 21:10
- **修改文件**:
  - `compare_rdc.py` (新建, +250 行) - 对比入口脚本及 HTML 生成
- **Commit**: `feat(diff): add compare_rdc.py with HTML diff report`
- **自评摘要**: 
  - 生成独立 HTML 对比报告，含颜色编码差异
  - Summary 面板显示关键指标变化百分比
  - 支持 `--json` 输出纯 JSON 差异数据
- **评分状态**: 🟡 待认领
- **评审者**: -

---

### [TASK-012] CLI 对比入口
- **完成者**: Flux-0119
- **完成时间**: 2026-01-19 21:15
- **修改文件**:
  - `compare_rdc.py` (修改) - 集成 argparse 命令行参数
- **Commit**: `feat(diff): add CLI argument parsing`
- **自评摘要**: 
  - 支持 `py -3 compare_rdc.py baseline.json target.json -o diff.html`
  - 支持 `--json` 格式选项
- **评分状态**: 🟡 待认领
- **评审者**: -

---

### [TASK-013] 性能回归检测
- **完成者**: Flux-0119
- **完成时间**: 2026-01-19 21:20
- **修改文件**:
  - `diff/regression_detector.py` (新建, +120 行) - 回归检测器
- **Commit**: `feat(diff): add RegressionDetector with 6 rules`
- **自评摘要**: 
  - 实现 REG001-006 回归检测规则
  - 在 g145-battle-2 对比中检测到 4 个 CRITICAL 回归
  - 回归摘要集成到 HTML 报告
- **评分状态**: 🟡 待认领
- **评审者**: -

---

### [TASK-002] Mesh Info 选项卡数据解析
- **完成者**: Echo-0119
- **完成时间**: 2026-01-19 17:00
- **修改文件**:
  - `parse_rdc_xml.py` (+120/-5 行) - 添加 Binding Record 跟踪和 Mesh Info 解析
  - `generate_real_report.py` (+50/-3 行) - 添加 meshInfo→meshData 转换函数
- **Commit**: `feat(parser): add mesh info extraction for VB/IB`
- **自评摘要**: 
  - 完成了 Mesh Info 解析功能，从 XML 中提取 VB/IB 绑定记录
  - 遇到字段名不匹配问题（meshInfo vs meshData），添加了 `convert_mesh_info_to_mesh_data` 转换函数
  - 通过自动化验证：136 个 Draw 事件全部含有 vertexBuffers 数据
- **评分状态**: 🟡 待认领
- **评审者**: -

<!-- 
待评分任务模板（完成者复制后填写）:

### [TASK-XXX] 任务标题
- **完成者**: Agent名字 (如 Echo-0119)
- **完成时间**: YYYY-MM-DD HH:MM
- **修改文件**:
  - `file1.py` (+XX/-YY 行)
  - `file2.py` (+XX/-YY 行)
- **Commit**: `feat(xxx): 描述`
- **自评摘要**: 
  - 完成了什么
  - 遇到什么问题及如何解决
- **评分状态**: 🟡 待认领
- **评审者**: -
-->

---

## 📊 评分标准

| 维度 | 权重 | 说明 |
|------|------|------|
| **代码质量** | 40% | 语法正确、结构清晰、注释完整、边界处理 |
| **测试验证** | 30% | 自动验证、E2E 测试、边界测试 |
| **文档同步** | 20% | CHANGELOG/INDEX/注释 同步更新 |
| **效率** | 10% | 预估 vs 实际工时 |

### 评分等级

| 分数 | 等级 | 处理 |
|------|------|------|
| 4.0 - 5.0 | ✅ 优秀 | 完成归档 |
| 3.5 - 3.9 | ⚠️ 良好 | 完成归档，记录改进点 |
| < 3.5 | 🔴 需返工 | 标记返工，重新分配 |

---

## 🔄 评分流程

```
1. Agent A 完成任务
      ↓
2. Agent A 在此文件添加待评分记录
      ↓
3. Agent B 认领评分（检查不是自己的任务）
      ↓
4. Agent B 评审并打分
      ↓
5. 评分 ≥ 3.5 → 移到 reviews/YYYY-MM-DD.md 归档
   评分 < 3.5 → 标记返工，任务回到任务看板
```

---

## 🔗 相关链接

- [今日评分记录](./2026-01-19.md)
- [任务看板](../tasks/)
- [开发规范](../CONVENTIONS.md)
