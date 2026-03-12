# 跨页面证据链 (Evidence Chain)

> **版本**: 2.4.0 | **状态**: ✅ 已实现 | **日期**: 2025-02-05

## WHAT

实现 HTML 报告中 Texture、Event、Shader 三个页面之间的双向跨页跳转，形成完整的证据链闭环。

## WHY

在分析 RDC 报告时，用户需要快速关联：
- 某个纹理是在哪个 Draw Call 中被使用的？
- 某个 Draw Call 使用了哪些 Shader？
- 某个 Shader 被哪些 Draw Call 引用？

传统方式需要手动在多个页面间切换和搜索，效率低下。

## HOW

### 里程碑实现

| 里程碑 | 方向 | 描述 | 状态 |
|--------|------|------|------|
| **M1** | Texture → Event | 纹理卡片点击跳转到 Events 页面对应 Draw Call | ✅ |
| **M2** | Event → Shader | Events 页面跳转到 Shaders 页面对应 Shader | ✅ |
| **M3** | Shader → Event/Texture | Shader 详情跳转回关联的 Event 或 Texture | ✅ |

### 技术实现

#### URL 参数传递

```
textures.html?id=468&highlight=true
events.html?eventId=35&highlight=true
shaders.html?shaderId=vk_shader_001&highlight=true
```

#### 自动滚动定位

```javascript
function scrollToElement(id, highlight = true) {
    const element = document.getElementById(id);
    if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        if (highlight) {
            element.classList.add('evidence-highlight');
            setTimeout(() => element.classList.remove('evidence-highlight'), 3000);
        }
    }
}
```

#### CSS 脉冲高亮

```css
.evidence-highlight {
    animation: pulse-highlight 0.5s ease-in-out 3;
}

@keyframes pulse-highlight {
    0%, 100% { background-color: transparent; }
    50% { background-color: rgba(255, 215, 0, 0.3); }
}
```

### 数据关联

#### Texture → Event 关联

```python
# 从 XML 解析 texture 使用信息
texture_bindings = {
    "texture_id": 468,
    "used_in_events": [35, 42, 78],  # Draw Call IDs
    "binding_slot": "t0",
    "usage": "SRV"  # Shader Resource View
}
```

#### Event → Shader 关联

```python
# 从 Pipeline State 提取 shader 绑定
event_shaders = {
    "event_id": 35,
    "vertex_shader": "vs_main_001",
    "fragment_shader": "fs_pbr_lighting",
    "compute_shader": None
}
```

### 使用示例

1. **从 Textures 页面开始**
   - 点击纹理缩略图
   - 自动跳转到 `events.html?textureId=468`
   - Events 页面高亮显示使用该纹理的所有 Draw Call

2. **从 Events 页面继续**
   - 点击 Draw Call 的 Shader 链接
   - 跳转到 `shaders.html?shaderId=vs_main_001`
   - Shader 详情页显示并高亮

3. **返回关联**
   - Shader 页面显示"Used by Events: #35, #42"
   - 点击事件 ID 返回 Events 页面

## 文件变更

| 文件 | 变更 |
|------|------|
| `bundle/pages/textures.html` | 添加点击跳转逻辑 |
| `bundle/pages/events.html` | 添加 URL 参数解析和高亮 |
| `bundle/pages/shaders.html` | 添加双向跳转链接 |
| `bundle/assets/js/evidence-chain.js` | 通用跳转/高亮逻辑 |
| `bundle/assets/css/evidence-chain.css` | 高亮动画样式 |

## 验证

```bash
# 生成报告
py -3 scripts/rdc_analyzer/rdc_to_bundle_report.py input.rdc -o output/

# 打开报告验证跳转
start output/textures.html
# 点击任意纹理 → 应跳转到 events.html 并高亮
```

## 关联文档

- [EXPORT_ROUTES.md](EXPORT_ROUTES.md) - Bundle 报告生成流程
- [ARCHITECTURE_V1.md](ARCHITECTURE_V1.md) - 整体架构
