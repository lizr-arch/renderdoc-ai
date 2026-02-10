# Skill 设计规范：RDC Event Asset Orchestrator

> 文档类型：Skill Spec（设计稿）  
> 更新日期：2026-02-10  
> 目标：把“单 Event 资产导出闭环”封装成可复用 Skill，复用现有脚本而不是重写逻辑。

---

## 1. Skill 定位

**名称建议**：`rdc-event-asset-orchestrator`  
**一句话**：输入 event 与捕获文件（或中间态），输出可导入引擎的资产包（Mesh/Texture/Shader/Material + 索引清单）。

### 1.1 设计原则

- Orchestrator-first：编排已有脚本。
- Script-authoritative：数据由脚本生成，AI 只做语义增强。
- Schema-first：所有结构化输出必须可校验。

---

## 2. 触发场景（Trigger）

- “把某个 event 导出成可导入 Unity/Unreal 的资源包”
- “我已经有 xml/zip 或 intermediate，直接生成 mesh/material/shader/textures”
- “批量挑选高价值 event 并导出，再给出失败重试建议”

---

## 3. 输入契约（Input Contract）

### 3.1 必选参数

```json
{
  "event_id": 22149,
  "out_dir": "D:/backup/export_out"
}
```

### 3.2 三选一输入源

```json
{
  "rdc_path": "D:/backup/sample.rdc"
}
```

或

```json
{
  "xml_path": "D:/backup/sample_export.zip.xml",
  "zip_path": "D:/backup/sample_export.zip"
}
```

或

```json
{
  "intermediate_dir": "D:/backup/event_22149/intermediate"
}
```

### 3.3 可选参数

- `engine_targets`: `["unity", "unreal", "messiah"]`
- `rgba_manifest_path`: 外部纹理 RGBA 覆盖清单
- `scan_json_path`: 批处理/自动选点输入
- `tools`: `spirv_cross/fxc/dxc` 显式路径
- `strict_mode`: 严格失败模式（默认 false）

---

## 4. 输出契约（Output Contract）

### 4.1 目录结构

```text
<out>/event_<id>/
  intermediate/              # 如输入已是 intermediate，可标记 reused
  import_bundle/
    bundle_manifest.json
    mesh/mesh.obj
    materials/materials.json
    shaders/*
    textures/*
  fbx/
    unity/*
    unreal/*
  artifact_index.json
```

### 4.2 核心索引：`artifact_index.json`

```json
{
  "schema_version": "1.0",
  "event_id": 22149,
  "api": "Vulkan",
  "stages": [
    {"name": "extract_intermediate", "status": "ok"},
    {"name": "export_import_bundle", "status": "ok"},
    {"name": "export_fbx_assets", "status": "ok"}
  ],
  "artifacts": {
    "mesh": "event_22149/import_bundle/mesh/mesh.obj",
    "materials": "event_22149/import_bundle/materials/materials.json",
    "shaders": "event_22149/fbx/unity/shader_import_plan.json",
    "textures": "event_22149/import_bundle/textures"
  },
  "status_counts": {
    "shader": {"converted": 3, "reconstructed_hlsl": 1, "manual_review": 0},
    "texture": {"decoded_rgba8_png": 5, "raw_copy": 1, "missing_source": 0}
  }
}
```

> 建议新增 schema：`scripts/rdc_analyzer/schema/artifact_index.schema.json`（本 spec 阶段先定义，不在本轮实现）。

---

## 5. 执行阶段（Pipeline）

### Stage S0: Precheck

- 校验输入组合是否合法（rdc/xml+zip/intermediate 三选一）。
- 校验 `event_id`、输出目录可写、外部工具探测。

### Stage S1: Intermediate

- 若已有 `intermediate_dir`：标记 `reused`。
- 否则调用 `extract_event_intermediate.py` 生成中间态。

### Stage S2: Import Bundle

- 调用 `export_event_import_bundle.py`。
- 若提供 `rgba_manifest_path`，注入 RGBA bytes 覆盖。

### Stage S3: FBX Assets

- 调用 `export_fbx_assets.py`。
- 汇总 shader plan 状态（converted/reconstructed_hlsl/manual_review 等）。

### Stage S4: Verify & Index

- 聚合各阶段状态，生成 `artifact_index.json`。
- 输出可重跑命令与失败原因（可机器读）。

### Stage S5（可选）: AI Enrichment

- 读取导出产物，补充语义标签（材质槽位建议、命名建议）。
- 不修改核心导出数据，仅追加 sidecar 建议文件。

---

## 6. 失败策略

### 6.1 可恢复错误（Retryable）

- 外部工具路径缺失（spirv-cross/fxc/dxc）
- 部分纹理 payload 缺失，但可继续 raw fallback
- 单阶段超时（支持单阶段重跑）

### 6.2 不可恢复错误（Non-retryable）

- 输入文件缺失或损坏
- schema 严重不匹配
- event 不存在或与 api 不兼容

### 6.3 降级策略

- FBX 阶段失败时保底保留 `import_bundle/` 与 `obj/`。
- Shader 转换失败时输出原始二进制与状态码，不中断全部流程（除 strict 模式）。

---

## 7. 与 Unity / Unreal / Messiah 的关系

- **Unity/Unreal**：先统一走 OBJ 中间态，再由 FBX 层做坐标系与目录适配。
- **Messiah**：优先消费 `import_bundle/`（mesh/material/texture/shader），后续追加专用 adapter。
- 统一原则：中间态契约稳定，引擎适配层可独立迭代。

---

## 8. 实施拆分建议（供后续 /do）

1. M1：实现 orchestrator CLI（仅串联 S0-S4，不加 AI）。
2. M2：引入 `artifact_index.schema.json` 并接入验证。
3. M3：增加 AI enrichment sidecar（非阻断）。
4. M4：扩展 batch orchestrator 与 scan 选点联动。

---

## 9. 验收标准（Definition of Done）

- 同一 event 输入可稳定复现同一目录结构与关键 JSON 字段。
- `artifact_index.json` 可准确反映各阶段成功/失败。
- 在无 FBX 后端场景下仍可得到可消费的 `import_bundle/`。
- 所有失败都有 machine-readable status 与可重跑建议。
