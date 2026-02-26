# WebUI 交互测试矩阵（Index / Textures / Shaders / Recommendations）

> 更新日期: 2026-02-26  
> 适用范围: index.html / textures.html / shaders.html / recommendations.html（events.html 已移除）  
> 数据来源:  
> - 模板: scripts/rdc_analyzer/templates/*.html  
> - 运行时列表生成: scripts/rdc_analyzer/report_bundle_generator.py  
> - 跳转/高亮: scripts/rdc_analyzer/templates/navigation.js  
> 统计说明: 静态控件数量基线仅统计模板内固定控件，不包含数据驱动的列表项/建议项。

## 1. 分类体系
- 页面导航：顶部菜单/快速导航/统计卡片
- 搜索/筛选/排序：搜索框、筛选 chips、下拉排序
- 列表选择与定位：列表项点击、定位按钮、资源链接
- 视图/显示控制：缩放、翻转、代码模式
- 面板折叠：左右面板与属性分组折叠
- 动作/导出/复制：下载、导出、复制
- 跨页面/GUI 跳转：RdcNav.buildLink / jumpToRenderDoc
- 其他：键盘导航

## 2. 静态控件数量基线（模板扫描）
| 页面 | Buttons | Inputs | Selects | Links | onclick | oninput | onchange | filter_chips | addEventListener(click/change) | 备注 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| index | 0 | 0 | 0 | 8 | 3 | 0 | 0 | 0 | 0 | 已移除 issues 卡片 |
| textures | 6 | 1 | 1 | 6 | 12 | 1 | 1 | 7 | 4/0 | 不含纹理列表项 |
| shaders | 8 | 1 | 2 | 6 | 17 | 1 | 2 | 8 | 2/0 | 不含 shader 列表项 |
| recommendations | 2 | 1 | 2 | 4 | 3 | 0 | 0 | 0 | 1/2 | 不含建议列表项 |

> 统计脚本: scripts/_tmp_ui_interaction_inventory.py（静态 HTML 解析）

## 3. 页面交互矩阵
### 3.1 Index（index.html）
| 控件/入口 | 分类 | 操作 | 目标效果 | 数据/依赖 | 来源 |
|---|---|---|---|---|---|
| 快速导航卡片（纹理/问题纹理/Shader/Mali） | 页面导航 | 点击链接 | 跳转到对应页面/带 filter 参数 | 无 | scripts/rdc_analyzer/templates/index.html:492, scripts/rdc_analyzer/templates/index.html:499, scripts/rdc_analyzer/templates/index.html:506, scripts/rdc_analyzer/templates/index.html:513 |
| 帧缩略图 | 视图/显示 | 点击缩略图 | 打开 lightbox 预览 | FRAME_THUMBNAIL | scripts/rdc_analyzer/templates/index.html:590 |
| Lightbox 关闭 | 视图/显示 | 点击遮罩或× | 关闭 lightbox | 需已打开 | scripts/rdc_analyzer/templates/index.html:625, scripts/rdc_analyzer/templates/index.html:626 |

### 3.2 Textures（textures.html）
| 控件/入口 | 分类 | 操作 | 目标效果 | 数据/依赖 | 来源 |
|---|---|---|---|---|---|
| 顶部菜单（概览/纹理/Shader/优化） | 页面导航 | 点击菜单 | 跳转页面 | 无 | scripts/rdc_analyzer/templates/textures.html:716 |
| 纹理列表项 | 列表选择 | 点击列表项 | 选中纹理、更新预览与属性 | texture 数据 | scripts/rdc_analyzer/report_bundle_generator.py:910 |
| 搜索框 | 搜索/筛选 | 输入关键字 | 过滤纹理列表 | texture 数据 | scripts/rdc_analyzer/templates/textures.html:740 |
| 排序下拉 | 搜索/排序 | 选择排序项 | 列表按 name/size/vram/format 排序 | texture 数据 | scripts/rdc_analyzer/templates/textures.html:742 |
| 筛选 chips（全部/问题/大尺寸/无 Mip） | 搜索/筛选 | 点击 chip | 切换过滤条件 | texture 数据 | scripts/rdc_analyzer/templates/textures.html:751 |
| 导出问题 JSON/CSV | 动作/导出 | 点击链接 | 下载问题列表 | issues_export 文件 | scripts/rdc_analyzer/templates/textures.html:757, scripts/rdc_analyzer/templates/textures.html:758 |
| 左/右面板折叠 | 面板折叠 | 点击面板标题 | 收起/展开对应面板 | 无 | scripts/rdc_analyzer/templates/textures.html:733, scripts/rdc_analyzer/templates/textures.html:804 |
| 属性分组折叠 | 面板折叠 | 点击分组标题 | 收起/展开分组内容 | 无 | scripts/rdc_analyzer/templates/textures.html:812, scripts/rdc_analyzer/templates/textures.html:846, scripts/rdc_analyzer/templates/textures.html:857 |
| 缩放控制（➕/➖/适应） | 视图/显示 | 点击按钮 | 更新缩放比例与显示 | 需预览图 | scripts/rdc_analyzer/templates/textures.html:782 |
| 翻转（↕） | 视图/显示 | 点击按钮 | 垂直翻转预览 | 需预览图 | scripts/rdc_analyzer/templates/textures.html:786 |
| 详情操作：↗ GUI | 跨 GUI 跳转 | 点击按钮 | jumpToRenderDoc('texture', id) | 需 resource id | scripts/rdc_analyzer/templates/textures.html:873 |
| 详情操作：📍定位 | 列表定位 | 点击按钮 | 左侧列表滚动并高亮当前纹理 | 需当前纹理 | scripts/rdc_analyzer/templates/textures.html:878 |
| 资源链接（分析建议区） | 列表定位 | 点击 resource id | 选中对应纹理并滚动高亮 | 需 resource id | scripts/rdc_analyzer/templates/textures.html:1163 |

### 3.3 Shaders（shaders.html）
| 控件/入口 | 分类 | 操作 | 目标效果 | 数据/依赖 | 来源 |
|---|---|---|---|---|---|
| 顶部菜单（概览/纹理/Shader/优化） | 页面导航 | 点击菜单 | 跳转页面 | 无 | scripts/rdc_analyzer/templates/shaders.html:1189 |
| Shader 列表项 | 列表选择 | 点击列表项 | 选中 Shader、更新右侧/代码区 | shader 数据 | scripts/rdc_analyzer/report_bundle_generator.py:1239 |
| 搜索框 | 搜索/筛选 | 输入关键字 | 过滤 Shader 列表 | shader 数据 | scripts/rdc_analyzer/templates/shaders.html:1213 |
| 排序下拉 | 搜索/排序 | 选择排序项 | 列表按 name/cycles/usage 排序 | shader 数据 | scripts/rdc_analyzer/templates/shaders.html:1215 |
| 筛选 chips（all/VS/FS/CS/issues） | 搜索/筛选 | 点击 chip | 切换类型/问题过滤 | shader 数据 | scripts/rdc_analyzer/templates/shaders.html:1223 |
| 导出问题 JSON/CSV | 动作/导出 | 点击链接 | 下载问题列表 | issues_export 文件 | scripts/rdc_analyzer/templates/shaders.html:1230, scripts/rdc_analyzer/templates/shaders.html:1231 |
| 左/右面板折叠 | 面板折叠 | 点击面板标题 | 收起/展开对应面板 | 无 | scripts/rdc_analyzer/templates/shaders.html:1206, scripts/rdc_analyzer/templates/shaders.html:1310 |
| 属性分组折叠 | 面板折叠 | 点击分组标题 | 收起/展开分组内容 | 无 | scripts/rdc_analyzer/templates/shaders.html:1339, scripts/rdc_analyzer/templates/shaders.html:1365 |
| Mali 面板折叠 | 面板折叠 | 点击 Mali 标题 | 展开/收起 Mali 内容 | Mali 数据可选 | scripts/rdc_analyzer/templates/shaders.html:1322 |
| HLSL 按钮 | 视图/显示 | 点击按钮 | 显示 HLSL 代码 | 需 HLSL 数据 | scripts/rdc_analyzer/templates/shaders.html:1261 |
| GPU 选择器 | 视图/显示 | 选择 GPU | 切换 Mali 目标 GPU | Mali 数据可选 | scripts/rdc_analyzer/templates/shaders.html:1266 |
| 复制代码（📋） | 动作/复制 | 点击按钮 | 复制当前 HLSL 到剪贴板 | 需 HLSL | scripts/rdc_analyzer/templates/shaders.html:1293 |
| 导出 Shader（详情按钮） | 动作/导出 | 点击按钮 | 导出 .hlsl 文件 | 需 HLSL | scripts/rdc_analyzer/templates/shaders.html:1406 |
| ↗ GUI | 跨 GUI 跳转 | 点击按钮 | jumpToRenderDoc('shader', id) | 需 shader id | scripts/rdc_analyzer/templates/shaders.html:1403, scripts/rdc_analyzer/templates/navigation.js:284 |
| 分页（上一页/下一页） | 列表导航 | 点击按钮 | 切换 Shader 列表页 | 列表需分页 | scripts/rdc_analyzer/templates/shaders.html:1753 |

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
前置：存在 FRAME_THUMBNAIL。  
- 点击问题纹理快速导航 → 进入 textures.html?filter=issues（筛选状态更新）。  
- 点击帧缩略图 → lightbox 弹出；点击遮罩或× → lightbox 关闭。  

### Textures
前置：纹理列表 ≥ 3；至少 1 个带 thumbnail；至少 1 个带 issues。  
- 搜索框输入关键词 → 列表即时过滤。  
- 排序下拉切换到 VRAM/尺寸 → 列表顺序变化，摘要提示更新。  
- 点击筛选 chips（问题/大尺寸/无 Mip）→ 列表过滤、生效提示更新。  
- 点击任意纹理列表项 → 预览与属性面板刷新，当前项高亮。  
- 点击↗ GUI → RenderDoc GUI 跳转到对应纹理（依赖 /api/jump）。  
- 点击📍 在列表中定位 → 列表滚动到当前纹理并高亮。  
- 缩放按钮（➕/➖/适应）→ 预览缩放比例变化；翻转按钮（↕）生效。  

### Shaders
前置：Shader 列表 ≥ 3；至少 1 个具备 HLSL；可选 Mali 数据。  
- 搜索框/筛选/排序操作 → 列表过滤与排序更新。  
- 点击 Shader 列表项 → 右侧属性与代码区更新。  
- 点击HLSL 代码 → 展示代码（无数据时显示空态）。  
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
- GUI 跳转依赖 /api/jump，需 RenderDoc GUI 侧服务运行；失败仅控制台告警。  
