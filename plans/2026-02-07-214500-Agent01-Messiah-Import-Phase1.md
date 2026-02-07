# Plan: Messiah Import Phase-1（基于 Import Bundle）

- Date: 2026-02-07
- Agent: Agent01
- Branch: v1.x
- Stage: /plan
- Scope: 在现有 event_<id>/import_bundle 基础上，补齐可直接喂给 Messiah 资源仓库的导入路径，优先完成单 event 可加载。

---

## 1. 现状与证据

1. 现有导出链路（已完成）
   - export_event_import_bundle.py 能输出 mesh/mesh.obj、materials/materials.json、shaders/*、textures/*、bundle_manifest.json。
   - 结构校验已覆盖 import_bundle_manifest.schema.json、import_bundle_materials.schema.json、batch_import_bundle_summary.schema.json。

2. 现有 Messiah 导出器（已存在）
   - scripts/rdc_analyzer/export_messiah_assets.py。
   - scripts/rdc_analyzer/exporters/messiah_exporter.py 当前输入是 intermediate（依赖 vertex.bin/index.bin/material.json）。

3. 当前缺口
   - Import Bundle -> Messiah 还没有直连入口。
   - import_bundle/mesh/mesh.obj 与 Messiah 当前需要的 resource.data（vertex/index stream）之间缺少转换层。
   - 材质目前是最小模板绑定，尚未按 materials.json 完整映射 sampler/texture slot。

---

## 2. 目标与 DoD

### 2.1 目标

- 新增一条入口：import_bundle -> messiah repository。
- 输入：event_<id>/import_bundle。
- 输出：messiah/Package/Repository/rdc_event_<id>.local（Mesh/Texture/Material/Model + resource.repository）。

### 2.2 DoD

- [ ] 能从 import_bundle 读取 mesh/material/texture/shader 元数据并生成 Messiah repo。
- [ ] 至少 1 个真实 event（Vulkan）导出后目录完整，GUID 引用闭环。
- [ ] 新增最小 schema/字段校验（入口参数 + manifest 核心字段）。
- [ ] 增加 2 组自动化测试（最小样例 + 缺字段失败样例）。

---

## 3. 实施拆分（2-5 分钟粒度）

- [ ] Task 1: 新增入口脚本 export_messiah_from_bundle.py
  - 参数：--bundle、--out、--event（可选）。
  - 行为：读取 bundle_manifest.json 与 materials/materials.json，驱动后续转换。

- [ ] Task 2: 增加 Bundle 读取层（解析器）
  - 新文件：scripts/rdc_analyzer/exporters/messiah_bundle_adapter.py。
  - 输出统一中间对象：MeshSource/MaterialSource/TextureSource。

- [ ] Task 3: Mesh 转换（Phase-1 简化）
  - 先支持 OBJ（三角面 + position/normal/uv），生成 Messiah resource.data。
  - 缺失法线/切线时按策略补默认值并记录 warning。

- [ ] Task 4: 纹理与材质映射
  - 纹理：优先 PNG，回退 bin（标记 unresolved）。
  - 材质：按 materials.json 绑定主纹理到 tBaseMap；后续扩展多槽位映射。

- [ ] Task 5: 结果校验与测试
  - 新增 test_messiah_bundle_adapter.py（样例输入 -> 资源计数正确）。
  - 新增 test_export_messiah_from_bundle.py（CLI smoke + 缺字段失败）。

---

## 4. 风险与应对

1. OBJ 到 Messiah stream 格式映射风险
   - 应对：Phase-1 先支持最小顶点布局（P3F_N4B_T2F），其余字段默认填充。

2. 纹理格式风险（raw/bin 无法直接用于 texture.xml）
   - 应对：Phase-1 仅承诺 PNG 直通；raw 标注 unresolved 并继续导出其余资源。

3. Shader 汇编到材质模板映射不完备
   - 应对：先固定 Unlit/PBR 基础模板，保留 shader 元数据用于后续规则扩展。

---

## 5. 验证命令（记录）

- py -3 -m py_compile scripts/rdc_analyzer/export_messiah_from_bundle.py scripts/rdc_analyzer/exporters/messiah_bundle_adapter.py
- py -3 -m pytest scripts/rdc_analyzer/tests/test_messiah_bundle_adapter.py scripts/rdc_analyzer/tests/test_export_messiah_from_bundle.py -q

---

## 6. Next Step

进入 /do：先完成 Task 1 + Task 2（入口和解析层），用最小样例跑通后再补 Mesh/Material 细节。
