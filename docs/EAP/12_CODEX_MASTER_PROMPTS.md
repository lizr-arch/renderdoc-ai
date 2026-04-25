# 12_CODEX_MASTER_PROMPTS — 可复制给本地 Codex 的逐轮 Prompt

用途：每轮把对应文档和本 prompt 的对应段落一起喂给本地 Codex。  
建议：每轮只让 Codex 做一个阶段，避免一次性改太多。

---

## Prompt 0 — 仓库侦察，不写代码

```text
你是本地代码仓库中的高级图形引擎工具开发助手。现在只做仓库侦察，不允许修改任何代码。

请阅读以下文档：
- 00_README_FEED_ORDER.md
- 01_REPO_RECON_AND_BOUNDARIES.md

任务：
1. 搜索当前仓库，找出构建系统、渲染后端、RenderGraph、draw/dispatch 提交路径、resource 创建路径、shader/material/PSO 数据来源、capture lifecycle。
2. 生成 Docs/EAP/EAP_IMPLEMENTATION_MAP.md。如果仓库没有 Docs，就生成 docs/eap/EAP_IMPLEMENTATION_MAP.md。
3. 输出推荐模块目录、建议修改文件列表、风险点、测试方式。
4. 本轮禁止修改任何源码、build 文件或 third-party 文件。

完成后只给出：
- 生成的 EAP_IMPLEMENTATION_MAP.md 路径；
- 摘要；
- 下一轮建议。
```

---

## Prompt 1 — RenderDocBridge

```text
你现在开始实现 Engine Annotation Protocol 的第 1 个代码任务：RenderDocBridge。

请阅读：
- 00_README_FEED_ORDER.md
- 02_EAP_PROTOCOL_SPEC.md
- 03_TASK_RENDERDOC_BRIDGE.md
- Docs/EAP/EAP_IMPLEMENTATION_MAP.md（或 docs/eap/EAP_IMPLEMENTATION_MAP.md）

任务：
1. 新增 RenderDocBridge 模块，动态发现 RenderDoc in-application API。
2. 支持 API 1.7.0 的 SetObjectAnnotation / SetCommandAnnotation。
3. RenderDoc 不存在、API 不足、参数非法时必须 no-op 或返回明确 status，不能崩溃。
4. 加配置开关：EAP_ENABLE_RENDERDOC、EAP_ENABLE_ANNOTATIONS、EAP_ENABLE_SIDECAR。
5. 加单测或 mock 测试，覆盖 no RenderDoc、invalid args、return code mapping、thread-safe Init。
6. 不要接入 render graph，不要写 sidecar，不要修改 RenderDoc 源码。

请在完成后运行可用的 build/test 命令。如果不能运行，说明具体原因。
最终输出：修改文件清单、接口摘要、测试结果、下一轮建议。
```

---

## Prompt 2 — EAP Core Types

```text
你现在实现 Engine Annotation Protocol 的第 2 个代码任务：EAP Core Types。

请阅读：
- 02_EAP_PROTOCOL_SPEC.md
- 03_TASK_RENDERDOC_BRIDGE.md
- 04_TASK_EAP_CORE_TYPES.md
- Docs/EAP/EAP_IMPLEMENTATION_MAP.md

任务：
1. 新增 EAP ID、context、key constants、key/value validation、AnnotationWriter、EAPRuntime、ScopedPass。
2. 实现 annotation 写入预算和 OnlyWhenCapturing 逻辑。
3. 定义 ISidecarSink 接口，但不要写 JSON 文件。
4. 所有 key 不允许散落硬编码，必须集中在 EAPKeys.h 或等价文件。
5. 加单测：key validation、empty fields skipped、budget exceeded、ScopedPass push/pop、OnlyWhenCapturing。
6. 不要接入真实 render graph，不要写 sidecar，不要调用网络。

完成后运行测试。输出修改文件清单、测试结果、当前限制。
```

---

## Prompt 3 — Engine Hooks

```text
你现在实现 Engine Annotation Protocol 的第 3 个任务：接入真实引擎 hooks。

请阅读：
- 02_EAP_PROTOCOL_SPEC.md
- 04_TASK_EAP_CORE_TYPES.md
- 05_TASK_ENGINE_HOOKS.md
- Docs/EAP/EAP_IMPLEMENTATION_MAP.md

任务：
1. 在 frame begin/end 接入 EAPRuntime::BeginFrame/EndFrame。
2. 在 RenderGraph pass execute 或 debug marker scope 附近接入 eap::ScopedPass。
3. 在 draw/dispatch submit 路径构建 DrawContext，并调用 AnnotationWriter 写 command annotations。
4. 在 texture/buffer 创建或 debug name 设置处构建 ResourceContext，并调用 AnnotationWriter 写 object annotations。
5. 实现当前后端需要的 RenderDocBackendAdapter，优先支持项目主力 API。其它后端可以 no-op 并记录 diagnostics。
6. 不要重构 renderer，不要修改 RenderDoc 源码，不要写网络。
7. EAP 关闭或无 RenderDoc 时必须无功能影响。

完成后运行编译/测试。输出：接入点列表、字段来源、缺失字段、手动抓帧验证步骤。
```

---

## Prompt 4 — Sidecar Writer

```text
你现在实现 Engine Annotation Protocol 的第 4 个任务：Sidecar Writer。

请阅读：
- 02_EAP_PROTOCOL_SPEC.md
- 04_TASK_EAP_CORE_TYPES.md
- 06_TASK_SIDECAR_WRITER.md

任务：
1. 实现 SidecarWriter，作为 ISidecarSink 收集 frame/pass/command/resource。
2. 按协议输出 *.rmeta.json。
3. 实现 atomic write。
4. 实现 RedactionPolicy：LocalFull、ProjectInternal、CrossProject、ExternalVendor。
5. 尝试绑定最新 RenderDoc capture path；如果不可用，写 last_frame.rmeta.json。
6. 加单测：minimal sidecar、empty fields skipped、hash formatting、atomic write、redaction、limits。
7. 不要上传，不要联网，不要读取 .rdc。

完成后运行测试。输出 sidecar 示例、文件路径、测试结果、已知限制。
```

---

## Prompt 5 — Rule Engine

```text
你现在实现 Engine Annotation Protocol 的第 5 个任务：Rule Engine MVP。

请阅读：
- 02_EAP_PROTOCOL_SPEC.md
- 06_TASK_SIDECAR_WRITER.md
- 07_TASK_RULE_ENGINE_MVP.md

任务：
1. 实现 RuleEngine、IRule、RuleResult、RuleEvidence。
2. 实现默认规则：missing_required_context、annotation_budget_exceeded、texture.streaming_low_mip、texture.suspicious_format、rendergraph.empty_pass、shader.missing_hash、pipeline.too_many_unique_pso、material.path_redacted。
3. 每个规则结果必须有 evidence。
4. 规则只读 sidecar model，不读取 .rdc，不调用 LLM。
5. 输出 capture.rules.json 或等价 JSON。
6. 加单测覆盖每个规则。

完成后运行测试。输出规则列表、JSON 示例、测试结果、哪些规则是 heuristic。
```

---

## Prompt 6 — Analyzer CLI

```text
你现在实现 Engine Annotation Protocol 的第 6 个任务：EAP Analyzer CLI。

请阅读：
- 02_EAP_PROTOCOL_SPEC.md
- 06_TASK_SIDECAR_WRITER.md
- 07_TASK_RULE_ENGINE_MVP.md
- 08_TASK_ANALYZER_CLI.md

任务：
1. 新增 eap-analyze 命令行工具。
2. 支持 summary、rules、query、export-context、bind 子命令。
3. 支持 JSON 输出和稳定 exit code。
4. rules 子命令调用 RuleEngine。
5. export-context 默认 redacted，限制输出大小。
6. 不读取 .rdc，不联网，不调用 LLM。
7. 加 CLI 单测或 golden file 测试。

完成后运行测试。输出命令用法、示例输出、exit code、CI 示例。
```

---

## Prompt 7 — 最小 UI 或 HTML Report

```text
你现在实现 Engine Annotation Protocol 的第 7 个任务：最小 UI / HTML Report。

请阅读：
- 08_TASK_ANALYZER_CLI.md
- 09_TASK_UI_MINIMAL.md

任务：
1. 优先实现 eap-analyze report，生成 capture_report.html；如果仓库有更合适的 editor panel，也可以实现 editor panel。
2. report 必须包含 capture summary、pass list、rule results、evidence、search index。
3. 默认遵守 redaction policy。
4. 不要深改 qrenderdoc，除非仓库已经有明确 fork 和 UI 集成点。
5. 不要启动 web server，不要上传。

完成后输出 report 生成命令、示例文件路径、已知限制。
```

---

## Prompt 8 — 只读 MCP，后置

```text
你现在实现 Engine Annotation Protocol 的第 8 个任务：只读 MCP Server。确认前置的 sidecar、rule engine、analyzer CLI 已经可用。

请阅读：
- 08_TASK_ANALYZER_CLI.md
- 10_TASK_MCP_READONLY_SERVER.md
- 11_VALIDATION_TEST_SECURITY.md

任务：
1. 新增只读 MCP server，默认 stdio transport。
2. 实现 resources：capture summary、rendergraph、rules、resources、commands、shaders、materials、diagnostics。
3. 实现只读 tools：load_sidecar、summarize_capture、list_passes、search_commands、get_command、get_resource、run_rules、export_context、explain_rule_evidence。
4. 限制读取路径，只允许用户显式传入的 .rmeta.json 或 allowlist 目录。
5. 默认 redaction = project_internal。
6. 记录 audit log。
7. 禁止上传、删除、远程抓帧、创建工单、修改 annotation、读取任意文件。
8. 加测试：合法 sidecar、拒绝非 sidecar、拒绝 path traversal、redaction、audit log。

完成后输出连接方式、tools/resources 列表、安全限制、测试结果。
```

---

## Prompt 9 — 总体验收

```text
你现在做 EAP 总体验收，不新增功能，除非必须修 bug。

请阅读：
- 11_VALIDATION_TEST_SECURITY.md

任务：
1. 跑所有 EAP 单测。
2. 跑可用的集成测试。
3. 生成或更新 Docs/EAP/EAP_STATUS.md。
4. EAP_STATUS.md 必须包含：完成项、未完成项、如何抓帧验证、如何生成 sidecar、如何运行 eap-analyze、性能风险、安全风险、下一步建议。
5. 如果测试不能运行，写清楚原因和需要的环境。

输出：EAP_STATUS.md 路径、测试摘要、阻塞问题。
```

---

## 通用 Codex 约束，每轮都附上

```text
全局约束：
- 不要重写 RenderDoc core。
- 不要修改 RenderDoc 源码，除非任务文档明确要求。
- 无 RenderDoc 时必须 no-op。
- Shipping build 默认禁用。
- 不要联网，不要上传，不要调用外部 LLM。
- 不要把完整资产或 shader source 写入 sidecar。
- 不要在热路径做大量堆分配或字符串格式化。
- 每轮尽量小步提交，保证可编译。
- 如果某字段不可获得，跳过并记录 diagnostics，不要伪造。
- 输出必须包含修改文件清单、测试结果、已知限制。
```

