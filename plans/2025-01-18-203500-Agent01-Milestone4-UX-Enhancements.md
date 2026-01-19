# Milestone 4: UX 交互增强与高级功能

> **创建时间**: 2025-01-18 20:35:00
> **Agent ID**: Agent01
> **状态**: 📋 Planning → 🚧 In Progress

---

## Scope / 范围

基于用户反馈，修复 Bug 并添加以下 UX 增强功能：
1. 修复中间预览面板缩略图不显示的问题
2. 右侧面板纹理可点击选中并联动
3. 中间面板添加"定位"按钮
4. Event ID 点击跳转
5. 真实纹理缩略图提取
6. VRAM 可视化图表
7. 纹理对比视图
8. 导出优化清单

---

## Assumptions / 假设

1. 演示报告使用 SVG 占位符缩略图即可满足开发测试需求
2. 真实缩略图提取需要 RenderDoc Python API（`renderdoc` 模块），可能需要编译支持
3. VRAM 图表使用纯 CSS/JS 实现（不引入 Chart.js 等外部依赖）
4. 当前报告已有 Draw Call 事件结构（`used_in_events` 字段）

---

## Task Checklist / 任务清单

### Phase 1: Bug 修复 (High Priority)

- [ ] **Task 1.1**: 为演示数据生成 SVG 占位符缩略图
  - 文件: `generate_145_demo_report.py`
  - 行号: ~91
  - 修改: 添加 `generate_placeholder_thumbnail()` 函数，生成 Base64 SVG

- [ ] **Task 1.2**: UI 回退 - 无缩略图时显示彩色占位符
  - 文件: `generate_offline_report.py`
  - 行号: ~3089-3100 (`selectTexture` 函数内)
  - 修改: 当 `!tex.thumbnail` 时，生成动态 SVG 并显示

### Phase 2: 交互联动 (High Priority)

- [ ] **Task 2.1**: 右侧纹理点击事件
  - 文件: `generate_offline_report.py`
  - 位置: `renderDuplicateAnalysis()` 和 `renderUnusedAnalysis()` 函数
  - 修改: 为纹理项添加 `onclick="selectTextureByResourceId('${tex.resource_id}')"`

- [ ] **Task 2.2**: 添加 `selectTextureByResourceId()` 函数
  - 文件: `generate_offline_report.py`
  - 位置: JavaScript 部分
  - 功能: 根据 resource_id 找到纹理索引，调用 `selectTexture(index)`

- [ ] **Task 2.3**: 左侧列表自动滚动定位
  - 文件: `generate_offline_report.py`
  - 位置: `selectTexture()` 函数内
  - 修改: 调用 `virtualScroller.scrollToIndex(index)`

- [ ] **Task 2.4**: 中间面板"定位"按钮
  - 文件: `generate_offline_report.py`
  - 位置: 中间面板 HTML 结构
  - 修改: 添加按钮 `<button onclick="scrollToCurrentTexture()">🔍 在列表中定位</button>`

### Phase 3: Event ID 跳转 (Medium Priority)

- [ ] **Task 3.1**: EID 标签点击事件
  - 文件: `generate_offline_report.py`
  - 位置: `updateTextureAnalysis()` 中生成 EID 标签的部分
  - 修改: 添加 `onclick="jumpToEvent(${eid})"`

- [ ] **Task 3.2**: 添加 `jumpToEvent()` 函数
  - 功能: 如果存在 Draw Call 视图/Tab，跳转并高亮；否则显示提示

### Phase 4: 真实缩略图提取 (High Priority - 独立模块)

- [ ] **Task 4.1**: 调研 RenderDoc Python API 缩略图提取方法
  - 参考: `qrenderdoc/Code/pyrenderdoc/renderdoc.i`
  - 核心类: `ReplayController.GetTextureData()`

- [ ] **Task 4.2**: 创建 `extract_thumbnails.py` 脚本
  - 输入: RDC 文件路径
  - 输出: 包含 Base64 缩略图的 JSON
  - 依赖: `renderdoc` Python 模块（需要 RenderDoc 构建支持）

- [ ] **Task 4.3**: 集成到报告生成流程
  - 修改 `generate_offline_report.py` 的 thumbnail 加载逻辑

### Phase 5: VRAM 可视化 (Medium Priority)

- [ ] **Task 5.1**: 添加 VRAM 统计计算
  - 按格式分类统计
  - 按尺寸分类统计
  - 按类型（Diffuse/Normal/UI 等）分类统计

- [ ] **Task 5.2**: 实现纯 CSS 饼图组件
  - 使用 `conic-gradient` 实现
  - 支持 hover 显示详情

- [ ] **Task 5.3**: 实现纯 CSS 柱状图组件
  - 使用 flexbox + 动态高度
  - 显示格式/尺寸分布

### Phase 6: 纹理对比视图 (Medium Priority)

- [ ] **Task 6.1**: 添加"对比"按钮和选择机制
  - 复选框或 Ctrl+Click 多选
  - 选中两个后启用"对比"按钮

- [ ] **Task 6.2**: 实现并排对比弹窗
  - 两个图片区域
  - 同步缩放/平移

- [ ] **Task 6.3**: 差异高亮（可选）
  - 像素级对比
  - 差异区域标红

### Phase 7: 导出优化清单 (Low Priority)

- [ ] **Task 7.1**: 添加"导出"按钮
  - 位置: 工具栏或右下角

- [ ] **Task 7.2**: 实现导出逻辑
  - JSON 格式: `{ duplicates: [...], unused: [...], suggestions: [...] }`
  - CSV 格式: 表格形式

- [ ] **Task 7.3**: 触发浏览器下载
  - 使用 Blob + URL.createObjectURL

---

## Risks / Blockers / 风险与阻塞

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| RenderDoc Python API 未编译 | 无法提取真实缩略图 | 优先使用占位符，真实缩略图作为可选功能 |
| 大量纹理时图表性能 | UI 卡顿 | 限制图表显示的分类数量（Top 10） |
| 跨浏览器兼容性 | CSS 图表不兼容 | 使用标准 CSS，测试 Chrome/Firefox/Edge |

---

## Verification / Acceptance / 验收标准

### Phase 1
- [x] 演示报告中间面板显示彩色占位符缩略图
- [ ] 真实 RDC 报告（如有）显示实际或占位缩略图

### Phase 2
- [ ] 点击右侧重复组/未使用纹理中的任意项，中间面板显示预览
- [ ] 左侧列表自动滚动到对应位置并高亮
- [ ] 中间面板"定位"按钮正常工作

### Phase 3
- [ ] 点击 EID 标签有视觉反馈（至少 console.log 或 toast）

### Phase 4-7
- [ ] 独立验证（根据实现进度）

---

## Next Steps / 下一步

1. **立即执行**: Phase 1 (Bug 修复) + Phase 2 (交互联动) - 预计 15-20 分钟
2. **后续**: Phase 3-7 按优先级逐步实现

---

## Decisions / 决策记录

| 日期 | 决策 | 原因 |
|------|------|------|
| 2025-01-18 | 使用 SVG 占位符而非 Canvas | SVG 更轻量，Base64 编码后尺寸小 |
| 2025-01-18 | 右侧点击直接复用 selectTexture | 统一交互模式，减少代码重复 |
| 2025-01-18 | 图表使用纯 CSS | 避免引入外部依赖，保持单文件报告 |

---

**等待用户确认后进入 `/do` 阶段**
