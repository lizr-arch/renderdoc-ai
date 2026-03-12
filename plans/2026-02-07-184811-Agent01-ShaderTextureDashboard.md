# /plan - Textures + Shaders 仪表盘化改造（全量搜索/筛选/排序）

> 时间：2026-02-07 18:48:11
> Agent：Agent01
> 阶段：/plan（只读设计，不改代码）

---

## Scope / Assumptions

### Scope（本轮实现）
1. Shaders 页面改为全量数据驱动：搜索/筛选/排序作用于 shaderData 全量，而非仅 DOM 前 50 条。
2. Shaders 列表采用分页渲染（优先稳定性），并保留选中态、URL 跳转高亮能力。
3. Textures 页面可读性优化：默认排序与默认选中策略让首屏可读；中间主预览优先，右侧不再强调重复预览。
4. 按钮与工具栏审美收敛：查看 HLSL 代码 + AI Shader 优化 改为专业仪表盘主操作组。
5. 回归测试补齐：新增/更新前端契约测试 + UI smoke 断言。

### Assumptions（假设，待验证）
- D:\\backup\\endfield_report 为当前验收样例输出目录。
- HLSL 源是否存在取决于导出链路，不承诺必有 HLSL，UI 只承诺状态可解释。
- 现有 navigation.js 跨页高亮逻辑继续可用（需确保 .shader-item[data-id] 结构不变）。

---

## Navigation Evidence（定位证据）

### 1) Codemap 查询（最多 3 条）
1. codemap  filterTextures -Repo renderdoc -Num 20
2. codemap AI Shader 优化 -Repo renderdoc -Num 20
3. codemap hlslBtn -Repo renderdoc -Num 20

### 2) 候选命中（>=3）
- [renderdoc] scripts/rdc_analyzer/analyze_rdc.py:2375 -> function filterTextures()
- [renderdoc] scripts/rdc_analyzer/analyze_rdc.py:2391 -> gridSearch.addEventListener('input', filterTextures)
- [renderdoc] scripts/rdc_analyzer/generate_simple_report.py:202 -> function filterTextures()

说明：codemap 对当前 templates/*.html 命中不足，已按 AGENTS 规则降级到 Serena/定点读取定位真实改动点。

### 3) 本轮跟进命中（Serena/精读）
- scripts/rdc_analyzer/templates/textures.html:424  (#textureSearch)
- scripts/rdc_analyzer/templates/textures.html:443  (#textureList)
- scripts/rdc_analyzer/templates/textures.html:749  (selectTexture)
- scripts/rdc_analyzer/templates/textures.html:786  (updateTexturePreview)
- scripts/rdc_analyzer/templates/textures.html:884  (filterTextures)
- scripts/rdc_analyzer/templates/shaders.html:798   (#shaderSearch)
- scripts/rdc_analyzer/templates/shaders.html:817   (#shaderList)
- scripts/rdc_analyzer/templates/shaders.html:832   (#hlslBtn)
- scripts/rdc_analyzer/templates/shaders.html:833   (#aiOptimizeBtn)
- scripts/rdc_analyzer/templates/shaders.html:1501  (filterShaders)
- scripts/rdc_analyzer/report_bundle_generator.py:831 (for shader in self.shaders[:50])

### 4) Follow-up 目标（1-2 个）
1. scripts/rdc_analyzer/templates/shaders.html：核心分支点（搜索/筛选/排序逻辑与按钮布局均在此）。
2. scripts/rdc_analyzer/report_bundle_generator.py：是否继续限制 50 条初始渲染的注册点。

---

## File List（精确到行号范围）

1. scripts/rdc_analyzer/templates/shaders.html
   - 样式区：1-120（主操作按钮组、工具栏布局）
   - 结构区：563-640（左侧列表 + 主工具栏）
   - 数据与交互：997-1625（shaderData、filterShaders、初始化）
2. scripts/rdc_analyzer/report_bundle_generator.py
   - Shader fallback 列表构造：820-890（当前 self.shaders[:50]）
   - Textures 列表数据集字段：565-625（保持兼容，必要时微调排序字段）
3. scripts/rdc_analyzer/templates/textures.html
   - 样式与结构：1-120, 416-520
   - 交互：749-930（selectTexture / updateTexturePreview / filterTextures / sortTextures）
4. scripts/rdc_analyzer/tests/test_bundle_report_assets.py
   - 新增契约测试：验证 Shaders 全量搜索/分页容器标记、Textures 默认排序策略标记。
5. scripts/rdc_analyzer/tools/ui_headless_smoke.py
   - 新增断言：Shaders 搜索命中非首屏条目、Textures 默认选中可读资源。
6. scripts/rdc_analyzer/tests/test_ui_headless_smoke.py
   - 补充启用态 smoke 的关键检查项（保持默认 skip）。

---

## 实施步骤（2-5 分钟粒度）

- [ ] 1. Shaders：引入全量数据流水线状态变量
  代码草案：
      const allShaders = Array.isArray(shaderData) ? shaderData : [];
      let filteredShaders = [...allShaders];
      let currentPage = 1;
      const pageSize = 100;
      let selectedShaderId = null;

- [ ] 2. Shaders：重写筛选/排序为数据级处理
  代码草案：
      function applyShaderQuery() {
        const keyword = (document.getElementById('shaderSearch').value || '').toLowerCase().trim();
        const typeFilter = currentFilter;
        const sortBy = document.getElementById('sortSelect').value;

        filteredShaders = allShaders.filter((s) => {
          const name = String(s.name || '').toLowerCase();
          const type = String((s.type || s.stage || '')).toLowerCase();
          const id = String(s.id || '').toLowerCase();
          const hitKeyword = !keyword || (name + ' ' + type + ' ' + id).includes(keyword);
          const hitFilter = typeFilter === 'all' ? true : (typeFilter === 'issues'
            ? !!((s.issues && s.issues.length) || (s.suggestions && s.suggestions.length))
            : type === typeFilter);
          return hitKeyword && hitFilter;
        });

        filteredShaders.sort((a, b) => {
          if (sortBy === 'name') return String(a.name || '').localeCompare(String(b.name || ''));
          if (sortBy === 'cycles') return Number((b.mali && b.mali.totalCycles) || 0) - Number((a.mali && a.mali.totalCycles) || 0);
          if (sortBy === 'usage') return Number((b.usedBy || []).length) - Number((a.usedBy || []).length);
          return 0;
        });

        currentPage = 1;
        renderShaderPage();
      }

- [ ] 3. Shaders：新增分页渲染器 + 页控件
  - renderShaderPage() 仅渲染当前页 DOM，renderPager() 渲染页码/上一页/下一页。
  - 保留 .shader-item[data-id] 结构，确保导航高亮兼容。

- [ ] 4. Shaders：按钮组视觉升级（专业仪表盘）
  - 主按钮固定高度、胶囊容器阴影/边框一致、主次层次分明。
  - 1366 宽度下不换行、不挤压。

- [ ] 5. Shaders：HLSL 空状态文案升级
  - 区分三类状态：未点击 / 无 HLSL 但有 source / 无任何源码。
  - 在 showHlsl() 触发后写入明确下一步建议。

- [ ] 6. Textures：默认可读排序 + 默认选中可读资源
  - sortTextures() 默认 vram 降序；首次加载自动选择首个可读候选（非极小纹理优先）。
  - 候选规则：max(width,height) >= 256 优先，否则 fallback 首项。

- [ ] 7. Textures：UI 信息密度优化
  - 列表元信息统一：WxH • format • mip • vram。
  - 右侧去重：不再强调重复预览，只保留诊断信息/使用情况。

- [ ] 8. 生成器与模板契约微调
  - 若前端完全数据驱动，则 SHADER_LIST_HTML 仅保留 fallback，不作为唯一来源。
  - 保障 SHADER_DATA_JSON 字段齐全（id/name/type/stage/usedBy/mali/source/hlsl）。

- [ ] 9. 测试补齐
  - test_bundle_report_assets.py：新增分页容器存在、搜索针对全量数据的契约断言。
  - ui_headless_smoke.py：新增搜索命中后计数变化 + 可定位到非首屏 shader 断言。

- [ ] 10. 端到端验证（你只看 HTML）
  - 使用 D:\\backup\\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc 重新生成 bundle。
  - 输出关键验收截图与检查项结论。

---

## 影响分析

### 正向影响
- 解决搜索不到的核心 UX 问题（DOM 前 50 限制被移除/弱化）。
- 页面首屏质量提升：用户第一眼可看到可读纹理与稳定按钮布局。
- 为后续服务挂载 + 按需高清预览保留接口，不与当前 B 路线冲突。

### 风险与回滚
- 风险1：列表从静态 DOM 转分页渲染后，跨页高亮可能失效。
  缓解：保留 data-id 与 selectShader(id) 入口；renderShaderPage 后再执行高亮。
- 风险2：分页/筛选后选中项丢失。
  缓解：selectedShaderId 持久化，若被过滤则显示当前项被筛选隐藏。
- 风险3：HLSL 文案误导可转换。
  缓解：文案明确视数据源与工具链可用性而定。

---

## Build/Test/Lint Quick Guide（命令仅记录不执行）

### 静态检查
py -3 -m py_compile scripts/rdc_analyzer/report_bundle_generator.py
py -3 -m py_compile scripts/rdc_analyzer/tools/ui_headless_smoke.py

预期：无语法错误

### 单测
py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -v --tb=short
py -3 -m pytest scripts/rdc_analyzer/tests/test_renderdoccmd_export_select.py -v --tb=short

预期：全部通过

### 可选 UI Smoke（默认 skip）
set RDC_UI_SMOKE=1
set RDC_UI_SMOKE_REPORT_DIR=D:\\backup\\endfield_report
py -3 -m pytest scripts/rdc_analyzer/tests/test_ui_headless_smoke.py -v --tb=short

预期：1 passed

### Bundle 生成（headless）
set RDC_TEX_EXPORT_SOURCE=renderdoccmd
set RDC_TEX_EXPORT_LIMIT=9999
py -3 scripts/rdc_analyzer/analyze_xml_report.py D:\\backup\\EndfieldTBeta2_2025.12.18_14.36_frame42231.zip.xml -o D:\\backup\\endfield_report --ui-version bundle

预期：输出 index/events/textures/shaders/recommendations + manifest.json

---

## Definition of Done（DoD）

- [ ] Shaders 搜索/筛选/排序对全量 shaderData 生效，不再受前 50 DOM 限制。
- [ ] Shaders 左侧列表可滚动、可分页，查看 HLSL 代码 与 AI Shader 优化 不重叠且风格统一。
- [ ] Textures 首屏默认选中可读纹理，中间主预览清晰，右侧属性可滚动。
- [ ] 你只打开 HTML 即可完成视觉验收，无手动补操作。
- [ ] 单测 + smoke（启用态）通过。

---

## Next Step

等待你确认后进入 /do 执行本计划。
