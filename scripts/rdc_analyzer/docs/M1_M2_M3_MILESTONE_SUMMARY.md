# RDC Analyzer - 资源使用索引与证据链系统

> **版本**: 1.0.0  
> **日期**: 2025-01-22  
> **范围**: M1 资源使用索引 + M2 证据链 + M3 UI 增强

---

## 目录

1. [项目概述](#1-项目概述)
2. [里程碑概览](#2-里程碑概览)
3. [已完成功能清单](#3-已完成功能清单)
4. [文件变更清单](#4-文件变更清单)
5. [测试状态](#5-测试状态)
6. [下一步计划](#6-下一步计划)

---

## 1. 项目概述

### 1.1 背景

RDC Analyzer 需要从"发现问题"升级为"解释问题"：

- **Before**: 仅报告 "纹理 tex_123 太大"
- **After**: 提供证据链，说明 "纹理 tex_123 (4096x4096) 超过 2048 阈值，影响 3 个绘制调用，点击跳转查看"

### 1.2 核心目标

| 目标 | 描述 |
|------|------|
| **数据索引** | 建立资源（纹理/Shader/Buffer）与事件的双向映射 |
| **证据生成** | 为每个性能问题生成完整的证据链 |
| **UI 增强** | 在 HTML 报告中支持证据展示和跨页面跳转 |

---

## 2. 里程碑概览

### M1: 资源使用索引 (ResourceUsageIndex) ✅

**目标**: 构建资源 ↔ 事件的双向映射

| 任务 | 状态 | 说明 |
|------|------|------|
| ResourceUsageIndex 数据结构 | ✅ | `core/types.py` |
| 索引构建器 | ✅ | `core/resource_usage_builder.py` |
| 序列化支持 | ✅ | `to_dict()` / `from_dict()` |
| 报告生成器集成 | ✅ | `set_resource_usage_index()` |

### M2: 证据链系统 (EvidenceChain) ✅

**目标**: 为每个 Issue 提供完整的证据支持

| 任务 | 状态 | 说明 |
|------|------|------|
| EvidenceChain 数据结构 | ✅ | `core/types.py` |
| ContextEvidence 类型 | ✅ | 支持 metric/comparison/context 类型 |
| Action 类型 | ✅ | 支持 jump/highlight 操作 |
| PerformanceIssue 集成 | ✅ | `evidence_chain` 字段 |
| to_canonical() 转换 | ✅ | 正确传递 evidence_chain 到 evidence |

### M3: UI 增强 (前端集成) ✅

**目标**: 在 HTML 报告中支持证据展示和跨页面跳转

| 任务 | 状态 | 说明 |
|------|------|------|
| M3.1 navigation.js 更新 | ✅ | 参数别名支持 (id/eid/sid/tid) |
| M3.2 模板集成 | ✅ | textures/events/shaders 支持深链接 |
| M3.3 证据展示面板 | ✅ | recommendations.html 完整实现 |
| M3.3 数据管道修复 | ✅ | report_bundle_generator.py 保留 evidence |
| M3.4 E2E 测试清单 | ✅ | `docs/E2E_MANUAL_TEST_CHECKLIST.md` |
| M3.4 单元测试 | ✅ | `tests/test_evidence_chain_pipeline.py` (4 tests) |

---

## 3. 已完成功能清单

### 3.1 核心类型定义

```python
# core/types.py

@dataclass
class EvidenceChain:
    """证据链"""
    issue_code: str
    summary: str
    evidences: List[ContextEvidence]
    actions: List[Action]
    affected_resources: List[str]
    affected_events: List[int]
    impact_score: float
    verification_plan: str

@dataclass
class ContextEvidence:
    """证据项"""
    type: str  # metric | comparison | context
    label: str
    value: Any
    threshold: Optional[Any]
    unit: str
    severity: str
    resource_id: Optional[str]

@dataclass
class Action:
    """可执行操作"""
    type: str  # jump | highlight
    label: str
    target_page: str
    target_id: str
    params: Dict
```

### 3.2 前端功能

| 功能 | 文件 | 说明 |
|------|------|------|
| 跨页面导航 | `navigation.js` | RdcNav 单例，支持 buildLink/highlight |
| 脉冲动画 | `common.css` | `.jump-highlight` 类，2秒橙色边框闪烁 |
| 深链接处理 | `textures.html` | `?id=xxx&highlight=true` 支持 |
| 深链接处理 | `events.html` | `?eid=xxx&highlight=true` 支持 |
| 深链接处理 | `shaders.html` | `?sid=xxx&highlight=true` 支持 |
| 证据展示 | `recommendations.html` | `renderEvidenceChain()` 函数 |

---

## 4. 文件变更清单

### 新增文件

| 文件 | 用途 |
|------|------|
| `core/evidence_chain_builder.py` | 证据链构建器 |
| `core/evidence_builder.py` | 证据构建工具 |
| `tests/test_evidence_chain_pipeline.py` | 数据管道测试 (4 tests) |
| `docs/E2E_MANUAL_TEST_CHECKLIST.md` | 手动测试清单 |
| `docs/M1_M2_M3_MILESTONE_SUMMARY.md` | 本文档 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `core/types.py` | 新增 EvidenceChain, ContextEvidence, Action 类型 |
| `report_bundle_generator.py` | 保留 evidence 字段传递 |
| `templates/navigation.js` | 参数别名支持 |
| `templates/textures.html` | 深链接高亮集成 |
| `templates/events.html` | 深链接高亮集成 |
| `templates/shaders.html` | 深链接高亮集成 |
| `templates/recommendations.html` | 证据展示面板 |

---

## 5. 测试状态

### 5.1 单元测试

```bash
# 运行所有测试
py -3 -m pytest tests/ -v --tb=short

# 当前状态
# 33 passed (29 原有 + 4 新增)
```

| 测试文件 | 测试数 | 状态 |
|----------|--------|------|
| test_schema_bridge_integration.py | 16 | ✅ |
| test_pipeline_sampler.py | 13 | ✅ |
| test_evidence_chain_pipeline.py | 4 | ✅ |

### 5.2 E2E 手动测试

参见：`docs/E2E_MANUAL_TEST_CHECKLIST.md`

| 用例 | 状态 |
|------|------|
| TC-001: 跳转到纹理 | ⬜ 待测试 |
| TC-002: 跳转到事件 | ⬜ 待测试 |
| TC-003: 跳转到 Shader | ⬜ 待测试 |
| TC-004: 证据面板内容 | ⬜ 待测试 |
| TC-005: 深链接验证 | ⬜ 待测试 |
| TC-006: 控制台日志 | ⬜ 待测试 |

---

## 6. 下一步计划

### P1: 完成 E2E 验证

- [ ] 使用真实 RDC 报告执行手动测试
- [ ] 修复发现的问题
- [ ] 更新测试状态

### P2: 规则增强

- [ ] 为更多性能规则添加 EvidenceChain 生成
- [ ] 实现 EvidenceChainBuilder.from_resource_usage() 便捷方法

### P3: 文档完善

- [ ] 更新 INDEX.md 索引
- [ ] 添加架构图

---

*本文档记录了 M1+M2+M3 三个里程碑的完整实现状态。*
