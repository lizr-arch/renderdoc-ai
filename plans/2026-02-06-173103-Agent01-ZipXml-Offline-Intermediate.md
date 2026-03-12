# ZipXML Offline Intermediate Extraction Plan (Single Event)

Version: 1.0.0
Owner: Agent01 (Codex)
Created: 2026-02-06 17:31:03
Status: /do completed (Task 1-6 done)

## Scope

In:
- 从 capture.zip.xml + capture.zip 离线提取单个 eventId 的 Mesh/Material/Shader/Texture 中间态。
- 输出 intermediate/ 目录，结构兼容现有 export_fbx_assets.py。
- 保持无 GPU / 无回放路径可用。

Out:
- 不实现多事件批处理。
- 不实现 FBX SDK/C++ CLI 构建。
- 不实现复杂纹理布局反解码（仅接入已有 RGBA 解码器与原始 bytes）。

## Assumptions

- 输入 zip.xml 为 chunk 结构（<rdc><chunks><chunk ...>），不包含 <event> 标签。
- 目标 API 先覆盖 Vulkan + D3D11；D3D12/GLES 先预留钩子。
- 纹理输出优先 RGBA8；解码失败时回退原始 bytes 并记录 manifest。

## Navigation Evidence (Required)

### codemap queries used
1. codemap -Repo renderdoc 'zip.xml' -Num 20
2. codemap -Repo renderdoc 'extract_event_state' -Num 20
3. codemap -Repo renderdoc 'write_intermediate' -Num 20

### Candidate hits
- [renderdoc] renderdoc/serialise/codecs/xml_codec.cpp:1162 — "zip.xml"（zip.xml codec 注册点）
- [renderdoc] renderdoccmd/renderdoccmd.cpp:1511 — .zip.xml 优先匹配注释（输入分支判定）
- [renderdoc] util/test/rdtest/testcase.py:955 — Convert(..., 'zip.xml', ...)（官方测试中 zip.xml 转换路径）

### Follow-up targets and why
- scripts/rdc_analyzer/analyze_xml_report.py:176（_convert_rdc_to_zipxml）：确认当前 zip.xml 资产生成与路径规则。
- scripts/rdc_analyzer/xmlzip_event_extractor.py:76（extract_event_state）：当前逻辑依赖 <event>，是根因分叉点。

### Next step (OpenGrok / Serena)
- OpenGrok: http://127.0.0.1:8080/source/xref/renderdoc/renderdoc/serialise/codecs/xml_codec.cpp#1162
- OpenGrok: http://127.0.0.1:8080/source/xref/renderdoc/renderdoccmd/renderdoccmd.cpp#1511
- Serena query: find_symbol(name_path_pattern="extract_event_state", relative_path="scripts/rdc_analyzer/xmlzip_event_extractor.py")

## Repo / File List (line-focused)

Modify:
- scripts/rdc_analyzer/xmlzip_event_extractor.py:16（EventState 数据结构扩展）
- scripts/rdc_analyzer/xmlzip_event_extractor.py:76（替换 <event> 依赖，改为 chunk 解析入口）
- scripts/rdc_analyzer/xmlzip_event_extractor.py:104（write_intermediate 写入真实 schema 字段）
- scripts/rdc_analyzer/analyze_xml_report.py:176（复用 zip.xml 资产定位逻辑）
- scripts/rdc_analyzer/docs/INDEX.md:1（增加离线事件提取文档入口）
- plans/2026-02-04-150000-Agent01-FBX-Export-Pipeline.md:322（同步风险闭环/勾选）

Create:
- scripts/rdc_analyzer/parsers/zipxml_event_parser.py
- scripts/rdc_analyzer/extract_event_intermediate.py
- scripts/rdc_analyzer/tests/test_zipxml_event_parser.py
- scripts/rdc_analyzer/tests/test_extract_event_intermediate.py
- scripts/rdc_analyzer/docs/ZIPXML_EVENT_EXTRACTION.md

## Build/Test/Lint Quick Guide (commands only, not executed in /plan)

- py -3 -m pytest scripts/rdc_analyzer/tests/test_zipxml_event_parser.py -v --tb=short
  预期：PASS
- py -3 -m pytest scripts/rdc_analyzer/tests/test_extract_event_intermediate.py -v --tb=short
  预期：PASS
- py -3 -m pytest scripts/rdc_analyzer/tests/test_xmlzip_event_extractor.py -v --tb=short
  预期：PASS
- py -3 -m py_compile scripts/rdc_analyzer/parsers/zipxml_event_parser.py
  预期：无输出（成功）
- py -3 scripts/rdc_analyzer/extract_event_intermediate.py --xml D:ackup\大远景_export.zip.xml --zip D:ackup\大远景_export.zip --event <id> --out D:ackup\endfield_event_extract
  预期：生成 intermediate/mesh|materials|shaders|textures 与 manifest.json

## Approach (Pseudo-code)

A. 新增 zip.xml 事件解析器（chunk 语义）

    from dataclasses import dataclass
    import xml.etree.ElementTree as ET

    @dataclass
    class DrawEvent:
        event_id: int
        chunk_index: int
        name: str
        api: str

    def iter_draw_events(xml_path: str):
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for chunk in root.findall('.//chunk'):
            name = chunk.get('name', '')
            if 'Draw' in name or 'Dispatch' in name:
                yield DrawEvent(
                    event_id=int(chunk.get('chunkIndex', '0')),
                    chunk_index=int(chunk.get('chunkIndex', '0')),
                    name=name,
                    api=_detect_api(root),
                )

B. 资源绑定解析（VB/IB/Texture/Shader）

    def extract_event_resources(xml_path: str, event_id: int) -> dict:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        chunks = root.findall('.//chunk')
        target = _find_chunk_by_event(chunks, event_id)
        related = _collect_related_chunks(chunks, target)
        return {
            'vertex_buffers': _parse_vb_bindings(related),
            'index_buffer': _parse_ib_binding(related),
            'textures': _parse_texture_bindings(related),
            'shaders': _parse_shader_bindings(related),
        }

C. 写中间态（兼容 export_fbx_assets）

    def build_intermediate_payload(resource_info: dict) -> dict:
        return {
            'mesh': {
                'vertex_count': resource_info.get('vertex_count', 0),
                'index_count': resource_info.get('index_count', 0),
                'index_format': resource_info.get('index_format', 'R32_UINT'),
                'vertex_layout': resource_info.get('vertex_layout', []),
            },
            'material': {
                'textures': resource_info.get('textures', []),
                'samplers': resource_info.get('samplers', []),
            },
            'shaders': resource_info.get('shaders', []),
        }

D. CLI 单事件导出入口

    import argparse
    from parsers.zipxml_event_parser import extract_event_resources
    from xmlzip_event_extractor import write_intermediate, EventState

    def main(argv=None):
        parser = argparse.ArgumentParser()
        parser.add_argument('--xml', required=True)
        parser.add_argument('--zip', required=True)
        parser.add_argument('--event', required=True, type=int)
        parser.add_argument('--out', required=True)
        args = parser.parse_args(argv)

        res = extract_event_resources(args.xml, args.event)
        state = EventState(
            index_buffer=res.get('index_buffer'),
            vertex_buffers=res.get('vertex_buffers', []),
            textures=res.get('textures', []),
            shaders=res.get('shaders', []),
        )
        write_intermediate(args.out, state, res.get('buffers', {}), res.get('shader_bins', {}), res.get('texture_bins', {}))
        return 0

## Impact Analysis

- 正向影响：打通离线路径，FBX 导出不再依赖 replay/GPU。
- 风险 1：不同 API chunk 命名不一致导致解析漏检。
  缓解：按 API 建立匹配表（Vulkan/D3D11 先行），并在 manifest 标出未匹配字段。
- 风险 2：zip 二进制条目名不稳定（000123 vs buffers/buffer123）。
  缓解：统一候选匹配函数 + 测试覆盖多命名样式。
- 风险 3：纹理解码失败。
  缓解：降级输出 raw bytes，记录 decode_status。

## Task Checklist

- [x] Task 1: zip.xml 事件索引解析器
- [x] Task 2: 单事件资源绑定解析（VB/IB/Texture/Shader）
- [x] Task 3: 中间态写入与 schema 对齐
- [x] Task 4: CLI 导出入口（zip.xml + zip -> intermediate）
- [x] Task 5: 测试覆盖与失败路径断言
- [x] Task 6: 文档与计划同步

## Action Items (TDD, 2–5 minute granularity)

Task 1 — zip.xml 事件索引解析器
1. 写失败测试：test_zipxml_event_parser.py::test_iter_draw_events_from_chunk_xml。
2. 运行：py -3 -m pytest scripts/rdc_analyzer/tests/test_zipxml_event_parser.py -k iter_draw -v（预期 FAIL）。
3. 实现 iter_draw_events/_detect_api 最小闭环。
4. 复跑同命令（预期 PASS）。
5. 提交：feat(rdc-analyzer): add zipxml draw-event parser。

Task 2 — 单事件资源绑定解析
1. 写失败测试：test_extract_event_resources_vb_ib_texture_shader。
2. 运行（预期 FAIL）。
3. 实现 _find_chunk_by_event/_collect_related_chunks + 资源解析函数。
4. 复跑（预期 PASS）。
5. 提交：feat(rdc-analyzer): parse offline event resources from zipxml。

Task 3 — 中间态写入/schema 对齐
1. 写失败测试：test_write_intermediate_contains_mesh_material_shader_keys。
2. 运行（预期 FAIL）。
3. 扩展 xmlzip_event_extractor.py 数据写入字段。
4. 复跑（预期 PASS）。
5. 提交：fix(rdc-analyzer): align intermediate payload with fbx exporter。

Task 4 — CLI 导出入口
1. 写失败测试：test_extract_event_intermediate_cli_outputs_expected_tree。
2. 运行（预期 FAIL）。
3. 实现 extract_event_intermediate.py。
4. 复跑（预期 PASS）。
5. 提交：feat(rdc-analyzer): add offline event intermediate cli。

Task 5 — 测试覆盖
1. 增加异常场景：event 不存在、zip entry 缺失、decode 失败回退。
2. 运行：py -3 -m pytest scripts/rdc_analyzer/tests/test_zipxml_event_parser.py scripts/rdc_analyzer/tests/test_extract_event_intermediate.py scripts/rdc_analyzer/tests/test_xmlzip_event_extractor.py -v --tb=short（预期 PASS）。
3. 提交：test(rdc-analyzer): cover offline zipxml extraction failures。

Task 6 — 文档与计划同步
1. 新增 ZIPXML_EVENT_EXTRACTION.md，写输入、输出、限制、示例。
2. 更新 docs/INDEX.md 导航。
3. 回写本计划勾选项与阻塞项。
4. 提交：docs(rdc-analyzer): document offline zipxml event extraction。

## Risks / Blockers

- zip.xml 与传统事件树结构不一致，存在字段映射遗漏风险。
- 样本依赖单文件（D:ackup\大远景_export.zip.xml），需后续补充 D3D11 样本交叉验证。
- 假设（待验证）：chunkIndex 可作为离线 event 近似 id；若不成立需引入更稳定的事件映射规则。

## Decisions

- 主路线采用离线解析 zip.xml + zip -> intermediate。
- FBX 导出链路保持不改架构，仅消费已稳定的 intermediate。
- 纹理统一输出 RGBA8；失败时保留原始 bytes。

## Verification / Acceptance (Definition of Done)

- 能从 zip.xml + zip 指定 eventId 生成完整 intermediate 目录。
- export_fbx_assets.py 可直接消费该目录并生成 obj/stats（无 FBX backend 时允许 RDC_FBX_ALLOW_MISSING=1）。
- 所有新增/相关测试通过。

## Next Steps

- 你确认后进入 /do，按 Task 1→6 严格 TDD 执行。
- 每完成 3 个任务回报一次进度与验证结果（Ready for feedback）。


## /do Progress Log (2026-02-06)

- Implemented parsers/zipxml_event_parser.py with streaming parse for:
  - draw/dispatch event index
  - Vulkan bind extraction for target event
  - Vulkan kBindBufferMemory and Internal::Initial Contents(eResDeviceMemory) mapping
- Implemented xtract_event_intermediate.py CLI:
  - --xml --zip --event --out [--vertex-stride]
  - offline VB/IB bytes extraction from memory blobs in ZIP
  - writes vent_<id>/intermediate + manifest.json
  - runtime JSON schema validation for mesh/material/shader/manifest
- Added schemas:
  - schema/intermediate_mesh.schema.json
  - schema/intermediate_material.schema.json
  - schema/intermediate_shader.schema.json
  - schema/intermediate_manifest.schema.json
- Added/updated tests:
  - 	est_zipxml_event_resources.py
  - 	est_extract_event_intermediate.py
  - 	est_intermediate_schemas.py
- Real sample validation:
  - command: py -3 scripts/rdc_analyzer/extract_event_intermediate.py --xml D:\backup\大远景_export.zip.xml --zip D:\backup\大远景_export.zip --event 23300 --out D:\backup\event_extract_test
  - output: D:\backup\event_extract_test\event_23300\intermediate
- Test evidence:
  - py -3 -m pytest scripts/rdc_analyzer/tests/test_zipxml_event_parser.py scripts/rdc_analyzer/tests/test_zipxml_event_resources.py scripts/rdc_analyzer/tests/test_extract_event_intermediate.py scripts/rdc_analyzer/tests/test_intermediate_schemas.py scripts/rdc_analyzer/tests/test_xmlzip_event_extractor.py scripts/rdc_analyzer/tests/test_xmlzip_intermediate_writer.py scripts/rdc_analyzer/tests/test_xmlzip_texture_decode_integration.py -v --tb=short
  - Result: 19 passed


## /do Extension Log (D3D11 Single-Event Offline)

- Extended `zipxml_event_parser.py`:
  - `extract_d3d11_bindings_for_event()` for IA/VB/IB + DrawIndexed params
  - `build_d3d11_buffer_data_map()` for `CreateBuffer.InitialData` + `Unmap.MapWrittenData`
- Extended `extract_event_intermediate.py`:
  - API dispatcher via XML header driver (`Vulkan` / `D3D11`)
  - D3D11 extraction path: `extract_d3d11_event_intermediate()`
  - kept output contract unchanged (`event_<id>/intermediate + manifest.json`)
- Added tests:
  - `test_extract_d3d11_bindings_and_buffer_map`
  - `test_extract_d3d11_event_intermediate_end_to_end`
  - `test_extract_d3d11_event_intermediate_missing_zip_entry`
- Verification:
  - `py -3 -m pytest scripts/rdc_analyzer/tests/test_zipxml_event_resources.py scripts/rdc_analyzer/tests/test_extract_event_intermediate.py -v --tb=short`
  - `py -3 -m pytest scripts/rdc_analyzer/tests/test_zipxml_event_parser.py scripts/rdc_analyzer/tests/test_zipxml_event_resources.py scripts/rdc_analyzer/tests/test_extract_event_intermediate.py scripts/rdc_analyzer/tests/test_intermediate_schemas.py scripts/rdc_analyzer/tests/test_xmlzip_event_extractor.py scripts/rdc_analyzer/tests/test_xmlzip_intermediate_writer.py scripts/rdc_analyzer/tests/test_xmlzip_texture_decode_integration.py -q`
  - Result: `22 passed`

## /do Extension Log (Import Bundle Closure)

- 日期：2026-02-07
- 目标：把 `event_<id>/intermediate` 落地为“可导入资源包”，形成单 event 闭环。

### 代码变更

1. 新增 `scripts/rdc_analyzer/export_event_import_bundle.py`
   - 支持两种入口：
     - `--intermediate`（已有中间态）
     - `--xml + --zip + --event`（一步式：先抽取中间态，再导出资源包）
   - 导出内容：
     - `mesh/mesh.obj + mesh.mtl`
     - `materials/materials.json`
     - `shaders/*.json + *.bin`
     - `textures/*.png|*.bin`
     - `bundle_manifest.json`
   - 纹理策略：优先 `decode_texture -> RGBA8 PNG`，失败回退 `raw_copy`。

2. 新增 schema
   - `scripts/rdc_analyzer/schema/import_bundle_manifest.schema.json`
   - `scripts/rdc_analyzer/schema/import_bundle_materials.schema.json`
   - 导出后自动执行结构校验（复用 `validate_json_file`）。

3. 新增测试
   - `scripts/rdc_analyzer/tests/test_export_event_import_bundle.py`
   - 覆盖：
     - RGBA8 解码为 PNG 成功路径
     - 未知格式回退 raw_copy 路径
     - manifest/materials 结构与统计字段检查

### 验证

- `py -3 -m py_compile scripts/rdc_analyzer/export_event_import_bundle.py scripts/rdc_analyzer/tests/test_export_event_import_bundle.py`
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_export_event_import_bundle.py scripts/rdc_analyzer/tests/test_obj_writer.py scripts/rdc_analyzer/tests/test_export_fbx_assets.py scripts/rdc_analyzer/tests/test_extract_event_intermediate.py scripts/rdc_analyzer/tests/test_intermediate_schemas.py -q`
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_zipxml_event_parser.py scripts/rdc_analyzer/tests/test_zipxml_event_resources.py scripts/rdc_analyzer/tests/test_extract_event_intermediate.py scripts/rdc_analyzer/tests/test_intermediate_schemas.py scripts/rdc_analyzer/tests/test_xmlzip_event_extractor.py scripts/rdc_analyzer/tests/test_xmlzip_intermediate_writer.py scripts/rdc_analyzer/tests/test_xmlzip_texture_decode_integration.py scripts/rdc_analyzer/tests/test_export_event_import_bundle.py -q`

- 结果：`24 passed`
