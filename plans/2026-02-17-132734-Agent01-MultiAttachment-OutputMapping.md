---
title: Multi-Attachment Output Mapping (Events UI)
date: 2026-02-17 13:27:34
agent: Agent01
stage: /plan
---

## Scope
- 对事件页（events.html）中的多 Render Target 显示与 Color0..N 映射规则进行澄清与可视化改进。
- 依据 RenderDoc 源码确认多 attachment 的输出顺序/规则，用于 UI 解释与标签。

## Assumptions
- events_data.json 的 
enderTargets 来自 RenderDoc GetOutputTargets() 的顺序，通常与 Color0..N 对应。
- 不同 API（Vulkan/GL/D3D）可能有不同 attachment 语义，需要以 RenderDoc 源码为准。
- 文档搜索无直接说明（search_docs 无结果），因此以源码/运行时数据为证据。

## Build/Test/Lint Quick Guide (仅记录，不执行)
- 生成报告（期望：退出码 0；日志包含 “bundle report” 或 “output_dir”）  
  py -3 scripts/rdc_analyzer/one_click_bundle_report.py "D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc" -o "D:\backup\endfield_report"
- 结构校验（期望：输出 rtCount=5）  
  py -3 -c "import json; data=json.load(open(\"D:/backup/endfield_report/events_data.json\", encoding=\"utf-8\")); e=next(x for x in data if x.get(\"eid\")==3461); print(\"rtCount\", len(e.get(\"renderTargets\", [])))"

## Repo / File List
- scripts/rdc_analyzer/templates/events.html (输出 Tabs/缩略图/映射说明 UI)
- scripts/rdc_analyzer/extract_pipeline_state.py (renderTargets 生成源头)
- scripts/rdc_analyzer/core/bridge.py (Attachment 关联信息)
- RenderDoc 源码（只读，用于规则确认）
  - 
enderdoc/api/replay/pipestate.inl
  - 
enderdoc/api/replay/pipestate.h
  - 
enderdoc/driver/vulkan/vk_replay.cpp
  - 
enderdoc/driver/gl/gl_replay.cpp
  - qrenderdoc/Windows/TextureViewer.cpp

## Approach (Pseudo-code)
`	ext
1) 读取 RenderDoc 源码：确认 GetOutputTargets() 返回顺序与 attachment 关系
2) 追踪 rdc_analyzer 侧：renderTargets 的构建顺序与字段
3) 在 events.html：
   - 明确 “Color0..N = renderTargets[i]”
   - 当 tab 超过 2 个时，允许横向滚动，避免被裁切
   - 输出区域显示 “来源说明” + 绑定数
4) 重新生成报告并验证 EID 3461 的 5 张 RT + Tabs 展示
`

## Code Sketch (完整片段示例)
`html
<!-- 输出 tabs 容器 -->
<div class="output-tabs" id="outputTabs"></div>

<style>
.output-tabs {
  display: flex;
  gap: 2px;
  overflow-x: auto;
  white-space: nowrap;
}
.output-tabs::-webkit-scrollbar {
  height: 6px;
}
</style>
`

`js
function buildOutputTabs(event) {
  const tabs = document.getElementById("outputTabs");
  tabs.innerHTML = "";
  const rtCount = Array.isArray(event?.renderTargets) ? event.renderTargets.length : 0;
  for (let i = 0; i < Math.max(1, rtCount); i++) {
    const key = "color" + i;
    const tab = document.createElement("div");
    tab.className = "output-tab";
    tab.dataset.output = key;
    tab.textContent = "Color " + i;
    tab.title = "renderTargets[" + i + "]";
    tab.onclick = () => selectOutput(key);
    tabs.appendChild(tab);
  }
}
`

## Impact Analysis
- 正面：多 RT 的 UI 显示完整，Color0..N 与 renderTargets 关系明确。
- 风险：不同 API 对 attachment 的语义不完全一致；说明文案需基于源码确认。
- 回退：不动渲染与数据，仅调整 UI；可安全回退为原布局。

## Action Items (2–5 分钟粒度)
- [x] 阅读 RenderDoc 源码：GetOutputTargets / colorAttachments 规则（pipestate + vk/gl replay）
- [x] 追踪 rdc_analyzer 构建顺序（extract_pipeline_state / bridge）
- [x] 明确 UI 映射规范（Color0..N == renderTargets[i] + 说明文案）
- [x] 修复 Tabs 显示裁切（横向滚动 + 视觉优化）
- [x] 重新生成报告并验证 EID 3461 的 5 张 RT 展示
- [ ] 记录结论与规则到文档（若需要）

## Risks & Blockers
- 渲染 API 混用导致 attachment 含义差异。
- 输出顺序可能依赖 RenderPass/Subpass 的具体组合。

## Decisions
- 先以 RenderDoc 源码为准确定义输出顺序，再调整 UI。
- UI 改动保持轻量，避免破坏现有布局风格。

## Verification / DoD
- EID 3461 在 events.html 中看到 5 个 Color Tabs，均可点击显示缩略图。
- “Color0..N 与 renderTargets[i]” 的说明文字可见。
- 报告生成命令成功（退出码 0）。

## Open Questions
- 是否需要对不同 API（Vulkan/GL/D3D）显示不同说明文案？
- 是否需要把 depth/stencil 作为独立信息卡片展示？

## Next Steps
- 等用户确认进入 /do 后执行修改并更新本计划勾选项。


## Addendum: Color2/3/4 空白 & 按钮策略

### Root Cause (Verified)
- EID 3461 的 renderTargets[2] 缩略图 PNG alpha 全为 0（全透明），因此视觉上看起来“空白”。
- renderTargets[3]/[4] 有可见像素，但透明覆盖率较低，容易与背景棋盘格混在一起。
- onerror 诊断仍保留，用于区分真实加载失败与透明/低覆盖率。

### Extra Action Items
- [x] 为 outputImg 添加 onerror 处理：显示失败信息与 URL
- [x] 若 fallback.thumbnail 含 %，加载失败时尝试 decodeURIComponent 的路径
- [x] 当 fallback 缩略图显示时隐藏“从 RDC 加载快照”按钮
- [x] 增加 Alpha 覆盖率提示（区分全透明/低覆盖率）
- [x] 重新生成报告并复测 EID 3461 Color2/3/4


### Verification Notes
- EID 3461: Color0/1/3/4 有可见像素；Color2 alpha 覆盖率 0（全透明）。
