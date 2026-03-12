# 证据链与交互设计规范
# Evidence Chain & UX Design Specification

> **Version**: 1.0.0 | **Created**: 2025-01-21 | **Status**: Draft
>
> **核心问题**: 如何让每个分析结论都有可追溯的证据，并提供便捷的交互验证？

---

## 1. 问题陈述

### 1.1 现有痛点

| 场景 | 当前体验 | 用户疑问 |
|------|----------|----------|
| "纹理过大 4K" | 仅显示尺寸 | 这张纹理用来做什么？值得 4K 吗？ |
| "频繁绑定" | 仅显示次数 | 在哪些 DrawCall 之间频繁？为什么？ |
| "Overdraw 警告" | 仅显示百分比 | 哪个区域？是哪些物体导致的？ |
| "Shader 性能差" | 仅显示指标 | 哪些指令消耗高？如何优化？ |

### 1.2 设计目标

```
┌─────────────────────────────────────────────────────────┐
│  结论 (What)  →  证据 (Why)  →  定位 (Where)  →  操作 (How) │
└─────────────────────────────────────────────────────────┘
     "4K过大"      "屏幕占2%"     "DrawCall#45"    "[跳转]"
```

**每个分析结论必须提供**：
1. **Why**: 为什么这是问题？（量化证据）
2. **Where**: 问题发生在哪里？（精确定位）
3. **How**: 如何查看/验证？（可交互操作）

---

## 2. 证据链数据模型

### 2.1 增强版 CanonicalIssue Schema

```python
@dataclass
class CanonicalIssue:
    """规范化 Issue 格式 v2.0 - 增加证据链支持"""
    
    # === 基础字段（现有）===
    code: str              # 规则 ID, e.g., "PERF003"
    severity: str          # critical | warning | info
    category: str          # performance | memory | correctness
    message: str           # 人类可读描述
    
    # === 定位字段（现有）===
    event_ids: List[int]   # 关联的 DrawCall/Event ID
    resource_ids: List[str] # 关联的资源 ID（纹理/Buffer/Shader）
    
    # === 证据字段（增强）===
    evidence: EvidenceChain  # 替换原有的 Dict[str, Any]
    
    # === 交互字段（新增）===
    actions: List[Action]  # 可执行的交互操作


@dataclass
class EvidenceChain:
    """
    证据链结构
    
    设计原则：每个证据都能回答 "为什么这是问题？"
    """
    # 量化证据
    actual_value: Any        # 实际值 (e.g., 4096)
    threshold_value: Any     # 阈值 (e.g., 2048)
    impact_score: float      # 影响分数 0-100 (用于排序)
    
    # 上下文证据
    context: ContextEvidence  # 使用上下文
    
    # 对比证据（可选）
    comparison: Optional[ComparisonEvidence] = None


@dataclass
class ContextEvidence:
    """
    上下文证据 - 解答"这个资源被如何使用"
    """
    # 使用者信息
    usage_summary: str       # "被 45 个 DrawCall 使用，渲染角色/场景"
    usage_locations: List[UsageLocation]  # 具体使用点
    
    # 屏幕影响
    screen_coverage: Optional[float]  # 屏幕占比 0-100%
    visibility_score: Optional[float]  # 可见性分数（考虑遮挡）
    
    # 绑定模式
    binding_pattern: Optional[BindingPattern]  # 绑定热力图数据


@dataclass
class UsageLocation:
    """资源使用位置"""
    event_id: int            # DrawCall ID
    event_name: str          # DrawCall 名称（如有 marker）
    pass_name: Optional[str] # 所属 RenderPass
    slot_type: str           # 绑定类型: "SRV" | "RTV" | "DSV" | "UAV"
    slot_index: int          # 槽位索引
    purpose_hint: str        # 用途推断: "Albedo" | "Normal" | "Shadow" | "Unknown"


@dataclass
class BindingPattern:
    """绑定模式分析（用于频繁绑定检测）"""
    bind_count: int          # 总绑定次数
    unique_bind_count: int   # 去重后的绑定次数
    redundant_count: int     # 冗余绑定次数
    event_range: Tuple[int, int]  # 发生区间 [start, end]
    hotspot_events: List[int]     # 热点事件列表
    timeline_data: List[Tuple[int, bool]]  # [(event_id, is_redundant), ...]


@dataclass
class Action:
    """可交互操作"""
    type: ActionType         # 操作类型
    label: str               # 显示文本
    target: str              # 操作目标（event_id/resource_id/pass_name）
    params: Dict[str, Any]   # 额外参数
    
    
class ActionType(Enum):
    """操作类型枚举"""
    JUMP_TO_EVENT = "jump_to_event"       # 跳转到 DrawCall
    JUMP_TO_RESOURCE = "jump_to_resource" # 跳转到资源详情
    JUMP_TO_PASS = "jump_to_pass"         # 跳转到 RenderPass
    SHOW_TIMELINE = "show_timeline"       # 显示时间线区间
    SHOW_HEATMAP = "show_heatmap"         # 显示热力图
    SHOW_COMPARISON = "show_comparison"   # 显示对比
    OPEN_IN_RENDERDOC = "open_in_renderdoc"  # 在 RenderDoc 中打开
```

---

## 3. 分析场景与证据链设计

### 3.1 场景：纹理过大

**Issue 生成示例**：

```json
{
  "code": "PERF003",
  "severity": "warning",
  "category": "memory",
  "message": "纹理 Albedo_Character_4K 分辨率过高 (4096x4096)",
  
  "event_ids": [45, 78, 112],
  "resource_ids": ["tex_12345"],
  
  "evidence": {
    "actual_value": {"width": 4096, "height": 4096, "memory_mb": 64},
    "threshold_value": {"max_width": 2048, "recommended_mb": 16},
    "impact_score": 75.5,
    
    "context": {
      "usage_summary": "渲染角色头部/手臂/腿部，共 3 个 DrawCall",
      "usage_locations": [
        {"event_id": 45, "event_name": "Draw Character Head", "slot_type": "SRV", "slot_index": 0, "purpose_hint": "Albedo"},
        {"event_id": 78, "event_name": "Draw Character Arms", "slot_type": "SRV", "slot_index": 0, "purpose_hint": "Albedo"},
        {"event_id": 112, "event_name": "Draw Character Legs", "slot_type": "SRV", "slot_index": 0, "purpose_hint": "Albedo"}
      ],
      "screen_coverage": 15.3,
      "visibility_score": 12.1
    }
  },
  
  "actions": [
    {"type": "jump_to_event", "label": "查看 DrawCall #45", "target": "45"},
    {"type": "jump_to_resource", "label": "查看纹理详情", "target": "tex_12345"},
    {"type": "show_comparison", "label": "对比 1K vs 4K 效果", "target": "tex_12345", "params": {"compare_sizes": [1024, 4096]}}
  ]
}
```

**UI 展示**：

```
┌─────────────────────────────────────────────────────────────┐
│ ⚠️ PERF003: 纹理分辨率过高                                   │
├─────────────────────────────────────────────────────────────┤
│ 📦 Albedo_Character_4K                                      │
│ 尺寸: 4096x4096 (64 MB)  │  推荐: ≤2048 (16 MB)             │
│                                                             │
│ 📍 使用情况:                                                 │
│   • DrawCall #45 - Character Head (Albedo)     [跳转]       │
│   • DrawCall #78 - Character Arms (Albedo)     [跳转]       │
│   • DrawCall #112 - Character Legs (Albedo)    [跳转]       │
│                                                             │
│ 📊 影响分析:                                                 │
│   屏幕占比: 15.3% | 可见性: 12.1% | 浪费: ~75%               │
│                                                             │
│ 💡 建议: 考虑降至 2048x2048，节省 48MB 且视觉差异微小        │
│                                                             │
│ [查看纹理预览]  [跳转首个DrawCall]  [对比1K/4K效果]          │
└─────────────────────────────────────────────────────────────┘
```

---

### 3.2 场景：频繁绑定

**Issue 生成示例**：

```json
{
  "code": "BIND007",
  "severity": "warning",
  "category": "performance",
  "message": "纹理 ShadowMap_Main 在 DrawCall #120-#180 间被冗余绑定 47 次",
  
  "event_ids": [120, 125, 130, 135, 140, 145, 150, 155, 160, 165, 170, 175, 180],
  "resource_ids": ["tex_67890"],
  
  "evidence": {
    "actual_value": 47,
    "threshold_value": 5,
    "impact_score": 62.0,
    
    "context": {
      "usage_summary": "ShadowMap 在阴影 Pass 后被连续绑定到多个物体渲染",
      "binding_pattern": {
        "bind_count": 60,
        "unique_bind_count": 1,
        "redundant_count": 47,
        "event_range": [120, 180],
        "hotspot_events": [125, 130, 135, 140, 145],
        "timeline_data": [
          [120, false], [125, true], [130, true], [135, true], 
          [140, true], [145, true], [150, true], [155, true],
          [160, true], [165, true], [170, true], [175, true], [180, false]
        ]
      }
    }
  },
  
  "actions": [
    {"type": "show_timeline", "label": "查看绑定时间线", "target": "120-180"},
    {"type": "jump_to_event", "label": "跳转首次绑定", "target": "120"},
    {"type": "jump_to_event", "label": "跳转热点区域", "target": "125"}
  ]
}
```

**UI 展示**：

```
┌─────────────────────────────────────────────────────────────┐
│ ⚠️ BIND007: 冗余资源绑定                                     │
├─────────────────────────────────────────────────────────────┤
│ 📦 ShadowMap_Main                                           │
│ 冗余绑定: 47 次  │  区间: DrawCall #120 - #180               │
│                                                             │
│ 📊 绑定时间线:                                               │
│   #120        #140        #160        #180                  │
│   │▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│               │
│   ↑首次绑定   ↑↑↑↑↑ 冗余热点区域              ↑解除绑定     │
│                                                             │
│ 💡 原因分析:                                                 │
│   ShadowMap 在 Pass "Shadow" 生成后，被 60 个物体渲染引用   │
│   但引擎每次 DrawCall 都重新绑定，未利用状态继承             │
│                                                             │
│ 💡 建议: 对使用相同 ShadowMap 的物体进行批次合并             │
│                                                             │
│ [查看完整时间线]  [跳转首次绑定 #120]  [跳转热点 #125]       │
└─────────────────────────────────────────────────────────────┘
```

---

### 3.3 场景：Overdraw

**Issue 生成示例**：

```json
{
  "code": "PERF001",
  "severity": "warning",
  "category": "performance",
  "message": "屏幕中央区域过度绘制严重，平均 5.2 次/像素",
  
  "event_ids": [200, 210, 220, 230, 240, 250],
  "resource_ids": [],
  
  "evidence": {
    "actual_value": 5.2,
    "threshold_value": 2.5,
    "impact_score": 85.0,
    
    "context": {
      "usage_summary": "UI 层叠加、半透明粒子、场景物体共同导致",
      "screen_coverage": 35.0,
      "heatmap_data": {
        "type": "overdraw",
        "resolution": [320, 180],
        "data_base64": "...",  // 压缩的热力图数据
        "hotspot_regions": [
          {"x": 160, "y": 90, "width": 100, "height": 80, "avg_overdraw": 7.3}
        ]
      }
    }
  },
  
  "actions": [
    {"type": "show_heatmap", "label": "查看 Overdraw 热力图", "target": "overdraw"},
    {"type": "jump_to_event", "label": "查看首个高 Overdraw DrawCall", "target": "200"},
    {"type": "show_timeline", "label": "查看该区域的绘制顺序", "target": "200-250"}
  ]
}
```

---

## 4. 资源反向索引系统

### 4.1 数据结构

```python
@dataclass
class ResourceUsageIndex:
    """
    资源使用反向索引
    
    核心功能：给定任意资源 ID，快速获取所有使用它的 DrawCall
    """
    
    # 纹理使用索引: texture_id -> [UsageRecord]
    texture_usage: Dict[str, List[UsageRecord]]
    
    # Buffer 使用索引: buffer_id -> [UsageRecord]  
    buffer_usage: Dict[str, List[UsageRecord]]
    
    # Shader 使用索引: shader_id -> [UsageRecord]
    shader_usage: Dict[str, List[UsageRecord]]
    
    # RenderTarget 写入索引: rt_id -> [event_id] (谁写入了这个 RT)
    rt_writers: Dict[str, List[int]]
    
    # RenderTarget 读取索引: rt_id -> [event_id] (谁读取了这个 RT)
    rt_readers: Dict[str, List[int]]


@dataclass
class UsageRecord:
    """单次资源使用记录"""
    event_id: int
    event_name: str
    pass_name: Optional[str]
    binding_type: str        # "SRV" | "UAV" | "RTV" | "DSV" | "VB" | "IB" | "CB"
    binding_slot: int
    shader_stage: str        # "VS" | "PS" | "CS" | "GS" | "HS" | "DS"
    purpose_hint: str        # 推断的用途
    timestamp_ns: Optional[int]  # 如有 GPU 时间戳
```

### 4.2 用途推断规则

```python
def infer_texture_purpose(
    texture: TextureInfo,
    binding_slot: int,
    binding_type: str,
    sampler_info: Optional[SamplerInfo]
) -> str:
    """
    推断纹理用途
    
    基于：名称、格式、尺寸、绑定位置、采样器设置
    """
    name_lower = texture.name.lower() if texture.name else ""
    
    # 名称匹配
    if "albedo" in name_lower or "diffuse" in name_lower or "basecolor" in name_lower:
        return "Albedo"
    if "normal" in name_lower:
        return "Normal"
    if "roughness" in name_lower or "metallic" in name_lower or "orm" in name_lower:
        return "Material"
    if "shadow" in name_lower:
        return "ShadowMap"
    if "ao" in name_lower or "ambient" in name_lower:
        return "AO"
    if "emissive" in name_lower:
        return "Emissive"
    if "lightmap" in name_lower:
        return "Lightmap"
    if "reflection" in name_lower or "env" in name_lower or "cubemap" in name_lower:
        return "Environment"
    
    # 格式推断
    if texture.format in ["BC5_UNORM", "BC5_SNORM", "R8G8_UNORM"]:
        return "Normal (格式推断)"
    if texture.format in ["R16_FLOAT", "R32_FLOAT", "D16_UNORM", "D24_UNORM_S8_UINT", "D32_FLOAT"]:
        return "Depth"
    if "SRGB" in texture.format:
        return "Color (sRGB)"
    
    # 绑定位置推断
    if binding_type == "RTV":
        return "RenderTarget"
    if binding_type == "DSV":
        return "DepthStencil"
    if binding_type == "UAV":
        return "UAV (读写)"
    
    # 槽位推断（假设标准 PBR 布局）
    slot_hints = {
        0: "Albedo (槽位推断)",
        1: "Normal (槽位推断)",
        2: "Material (槽位推断)",
        3: "AO (槽位推断)",
    }
    if binding_slot in slot_hints:
        return slot_hints[binding_slot]
    
    return "Unknown"
```

---

## 5. 交互跳转实现

### 5.1 HTML 报告跳转机制

```javascript
// 全局状态管理
const AppState = {
    currentView: 'overview',  // 'overview' | 'timeline' | 'textures' | 'issues'
    selectedEvent: null,
    selectedResource: null,
    highlightedEvents: [],
};

// 跳转到指定 DrawCall
function jumpToEvent(eventId) {
    AppState.selectedEvent = eventId;
    
    // 1. 切换到时间线视图
    switchView('timeline');
    
    // 2. 滚动到目标事件
    const eventElement = document.querySelector(`[data-event-id="${eventId}"]`);
    if (eventElement) {
        eventElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
        eventElement.classList.add('highlight-pulse');
        setTimeout(() => eventElement.classList.remove('highlight-pulse'), 2000);
    }
    
    // 3. 展开事件详情面板
    showEventDetailPanel(eventId);
}

// 跳转到资源详情
function jumpToResource(resourceId) {
    AppState.selectedResource = resourceId;
    
    // 1. 切换到资源视图
    switchView('textures');
    
    // 2. 选中目标资源
    selectResource(resourceId);
    
    // 3. 显示使用情况
    showResourceUsagePanel(resourceId);
}

// 高亮事件区间（用于频繁绑定等多事件问题）
function highlightEventRange(startId, endId) {
    AppState.highlightedEvents = [];
    
    // 找到区间内的所有事件
    const events = document.querySelectorAll('[data-event-id]');
    events.forEach(el => {
        const id = parseInt(el.dataset.eventId);
        if (id >= startId && id <= endId) {
            AppState.highlightedEvents.push(id);
            el.classList.add('in-range');
        } else {
            el.classList.remove('in-range');
        }
    });
    
    // 切换到时间线视图并滚动到起点
    switchView('timeline');
    jumpToEvent(startId);
}

// 显示资源使用情况面板
function showResourceUsagePanel(resourceId) {
    const usageData = ResourceUsageIndex[resourceId];
    if (!usageData) return;
    
    const panel = document.getElementById('usage-panel');
    panel.innerHTML = `
        <h3>使用情况: ${usageData.name || resourceId}</h3>
        <div class="usage-summary">${usageData.usage_summary}</div>
        <ul class="usage-list">
            ${usageData.usage_locations.map(loc => `
                <li onclick="jumpToEvent(${loc.event_id})" class="clickable">
                    <span class="event-badge">#${loc.event_id}</span>
                    <span class="event-name">${loc.event_name}</span>
                    <span class="purpose-tag">${loc.purpose_hint}</span>
                    <span class="binding-info">${loc.slot_type}[${loc.slot_index}]</span>
                </li>
            `).join('')}
        </ul>
    `;
    panel.classList.add('visible');
}
```

### 5.2 EXE 跳转机制（Qt）

```cpp
// 问题项点击处理
void IssueListWidget::onIssueClicked(const CanonicalIssue& issue) {
    // 显示证据详情
    m_evidencePanel->setIssue(issue);
    
    // 如果有关联事件，在时间线上高亮
    if (!issue.event_ids.empty()) {
        m_timelineView->highlightEvents(issue.event_ids);
        m_timelineView->scrollToEvent(issue.event_ids[0]);
    }
    
    // 如果有关联资源，在资源面板上选中
    if (!issue.resource_ids.empty()) {
        m_resourcePanel->selectResource(issue.resource_ids[0]);
    }
}

// 跳转操作处理
void IssueListWidget::executeAction(const Action& action) {
    switch (action.type) {
        case ActionType::JUMP_TO_EVENT:
            m_mainWindow->selectEvent(action.target.toInt());
            break;
            
        case ActionType::JUMP_TO_RESOURCE:
            m_mainWindow->selectResource(action.target);
            break;
            
        case ActionType::SHOW_TIMELINE:
            m_mainWindow->showTimelineRange(action.params["start"].toInt(), 
                                            action.params["end"].toInt());
            break;
            
        case ActionType::SHOW_HEATMAP:
            m_mainWindow->showHeatmapOverlay(action.params["type"].toString());
            break;
            
        case ActionType::OPEN_IN_RENDERDOC:
            QProcess::startDetached("qrenderdoc", 
                {m_rdcPath, "--event", action.target});
            break;
    }
}
```

---

## 6. 视图联动规范

### 6.1 四视图架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Header / 概览                          │
├─────────────────┬───────────────────────────────────────────┤
│                 │                                           │
│   问题列表       │            主视图区域                     │
│   (Issues)      │     ┌─────────────────────────────────┐   │
│                 │     │   Timeline / Texture / Pass     │   │
│   ───────       │     │   (根据选择切换)                 │   │
│   • PERF003     │     │                                 │   │
│   • BIND007  ←──┼──→  │   点击问题 → 跳转并高亮          │   │
│   • PERF001     │     │   点击资源 → 显示使用列表        │   │
│                 │     │   点击事件 → 展开详情            │   │
│                 │     └─────────────────────────────────┘   │
│                 │                                           │
├─────────────────┴───────────────────────────────────────────┤
│                      详情面板 (Detail)                       │
│   当前选中: DrawCall #45 - "Draw Character Head"            │
│   Pipeline State | Textures Bound | Shader Info | Timing    │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 联动规则

| 用户操作 | 响应行为 |
|----------|----------|
| 点击 Issue | 1. 主视图跳转到相关位置<br>2. 高亮关联事件/资源<br>3. 详情面板显示证据 |
| 点击 Texture | 1. 选中该纹理<br>2. 使用列表显示所有引用它的 DrawCall<br>3. 时间线上标记使用点 |
| 点击 DrawCall | 1. 选中该事件<br>2. 详情面板显示 Pipeline State<br>3. 资源面板高亮绑定的资源 |
| 点击 RenderPass | 1. 时间线范围框选该 Pass<br>2. 显示 Pass 内所有 DrawCall<br>3. 统计面板更新 |

---

## 7. 实现优先级

### Phase 1: 基础证据链（2 周）

- [ ] `EvidenceChain` 数据结构定义
- [ ] `ResourceUsageIndex` 构建逻辑
- [ ] 纹理用途推断 (`infer_texture_purpose`)
- [ ] `CanonicalIssue` 增加 `evidence` 和 `actions` 字段

### Phase 2: 交互跳转（2 周）

- [ ] HTML: `jumpToEvent()` / `jumpToResource()` 实现
- [ ] HTML: 事件高亮与范围选择
- [ ] HTML: 资源使用面板

### Phase 3: 高级可视化（3 周）

- [ ] 绑定热力图时间线
- [ ] Overdraw 热力图叠加
- [ ] Pass 时间线与嵌套视图

### Phase 4: EXE 集成（4 周）

- [ ] Qt 视图联动框架
- [ ] 与 RenderDoc 主界面集成
- [ ] 跨 GPU 回放支持

---

## 8. 附录：Issue 类型与证据需求矩阵

| Issue Code | 类型 | 必需证据 | 推荐操作 |
|------------|------|----------|----------|
| PERF001 | Overdraw | 热力图数据、区域覆盖率、绘制次数 | 热力图、跳转热点 |
| PERF003 | 纹理过大 | 尺寸、内存、屏幕占比、使用者列表 | 跳转DrawCall、对比 |
| PERF004 | 小批次 | 批次数、平均三角形数、合并潜力 | 跳转首个、批次列表 |
| BIND007 | 频繁绑定 | 绑定次数、冗余次数、时间线数据 | 时间线、跳转热点 |
| MEM001 | 内存泄漏 | 资源类型、大小、创建位置、未释放原因 | 跳转创建点 |
| RT001 | 无效RT切换 | 切换次数、切换间DrawCall数 | 时间线、Pass视图 |
| SHADER001 | 高指令数 | 指令类型分布、热点函数、ALU利用率 | Shader详情 |

---

*文档结束*
