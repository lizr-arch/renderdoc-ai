# UI 功能使用指南 (v2.6.2)

> **版本**: 2.6.2 | **更新日期**: 2025-02-06
> 
> **适用范围**: Bundle 报告的 events.html 页面高级功能

本文档介绍 RDC Analyzer 报告中的高级可视化功能，包括资源绑定热力图、Pass 分组视图和外部数据加载优化。

---

## 目录

1. [M4.1 资源绑定热力图](#m41-资源绑定热力图)
2. [M4.2 Pass 分组视图](#m42-pass-分组视图)
3. [Phase 7C 外部数据加载](#phase-7c-外部数据加载)
4. [功能截图参考](#功能截图参考)

---

## M4.1 资源绑定热力图

### 功能概述

热力图功能可视化资源（纹理、Buffer）在整个帧中的使用模式，帮助识别：
- **首次使用 (FIRST_USE)** - 蓝色：资源首次被绑定
- **连续使用 (CONTINUOUS)** - 绿色：资源在连续 Draw Call 中被复用
- **稀疏使用 (SPARSE)** - 黄色：资源间隔使用，可能导致缓存失效
- **孤立使用 (ISOLATED)** - 红色：资源仅使用一次，可能是问题指标

### 使用方法

1. **打开热力图面板**
   - 点击事件列表顶部的 **"🔥 绑定热力图"** 按钮
   - 热力图控制面板将展开

2. **选择资源**
   - 使用下拉菜单选择要分析的资源（纹理或 Buffer）
   - 热力图将在事件列表上方显示颜色条

3. **解读颜色**
   | 颜色 | 模式 | 含义 | 优化建议 |
   |------|------|------|----------|
   | 🔵 蓝色 | FIRST_USE | 资源首次绑定 | 正常 |
   | 🟢 绿色 | CONTINUOUS | 连续复用 | 最优，利用缓存 |
   | 🟡 黄色 | SPARSE | 间隔使用 | 考虑重排 Draw Call |
   | 🔴 红色 | ISOLATED | 仅使用一次 | 检查是否冗余绑定 |

### 技术实现

热力图由 `core/heatmap_builder.py` 模块生成，分析逻辑：

```python
# 使用模式判定逻辑
if first_occurrence:
    pattern = "FIRST_USE"
elif gap <= 1:
    pattern = "CONTINUOUS"
elif gap <= 5:
    pattern = "SPARSE"
else:
    pattern = "ISOLATED"
```

---

## M4.2 Pass 分组视图

### 功能概述

Pass 分组视图将扁平的事件列表转换为层级结构，基于 GPU 调试标记（Debug Markers）：
- `vkCmdDebugMarkerBeginEXT` / `vkCmdBeginDebugUtilsLabelEXT` - 开始新的 Pass
- `vkCmdDebugMarkerEndEXT` / `vkCmdEndDebugUtilsLabelEXT` - 结束当前 Pass

### 使用方法

1. **切换到 Pass 分组模式**
   - 点击事件列表底部的 **"📁 Pass 分组"** 按钮
   - 按钮文字变为 **"📋 扁平列表"**，表示当前为分组模式

2. **展开/折叠 Pass**
   - 点击 Pass 标题行可展开或折叠该组
   - Pass 标题显示组内 Draw Call 数量和总耗时

3. **切换回扁平列表**
   - 再次点击按钮返回原始扁平视图

### Pass 分组示例

```
📁 Shadow Pass (12 draws, 2.5ms)
├── #35 vkCmdDrawIndexed (258 indices)
├── #36 vkCmdDrawIndexed (258 indices)
└── ...

📁 GBuffer Pass (45 draws, 8.2ms)
├── #47 vkCmdDrawIndexed (1056 indices)
├── #48 vkCmdDrawIndexed (198 indices)
└── ...

📁 Lighting Pass (3 draws, 1.1ms)
└── ...
```

### 技术实现

分组使用栈结构处理嵌套标记：

```javascript
// templates/events.html - buildPassGroups()
function buildPassGroups(events) {
    const root = [];
    const stack = [{ children: root }];
    
    for (const event of events) {
        if (event.name.includes('DebugMarkerBegin') || 
            event.name.includes('BeginDebugUtilsLabel')) {
            // 推入新组
            const newGroup = { type: 'pass', name: event.markerName, children: [] };
            stack[stack.length - 1].children.push(newGroup);
            stack.push(newGroup);
        } else if (event.name.includes('DebugMarkerEnd') || 
                   event.name.includes('EndDebugUtilsLabel')) {
            // 弹出当前组
            if (stack.length > 1) stack.pop();
        } else {
            // 添加到当前组
            stack[stack.length - 1].children.push(event);
        }
    }
    return root;
}
```

---

## Phase 7C 外部数据加载

### 功能概述

外部数据加载优化将 JSON 数据从 HTML 中分离，显著减少初始页面大小：
- **HTML 大小减少**: 最高可达 **84%**
- **加载方式**: 异步按需加载
- **兼容性**: 完全向后兼容内嵌数据模式

### 使用方法

**生成报告时启用**：

```bash
# 使用 --external-data 标志
py -3 report_bundle_generator.py input.json -o output/ --external-data
```

**生成的文件结构**：

```
output/
├── index.html          # 仪表盘
├── events.html         # 事件页面 (精简版，无内嵌数据)
├── textures.html       # 纹理页面
├── shaders.html        # Shader 页面
├── events_data.json    # 事件数据 (外部文件)
├── textures_data.json  # 纹理数据 (外部文件)
├── shaders_data.json   # Shader 数据 (外部文件)
└── heatmap_data.json   # 热力图数据 (外部文件)
```

### 技术细节

**数据加载逻辑** (`templates/events.html`):

```javascript
// 检测外部数据模式
async function initializeData() {
    if (window.EVENTS_DATA) {
        // 内嵌模式 - 直接使用
        processEvents(window.EVENTS_DATA);
    } else {
        // 外部模式 - 异步加载
        try {
            const response = await fetch('./events_data.json');
            const data = await response.json();
            processEvents(data);
        } catch (error) {
            showError('无法加载事件数据');
        }
    }
}
```

### 性能对比

| 报告规模 | 内嵌模式 | 外部数据模式 | 减少比例 |
|----------|----------|--------------|----------|
| 小型 (100 事件) | 1.2 MB | 0.3 MB | 75% |
| 中型 (500 事件) | 5.8 MB | 1.1 MB | 81% |
| 大型 (2000 事件) | 24 MB | 3.8 MB | **84%** |

---

## 功能截图参考

### 热力图与 Pass 分组按钮位置

![M4 功能按钮](../../screenshots/m4_heatmap_pass_buttons.png)

**按钮说明**：
1. **🔥 绑定热力图** - 位于事件列表顶部，展开热力图控制面板
2. **📁 Pass 分组** - 位于事件列表底部，切换分组/扁平视图

---

## 相关文档

- [证据链跨页跳转](./EVIDENCE_CHAIN.md) - M1-M3 跨页面关联
- [E2E 工作流指南](./E2E_WORKFLOW_GUIDE.md) - 端到端分析流程
- [API 参考](./API_REFERENCE.md) - Python API 详细文档

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 2.6.2 | 2025-02-06 | 新增 M4.1/M4.2/7C 功能文档 |
| 2.6.1 | 2025-02-05 | Phase 7C 外部数据优化 |
| 2.5.0 | 2025-02-04 | M4 热力图/Pass 分组实现 |
