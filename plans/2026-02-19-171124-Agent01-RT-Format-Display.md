## Scope / Assumptions
- Scope: 在 **events.html** 的 RT 预览（主预览 + 右侧条带）显示 **RT 格式**，并保证可从 textures_data.json 反查格式。
- In: 前端 events.html（加载 textures_data.json，构建 textureMap，RT 标签显示 format），后端 timeline_builder 透传 format（可选但推荐），schema 更新。
- Out: ignore‑alpha 根因修复、RT 导出/渲染逻辑不改。
- 假设（待验证）: `textures_data.json` 中 `format` 字段始终存在且可用于渲染。

## Build / Test / Lint Quick Guide (记录命令，不自动执行)
- 生成报告（如需）：`py -3 scripts/rdc_analyzer/one_click_bundle_report.py "D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc" -o D:\backup\endfield_report`
- 视觉验证：打开 `D:\backup\endfield_report\events.html`，任意事件 → RT 列表/条带应显示 `VK_FORMAT_...`

## Repo / File List (含行号范围)
- `scripts/rdc_analyzer/templates/events.html:1801-1860`（数据加载：新增 textures_data.json + textureMap）
- `scripts/rdc_analyzer/templates/events.html:2968-3016`（RT 列表渲染：showRT / renderTargets）
- `scripts/rdc_analyzer/templates/events.html:3027-3050`（RT 条带：updateRtStrip）
- `scripts/rdc_analyzer/timeline_builder.py:248-420`（renderTargets 组装，加入 format / simple_format）
- `scripts/rdc_analyzer/schema/events_data.schema.json:117-145`（renderTargets schema 增加 format）

## Approach (Pseudo-code / 关键实现片段)
1) **events.html 加载 textures_data.json 并建索引**
```
let texturesData = [];
let textureMap = {};

// loadExternalData 内新增
const texturesRes = await fetch('textures_data.json').catch(() => null);
if (texturesRes && texturesRes.ok) {
  texturesData = await texturesRes.json();
  texturesData.forEach(t => { textureMap[String(t.id)] = t; });
}
```

2) **RT 列表渲染时显示 format**
```
const tex = textureMap[String(rt.id)] || {};
const fmt = rt.format || tex.format || tex.simple_format || '';
const fmtLabel = fmt ? `<div class="rt-format">${fmt}</div>` : '';
```
将 `fmtLabel` 拼到 `.rt-label` 或新行显示（不破坏现有布局）。

3) **timeline_builder 透传格式（后端增强）**
```
render_targets_list.append({
  "id": rt_id,
  "name": rt_name,
  "thumbnail": thumbnail,
  "slot": rt.get("slot", len(render_targets_list)),
  "format": tex_info.get("format") or tex_info.get("simple_format", "")
})
```

4) **schema 增加 format**
```
"format": { "type": "string", "description": "RT 格式 (如 VK_FORMAT_...)" }
```

## Impact Analysis
- 正面：事件页 RT 一眼可识别格式（比如 HDR / UNORM / SRGB）。
- 负面：events.html 增加一次 textures_data.json 请求（本地文件级别，影响可忽略）。
- 风险：format 缺失时需优雅降级；格式展示可能过长 → 需适度样式控制（单行裁剪）。

## Task Checklist (2-5 分钟粒度)
- [x] 在 events.html 加载 textures_data.json 并创建 textureMap
- [x] 在 RT 列表/条带渲染处显示 format（优先 rt.format，其次 textureMap.format）
- [x] timeline_builder.py 给 renderTargets 附加 format（供新报告写入）
- [x] events_data.schema.json 增加 renderTargets.format
- [ ] 生成/更新报告后做视觉验证（RT 标签出现格式）
- [ ] 更新本计划勾选状态 + 记录风险/决定
- [ ] Git 提交（Conventional Commits）

## Risks / Blockers
- `textures_data.json` 若被移除/未生成，会导致格式为空（需安全降级）。
- 旧报告若未更新 events.html，无法显示 format（需同步产物或重新生成）。

## Decisions
- 前端优先通过 textureMap 补齐格式；后端同时透传 format 作为长期方案。
- 不改变 RT 的数据结构语义，仅添加可选字段。
- 为便于立即验证，已同步修改 `D:\backup\endfield_report\events.html`。

## Verification / DoD
- events.html 的 RT 列表与条带均显示格式（至少 Color0/Color1 有值）。
- 无 format 时不报错、不影响缩略图显示。

## Open Questions
- 你更偏好在 **RT 名称行** 还是 **新行** 显示格式？
- 是否需要格式短名（simple_format）与全名切换？

## Next Steps
- 等你确认 /do 后执行计划并更新本文件。
