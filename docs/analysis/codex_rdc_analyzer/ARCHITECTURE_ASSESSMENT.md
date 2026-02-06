# 架构评估报告：4 个关键问题
# Architecture Assessment: 4 Critical Questions

> **Version**: 1.0.0 | **Created**: 2025-01-21 | **Status**: 评审中
>
> **背景**：在开始证据链开发前，需要评估现有系统的复用性和扩展性。

---

## 📋 评估摘要

| 问题 | 结论 | 建议 |
|------|------|------|
| 1. 现有 4 页面是否保留？ | ✅ **保留并增强** | 80% 代码复用，新增证据链模块 |
| 2. 数据接口是否够用？ | ⚠️ **部分缺失** | 新增 `ResourceUsageIndex` 和 `EvidenceChain` |
| 3. 是否方便扩展新分析点？ | ✅ **架构良好** | 已有 `CanonicalIssue` 规范化模型 |
| 4. 开发优先级如何？ | 见下文 | P0: 反向索引 → P1: 跳转 → P2: 可视化 |

---

## 1. 现有页面评估：保留 vs 重写

### 1.1 现有页面清单

| 文件 | 功能 | 代码行数 | 复用价值 |
|------|------|----------|----------|
| `index.html` | 概览仪表盘 | ~600 | 🟢 高 |
| `textures.html` | 纹理浏览器 | ~700 | 🟢 高 |
| `events.html` | 事件时间线 | ~1200 | 🟢 高 |
| `shaders.html` | Shader 分析 | ~800 | 🟢 高 |
| `recommendations.html` | 优化建议 | ~500 | 🟡 中 |

### 1.2 复用性分析

#### ✅ 可直接复用的部分（70%）

| 组件 | 位置 | 说明 |
|------|------|------|
| CSS 变量系统 | `common.css` | 完整的暗色主题 |
| 布局框架 | 各页面 | 三栏布局、卡片系统 |
| 纹理网格视图 | `textures.html` | 缩略图、排序、过滤 |
| 事件时间线 | `events.html` | Pass 分组、时间条 |
| Shader 列表 | `shaders.html` | Mali 分析结果展示 |
| 数据注入框架 | 各页面 | `{{PLACEHOLDER}}` 模板 |

#### ⚠️ 需要增强的部分（20%）

| 组件 | 现状 | 需要增强 |
|------|------|----------|
| 纹理详情面板 | 显示属性 | **新增使用者列表、跳转按钮** |
| Issue 卡片 | 只显示消息 | **新增证据区、操作按钮** |
| 事件详情 | 基础 Pipeline | **新增绑定资源高亮** |
| 跨页面跳转 | 无 | **新增 URL 参数联动** |

#### ❌ 需要新增的部分（10%）

| 组件 | 说明 |
|------|------|
| 资源使用面板 | 显示 "谁在用这个资源" |
| 证据详情弹窗 | 显示 Issue 的完整证据链 |
| 绑定热力图 | 时间线上的资源绑定可视化 |

### 1.3 结论：保留并增强

```
推荐方案：渐进式增强（Incremental Enhancement）

优点：
  ✅ 保留现有稳定功能
  ✅ 减少重写风险
  ✅ 可逐步验证
  ✅ 代码审查更容易

缺点：
  ⚠️ 需要理解现有代码
  ⚠️ 可能有一些技术债务
```

---

## 2. 数据接口评估：现有 vs 新增

### 2.1 现有数据结构

```python
# 当前 JSON 数据结构（简化）
{
    "textures": [
        {
            "resource_id": "123",
            "name": "Albedo_4K",
            "width": 4096,
            "height": 4096,
            "format": "BC7_UNORM",
            "estimated_size": 67108864,
            "thumbnail": "data:image/png;base64,..."
        }
    ],
    "events": [
        {
            "event_id": 45,
            "name": "DrawIndexed",
            "draw_type": "DrawIndexed",
            "index_count": 1234,
            "marker": "Character Head",
            "pass_name": "GBuffer"
        }
    ],
    "issues": [
        {
            "code": "PERF003",
            "severity": "warning",
            "message": "纹理过大",
            "event_ids": [45],
            "resource_ids": ["123"]
        }
    ]
}
```

### 2.2 缺失的关键数据

| 数据类型 | 现有 | 缺失 | 用途 |
|----------|------|------|------|
| **资源使用索引** | ❌ | `texture_usage_index` | 纹理 → 使用它的 DrawCall |
| **绑定详情** | ❌ | `binding_details` | DrawCall 绑定的所有资源 |
| **证据链** | ⚠️ 部分 | `evidence_chain` | 量化证据 + 上下文 |
| **操作列表** | ❌ | `actions` | 可交互的跳转操作 |
| **用途推断** | ❌ | `purpose_hint` | Albedo/Normal/Shadow 等 |

### 2.3 新增接口设计

```python
# 新增数据结构

# 1. 资源使用索引（反向索引）
"resource_usage_index": {
    "tex_123": {
        "name": "Albedo_4K",
        "usage_count": 3,
        "usage_locations": [
            {
                "event_id": 45,
                "event_name": "Draw Character Head",
                "pass_name": "GBuffer",
                "slot_type": "SRV",
                "slot_index": 0,
                "purpose_hint": "Albedo"
            }
        ]
    }
}

# 2. 增强的 Issue 格式
"issues": [
    {
        "code": "PERF003",
        "severity": "warning",
        "category": "memory",
        "message": "纹理 Albedo_4K 分辨率过高 (4096x4096)",
        
        "event_ids": [45, 78, 112],
        "resource_ids": ["tex_123"],
        
        # === 新增：证据链 ===
        "evidence": {
            "actual": {"width": 4096, "height": 4096, "memory_mb": 64},
            "threshold": {"max_width": 2048},
            "impact_score": 75.5,
            "context": {
                "usage_summary": "渲染角色，共 3 个 DrawCall",
                "screen_coverage": 15.3
            }
        },
        
        # === 新增：可执行操作 ===
        "actions": [
            {"type": "jump_to_event", "label": "跳转 #45", "target": "45"},
            {"type": "jump_to_resource", "label": "查看纹理", "target": "tex_123"}
        ]
    }
]
```

### 2.4 接口兼容性策略

```
策略：向后兼容 + 渐进增强

1. 保留所有现有字段
2. 新增字段为可选（Optional）
3. 前端检测字段存在性后显示增强功能
4. 老数据仍可正常显示
```

---

## 3. 扩展性评估：新增分析点

### 3.1 当前分析器架构

```
BaseAnalyzer (基类)
    ├── PerformanceAnalyzer      # PERF001-007
    ├── ResourceAnalyzer         # 资源问题
    ├── StateAnalyzer            # 状态问题
    ├── PassAnalyzer             # Pass 问题
    ├── TileBasedAnalyzer        # TBR 问题
    ├── AdrenoAnalyzer           # Adreno GPU
    └── HotspotAnalyzer          # 热点分析
```

### 3.2 扩展流程（现有）

```python
# 添加新分析规则的步骤：

# 1. 在 Analyzer 中添加检测逻辑
class PerformanceAnalyzer(BaseAnalyzer):
    def analyze(self):
        # ... 现有规则 ...
        self._check_new_rule()  # 新增
    
    def _check_new_rule(self):
        # 检测逻辑
        if some_condition:
            self.add_issue(Issue(
                code="PERF008",
                severity="warning",
                message="新问题描述",
                event_ids=[...],
                resource_ids=[...],
            ))

# 2. Issue 自动转换为 CanonicalIssue（已实现）
# 3. CanonicalIssue 自动序列化为 JSON（已实现）
# 4. 前端自动显示新 Issue（已实现）
```

### 3.3 扩展性评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 添加新规则 | 🟢 5/5 | 只需添加检测方法 |
| 规范化输出 | 🟢 5/5 | `CanonicalIssue` 统一格式 |
| 前端显示 | 🟢 4/5 | 自动显示，可能需微调样式 |
| **证据链支持** | 🟡 3/5 | **需要增强** |
| **交互操作** | 🔴 2/5 | **需要新增** |

### 3.4 增强方案：证据链模板

```python
# 新增：证据链构建器（降低扩展门槛）

class EvidenceBuilder:
    """证据链构建器 - 简化新规则的证据生成"""
    
    @staticmethod
    def for_oversized_texture(
        texture: TextureInfo,
        usage_index: ResourceUsageIndex,
        threshold_width: int = 2048
    ) -> EvidenceChain:
        """纹理过大问题的标准证据链"""
        return EvidenceChain(
            actual_value={"width": texture.width, "height": texture.height},
            threshold_value={"max_width": threshold_width},
            impact_score=calculate_impact(texture, usage_index),
            context=ContextEvidence(
                usage_summary=usage_index.get_summary(texture.id),
                usage_locations=usage_index.get_locations(texture.id),
                screen_coverage=estimate_screen_coverage(texture, usage_index),
            )
        )
    
    @staticmethod
    def for_redundant_binding(
        resource_id: str,
        binding_events: List[int],
        threshold: int = 5
    ) -> EvidenceChain:
        """冗余绑定问题的标准证据链"""
        # ... 类似实现 ...
```

### 3.5 新规则扩展示例

```python
# 添加新规则 PERF008（GPU 热点）的完整流程

# Step 1: 添加检测逻辑
def _check_gpu_hotspot(self):
    for event in self.events:
        if event.gpu_time_ms > self.config.hotspot_threshold_ms:
            # Step 2: 使用 EvidenceBuilder 生成证据
            evidence = EvidenceBuilder.for_gpu_hotspot(
                event=event,
                threshold_ms=self.config.hotspot_threshold_ms,
                top_events=self._get_top_n_events(10)
            )
            
            # Step 3: 生成标准 Issue
            self.add_issue(CanonicalIssue(
                code="PERF008",
                severity="warning",
                category="performance",
                message=f"DrawCall #{event.event_id} 耗时 {event.gpu_time_ms:.1f}ms",
                event_ids=[event.event_id],
                evidence=evidence,
                actions=[
                    Action(ActionType.JUMP_TO_EVENT, "跳转", str(event.event_id)),
                    Action(ActionType.SHOW_TIMELINE, "查看热点区间", 
                           params={"start": event.event_id - 5, "end": event.event_id + 5})
                ]
            ))

# Step 4: 前端自动显示（无需修改）
```

---

## 4. 开发优先级与依赖链

### 4.1 功能依赖图

```
                    ┌─────────────────┐
                    │  P0: 反向索引   │
                    │  ResourceUsage  │
                    │     Index       │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
     ┌────────────┐  ┌────────────┐  ┌────────────┐
     │ P1a: 证据  │  │ P1b: 用途  │  │ P1c: 跳转  │
     │   链生成   │  │   推断     │  │   机制     │
     └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
           │               │               │
           └───────────────┼───────────────┘
                           ▼
                   ┌───────────────┐
                   │  P2: UI 增强  │
                   │  证据面板/跳转 │
                   └───────┬───────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │ P3a: 绑定  │  │ P3b: 热力  │  │ P3c: Pass  │
    │  热力图    │  │   图叠加   │  │   时间线   │
    └────────────┘  └────────────┘  └────────────┘
```

### 4.2 优先级排序

| 优先级 | 任务 | 工作量 | 价值 | 依赖 |
|--------|------|--------|------|------|
| **P0** | ResourceUsageIndex 构建 | 2 天 | 🔴 核心 | 无 |
| **P1a** | EvidenceChain 数据结构 | 1 天 | 🔴 核心 | P0 |
| **P1b** | 纹理用途推断 | 1 天 | 🟡 增强 | P0 |
| **P1c** | 跳转 URL 参数机制 | 1 天 | 🔴 核心 | 无 |
| **P2a** | 证据详情面板 UI | 2 天 | 🔴 核心 | P1a |
| **P2b** | 资源使用面板 UI | 2 天 | 🔴 核心 | P0 |
| **P2c** | 跳转高亮效果 | 1 天 | 🟡 增强 | P1c |
| **P3a** | 绑定热力图时间线 | 3 天 | 🟢 可选 | P0, P2 |
| **P3b** | Overdraw 热力图叠加 | 3 天 | 🟢 可选 | P2 |
| **P3c** | Pass 嵌套时间线 | 2 天 | 🟢 可选 | P2 |

### 4.3 推荐开发顺序

```
Week 1: 核心基础（P0 + P1）
├── Day 1-2: ResourceUsageIndex 构建逻辑
├── Day 3: EvidenceChain 数据结构
├── Day 4: 纹理用途推断规则
└── Day 5: 跳转 URL 参数机制

Week 2: UI 增强（P2）
├── Day 1-2: 证据详情面板
├── Day 3-4: 资源使用面板
└── Day 5: 跳转高亮效果

Week 3: 高级可视化（P3）- 可选
├── Day 1-3: 绑定热力图时间线
├── Day 4-5: Overdraw 热力图叠加
└── (后续): Pass 嵌套时间线
```

### 4.4 验收标准（Definition of Done）

| 阶段 | 验收标准 |
|------|----------|
| P0 完成 | 点击任意纹理，可看到使用它的 DrawCall 列表 |
| P1 完成 | Issue 卡片显示量化证据和上下文摘要 |
| P2 完成 | 点击 Issue 中的 "跳转" 按钮，页面自动定位并高亮 |
| P3 完成 | 时间线上可视化显示资源绑定频率热力图 |

---

## 5. 实施建议

### 5.1 代码修改清单

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| `core/types.py` | **增强** | 新增 `EvidenceChain`, `ResourceUsageIndex` |
| `core/resource_usage_builder.py` | **新增** | 构建反向索引的逻辑 |
| `core/evidence_builder.py` | **新增** | 证据链生成辅助类 |
| `report_bundle_generator.py` | **增强** | 输出新字段到 JSON |
| `templates/*.html` | **增强** | 新增 UI 组件 |
| `templates/common.css` | **增强** | 新增样式 |

### 5.2 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 反向索引性能问题 | 中 | 中 | 分块处理，限制最大条目 |
| 跨页面跳转不稳定 | 低 | 高 | 降级到页内滚动 |
| 老数据兼容性问题 | 低 | 中 | 字段可选，前端检测 |
| UI 样式冲突 | 低 | 低 | 使用 BEM 命名空间 |

---

## 6. 总结

### 6.1 关键决策

1. **保留现有 4 页面**，渐进式增强
2. **新增 `ResourceUsageIndex`** 作为证据链的核心数据源
3. **增强 `CanonicalIssue`**，添加 `evidence` 和 `actions` 字段
4. **P0 优先**：先完成反向索引，再做 UI

### 6.2 下一步行动

1. ✅ 确认架构评估报告
2. 🔜 开始 P0：实现 `ResourceUsageIndex` 构建器
3. 🔜 更新 `report_bundle_generator.py` 输出新字段
4. 🔜 增强 `textures.html` 显示使用者列表

---

*文档结束*
