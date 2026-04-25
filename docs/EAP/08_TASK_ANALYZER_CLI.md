# 08_TASK_ANALYZER_CLI — 任务 6：EAP Analyzer CLI

目标：实现一个本地命令行工具，用来读取 `*.rmeta.json` sidecar、运行规则、输出摘要和 JSON 报告。  
该 CLI 是后续 CI、MCP、Capture Hub、AI 的第一层入口。

---

## 1. 输入文档

Codex 本轮必须读取：

- `02_EAP_PROTOCOL_SPEC.md`
- `06_TASK_SIDECAR_WRITER.md`
- `07_TASK_RULE_ENGINE_MVP.md`
- 本文件

---

## 2. CLI 名称

推荐：

```text
eap-analyze
```

如果仓库已有命名规范，可以使用：

```text
renderdoc-eap-analyze
company-renderdoc-analyze
```

---

## 3. 推荐目录

```text
Tools/EAPAnalyzer/
  main.cpp
  EAPAnalyzerCli.cpp
  EAPAnalyzerCli.h
  README.md
```

如果仓库有 tools build system，接入现有 tools。

---

## 4. 命令设计

### 4.1 Summary

```bash
eap-analyze summary capture.rmeta.json
```

输出人类可读：

```text
EAP Capture Summary
- Project: ProjectA main abc123
- Frame: 1942 City_Day_03
- API: D3D12 Windows NVIDIA
- Passes: 42
- Commands: 18,240
- Resources: 3,812
- Materials: 1,220
- Shaders: 542
- Diagnostics: annotation budget ok
Top passes by command count:
  1. BasePass/Opaque: 8,451
  2. ShadowDepth: 4,210
  3. UI: 1,320
```

### 4.2 Rules

```bash
eap-analyze rules capture.rmeta.json --output capture.rules.json
```

输出：

- stdout 人类摘要；
- `capture.rules.json` 机器可读结果。

### 4.3 Query

```bash
eap-analyze query capture.rmeta.json --material M_HeroFace
eap-analyze query capture.rmeta.json --pass BasePass
eap-analyze query capture.rmeta.json --resource T_HeroFace_D
```

首版可以只支持简单 substring 搜索。

### 4.4 Export minimal MCP context

```bash
eap-analyze export-context capture.rmeta.json --output capture.context.json
```

输出给 MCP/LLM 的压缩上下文，不含敏感路径，默认 redacted：

```json
{
  "summary": {},
  "top_passes": [],
  "rule_results": [],
  "interesting_commands": [],
  "interesting_resources": []
}
```

### 4.5 Bind RDC path

如果 sidecar 没绑定 capture：

```bash
eap-analyze bind --sidecar last_frame.rmeta.json --rdc foo.rdc --output foo.rmeta.json
```

---

## 5. Exit code

CI 需要稳定 exit code：

| Exit code | 含义 |
|---:|---|
| 0 | 成功，无 error/critical 规则 |
| 1 | 有 error/critical 规则 |
| 2 | 输入文件不存在或 parse 失败 |
| 3 | 参数错误 |
| 4 | 内部错误 |

Warning 不应默认返回 1，除非用户传：

```bash
--fail-on warning
```

---

## 6. 参数

```text
Usage:
  eap-analyze summary <sidecar>
  eap-analyze rules <sidecar> [--config rules.json] [--output out.json] [--fail-on warning|error|critical]
  eap-analyze query <sidecar> [--pass text] [--material text] [--resource text] [--shader text] [--limit N]
  eap-analyze export-context <sidecar> [--rules rules.json] [--output out.json] [--redaction project_internal|cross_project|external_vendor]
  eap-analyze bind --sidecar file.rmeta.json --rdc file.rdc [--output out.rmeta.json]
```

---

## 7. Parser 要求

首版 parser 可以只解析 EAP v1 sidecar 所需字段。要求：

- JSON parse 失败给明确错误；
- schema version 不支持时给明确错误；
- 缺少 optional 字段不崩溃；
- 缺少 schema/version 时警告但尝试解析；
- 不读取 `.rdc`。

---

## 8. 输出 JSON

### 8.1 Summary JSON

```bash
eap-analyze summary capture.rmeta.json --json
```

输出：

```json
{
  "project": "ProjectA",
  "frame_index": 1942,
  "pass_count": 42,
  "command_count": 18240,
  "resource_count": 3812,
  "material_count": 1220,
  "shader_count": 542,
  "top_passes_by_command_count": [
    { "id": "pass:base_opaque", "name": "BasePass/Opaque", "command_count": 8451 }
  ],
  "diagnostics": {
    "annotation_budget_exceeded": false
  }
}
```

### 8.2 Rules JSON

见 `07_TASK_RULE_ENGINE_MVP.md`。

---

## 9. Query 输出

示例：

```bash
eap-analyze query foo.rmeta.json --material HeroFace --limit 5
```

输出：

```text
Found 3 matching commands:
- draw:8251 pass=BasePass/Opaque material=/Game/Characters/Hero/M_HeroFace mesh=SK_Hero_Head lod=1 pso=0x...
- draw:8252 pass=BasePass/Opaque material=/Game/Characters/Hero/M_HeroFace mesh=SK_Hero_Body lod=0 pso=0x...

Related resources:
- res:hero_face_d T_HeroFace_D BC7_UNORM_SRGB 2048x2048 mips=12 resident=4 wanted=2
```

---

## 10. Redacted context export

该命令为 AI/MCP 准备上下文。默认不输出完整路径，除非用户指定：

```bash
--redaction local_full
```

上下文必须控制大小：

| 项 | 默认上限 |
|---|---:|
| top passes | 20 |
| rule results | 50 |
| commands | 100 |
| resources | 100 |
| string length | 256 |

---

## 11. README

新增 `Tools/EAPAnalyzer/README.md`：

内容包括：

- 用法；
- sidecar 示例；
- exit code；
- CI 示例；
- redaction 提醒。

CI 示例：

```bash
eap-analyze rules artifacts/capture.rmeta.json --output artifacts/capture.rules.json --fail-on error
```

---

## 12. 单测要求

1. `summary` 解析最小 sidecar；
2. `rules` 输出 rules JSON；
3. `query --material` 找到命令；
4. `query --resource` 找到资源；
5. `export-context` redaction 生效；
6. 输入文件不存在 exit code 2；
7. 参数错误 exit code 3；
8. warning 不默认失败；
9. `--fail-on warning` 时 warning 返回 1。

---

## 13. Codex 禁止事项

- 不要联网；
- 不要上传 capture；
- 不要读取 `.rdc`；
- 不要把 CLI 写成只能人工读，必须支持 JSON；
- 不要把 warning 默认作为失败；
- 不要调用 LLM。

---

## 14. 本轮完成输出

Codex 最终输出：

1. CLI 命令列表；
2. 示例输出；
3. 单测结果；
4. CI 使用方式；
5. 下一轮进入 `09_TASK_UI_MINIMAL.md` 或 `10_TASK_MCP_READONLY_SERVER.md`。

