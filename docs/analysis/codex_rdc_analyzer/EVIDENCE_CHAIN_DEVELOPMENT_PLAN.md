# 证据链功能开发计划
# Evidence Chain Development Plan

> **Version**: 1.0.0 | **Created**: 2025-01-24 | **Status**: 开发中
>
> **来源文档**：
> - `EVIDENCE_CHAIN_UX_DESIGN.md` - 证据链数据模型与交互规范
> - `ARCHITECTURE_ASSESSMENT.md` - 架构评估与优先级
> - `UI_INTERACTION_AUDIT.md` - 现有 UI 组件盘点
>
> **目标**：完成本计划后，三个源文档中的所有功能需求均应实现完毕。

---

## 📊 开发概览

### 总体统计

| 维度 | 数量 | 说明 |
|------|------|------|
| 里程碑 | 4 个 | M1-M4 递进依赖 |
| 开发点 | 28 个 | 可勾选的最小任务单元 |
| 预估工时 | 8-10 天 | 每个开发点约 0.5-1 天 |
| 新增文件 | 4 个 | Python 模块 |
| 修改文件 | 8 个 | 现有代码增强 |

### 里程碑依赖图

```
M1: 数据基础层 (2天)
    │
    ├──→ M2: 证据链生成 (2天)
    │        │
    │        └──→ M3: UI 增强 (3天)
    │                  │
    └──────────────────┴──→ M4: 高级可视化 (2天, 可选)
```

### 验收标准速查

| 里程碑 | 验收标准 |
|--------|----------|
| M1 完成 | 点击任意纹理，可看到使用它的 DrawCall 列表 |
| M2 完成 | Issue 卡片显示量化证据、上下文摘要、跳转按钮 |
| M3 完成 | 点击"跳转"按钮，页面自动定位并高亮目标元素 |
| M4 完成 | 时间线显示资源绑定热力图（可选） |

---

## 🏁 M1: 数据基础层（ResourceUsageIndex）

> **目标**：构建资源反向索引，解锁"使用情况"功能
> 
> **预估工时**：2 天
>
> **解决问题**（来自 UI_INTERACTION_AUDIT.md）：
> - ❌ `usedBy` 数据未填充，导致"使用情况"列表始终为空
> - ❌ Shader 绑定信息不完整

### 开发点清单

#### M1.1 数据结构定义
- [ ] **M1.1.1** 在 `core/types.py` 新增 `UsageRecord` 数据类
  ```python
  @dataclass
  class UsageRecord:
      event_id: int
      event_name: str
      pass_name: Optional[str]
      binding_type: str        # "SRV" | "UAV" | "RTV" | "DSV"
      binding_slot: int
      shader_stage: str        # "VS" | "PS" | "CS"
      purpose_hint: str        # "Albedo" | "Normal" | "Unknown"
  ```

- [ ] **M1.1.2** 在 `core/types.py` 新增 `ResourceUsageIndex` 数据类
  ```python
  @dataclass
  class ResourceUsageIndex:
      texture_usage: Dict[str, List[UsageRecord]]
      buffer_usage: Dict[str, List[UsageRecord]]
      shader_usage: Dict[str, List[UsageRecord]]
      rt_writers: Dict[str, List[int]]
      rt_readers: Dict[str, List[int]]
  ```

#### M1.2 构建器实现
- [ ] **M1.2.1** 新建 `core/resource_usage_builder.py`
- [ ] **M1.2.2** 实现 `ResourceUsageBuilder.build(events, textures, shaders)` 方法
  - 遍历所有 DrawCall 事件
  - 记录每个资源的使用位置
  - 构建反向索引

- [ ] **M1.2.3** 实现纹理用途推断 `infer_texture_purpose()`
  - 基于纹理名称匹配（albedo/normal/shadow 等）
  - 基于格式推断（BC5 → Normal）
  - 基于槽位推断（slot 0 → Albedo）

#### M1.3 集成到报告生成
- [ ] **M1.3.1** 修改 `report_bundle_generator.py`
  - 在生成报告前调用 `ResourceUsageBuilder`
  - 将 `usedBy` 数据注入到 textures 和 shaders JSON

- [ ] **M1.3.2** 更新 JSON Schema
  - textures 数组元素新增 `usedBy: List[UsageRecord]`
  - shaders 数组元素新增 `usedBy: List[UsageRecord]`

#### M1.4 验证
- [ ] **M1.4.1** 编写单元测试 `tests/test_resource_usage_builder.py`
- [ ] **M1.4.2** 生成测试报告，验证 textures.html 显示使用列表

### M1 验收标准
```
✅ 打开 textures.html
✅ 选中任意纹理
✅ 右侧面板"使用情况"区域显示 DrawCall 列表
✅ 列表包含：事件ID、事件名称、绑定类型、用途推断
```

---

## 🔗 M2: 证据链生成（EvidenceChain）

> **目标**：为每个 Issue 生成完整的证据链数据
>
> **预估工时**：2 天
>
> **解决问题**（来自 EVIDENCE_CHAIN_UX_DESIGN.md）：
> - 问题卡片只显示消息，缺少量化证据和操作按钮
> - 无法回答"为什么这是问题"

### 开发点清单

#### M2.1 数据结构定义
- [ ] **M2.1.1** 在 `core/types.py` 新增 `EvidenceChain` 数据类
  ```python
  @dataclass
  class EvidenceChain:
      actual_value: Any
      threshold_value: Any
      impact_score: float
      context: ContextEvidence
      comparison: Optional[ComparisonEvidence] = None
  ```

- [ ] **M2.1.2** 新增 `ContextEvidence` 数据类
  ```python
  @dataclass
  class ContextEvidence:
      usage_summary: str
      usage_locations: List[UsageLocation]
      screen_coverage: Optional[float]
      visibility_score: Optional[float]
      binding_pattern: Optional[BindingPattern]
  ```

- [ ] **M2.1.3** 新增 `Action` 和 `ActionType` 枚举
  ```python
  class ActionType(Enum):
      JUMP_TO_EVENT = "jump_to_event"
      JUMP_TO_RESOURCE = "jump_to_resource"
      JUMP_TO_PASS = "jump_to_pass"
      SHOW_TIMELINE = "show_timeline"
      SHOW_HEATMAP = "show_heatmap"

  @dataclass
  class Action:
      type: ActionType
      label: str
      target: str
      params: Dict[str, Any] = field(default_factory=dict)
  ```

#### M2.2 证据构建器
- [ ] **M2.2.1** 新建 `core/evidence_builder.py`
- [ ] **M2.2.2** 实现 `EvidenceBuilder.for_oversized_texture()`
  - 输入：TextureInfo, ResourceUsageIndex, threshold
  - 输出：EvidenceChain（含使用摘要、屏幕占比估算）

- [ ] **M2.2.3** 实现 `EvidenceBuilder.for_redundant_binding()`
  - 输入：resource_id, binding_events, threshold
  - 输出：EvidenceChain（含绑定模式、热点事件）

- [ ] **M2.2.4** 实现 `EvidenceBuilder.for_high_instruction_shader()`
  - 输入：ShaderInfo, MaliocResult
  - 输出：EvidenceChain（含指令分布、性能瓶颈）

#### M2.3 集成到分析器
- [ ] **M2.3.1** 修改 `CanonicalIssue` 类
  - 新增 `evidence: Optional[EvidenceChain]` 字段
  - 新增 `actions: List[Action]` 字段

- [ ] **M2.3.2** 更新现有分析规则调用 EvidenceBuilder
  - `PerformanceAnalyzer._check_oversized_textures()`
  - `ResourceAnalyzer._check_redundant_bindings()`
  - `HotspotAnalyzer._check_gpu_hotspots()`

- [ ] **M2.3.3** 更新 JSON 序列化
  - `CanonicalIssue.to_dict()` 输出 evidence 和 actions

#### M2.4 验证
- [ ] **M2.4.1** 编写单元测试 `tests/test_evidence_builder.py`
- [ ] **M2.4.2** 生成测试报告，验证 Issue JSON 包含完整证据

### M2 验收标准
```
✅ 打开生成的 report.json
✅ issues 数组中每个 issue 包含 evidence 对象
✅ evidence 包含：actual_value, threshold_value, impact_score, context
✅ issue 包含 actions 数组，每个 action 有 type/label/target
```

---

## 🎨 M3: UI 增强（跳转与证据展示）

> **目标**：实现跨页面跳转、高亮、证据面板
>
> **预估工时**：3 天
>
> **解决问题**（来自 UI_INTERACTION_AUDIT.md + ARCHITECTURE_ASSESSMENT.md）：
> - ⚠️ 问题项点击无法跳转到具体证据
> - ❌ 跨页面高亮未实现
> - ❌ "跳转到资源"按钮的 action 数据不完整

### 开发点清单

#### M3.1 URL 跳转机制
- [ ] **M3.1.1** 在各 HTML 页面新增 `parseUrlParams()` 函数
  ```javascript
  function parseUrlParams() {
      const params = new URLSearchParams(window.location.search);
      return {
          id: params.get('id'),
          highlight: params.get('highlight') === 'true',
          scroll: params.get('scroll') !== 'false'
      };
  }
  ```

- [ ] **M3.1.2** 实现 `highlightAndScrollTo(id)` 函数
  - 找到目标元素 `[data-id="${id}"]`
  - 添加 `.highlight-pulse` 动画类
  - 调用 `scrollIntoView({ behavior: 'smooth', block: 'center' })`

- [ ] **M3.1.3** 在页面 `DOMContentLoaded` 时调用
  ```javascript
  document.addEventListener('DOMContentLoaded', () => {
      const params = parseUrlParams();
      if (params.id) {
          highlightAndScrollTo(params.id);
      }
  });
  ```

#### M3.2 跳转按钮实现
- [ ] **M3.2.1** 更新 `textures.html` 使用情况列表
  - 每个 UsageRecord 生成可点击链接
  - 点击跳转到 `events.html?id={event_id}&highlight=true`

- [ ] **M3.2.2** 更新 `shaders.html` 使用情况列表
  - 同上

- [ ] **M3.2.3** 更新 `recommendations.html` 操作按钮
  - 根据 action.type 生成不同跳转链接
  - `jump_to_event` → `events.html?id=...`
  - `jump_to_resource` → `textures.html?id=...`

- [ ] **M3.2.4** 更新 `index.html` 问题卡片
  - 显示 Issue 的 actions 按钮

#### M3.3 证据详情面板
- [ ] **M3.3.1** 在 `recommendations.html` 新增证据区块
  ```html
  <div class="evidence-section">
      <div class="evidence-header">📊 证据详情</div>
      <div class="evidence-row">
          <span class="label">实际值:</span>
          <span class="value actual">{{actual_value}}</span>
      </div>
      <div class="evidence-row">
          <span class="label">阈值:</span>
          <span class="value threshold">{{threshold_value}}</span>
      </div>
      <div class="evidence-row">
          <span class="label">影响分:</span>
          <span class="value impact">{{impact_score}}</span>
      </div>
  </div>
  ```

- [ ] **M3.3.2** 新增证据面板样式到 `common.css`
  ```css
  .evidence-section { ... }
  .evidence-row { display: flex; justify-content: space-between; }
  .value.actual { color: var(--accent-red); }
  .value.threshold { color: var(--accent-blue); }
  .highlight-pulse { animation: pulse 1s ease-in-out 3; }
  @keyframes pulse {
      0%, 100% { background: transparent; }
      50% { background: rgba(88, 166, 255, 0.3); }
  }
  ```

- [ ] **M3.3.3** 新增使用情况摘要区块
  ```html
  <div class="context-section">
      <div class="context-header">📍 使用情况</div>
      <div class="usage-summary">{{usage_summary}}</div>
      <ul class="usage-list">
          {{#each usage_locations}}
          <li onclick="jumpToEvent({{event_id}})">
              <span class="eid">#{{event_id}}</span>
              <span class="name">{{event_name}}</span>
              <span class="purpose">{{purpose_hint}}</span>
          </li>
          {{/each}}
      </ul>
  </div>
  ```

#### M3.4 验证
- [ ] **M3.4.1** 端到端测试：从 recommendations.html 跳转到 events.html
- [ ] **M3.4.2** 验证高亮动画正常播放
- [ ] **M3.4.3** 验证 textures.html 使用列表可点击

### M3 验收标准
```
✅ 打开 recommendations.html
✅ 选中一个 Issue
✅ 右侧面板显示证据详情（实际值/阈值/影响分）
✅ 点击"跳转到 DrawCall #45"按钮
✅ 页面跳转到 events.html?id=45&highlight=true
✅ 目标事件自动滚动到视口中央
✅ 目标事件显示 3 次脉冲高亮动画
```

---

## 📈 M4: 高级可视化（可选）

> **目标**：绑定热力图、Overdraw 叠加等高级功能
>
> **预估工时**：2 天
>
> **优先级**：低（P3）- 可在后续迭代中实现
>
> **解决问题**（来自 EVIDENCE_CHAIN_UX_DESIGN.md）：
> - 绑定热力图时间线
> - Overdraw 热力图叠加

### 开发点清单

#### M4.1 绑定热力图
- [ ] **M4.1.1** 在 `events.html` 时间线新增热力图图层
- [ ] **M4.1.2** 实现 `renderBindingHeatmap(resource_id)` 函数
- [ ] **M4.1.3** 冗余绑定区域标红，正常绑定标绿

#### M4.2 Pass 嵌套时间线
- [ ] **M4.2.1** 在 `events.html` 新增 Pass 分组视图
- [ ] **M4.2.2** 实现 Pass 折叠/展开
- [ ] **M4.2.3** 显示 Pass 级别的 GPU 时间统计

### M4 验收标准（可选）
```
✅ 在 Issue 详情中点击"查看绑定时间线"
✅ 时间线上显示资源绑定热力图
✅ 红色区域表示冗余绑定
```

---

## 📁 文件变更清单

### 新增文件

| 文件路径 | 里程碑 | 说明 |
|----------|--------|------|
| `core/resource_usage_builder.py` | M1 | 资源使用索引构建器 |
| `core/evidence_builder.py` | M2 | 证据链生成辅助类 |
| `tests/test_resource_usage_builder.py` | M1 | 单元测试 |
| `tests/test_evidence_builder.py` | M2 | 单元测试 |

### 修改文件

| 文件路径 | 里程碑 | 修改内容 |
|----------|--------|----------|
| `core/types.py` | M1, M2 | 新增 UsageRecord, ResourceUsageIndex, EvidenceChain, Action |
| `report_bundle_generator.py` | M1, M2 | 集成 ResourceUsageBuilder, 输出新字段 |
| `templates/textures.html` | M1, M3 | 使用情况列表, 跳转功能 |
| `templates/shaders.html` | M1, M3 | 使用情况列表, 跳转功能 |
| `templates/events.html` | M3 | URL 参数解析, 高亮动画 |
| `templates/recommendations.html` | M2, M3 | 证据面板, 操作按钮 |
| `templates/index.html` | M3 | 问题卡片操作按钮 |
| `templates/common.css` | M3 | 高亮动画, 证据面板样式 |

---

## ✅ 进度追踪

### M1: 数据基础层
- [ ] M1.1.1 UsageRecord 数据类
- [ ] M1.1.2 ResourceUsageIndex 数据类
- [ ] M1.2.1 新建 resource_usage_builder.py
- [ ] M1.2.2 build() 方法实现
- [ ] M1.2.3 infer_texture_purpose() 实现
- [ ] M1.3.1 report_bundle_generator 集成
- [ ] M1.3.2 JSON Schema 更新
- [ ] M1.4.1 单元测试
- [ ] M1.4.2 生成测试报告验证

### M2: 证据链生成
- [ ] M2.1.1 EvidenceChain 数据类
- [ ] M2.1.2 ContextEvidence 数据类
- [ ] M2.1.3 Action 和 ActionType
- [ ] M2.2.1 新建 evidence_builder.py
- [ ] M2.2.2 for_oversized_texture()
- [ ] M2.2.3 for_redundant_binding()
- [ ] M2.2.4 for_high_instruction_shader()
- [ ] M2.3.1 CanonicalIssue 增强
- [ ] M2.3.2 分析规则集成
- [ ] M2.3.3 JSON 序列化更新
- [ ] M2.4.1 单元测试
- [ ] M2.4.2 生成测试报告验证

### M3: UI 增强
- [ ] M3.1.1 parseUrlParams() 函数
- [ ] M3.1.2 highlightAndScrollTo() 函数
- [ ] M3.1.3 DOMContentLoaded 集成
- [ ] M3.2.1 textures.html 使用列表跳转
- [ ] M3.2.2 shaders.html 使用列表跳转
- [ ] M3.2.3 recommendations.html 操作按钮
- [ ] M3.2.4 index.html 问题卡片按钮
- [ ] M3.3.1 证据区块 HTML
- [ ] M3.3.2 证据面板样式
- [ ] M3.3.3 使用情况摘要区块
- [ ] M3.4.1 端到端跳转测试
- [ ] M3.4.2 高亮动画测试
- [ ] M3.4.3 使用列表点击测试

### M4: 高级可视化（可选）
- [ ] M4.1.1 热力图图层
- [ ] M4.1.2 renderBindingHeatmap()
- [ ] M4.1.3 冗余标色
- [ ] M4.2.1 Pass 分组视图
- [ ] M4.2.2 Pass 折叠
- [ ] M4.2.3 GPU 时间统计

---

## 🔄 执行建议

### 每日工作流

1. **开始前**：查看本文档，确认当天目标开发点
2. **开发时**：完成一个开发点后立即勾选 `[x]`
3. **结束时**：更新进度，记录遇到的问题
4. **验收时**：按里程碑验收标准逐项检查

### 遇阻处理

| 问题类型 | 处理方式 |
|----------|----------|
| 技术问题 | 记录到 Risks/Blockers，尝试 3 次后请求帮助 |
| 需求变更 | 回退到 /plan 阶段，更新本文档后继续 |
| 依赖阻塞 | 标记阻塞原因，先做其他独立任务 |

### Git 提交规范

每完成一个里程碑后提交：

```bash
git add .
git commit -m "feat(evidence-chain): M1 完成 - ResourceUsageIndex 构建

- 新增 UsageRecord, ResourceUsageIndex 数据类
- 实现 resource_usage_builder.py
- 集成到 report_bundle_generator
- 通过单元测试"
```

---

*文档结束 - 开发过程中请持续更新进度*
