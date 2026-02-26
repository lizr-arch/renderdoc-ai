# WebUI 交互测试矩阵（Index / Textures / Shaders / Recommendations）

> 更新日期: 2026-02-26  
> 适用范围: index.html / textures.html / shaders.html / recommendations.html（events.html 已移除）  
> 数据来源:  
> - 模板: scripts/rdc_analyzer/templates/*.html  
> - 运行时列表生成: scripts/rdc_analyzer/report_bundle_generator.py  
> - 跳转/高亮: scripts/rdc_analyzer/templates/navigation.js  
> 统计说明:  静态控件数量基线仅统计模板内固定控件，不包含数据驱动的列表项/建议项。

## 1. 分类体系
- 页面导航：顶部菜单/快速导航/统计卡片
- 搜索/筛选/排序：搜索框、筛选 chips、下拉排序
- 列表选择与定位：列表项点击、定位按钮、资源链接
- 视图/显示控制：缩放、翻转、通道、网格视图、代码模式
- 面板折叠：左右面板与属性分组折叠
- 动作/导出/复制：下载、导出、复制
- 跨页面/GUI 跳转：RdcNav.buildLink / jumpToRenderDoc
- 其他：键盘导航、占位按钮

## 2. 静态控件数量基线（模板扫描）
| 页面 | Buttons | Inputs | Selects | Links | onclick | oninput | onchange | filter_chips | addEventListener(click/change) | 备注 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| index | 0 | 0 | 0 | 10 | 5 | 0 | 0 | 0 | 0 | 不含 issues 列表按钮 |
| textures | 16 | 1 | 1 | 6 | 22 | 1 | 1 | 7 | 6/0 | 不含纹理列表项 |
| shaders | 12 | 1 | 2 | 6 | 17 | 1 | 2 | 8 | 3/0 | 不含 shader 列表项 |
| recommendations | 2 | 1 | 2 | 4 | 3 | 0 | 0 | 0 | 1/2 | 不含建议列表项 |

> 统计脚本: scripts/_tmp_ui_interaction_inventory.py（静态 HTML 解析）

## 3. 页面交互矩阵
### 3.1 Index（index.html）
| 控件/入口 | 分类 | 操作 | 目标效果 | 数据/依赖 | 来源 |
|---|---|---|---|---|---|
| 统计卡片纹理 | 页面导航 | 点击卡片 | 跳转到 textures.html | 无 | scripts/rdc_analyzer/templates/index.html:428 |
| 统计卡片Shaders | 页面导航 | 点击卡片 | 跳转到 shaders.html | 无 | scripts/rdc_analyzer/templates/index.html:438 |
| 快速导航卡片（纹理/问题纹理/Shader/Mali） | 页面导航 | 点击链接 | 跳转到对应页面/带 filter 参数 | 无 | scripts/rdc_analyzer/templates/index.html:491, scripts/rdc_analyzer/templates/index.html:499, scripts/rdc_analyzer/templates/index.html:506, scripts/rdc_analyzer/templates/index.html:513 |
| 优化建议导出（JSON/CSV） | 动作/导出 | 点击链接 | 下载 issues_export.json / issues_export.csv | 生成文件存在 | scripts/rdc_analyzer/templates/index.html:565, scripts/rdc_analyzer/templates/index.html:566 |
| Issues 列表↗ GUI按钮 | 跨 GUI 跳转 | 点击按钮 | 触发 jumpToRenderDoc(eventId) → /api/jump | 需 event_id | scripts/rdc_analyzer/report_bundle_generator.py:678, scripts/rdc_analyzer/templates/navigation.js:284 |
| 帧缩略图 | 视图/显示 | 点击缩略图 | 打开 lightbox 预览 | FRAME_THUMBNAIL | scripts/rdc_analyzer/templates/index.html:617 |
| Lightbox 关闭 | 视图/显示 | 点击遮罩或× | 关闭 lightbox | 需已打开 | scripts/rdc_analyzer/templates/index.html:652, scripts/rdc_analyzer/templates/index.html:653 |

### 3.2 Textures（textures.html）
| 控件/入口 | 分类 | 操作 | 目标效果 | 数据/依赖 | 来源 |
|---|---|---|---|---|---|
| 顶部菜单（概览/纹理/Shader/优化） | 页面导航 | 点击菜单 | 跳转页面 | 无 | scripts/rdc_analyzer/templates/textures.html:716 |
| 纹理列表项 | 列表选择 | 点击列表项 | 选中纹理、更新预览与属性 | texture 数据 | scripts/rdc_analyzer/report_bundle_generator.py:910 |
| 搜索框 | 搜索/筛选 | 输入关键字 | 过滤纹理列表 | texture 数据 | scripts/rdc_analyzer/templates/textures.html:740 |
| 排序下拉 | 搜索/排序 | 选择排序项 | 列表按 name/size/vram/format 排序 | texture 数据 | scripts/rdc_analyzer/templates/textures.html:742 |
| 筛选 chips（全部/问题/大尺寸/无 Mip） | 搜索/筛选 | 点击 chip | 切换过滤条件 | texture 数据 | scripts/rdc_analyzer/templates/textures.html:751 |
| 导出问题 JSON/CSV | 动作/导出 | 点击链接 | 下载问题列表 | issues_export 文件 | scripts/rdc_analyzer/templates/textures.html:757, scripts/rdc_analyzer/templates/textures.html:758 |
| 左/右面板折叠 | 面板折叠 | 点击面板标题 | 收起/展开对应面板 | 无 | scripts/rdc_analyzer/templates/textures.html:733, scripts/rdc_analyzer/templates/textures.html:828 |
| 属性分组折叠 | 面板折叠 | 点击分组标题 | 收起/展开分组内容 | 无 | scripts/rdc_analyzer/templates/textures.html:836, scripts/rdc_analyzer/templates/textures.html:870, scripts/rdc_analyzer/templates/textures.html:881 |
| 缩放控制（➕/➖/适应） | 视图/显示 | 点击按钮 | 更新缩放比例与显示 | 需预览图 | scripts/rdc_analyzer/templates/textures.html:782, scripts/rdc_analyzer/templates/textures.html:1475 |
| 翻转（↕） | 视图/显示 | 点击按钮 | 垂直翻转预览 | 需预览图 | scripts/rdc_analyzer/templates/textures.html:786, scripts/rdc_analyzer/templates/textures.html:1497 |
| 通道按钮（R/G/B/A） | 视图/显示 | 点击按钮 | 切换按钮状态；当前仅日志 | 预览图可选 | scripts/rdc_analyzer/templates/textures.html:790, scripts/rdc_analyzer/templates/textures.html:1460 |
| 网格视图（⊞） | 视图/显示 | 点击按钮 | 切换列表网格布局 | 无 | scripts/rdc_analyzer/templates/textures.html:798, scripts/rdc_analyzer/templates/textures.html:1526 |
| 对比模式（🔀） | 视图/显示 | 点击按钮 | 显示/隐藏对比面板 | 需预览图 | scripts/rdc_analyzer/templates/textures.html:797, scripts/rdc_analyzer/templates/textures.html:1521 |
| 对比关闭（×） | 视图/显示 | 点击关闭 | 清空对比槽位 | 有对比数据 | scripts/rdc_analyzer/templates/textures.html:927, scripts/rdc_analyzer/templates/textures.html:936 |
| 详情操作：↗ GUI | 跨 GUI 跳转 | 点击按钮 | jumpToRenderDoc('texture', id) | 需 resource id | scripts/rdc_analyzer/templates/textures.html:897, scripts/rdc_analyzer/templates/textures.html:1557 |
| 详情操作：🔀 对比 | 动作 | 点击按钮 | 将当前纹理加入对比 | 需预览图 | scripts/rdc_analyzer/templates/textures.html:900, scripts/rdc_analyzer/templates/textures.html:1531 |
| 详情操作：📍定位 | 列表定位 | 点击按钮 | 左侧列表滚动并高亮当前纹理 | 需当前纹理 | scripts/rdc_analyzer/templates/textures.html:905, scripts/rdc_analyzer/templates/textures.html:1605 |
| 资源链接（分析建议区） | 列表定位 | 点击 resource id | 选中对应纹理并滚动高亮 | 需 resource id | scripts/rdc_analyzer/templates/textures.html:1223, scripts/rdc_analyzer/templates/textures.html:1569 |
| 颜色拾取器 Hex | 动作/复制 | 点击 Hex | 复制当前 Hex 文本 | 预览图可选 | scripts/rdc_analyzer/templates/textures.html:821, scripts/rdc_analyzer/templates/textures.html:1620 |
| 导出按钮（💾） | 动作/导出 | 点击按钮 | 当前无绑定逻辑（占位） | 无 | scripts/rdc_analyzer/templates/textures.html:804 |
| Lightbox 关闭 | 视图/显示 | 点击遮罩或× | 关闭 lightbox（需已打开） | openLightbox 未绑定 | scripts/rdc_analyzer/templates/textures.html:916, scripts/rdc_analyzer/templates/textures.html:917 |

### 3.3 Shaders（shaders.html）
| 控件/入口 | 分类 | 操作 | 目标效果 | 数据/依赖 | 来源 |
|---|---|---|---|---|---|
| 顶部菜单（概览/纹理/Shader/优化） | 页面导航 | 点击菜单 | 跳转页面 | 无 | scripts/rdc_analyzer/templates/shaders.html:1189 |
| Shader 列表项 | 列表选择 | 点击列表项 | 选中 Shader、更新右侧/代码区 | shader 数据 | scripts/rdc_analyzer/report_bundle_generator.py:1239 |
| 搜索框 | 搜索/筛选 | 输入关键字 | 过滤 Shader 列表 | shader 数据 | scripts/rdc_analyzer/templates/shaders.html:1213 |
| 排序下拉 | 搜索/排序 | 选择排序项 | 列表按 name/cycles/usage 排序 | shader 数据 | scripts/rdc_analyzer/templates/shaders.html:1215 |
| 筛选 chips（all/VS/FS/CS/issues） | 搜索/筛选 | 点击 chip | 切换类型/问题过滤 | shader 数据 | scripts/rdc_analyzer/templates/shaders.html:1223 |
| 导出问题 JSON/CSV | 动作/导出 | 点击链接 | 下载问题列表 | issues_export 文件 | scripts/rdc_analyzer/templates/shaders.html:1230, scripts/rdc_analyzer/templates/shaders.html:1231 |
| 左/右面板折叠 | 面板折叠 | 点击面板标题 | 收起/展开对应面板 | 无 | scripts/rdc_analyzer/templates/shaders.html:1206, scripts/rdc_analyzer/templates/shaders.html:1317 |
| 属性分组折叠 | 面板折叠 | 点击分组标题 | 收起/展开分组内容 | 无 | scripts/rdc_analyzer/templates/shaders.html:1346, scripts/rdc_analyzer/templates/shaders.html:1372 |
| Mali 面板折叠 | 面板折叠 | 点击 Mali 标题 | 展开/收起 Mali 内容 | Mali 数据可选 | scripts/rdc_analyzer/templates/shaders.html:1329 |
| HLSL 按钮 | 视图/显示 | 点击按钮 | 显示 HLSL 代码 | 需 HLSL 数据 | scripts/rdc_analyzer/templates/shaders.html:1261, scripts/rdc_analyzer/templates/shaders.html:2434 |
| AI Shader 优化 | 视图/显示 | 点击按钮 | 切换 AI 优化模式（UI 变化） | 需 Shader 选中 | scripts/rdc_analyzer/templates/shaders.html:1262, scripts/rdc_analyzer/templates/shaders.html:2439 |
| GPU 选择器 | 视图/显示 | 选择 GPU | 切换 Mali 目标 GPU | Mali 数据可选 | scripts/rdc_analyzer/templates/shaders.html:1267, scripts/rdc_analyzer/templates/shaders.html:1632 |
| 复制代码（📋） | 动作/复制 | 点击按钮 | 复制当前 HLSL 到剪贴板 | 需 HLSL | scripts/rdc_analyzer/templates/shaders.html:1299, scripts/rdc_analyzer/templates/shaders.html:2394 |
| 导出 Shader（详情按钮） | 动作/导出 | 点击按钮 | 导出 .hlsl 文件 | 需 HLSL | scripts/rdc_analyzer/templates/shaders.html:1413, scripts/rdc_analyzer/templates/shaders.html:2380 |
| ↗ GUI | 跨 GUI 跳转 | 点击按钮 | jumpToRenderDoc('shader', id) | 需 shader id | scripts/rdc_analyzer/templates/shaders.html:1410, scripts/rdc_analyzer/templates/shaders.html:2368, scripts/rdc_analyzer/templates/navigation.js:284 |
| 分页（上一页/下一页） | 列表导航 | 点击按钮 | 切换 Shader 列表页 | 列表需分页 | scripts/rdc_analyzer/templates/shaders.html:1760 |
| 自动换行/搜索/导出（工具栏） | 其他 | 点击按钮 | 当前无绑定逻辑（占位） | 无 | scripts/rdc_analyzer/templates/shaders.html:1294, scripts/rdc_analyzer/templates/shaders.html:1295, scripts/rdc_analyzer/templates/shaders.html:1300 |

### 3.4 Recommendations（recommendations.html）
| 控件/入口 | 分类 | 操作 | 目标效果 | 数据/依赖 | 来源 |
|---|---|---|---|---|---|
| 顶部菜单（概览/纹理/着色器/优化建议） | 页面导航 | 点击菜单 | 跳转页面 | 无 | scripts/rdc_analyzer/templates/recommendations.html:494 |
| 严重度下拉 | 搜索/筛选 | 选择严重度 | 过滤建议列表 | 建议数据 | scripts/rdc_analyzer/templates/recommendations.html:533, scripts/rdc_analyzer/templates/recommendations.html:830 |
| 分类下拉 | 搜索/筛选 | 选择分类 | 过滤建议列表 | 建议数据 | scripts/rdc_analyzer/templates/recommendations.html:539, scripts/rdc_analyzer/templates/recommendations.html:831 |
| 搜索框 | 搜索/筛选 | 输入关键字 | 过滤建议列表 | 建议数据 | scripts/rdc_analyzer/templates/recommendations.html:543, scripts/rdc_analyzer/templates/recommendations.html:832 |
| 建议列表项 | 列表选择 | 点击列表项 | 右侧详情更新 | 建议数据 | scripts/rdc_analyzer/templates/recommendations.html:836 |
| 快速跳转按钮 | 跨页面跳转 | 点击按钮 | 跳转到 textures/shaders 并定位 | 证据链 actions | scripts/rdc_analyzer/templates/recommendations.html:720 |
| 高亮按钮 | 视图/显示 | 点击按钮 | 高亮目标资源 | 目标元素存在 | scripts/rdc_analyzer/templates/recommendations.html:725, scripts/rdc_analyzer/templates/recommendations.html:800 |
| 受影响资源标签 | 跨页面跳转 | 点击标签 | 跳转到对应页面并定位 | 资源 id 可识别 | scripts/rdc_analyzer/templates/recommendations.html:748 |
| 键盘导航（↑/↓/j/k） | 其他 | 键盘操作 | 切换选中项并滚动 | 列表非空 | scripts/rdc_analyzer/templates/recommendations.html:843 |

## 4. 测试步骤（按页面）
### Index
前置：存在 FRAME_THUMBNAIL；issues 列表中至少一条含 event_id。  
- 点击纹理统计卡片 → 跳转到 textures.html。  
- 点击Shaders统计卡片 → 跳转到 shaders.html。  
- 点击问题纹理快速导航 → 进入 textures.html?filter=issues（筛选状态更新）。  
- 点击导出 JSON/CSV → 下载文件成功。  
- 点击 issues 列表的↗ GUI → RenderDoc GUI 发生跳转（依赖 /api/jump 服务）。  
- 点击帧缩略图 → lightbox 弹出；点击遮罩或× → lightbox 关闭。  

### Textures
前置：纹理列表 ≥ 3；至少 1 个带 thumbnail；至少 1 个带 issues。  
- 搜索框输入关键词 → 列表即时过滤。  
- 排序下拉切换到 VRAM/尺寸 → 列表顺序变化，摘要提示更新。  
- 点击筛选 chips（问题/大尺寸/无 Mip）→ 列表过滤、生效提示更新。  
- 点击任意纹理列表项 → 预览与属性面板刷新，当前项高亮。  
- 点击↗ GUI → RenderDoc GUI 跳转到对应纹理（依赖 /api/jump）。  
- 点击🔀 对比 → 对比面板显示并填充槽位；点击槽位 × 清空。  
- 点击📍 在列表中定位 → 列表滚动到当前纹理并高亮。  
- 缩放按钮（➕/➖/适应）→ 预览缩放比例变化；翻转按钮（↕）生效。  
- 通道按钮（R/G/B/A）→ 按钮激活态切换（当前仅日志，无实际图像变化）。  
- 网格视图（⊞）→ 列表布局切换。  
- Hex 文本点击 → 复制当前 Hex 文本。  

### Shaders
前置：Shader 列表 ≥ 3；至少 1 个具备 HLSL；可选 Mali 数据。  
- 搜索框/筛选/排序操作 → 列表过滤与排序更新。  
- 点击 Shader 列表项 → 右侧属性与代码区更新。  
- 点击HLSL 代码 → 展示代码（无数据时显示空态）。  
- 点击AI Shader 优化 → UI 进入/退出 AI 模式。  
- 选择 GPU → Mali 目标 GPU 更新（有数据时刷新统计）。  
- 点击📋 复制代码 → 剪贴板写入 HLSL。  
- 点击导出详情按钮 → 下载 .hlsl 文件。  
- 点击↗ GUI → RenderDoc GUI 跳转到对应 Shader（依赖 /api/jump）。  
- 分页按钮（上一页/下一页）→ 切换页。  

### Recommendations
前置：建议列表非空；部分建议含 evidence_chain/actions/affected_resources。  
- 严重度/分类/搜索过滤 → 列表即时过滤。  
- 点击建议列表项 → 右侧详情更新。  
- 详情中的快速跳转按钮 → 跳转到 textures/shaders 并定位。  
- 详情中的高亮按钮 → 当前页面目标资源高亮。  
- 点击受影响资源标签 → 跳转到对应页面并定位。  
- 使用 ↑/↓ 或 j/k → 切换选中项并滚动。  

## 5. 已知占位/限制（测试时需标注）
- Textures: toolbar 的💾 导出按钮无绑定逻辑。  
- Textures: Lightbox 打开函数存在，但未绑定点击入口。  
- Textures: 通道过滤仅日志输出（未对图像生效）。  
- Textures: 颜色拾取器只显示/复制当前文本，未接入采样。  
- Shaders: toolbar 的↩️ 自动换行 / 🔍 搜索 / 💾 导出无绑定逻辑。  
- GUI 跳转依赖 /api/jump，需 RenderDoc GUI 侧服务运行；失败仅控制台告警。  
