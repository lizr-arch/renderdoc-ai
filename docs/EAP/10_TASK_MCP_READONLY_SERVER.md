# 10_TASK_MCP_READONLY_SERVER — 任务 8：只读 MCP Server，后置

目标：在 EAP sidecar、规则引擎、Analyzer CLI 稳定后，实现一个只读 MCP server，让本地大模型可以查询 capture 结构化数据。

---

## 1. 前置条件

必须先完成：

- RenderDocBridge；
- EAP core types；
- engine hooks；
- sidecar writer；
- rule engine；
- analyzer CLI。

没有这些前置，不要做 MCP。否则大模型只能猜。

当前 RenderDoc repo 的实现只推进 read-only MCP consumption 的 tooling 子集：它只读取用户显式传入且
allowlist 允许的 `.rmeta.json`，并用 synthetic fixtures 验收 summary/search/rule-result 行为。
本 repo 没有真实 engine-produced `capture.rmeta.json`，也不要声明真实 EAP capture 已接通。

真实验收 gate 是未来拿到同名或明确绑定的 `<capture>.rdc` + `<capture>.rmeta.json` 后，validator、
rules、MCP summary、MCP search 全部通过。

---

## 2. 安全原则

1. 首版 MCP **只读**。
2. 不提供上传、删除、远程抓帧、创建工单、修改 annotation 等写操作。
3. 默认只读取用户显式传入的 sidecar 路径。
4. 默认不读取 `.rdc` 二进制。
5. 默认使用 stdio transport；若使用 HTTP，只绑定 localhost，并要求 token。
6. 所有 tool 调用记录 audit log。
7. 输出默认 redacted。

---

## 3. MCP 资源设计

Resources：

```text
capture://current/summary
capture://current/rendergraph
capture://current/rules
capture://current/resources
capture://current/commands
capture://current/shaders
capture://current/materials
capture://current/diagnostics

pass://{pass_id}/summary
command://{command_id}/summary
resource://{resource_id}/summary
shader://{shader_id}/summary
material://{material_id}/summary
```

---

## 4. MCP tools 设计，只读

| Tool | 输入 | 输出 |
|---|---|---|
| `load_sidecar` | path, redaction_policy | capture summary |
| `summarize_capture` | none | summary |
| `list_passes` | filter, limit | pass list |
| `search_commands` | query/material/pass/resource/shader/pso | command list |
| `get_command` | command_id | command detail |
| `get_resource` | resource_id | resource detail |
| `run_rules` | config optional | rule results |
| `export_context` | redaction, limits | compressed LLM context |
| `explain_rule_evidence` | rule_id | evidence summary |

Current RenderDoc tooling names are intentionally explicit and stateless:

| Tool | 输入 | 当前验收 |
|---|---|---|
| `load_eap_sidecar` | path, max_bytes | Synthetic fixture load + Data Availability |
| `summarize_eap_sidecar` | path, max_bytes | Synthetic fixture counts/summary |
| `search_eap_commands` | path, query/pass/resource/material/shader/pipeline, limit | Synthetic fixture command search |
| `get_eap_rule_results` | path, severity, limit | Synthetic fixture `rules.results` filter |

These tools do not persist capture state, do not parse `.rdc`, and do not expose the raw full sidecar
payload.

禁止首版实现：

| Tool | 原因 |
|---|---|
| `upload_capture` | 有泄露风险 |
| `remote_capture` | 有副作用 |
| `create_issue` | 有外部系统写入 |
| `delete_capture` | 破坏性操作 |
| `modify_annotation` | 修改证据 |
| `open_arbitrary_file` | 文件越权 |

---

## 5. 推荐实现方式

首版可以不写复杂 C++。选择：

- Python MCP server，调用 `eap-analyze`；或
- Node/TypeScript MCP server，调用 `eap-analyze`；或
- C++ JSON-RPC server。

如果本地 Codex 在引擎 C++ 仓库中工作，推荐先生成：

```text
Tools/EAPMCPServer/
  README.md
  server.py 或 server.ts
  schema.md
```

---

## 6. 输入限制

`load_sidecar(path)` 必须：

- 只允许 `.rmeta.json`；
- 文件大小默认不超过 256MB；
- path 必须是用户显式传入，或者位于 allowlist 目录；
- 不展开 symlink 到 allowlist 外；
- 不执行任何路径中的命令。

---

## 7. 输出限制

默认 redaction：`project_internal`。

LLM context 限制：

| 项 | 默认上限 |
|---|---:|
| tokens approximate | 16k |
| pass count | 30 |
| rule count | 50 |
| command count | 100 |
| resource count | 100 |
| string length | 256 |

---

## 8. Prompt 模板

MCP server 可以暴露 prompts：

```text
diagnose_visual_bug
explain_pixel_placeholder
performance_triage_from_sidecar
summarize_capture_for_qa
compare_regression_placeholder
```

首版 `explain_pixel` 和 `compare_regression` 如果没有 pixel history / diff 数据，必须明确说明能力不足，不要伪造。

---

## 9. 示例 LLM 输出要求

模型回答必须引用 evidence：

```text
结论：疑似 texture streaming 低 mip。
证据：resource res:hero_face_d 的 resident_mip=4，wanted_mip=2；相关 command 为 draw:8251；材质为 mat:hero_face。
建议：检查 CharacterTextures budget、平台 memory profile、该资产 forced mip 设置。
```

禁止：

```text
可能是 shader 有问题。
```

除非有 shader evidence。

---

## 10. 测试要求

1. 加载合法 sidecar；
2. 拒绝非 sidecar 文件；
3. 拒绝超大文件；
4. search commands 正常；
5. run rules 正常；
6. export context redacted；
7. path traversal 被拒绝；
8. 无 sidecar 时 tools 返回明确错误；
9. audit log 记录 tool name、时间、path hash。

---

## 11. Codex 禁止事项

- 不要默认联网；
- 不要调用外部大模型 API；
- 不要开放写操作；
- 不要读取任意文件；
- 不要绕过 redaction；
- 不要实现远程 capture；
- 不要把 MCP server 作为后台常驻服务自动启动。

---

## 12. 本轮完成输出

Codex 最终输出：

1. MCP server 目录；
2. tools/resources 列表；
3. 安全限制；
4. 测试结果；
5. 如何用本地 Codex/Claude/其它 MCP client 连接。

