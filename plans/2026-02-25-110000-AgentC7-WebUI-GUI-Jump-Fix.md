# WebUI → GUI 跳转修复（Texture + 诊断）

## Scope / Assumptions
- 目标：修复 WebUI 点击纹理后 GUI 不跳转（TypeError: ViewTexture 参数类型不匹配）。
- 保持现有 /api/jump 与跳转队列机制不变，只修正 GUI 扩展侧的纹理跳转与回退策略。
- 假设：event 跳转逻辑本身可用，但可能因为 EID 映射或当前选中事件导致“看起来没跳”。若仍不明显，补充轻量日志。

## Files (line refs)
- `scripts/rdc_analyzer/ui_extension/analyzer_extension.py`: 298-325（`_jump_to_texture` 纹理跳转）、356-387（`dispatch_jump`/`_dispatch_jump_on_ui_thread` 行为参考）
- `scripts/rdc_analyzer/docs/WEBUI_AND_UI_EXTENSION.md`: 12, 53（跳转机制说明，仅作引用，不改）

## Build / Test / Lint Quick Guide (commands only)
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_webui_jump_queue.py -v`
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_webui_server.py -v`
- 手工验证（GUI）：Tools → RDC Analyzer → Open WebUI，点击纹理/事件/Shader 的 “↗ GUI”

## Pseudo-code
```
def _get_comp_type_typeless():
    for mod in (qrd, rd):
        comp = getattr(mod, "CompType", None)
        if comp and hasattr(comp, "Typeless"):
            return comp.Typeless
    return None

def _jump_to_texture(ctx, texture_id):
    ctx.ShowTextureViewer()
    viewer = ctx.GetTextureViewer()
    resource_id = _coerce_resource_id(texture_id)
    if hasattr(viewer, "ViewTexture"):
        try:
            comp_type = _get_comp_type_typeless()
            viewer.ViewTexture(resource_id, comp_type if comp_type else 0, True)
            return True
        except TypeError as exc:
            log("ViewTexture type mismatch, fallback", exc)
    if hasattr(viewer, "SetSelectedTexture"):
        viewer.SetSelectedTexture(resource_id)
        return True
    return False
```

## Impact Analysis
- 只影响 GUI 扩展侧纹理跳转；WebUI、报告生成、跳转队列不变。
- 若 `ViewTexture` 仍不接受参数类型，自动回退 `SetSelectedTexture`，确保“至少能选中纹理”。
- 新增日志仅在 TypeError 触发时出现，避免噪音。

## Task Checklist (2–5 min each)
- [x] TDD-1：评估是否可新增可测单元（结论：GUI 扩展依赖 RenderDoc 运行时，单测不可行；保留手工验证）。
- [x] Step-1：在 `_jump_to_texture` 中添加 `_get_comp_type_typeless` 与 TypeError 回退逻辑，代码片段如下：
```
def _get_comp_type_typeless():
    for mod in (qrd, rd):
        comp = getattr(mod, "CompType", None)
        if comp is not None and hasattr(comp, "Typeless"):
            return comp.Typeless
    return None
```
```
comp_type = _get_comp_type_typeless()
try:
    viewer.ViewTexture(resource_id, comp_type if comp_type is not None else 0, True)
    return True
except TypeError as exc:
    _log_event("ViewTexture type mismatch; fallback SetSelectedTexture", exc)
```
- [x] Step-2：`ViewTexture` 失败时回退 `SetSelectedTexture`，并保持最终失败时仍输出 “Jump to texture failed”。
- [x] Step-3：重新安装扩展：`py -3 scripts/rdc_analyzer/tools/install_ui_extension.py --name rdc_analyzer_ext --scripts-root D:\Code\git\renderdoc\scripts`
- [ ] Step-4：手工验证：点击纹理/事件/Shader “↗ GUI”，确认 GUI 打开纹理或定位事件；日志不再出现 `TextureViewer_ViewTexture` TypeError。

## Risks / Blockers
- 若 `CompType` 在当前绑定不存在或 SWIG 映射错误，`ViewTexture` 仍可能失败；回退 `SetSelectedTexture` 是兜底，但可能不自动聚焦纹理窗口。
- event 跳转“看起来没跳”可能是 EID 不存在或当前事件已选中，需要进一步数据映射排查。

## Decisions
- 优先保持 API 兼容：先尝试 `ViewTexture`，失败再回退 `SetSelectedTexture`。
- 不改跳转协议；修复集中在 GUI 扩展层。

## Verification / Acceptance (Definition of Done)
- 点击纹理跳转不再触发 `TextureViewer_ViewTexture` TypeError。
- GUI 中能看到对应纹理被选中/打开（至少 `SetSelectedTexture` 生效）。
- WebUI 与跳转队列文件仍正常生成/更新。

## Next Steps
- 等待 /do 执行实现与安装验证。
