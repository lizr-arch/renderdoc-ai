# Scope / Assumptions

- **目标**：在 `xml_to_bundle.py` 路线中，补齐 Vulkan Draw 事件的“实际绑定 Render Target（RT）集合”，用于 `events.html` / `textures.html` 的真实中间 RT 定位。
- **用户选择**：采用方案 **2（实际使用集合）**，不是“仅候选/仅命名猜测”。
- **输入样本**：`D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc`（one-click 产物已在 `D:\backup\endfield_report`）。
- **约束**：保持 headless 自动化；不引入 GUI 手工步骤；不修改 `renderdoc/3rdparty/` 与 `build*/`。

---

# Build/Test/Lint Quick Guide（命令仅记录；/do 阶段执行）

```bash
# 1) 单测（新增 RT 映射测试）
py -3 -m pytest scripts/rdc_analyzer/tests/test_xml_to_bundle_vulkan_rt_mapping.py -v

# 2) 回归现有 xml_to_bundle 缩略图测试
py -3 -m pytest scripts/rdc_analyzer/tests/test_xml_to_bundle_export_thumbnails.py -v

# 3) one-click 端到端（无 UI smoke，聚焦数据链）
py -3 scripts/rdc_analyzer/one_click_bundle_report.py \
  "D:\\backup\\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc" \
  -o "D:\\backup\\endfield_report" \
  --no-smoke --texture-max-size 256 -v

# 4) 验证 events_data.json 的 RT 覆盖率
py -3 -c "import json, pathlib; p=pathlib.Path(r'D:\\backup\\endfield_report\\events_data.json'); e=json.loads(p.read_text(encoding='utf-8')); n=sum(1 for x in e if x.get('renderTargets')); print('events=',len(e),'nonempty_rt=',n,'ratio=',round(n/max(1,len(e)),4))"
```

**预期输出（DoD）**：
- 新增测试通过（`PASSED`）
- `events_data.json` 中 `renderTargets` 非空事件数量 `> 0`
- `eid` 不再全为 `0`（至少出现多个不同值）

---

# Navigation Evidence（codemap 不可用时的等价证据）

## 查询记录（max 3）
1. `codemap "Color Attachment" -Num 20` → 环境报错 `codemap: command not found`（工具不可用）
2. `grep -n -E 'renderTargets|render_targets' scripts/rdc_analyzer/timeline_builder.py`
3. `grep -n -E 'vkCmdBeginRenderPass|OMSetRenderTargets|render_pass_begin' scripts/rdc_analyzer/parse_rdc_xml.py`

## 候选命中（>=3）
1. `[renderdoc] scripts/rdc_analyzer/timeline_builder.py:391`  
   `rt_data = evt.get("renderTargets", [])`（前端消费入口）
2. `[renderdoc] scripts/rdc_analyzer/timeline_builder.py:408`  
   `prepared["renderTargets"] = render_targets_list`（上游为空则页面必空）
3. `[renderdoc] scripts/rdc_analyzer/xml_to_bundle.py:127`  
   `"event_id": int(chunk.get("eventId", 0))`（当前导致 eid 可能全 0）
4. `[renderdoc] scripts/rdc_analyzer/parse_rdc_xml.py:814`  
   `render_pass_begin = ["vkCmdBeginRenderPass", ...]`（已有可复用的 Vulkan RenderPass 入口）
5. `[renderdoc] scripts/rdc_analyzer/parse_rdc_xml.py:1748`  
   `elif "OMSetRenderTargets" in name:`（当前 RT 解析偏 D3D 路径）

## 跟进点（1-2 个）
- 主跟进：`scripts/rdc_analyzer/xml_to_bundle.py`（当前 one-click 主链路）
- 参考实现：`scripts/rdc_analyzer/parse_rdc_xml.py`（RenderPass 结构与事件拼装思路）

---

# File List（计划修改清单，含行号范围）

1. `scripts/rdc_analyzer/xml_to_bundle.py:62`（`SimpleXmlParser.parse` 主循环）  
   - 增加 Vulkan 状态跟踪：`ImageView->Image`、`Framebuffer->attachments`、`active_rt_state`。
2. `scripts/rdc_analyzer/xml_to_bundle.py:124`（`_parse_draw_call`）  
   - 事件 ID 回退：`eventId` 缺失时使用 `chunkIndex`。
3. `scripts/rdc_analyzer/xml_to_bundle.py:294`（`xml_to_bundle_events_dict`）  
   - 透传 draw_call 的 `render_targets` 到事件 `renderTargets`。
4. `scripts/rdc_analyzer/tests/test_xml_to_bundle_vulkan_rt_mapping.py`（新文件）  
   - 覆盖最小 Vulkan 链路：`vkCreateImageView -> vkCreateFramebuffer -> vkCmdBeginRenderPass -> vkCmdDraw`。
5. （可选）`scripts/rdc_analyzer/docs/TEXTURE_EXTRACTION.md`（补充“实际 RT = 事件绑定数据”说明）

---

# Pseudo-code（完整实现草案）

```python
# xml_to_bundle.py

class SimpleXmlParser:
    VK_BEGIN_RENDERPASS = {"vkCmdBeginRenderPass", "vkCmdBeginRenderPass2", "vkCmdBeginRendering"}
    VK_END_RENDERPASS = {"vkCmdEndRenderPass", "vkCmdEndRenderPass2", "vkCmdEndRendering"}

    def parse(self, xml_path: str) -> Dict:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        driver = self._detect_driver(root)
        draw_calls = []
        textures = []
        buffers = []

        # --- Vulkan runtime maps ---
        image_view_to_image = {}       # view_id(str) -> image_id(str)
        framebuffer_to_views = {}      # fb_id(str) -> [view_id(str), ...]
        active_rt_state = {"color": [], "depth": None}

        for chunk in root.iter("chunk"):
            name = chunk.get("name", "")

            if name == "vkCreateImage":
                tex = self._parse_vk_image(chunk)
                if tex:
                    textures.append(tex)

            elif name == "vkCreateImageView":
                view_id, image_id = self._parse_vk_image_view(chunk)
                if view_id and image_id:
                    image_view_to_image[view_id] = image_id

            elif name == "vkCreateFramebuffer":
                fb_id, view_ids = self._parse_vk_framebuffer(chunk)
                if fb_id:
                    framebuffer_to_views[fb_id] = view_ids

            elif name in self.VK_BEGIN_RENDERPASS:
                # vkCmdBeginRenderPass: 从 RenderPassBegin.framebuffer 找附件
                fb_id = self._parse_begin_renderpass_framebuffer(chunk)
                active_rt_state = self._resolve_rt_state(fb_id, framebuffer_to_views, image_view_to_image)

            elif name in self.VK_END_RENDERPASS:
                active_rt_state = {"color": [], "depth": None}

            elif name in self.D3D11_DRAW_CALLS or name in self.VK_DRAW_CALLS:
                dc = self._parse_draw_call(chunk, name)
                if dc and name.startswith("vk"):
                    dc["render_targets"] = [
                        {"id": img_id, "slot": i}
                        for i, img_id in enumerate(active_rt_state["color"])
                    ]
                    if active_rt_state.get("depth"):
                        dc["depth_target"] = active_rt_state["depth"]
                if dc:
                    draw_calls.append(dc)

            elif name in self.VK_DISPATCH_CALLS:
                dc = self._parse_draw_call(chunk, name, is_dispatch=True)
                if dc:
                    draw_calls.append(dc)

            elif name == "vkCreateBuffer":
                buf = self._parse_vk_buffer(chunk)
                if buf:
                    buffers.append(buf)

        return {"driver": driver, "draw_calls": draw_calls, "textures": textures, "buffers": buffers}

    def _parse_draw_call(self, chunk, name, is_dispatch=False):
        event_raw = chunk.get("eventId")
        if event_raw is None:
            event_raw = chunk.get("chunkIndex", 0)
        event_id = int(event_raw)
        ...
        return {"event_id": event_id, ...}


def xml_to_bundle_events_dict(draw_calls: List[Dict]) -> List[Dict]:
    events = []
    for dc in draw_calls:
        event = {
            "eid": dc.get("event_id", 0),
            ...
            "renderTargets": dc.get("render_targets", []),
        }
        if dc.get("depth_target"):
            event["depthTarget"] = dc.get("depth_target")
        events.append(event)
    return events
```

---

# Task Checklist（2-5 分钟粒度）

- [x] T1：补充 `SimpleXmlParser` 的 Vulkan 运行态结构（ImageView/Framebuffer/active RT）。
- [x] T2：实现 `vkCreateImageView` 解析（`View -> image` 映射）。
- [x] T3：实现 `vkCreateFramebuffer` 解析（`Framebuffer -> pAttachments(View[])`）。
- [x] T4：实现 `vkCmdBeginRenderPass` / `vkCmdEndRenderPass` 状态切换并绑定当前 RT 集合。
- [x] T5：在 Vulkan Draw 事件写入 `render_targets`（color slots）与 `depth_target`（若有）。
- [x] T6：修复 `event_id` 回退逻辑（`eventId` 缺失时用 `chunkIndex`）。
- [x] T7：`xml_to_bundle_events_dict` 透传 `renderTargets` 到前端事件模型。
- [x] T8：新增最小单测覆盖 Vulkan RT 实绑链路；回归现有缩略图测试。
- [x] T9：用 Endfield 样本跑 one-click，验证 `events_data.json` 的 `renderTargets` 非空比率。

---

# Impact Analysis

## 直接收益
- `events.html` 右侧可展示真实 RT 绑定（不再全空）。
- `textures.html` 可基于“被哪些事件作为 RT 输出”建立真实反向链路。
- 视觉验收从“凭感觉看图”升级为“可定位到具体 Draw 的中间 RT”。

## 风险与缓解
1. **风险**：不同 API 的字段名大小写/层级差异（`RenderPassBegin` vs 变体）。  
   **缓解**：解析函数做多路径兜底（`RenderPassBegin`/`pRenderPassBegin`/`framebuffer`）。
2. **风险**：动态渲染 `vkCmdBeginRendering` 与传统 RenderPass 结构不同。  
   **缓解**：先覆盖 `vkCmdBeginRenderPass*` 主路径；动态渲染路径保留兜底并打日志。
3. **风险**：RT 包含 depth/stencil，前端显示可能与 color 混合。  
   **缓解**：事件结构先仅写入 color 到 `renderTargets`，depth 单独放 `depthTarget`。

## 兼容性
- 不改变旧页面字段语义；只增加事件中的可选字段。
- D3D11/D3D12 路径行为不受影响。

---

# Verification / Acceptance（Definition of Done）

- [x] events_data.json 中 renderTargets 非空事件数量 > 0。
- [x] events_data.json 的 eid 不再全部为 0（出现多个唯一值）。
- [x] textures.html / events.html 能看到 RT 关联信息（不要求新增 UI 控件，仅数据可见）。
- [x] 新增测试 + 回归测试通过。

---

# Next Steps（/do 阶段）

1. 先做 **T1-T7**（数据链打通）并跑单测。  
2. 再做 **T8-T9**（样本验证 + 结果截图/JSON统计）。  
3. 若结果稳定，再进入下一轮 UI 精修（筛选“仅显示作为 RT 输出的纹理”）。


---

# /do 执行记录（2026-02-16）

- 已完成 Vulkan 实际 RT 绑定链路：vkCreateImageView -> vkCreateFramebuffer -> vkCmdBeginRenderPass -> vkCmdDraw。
- 已完成 event_id 回退策略：eventId=0/缺失时回退 chunkIndex。
- 新增测试：scripts/rdc_analyzer/tests/test_xml_to_bundle_vulkan_rt_mapping.py，并通过。
- 回归测试：scripts/rdc_analyzer/tests/test_xml_to_bundle_export_thumbnails.py、scripts/rdc_analyzer/tests/test_one_click_bundle_report.py，均通过。
- Endfield 实测结果（D:/backup/endfield_report/events_data.json）：
  - events=337
  - with_rt=212（renderTargets 非空）
  - eid_unique=337
  - eid_zero=0
- 风险备注：vkCmdBeginRendering（动态渲染）当前仍按兜底路径处理，后续可补 attachment 解析增强。
