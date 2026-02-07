# Messiah 导入现状与下一步（2026-02-08）

## 1. 当前已具备能力

- 已有导出脚本：scripts/rdc_analyzer/export_messiah_assets.py
- 已有导出器：scripts/rdc_analyzer/exporters/messiah_exporter.py
- 导出入口：scripts/rdc_analyzer/export_messiah_from_bundle.py （import_bundle -> messiah）
- 适配层：scripts/rdc_analyzer/exporters/messiah_bundle_adapter.py
- 当前输入：event_<id>/import_bundle
- 当前输出：<out>/messiah/Package/Repository/rdc_event_<id>.local

该导出器目前可生成：
- Mesh 资源：resource.xml + resource.data
- Texture 资源：texture.xml + resource.data
- Material 资源：resource.xml
- Model 资源：resource.xml
- Repository 索引：resource.repository
- 对齐元数据：import_bundle_mapping.json

## 2. 与 Import Bundle 流水线的关系

离线单 event 主链路：
- extract_event_intermediate.py
- export_event_import_bundle.py
- export_event_import_bundle_batch.py

其中 import_bundle 作为引擎无关中间态，Messiah 导入器消费其 mesh/materials/textures 子目录完成资源落盘。

## 3. 本轮新增（Phase-1.5）

- 材质模板自动推断：根据 shader stage + 纹理槽位提示，在 Unlit/PBR 间选择。
- 材质多纹理参数映射：支持 tBaseMap/tNormalMap/tPBRMap/tEmissiveMap/tExtraMap*。
- 纹理导出对齐元数据：导出与缺失纹理分别记录到 import_bundle_mapping.json，用于后续修复与跨引擎转换。
- 兼容 png/bin 纹理资源输入，缺失纹理不阻断 Mesh/Model 导出。

## 4. 当前边界与下一步

- 当前仍是单 material 主路径（优先首个 material）。
- Shader 代码仍以中间态/元数据驱动，未直接产出 Messiah 可执行 shader 资产。
- 下一步建议：
  1. 多 material / 多 submesh 导入。
  2. 参数语义字典（Unity/UE/Messiah）统一映射。
  3. 将 import_bundle_mapping.json 接入后续 FBX/引擎侧转换器。

## 5. 已补齐验证

- scripts/rdc_analyzer/tests/test_messiah_bundle_adapter.py
- scripts/rdc_analyzer/tests/test_export_messiah_from_bundle.py
- scripts/rdc_analyzer/tests/test_messiah_material_multi_texture.py
