## Scope / Assumptions
- Scope: 事件页 Render Target 缩略图**真实缩放**到最大 512；Ignore-Alpha 的 debug 面板**可折叠**且**出错自动展开**。
- In: RT 缩略图生成/透传链路；events.html 的 debug 面板 UI/JS。
- Out: 纹理页面/Shader 页面样式调整；其它导出流程不改。
- 假设（待验证）: `export_texture_base64(..., max_size)` 支持真实缩放（通过 RenderDoc SaveTexture 的 maxResolution 或等价参数）。

## Build / Test / Lint Quick Guide (记录命令，不自动执行)
- 生成报告：`py -3 scripts/rdc_analyzer/one_click_bundle_report.py "D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc" -o D:\backup\endfield_report`
  - 预期输出包含：`Bundle Report Generated Successfully!`
- 尺寸验证（脚本）：读取 `events_data.json` 中 RT 缩略图文件，最大边 ≤ 512

## Repo / File List (含行号)
- `scripts/rdc_analyzer/rdc_to_bundle_report.py:43`（RT_SNAPSHOT_MAX_SIZE）
- `scripts/rdc_analyzer/rdc_to_bundle_report.py:550`（export_texture_base64 使用点）
- `scripts/rdc_analyzer/timeline_builder.py:391`（renderTargets 列表构建）
- `scripts/rdc_analyzer/templates/events.html:1641`（A 按钮）
- `scripts/rdc_analyzer/templates/events.html:3228`（A 按钮逻辑/绑定）

## Approach (Pseudo-code / 关键实现片段)
1) **RT 缩略图真实缩放到 512**
```
# rdc_to_bundle_report.py
RT_SNAPSHOT_MAX_SIZE = 512

def export_texture_base64(tex_id, max_size):
    save_data = rd.TextureSave()
    ...
    save_data.maxResolution = max_size  # 若 API 支持
    controller.SaveTexture(save_data, path)
```
> 若 `maxResolution` 不可用：回退为 RenderDoc 支持的等价字段；若仍不支持则在风险中记录并提示替代方案。

2) **事件页优先使用 RT 自带缩略图（避免被 texture_lookup 覆盖）**
```
# timeline_builder.py
thumb = rt.get("thumbnail") or tex_info.get("thumbnail", "")
render_targets_list.append({
  "id": rt_id,
  "name": rt_name,
  "thumbnail": thumb,
  "slot": rt.get("slot", len(render_targets_list)),
  "format": rt.get("format") or tex_info.get("format") or tex_info.get("simple_format","")
})
```

3) **Ignore-Alpha Debug 面板折叠 + 出错自动展开**
```
# events.html
// 默认折叠
debugPanel.classList.add('collapsed')

function updateIgnoreAlphaDebug(..., errorText) {
  const hasError = !!errorText;
  debugPanel.classList.toggle('collapsed', !hasError && !debugPinned);
}
```

## Impact Analysis
- 性能：RT 缩略图文件体积下降，加载更快。
- 体验：事件页 RT 更清晰且更快；debug 信息不打扰，出错自动展开。
- 风险：RenderDoc API 若不支持 maxResolution，会导致“真实缩放”无法落实（需替代方案）。

## Task Checklist (2-5 分钟粒度)
- [x] 定位 RT 缩略图生成函数，确认是否支持 maxResolution
- [x] 将 RT 真实缩放参数固定为 512（写入生成链路）
- [x] timeline_builder 优先使用 rt.thumbnail，避免覆盖
- [x] events.html debug 面板折叠 + 出错自动展开
- [x] 更新本计划勾选状态 + 记录风险/决定
- [ ] Git 提交（Conventional Commits）

## Risks / Blockers
- renderdoccmd export 的 --max-size 未实际生效（已用 PIL 后处理降采样规避）。
- PIL 依赖不可用时无法后处理（当前环境可用）。

## Decisions
- 目标尺寸：**最大边 512**
- Debug 面板：**默认折叠，出错自动展开**
- RT 缩略图优先级：**RT 自带 > texture_lookup**
- 缩放策略：**导出后再用 PIL 降采样到 512**

## Verification / DoD
- 事件页 RT 缩略图最大边 ≤ 512（脚本验证）
- A 按钮正常；debug 面板默认折叠，发生错误时自动展开
- 视觉验证：RT 清晰度满足预期、加载更快

## Next Steps
- 你确认 /do 后开始实现
