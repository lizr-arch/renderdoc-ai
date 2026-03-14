# 离线/CI 报告设计案（XML/JSON → HTML）

## 角色与场景
- 无 GUI 环境、CI 回归、批量生成、容灾（驱动/平台打不开 RDC）。

## 目标
- 复用 GUI 的报告模板，确保视觉与结构一致。
- 提供轻量/全量两种模式；生成 JSON 快照，方便对比与 AI。

## 数据来源
- renderdoccmd export: XML / chrome.json / zip.xml（含纹理）。
- 字段缺失时做显式提示，并提供“使用 MCP 查询补全”的指引。

## 主要能力
- CLI 过滤（marker/event/flags/only_actions），控制体积与关注范围。
- 输出：HTML（共用模板）、JSON 快照、可选压缩包。
- CI 友好：退出码、耗时统计、体积统计，diff 模式（未来）。

## 模板与适配
- 模板与 GUI 共用；适配器处理字段缺失和占位。
- 轻量模式：仅概要 + Top-N；全量模式：完整事件/纹理/shader 列表。

## 参数示例
```
py -3 scripts/rdc_analyzer/xml_to_bundle.py capture.xml \
  --event-id-min 7300 --event-id-max 7700 \
  --flags-filter Drawcall,Dispatch \
  --only-actions \
  --mode lightweight \
  --json-snapshot out.json
```

## 非目标
- 不负责实时数据（由 MCP 补拉）。
- 不生成 AI 结论（由 Skill/外部调用完成）。

## 验收指标
- 与 GUI 模板一致性：结构一致，缺失项标记清晰。
- CI 可用性：默认轻量模式输出体积可控；支持无图形环境运行。
