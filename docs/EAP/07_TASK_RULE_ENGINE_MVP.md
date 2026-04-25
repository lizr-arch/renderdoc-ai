# 07_TASK_RULE_ENGINE_MVP — 任务 5：Rule Engine MVP

目标：实现首批确定性规则，让 sidecar 可以自动诊断常见渲染问题，并给 AI/MCP/CI 提供可信证据。

---

## 1. 输入文档

Codex 本轮必须读取：

- `02_EAP_PROTOCOL_SPEC.md`
- `06_TASK_SIDECAR_WRITER.md`
- 本文件

---

## 2. 设计原则

1. **规则引擎先于大模型。** LLM 只能解释规则结果，不负责凭空判断。
2. **每个规则必须输出 evidence。** 没有 evidence 的结论不输出。
3. **规则输出必须机器可读。** 用于 CI、MCP、Web、bug report。
4. **规则必须可配置阈值。** 不同项目、平台、画质档不同。
5. **首版只基于 sidecar。** 不读取 `.rdc` 二进制。

---

## 3. 推荐文件

```text
Source/Runtime/RenderDocEAP/Public/EAPRuleEngine.h
Source/Runtime/RenderDocEAP/Private/EAPRuleEngine.cpp
Source/Runtime/RenderDocEAP/Private/EAPRuleTexture.cpp
Source/Runtime/RenderDocEAP/Private/EAPRuleStructure.cpp
Source/Runtime/RenderDocEAP/Tests/EAPRuleEngineTests.cpp
Docs/EAP/EAP_RULES.md
```

如果规则引擎用于 CLI，而不是运行时，也可以放在：

```text
Tools/EAPAnalyzer/Rules/
```

首版建议 runtime 和 CLI 共享一个小库。

---

## 4. Rule result schema

```cpp
enum class RuleSeverity {
  Info,
  Warning,
  Error,
  Critical,
};

struct RuleEvidence {
  std::string kind;       // command/resource/pass/shader/material/pipeline/frame
  std::string id;
  std::string key;
  std::string value;
};

struct RuleResult {
  std::string ruleId;
  RuleSeverity severity;
  std::string title;
  std::string message;
  std::vector<RuleEvidence> evidence;
  std::vector<std::string> relatedCommands;
  std::vector<std::string> relatedResources;
  std::string recommendation;
};
```

JSON 输出：

```json
{
  "id": "rule:texture.streaming_low_mip",
  "severity": "warning",
  "title": "Texture resident mip is lower than wanted mip",
  "message": "T_HeroFace_D resident mip is 4 while wanted mip is 2.",
  "evidence": [
    { "kind": "resource", "id": "res:hero_face_d", "key": "streaming.resident_mip", "value": "4" },
    { "kind": "resource", "id": "res:hero_face_d", "key": "streaming.wanted_mip", "value": "2" }
  ],
  "related_commands": ["draw:8251"],
  "related_resources": ["res:hero_face_d"],
  "recommendation": "Check texture streaming budget, residency, or forced mip bias for this asset."
}
```

---

## 5. Rule Engine 接口

```cpp
struct RuleConfig {
  bool enableTextureRules = true;
  bool enableStructureRules = true;
  bool enableShaderRules = true;
  bool enablePerformanceRules = false;

  uint32_t maxAllowedMipDelta = 1;
  uint32_t minPassDrawCountWarning = 0;
  uint32_t maxPermutationKeyLength = 512;
};

struct RuleInput {
  // Prefer typed sidecar model. If unavailable, parse JSON into this model.
  const SidecarModel* sidecar = nullptr;
};

class IRule {
public:
  virtual ~IRule() = default;
  virtual std::string_view Id() const = 0;
  virtual void Evaluate(const RuleInput&, const RuleConfig&, std::vector<RuleResult>& out) = 0;
};

class RuleEngine {
public:
  void RegisterDefaultRules();
  void RegisterRule(std::unique_ptr<IRule> rule);
  std::vector<RuleResult> Evaluate(const RuleInput&, const RuleConfig&);
};
```

---

## 6. 首批规则

### 6.1 `rule:eap.missing_required_context`

检查 command 是否缺少：

- pass id/name；
- cmd kind/index；
- material 或 shader 或 pso 至少一项。

Severity：warning。

输出示例：

```text
Command draw:8251 has no material, shader, or PSO metadata. Hook may be too low-level.
```

### 6.2 `rule:eap.annotation_budget_exceeded`

检查：

- `diagnostics.annotation_budget_exceeded`；
- `command_limit_exceeded`；
- `resource_limit_exceeded`。

Severity：warning / error。

### 6.3 `rule:texture.streaming_low_mip`

条件：

```text
resident_mip - wanted_mip > maxAllowedMipDelta
```

Severity：warning。

推荐：

- 检查 streaming budget；
- 检查 asset forced mip；
- 检查 camera distance / screen size；
- 检查 platform memory profile。

### 6.4 `rule:texture.suspicious_format`

简单格式检查：

- normal map 使用 sRGB；
- albedo 使用非 sRGB；
- UI texture 使用过大未压缩格式；
- HDR target 使用低精度格式。

首版只能用 name/path heuristic：

| name/path 包含 | 期望 |
|---|---|
| `_N`, `Normal`, `NRM` | non-sRGB |
| `_D`, `BaseColor`, `Albedo` | sRGB，除非项目配置另有说明 |
| `HDR`, `SceneColor` | HDR format |

Severity：info/warning。因为 heuristic 可能误报。

### 6.5 `rule:rendergraph.empty_pass`

检查 pass command count 为 0 或小于阈值。

Severity：info/warning。

用于发现：

- pass 被错误剔除；
- pass 名字存在但没有实际 draw；
- render graph 依赖异常。

### 6.6 `rule:shader.missing_hash`

Draw/dispatch 缺少 shader hash 且也缺少 PSO hash。

Severity：warning。

说明：

```text
This capture is less useful for regression analysis because shader/pipeline identity is missing.
```

### 6.7 `rule:pipeline.too_many_unique_pso`

统计 frame 内 unique pso hash 数量。阈值默认只做 info，不阻断。

Severity：info/warning。

用于提示：

- PSO 爆炸；
- shader permutation 过多；
- batching 差。

### 6.8 `rule:material.path_redacted`

当 redaction policy 导致 material/asset path 不可见时，输出 info：

```text
Paths are redacted. Diagnosis can use hashes but cannot show asset paths.
```

---

## 7. 规则配置文件

支持可选 JSON 配置：

```json
{
  "rules": {
    "texture.streaming_low_mip": {
      "enabled": true,
      "max_allowed_mip_delta": 1
    },
    "pipeline.too_many_unique_pso": {
      "enabled": true,
      "warning_threshold": 5000
    }
  }
}
```

如果不实现完整 config parser，首版可硬编码默认值，但接口必须预留。

---

## 8. Sidecar 回写

Rule engine 应把结果写回 sidecar 或生成单独文件：

```text
capture.rmeta.json
capture.rules.json
```

首版推荐生成单独：

```text
capture.rules.json
```

避免修改原始 sidecar。

结构：

```json
{
  "schema": { "name": "EAPRules", "version": 1 },
  "capture_id": "cap:...",
  "sidecar_path": "capture.rmeta.json",
  "results": []
}
```

---

## 9. 单测要求

1. 空 sidecar 不崩溃；
2. missing context 规则命中；
3. texture low mip 规则命中；
4. wanted/resident mip 差值 <= 阈值不命中；
5. suspicious format heuristic 命中 normal+sRGB；
6. empty pass 命中；
7. redaction info 命中；
8. severity JSON 序列化正确；
9. evidence 包含 id/key/value。

---

## 10. Codex 禁止事项

- 不要让规则读取 `.rdc`；
- 不要调用 LLM；
- 不要输出没有 evidence 的强结论；
- 不要把 heuristic 规则标成 error/critical；
- 不要把规则失败变成游戏运行失败；
- 不要在 render hot path 跑规则，除非用户明确开启。

---

## 11. 本轮完成输出

Codex 最终输出：

1. 规则列表；
2. 规则输入/输出结构；
3. 规则 JSON 示例；
4. 单测结果；
5. 哪些规则是 heuristic；
6. 下一轮进入 `08_TASK_ANALYZER_CLI.md`。

