# Messiah 导入现状与下一步（2026-02-07）

## 1. 当前已具备能力

- 已有导出脚本：scripts/rdc_analyzer/export_messiah_assets.py
- 已有导出器：scripts/rdc_analyzer/exporters/messiah_exporter.py
- 当前输入：event_<id>/intermediate
- 当前输出：<out>/messiah/Package/Repository/rdc_event_<id>.local

该导出器目前可生成：
- Mesh 资源（resource.xml + resource.data）
- Texture 资源（texture.xml + resource.data）
- Material 资源（resource.xml）
- Model 资源（resource.xml）
- repository 索引（resource.repository）

## 2. 与最新 Import Bundle 流水线的关系

离线单 event 的主链路已经切到：
- extract_event_intermediate.py
- export_event_import_bundle.py
- export_event_import_bundle_batch.py

其中 import_bundle 已是对引擎友好的中间资产包，但当前 Messiah 导出器仍直接消费 intermediate。

## 3. 当前核心缺口

- 缺少 import_bundle -> messiah 直连入口。
- 缺少 mesh.obj -> Messiah resource.data 的转换层。
- 缺少 materials/materials.json 到 Messiah 多纹理材质参数的映射规则。

## 4. Phase-1 实施建议

- 先做最小闭环：单 event、OBJ mesh、主纹理绑定（tBaseMap）。
- 纹理优先 PNG 直通；raw/bin 仅标记 unresolved，不阻断 Mesh/Model 导出。
- 把入口与转换适配器独立出来，避免侵入现有 intermediate 导出器。

对应计划文档：
- plans/2026-02-07-214500-Agent01-Messiah-Import-Phase1.md
