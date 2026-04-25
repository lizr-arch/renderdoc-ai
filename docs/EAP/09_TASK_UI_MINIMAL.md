# 09_TASK_UI_MINIMAL — 任务 7：最小 UI / 调试面板

目标：在不大改 qrenderdoc 的前提下，先做一个最小可用的 EAP 查看入口，让开发者能看到 sidecar 摘要、规则结果和查询结果。

---

## 1. 输入文档

Codex 本轮必须读取：

- `06_TASK_SIDECAR_WRITER.md`
- `07_TASK_RULE_ENGINE_MVP.md`
- `08_TASK_ANALYZER_CLI.md`
- 本文件

---

## 2. 推荐路线

第一阶段不要深改 RenderDoc UI。优先做：

1. 引擎 editor 内 EAP 面板；或
2. 独立小工具；或
3. CLI + HTML report。

如果公司已经 fork qrenderdoc，才考虑在 qrenderdoc 内加 sidecar panel。

---

## 3. 最小 UI 功能

### 3.1 Capture Summary

显示：

- 项目、分支、commit、build；
- 平台、API、GPU、driver；
- frame、map、camera；
- pass 数；
- command 数；
- resource 数；
- diagnostics。

### 3.2 RenderGraph Pass List

表格：

| Pass | Category | Queue | Commands | Inputs | Outputs |
|---|---|---|---:|---:|---:|

支持按 pass 名称过滤。

### 3.3 Rule Results

表格：

| Severity | Rule | Title | Related |
|---|---|---|---|

点击 rule 展开 evidence。

### 3.4 Search

支持：

- material substring；
- resource substring；
- pass substring；
- shader hash；
- pso hash。

### 3.5 Open in RenderDoc

如果本机安装 RenderDoc 且 sidecar 绑定了 `.rdc`，提供按钮：

```text
Open RDC in RenderDoc
```

不要自动上传。

---

## 4. HTML report 方案

如果 UI 框架复杂，首版实现：

```bash
eap-analyze report capture.rmeta.json --rules capture.rules.json --output capture_report.html
```

HTML 内容：

- summary；
- rule results；
- top passes；
- suspicious resources；
- search index；
- raw JSON 折叠区。

优点：

- 开发快；
- QA/TA 可打开；
- 不依赖 qrenderdoc；
- 可以附到 bug 单。

---

## 5. qrenderdoc 内嵌方案，后置

如果决定改 qrenderdoc，建议新增：

```text
qrenderdoc/Windows/Custom/EAPPanel.*
qrenderdoc/Code/Interface/EAPSidecarModel.*
```

功能：

1. 打开 `.rdc` 时查找同名 `.rmeta.json`；
2. 显示 sidecar summary；
3. 显示 rule results；
4. 点击 related command 时跳转 event id。

注意：sidecar 的 `draw:8251` 不一定等于 RenderDoc event id。首版只能做文本关联；后续需要 event mapping。

---

## 6. Event mapping 后置设计

首版可在 sidecar command 中保存：

```json
"renderdoc_event_id": null
```

后续实现两种映射：

1. 通过 annotation key 在 RenderDoc replay 中查事件；
2. 在 capture 后用 replay API 解析 event tree，建立 `cmd.index -> eventId`。

本轮不要求实现。

---

## 7. Codex 禁止事项

- 不要为了 UI 重写 qrenderdoc；
- 不要引入 web server；
- 不要自动上传 report；
- 不要假设 `draw:8251 == RenderDoc event id`；
- 不要让 UI parse 失败导致 RenderDoc 打不开 capture；
- 不要输出敏感路径到 external report，除非 redaction policy 允许。

---

## 8. 验收标准

至少交付一个：

- editor panel；或
- standalone tool；或
- HTML report。

必须能显示：

1. capture summary；
2. pass list；
3. rule results；
4. evidence；
5. search result。

---

## 9. 本轮完成输出

Codex 最终输出：

- UI/report 入口；
- 生成命令；
- 示例截图路径或 HTML 文件路径；
- 已知限制；
- 是否需要 qrenderdoc 深度集成。

