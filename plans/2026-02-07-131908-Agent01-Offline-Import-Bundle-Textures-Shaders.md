# Plan: Offline Single-Event -> Import Bundle (Textures + Shaders)

- **Date**: 2026-02-07
- **Agent**: Agent01
- **Branch**: v1.x
- **Scope**: 补齐离线单 event 的 **Texture/Shader 绑定信息**，让 `import_bundle` 在 Unity/Unreal/Messiah 转换前就具备可组装的 `mesh/material/shader/texture`。

> 约束：
> - 优先 Vulkan + D3D11。
> - 纹理输出统一 RGBA8 PNG（若有 RGBA bytes/或可离线解码），否则回退 raw `.bin` 并记录状态。
> - Shader 先输出 sidecar（spirv/dxbc bin + json + 文本 disasm/glsl/hlsl），反编译 HLSL 作为增强项，不作为阻断。

---

## 0. 背景与现状

### 0.1 现有链路（已验证可运行）

1) **离线抽取单 event 中间态**（Vulkan/D3D11）
- 入口：`scripts/rdc_analyzer/extract_event_intermediate.py:585`
- Vulkan 路径：`scripts/rdc_analyzer/extract_event_intermediate.py:215`
- D3D11 路径：`scripts/rdc_analyzer/extract_event_intermediate.py:408`

2) **中间态导出 Import Bundle**（OBJ+materials+textures+shaders+manifest）
- 入口：`scripts/rdc_analyzer/export_event_import_bundle.py:228`

### 0.2 当前缺口

- `extract_event_intermediate.py` 在构造 `EventState` 时 `textures=[]`、`shaders=[]`（占位），所以真实样本导出后 `shader_count=0`、`texture_count=0`。
- 绑定解析当前只覆盖 `VB/IB + Draw`：
  - Vulkan：`scripts/rdc_analyzer/parsers/zipxml_event_parser.py:160`
  - D3D11：`scripts/rdc_analyzer/parsers/zipxml_event_parser.py:203`

---

## 1. 目标与 DoD（Definition of Done）

### 1.1 目标（单 event 闭环）

对指定 `event_id`：
- `event_<id>/intermediate/materials/material.json` 中 `textures[]` 不为空（若该 event 确实有采样纹理）。
- `event_<id>/intermediate/shaders/*.json + *.bin` 存在（至少 VS/PS 任一）。
- `event_<id>/import_bundle/`：
  - `textures/*.png`（优先）或 `textures/*.bin`（回退）
  - `materials/materials.json` 中记录每个纹理的 `slot/sampler/status/output_path`。
  - `bundle_manifest.json` 中 `shader_count/texture_count` 正确。

### 1.2 验证方式（你可人工验收）

- 使用真实样本（例如 Vulkan：`D:\backup\大远景_export.zip.xml/.zip`）
- 选择一个更像角色主体的 draw（按 indexCount 排序，例如 `event_id=22149`）
- 执行：
  - `py -3 scripts/rdc_analyzer/extract_event_intermediate.py ...`
  - `py -3 scripts/rdc_analyzer/export_event_import_bundle.py ...`
- 观察：import_bundle 的纹理数量与 RenderDoc GUI/报表中该 event 的绑定一致（允许少量缺失，需标注原因）。

---

## 2. 设计：中间态字段（最小可用 + 可扩展）

> 目标：保持“中间态”独立于引擎，但能映射到 Unity/Unreal/Messiah。

### 2.1 Texture 绑定条目（写入 material.json）

`material.textures[]` 每项建议：

```json
{
  "slot": "albedo",               // 或 vulkan: set0.binding3 / d3d11: PS.t0
  "sampler": "s0",               // 或 vulkan: set0.binding4
  "texture_id": 12345,            // ResourceId / ImageViewId（先用能稳定定位 zip entry 的 ID）
  "path": "tex_12345.bin",       // intermediate/textures/ 下的文件名
  "width": 1024,
  "height": 1024,
  "format": "VK_FORMAT_R8G8B8A8_UNORM"
}
```

约定：
- `path` 指向 `intermediate/textures/` 下的文件。
- 若你提供 RGBA bytes：`format` 可写成 `RGBA8`（`decoders/texture_decoder.py` 已支持）。

### 2.2 Shader 条目（写入 shaders/*.json）

`vs.json / ps.json` 建议：

```json
{
  "shader": {
    "stage": "vs",
    "bytecode_format": "spirv",  // 或 dxbc
    "entry": "main",
    "disassembly": "..."         // 可为空
  }
}
```

配套：
- `shaders/vs.bin` / `shaders/ps.bin` 原始字节码。
- `disassembly` 可以先放 “可读文本”（spirv_disasm / glsl / asm），HLSL 反编译后续增强。

---

## 3. 任务拆分（2-5 分钟粒度）

### Task 1（Vulkan）离线解析：DescriptorSet -> Image/Sampler 绑定

**目标**：在 `zipxml_event_parser.py` 为 Vulkan 增加 `textures` 输出（slot+sampler+resourceId）。

**依据（可复用逻辑证据）**：
- `scripts/rdc_analyzer/parse_rdc_xml.py:21` 解析 `vkUpdateDescriptorSets`
- `scripts/rdc_analyzer/parse_rdc_xml.py:91` 预扫描得到 `descriptor_set_contents`
- `scripts/rdc_analyzer/parse_rdc_xml.py:2331` 解析 `vkCmdBindDescriptorSets` 并展开 bindings

**实现步骤（伪代码）**：

```python
# 1) 预扫描：collect_descriptor_set_contents_until_event(xml_path, upto_event_id)
#    - 只扫描到目标 event_id（含）为止
#    - 输出 {setId(str)-> list[ {binding, descriptorType, resources:[{type,imageView/samplerId...}]} ] }

# 2) 主扫描：extract_vulkan_bindings_for_event(xml_path, event_id)
#    - 维持当前 IB/VB/draw
#    - 新增：跟踪最后一次 vkCmdBindDescriptorSets（或在 renderpass 内）
#    - 将 set/binding 展开为 images/samplers 列表
#    - 输出 bindings['textures'] = [ {slot, sampler, resource_id, ...} ]

# 3) 把 bindings['textures'] 写进 EventState.textures
```

**验证**：
- 新增/扩展单测（从样例 xml 构造 vkUpdateDescriptorSets + vkCmdBindDescriptorSets）。
- 对真实样本 `event_id=22149` 跑，`texture_count > 0`（若该 draw 绑定纹理）。

---

### Task 2（Vulkan）离线 shader：vkCreateShaderModule + pipeline 推断 stage

**目标**：对指定 event 的 pipeline，输出 VS/PS 的 shader bin/json。

**依据**：
- 现有工具：`scripts/rdc_analyzer/shader_extractor.py:72`
  - 能解析 `vkCreateShaderModule`（buffer index + codeSize）
  - 能解析 pipeline 推断 stage
  - 能用 `spirv-cross` 输出 GLSL（如果可用）

**实现步骤（伪代码）**：

```python
# 在 extract_event_intermediate 的 Vulkan 路径：
# - 找到目标 event 前最后一次 vkCmdBindPipeline（graphics pipeline id）
# - 通过 shader_extractor 的 pipeline mapping 找到该 pipeline 的 stage->shaderModuleId
# - 从 zip 读出对应 buffer index -> spirv bytes
# - 写入 intermediate/shaders/vs.json + vs.bin (同理 ps)
# - disassembly 可写 spirv header summary，或 glsl（若 spirv-cross 存在）
```

**验证**：
- 单测：最小 xml + zip 模拟 `vkCreateShaderModule` buffer entry。
- 真实样本：`shader_count > 0`。

---

### Task 3（D3D11）离线解析：SRV + Sampler + Shader 绑定

**目标**：对 D3D11 `DrawIndexed`，输出 PS/VS 的 `t#` 与 `s#` 绑定资源 ID。

**依据**：
- `scripts/rdc_analyzer/parse_rdc_xml.py:2188` 解析 `*SetShaderResources`
- `scripts/rdc_analyzer/parse_rdc_xml.py:2268` 解析 `*SetSamplers`
- xml 样本：`scripts/rdc_analyzer/test_captures/test_d3d11.xml:5055`

**实现步骤（伪代码）**：

```python
# extract_d3d11_bindings_for_event:
# - 在扫描到 event_id 之前跟踪：
#   - PSSetShaderResources / VSSetShaderResources (t#)
#   - PSSetSamplers / VSSetSamplers (s#)
#   - VSSetShader / PSSetShader (shader id)
# - 在 event_id 的 DrawIndexed 上输出：
#   - textures: [{slot:'PS.t0', sampler:'PS.s0', resource_id:<srv_id>}]
#   - shaders:  [{stage:'vs', resource_id:<shader_id>}, {stage:'ps', ...}]
```

**验证**：
- 单测：构造最小 D3D11 xml，检查输出结构。

---

### Task 4（导出闭环）把绑定写入 intermediate + import_bundle 端到端

**目标**：让 `export_event_import_bundle.py` 能拿到：
- intermediate/materials/material.json 的 textures
- intermediate/textures/ 下的 payload（你提供 RGBA bytes 或可离线解码的原始 bytes）

**实现步骤（伪代码）**：

```python
# extract_event_intermediate:
state = build_event_state_from_bindings(...)
state.textures = bindings.get('textures', [])
state.shaders  = bindings.get('shaders', [])
write_intermediate(...)

# 保持 export_event_import_bundle 不变或只做小增强：
# - 优先 decode_texture->png
# - 否则 raw_copy
```

**验证**：
- 用真实样本跑：import_bundle 里能看到 png 或 raw bin，并且 materials.json 有 output_path。

---

## 4. 影响分析

- 改动文件主要集中在 Python：
  - `scripts/rdc_analyzer/parsers/zipxml_event_parser.py`
  - `scripts/rdc_analyzer/extract_event_intermediate.py`
  - （可选）新增 `scripts/rdc_analyzer/parsers/vk_descriptor_parser.py` 用于复用 parse_rdc_xml 逻辑
  - schema 若需扩展（可选）：`scripts/rdc_analyzer/schema/intermediate_material.schema.json`
- 不涉及 `renderdoc/3rdparty/`。

---

## 5. Build/Test/Lint Quick Guide（只记录，不自动执行编译）

- 语法检查：
  - `py -3 -m py_compile scripts/rdc_analyzer/parsers/zipxml_event_parser.py scripts/rdc_analyzer/extract_event_intermediate.py`
- 单测：
  - `py -3 -m pytest scripts/rdc_analyzer/tests/test_zipxml_event_parser.py scripts/rdc_analyzer/tests/test_zipxml_event_resources.py -q`
  - `py -3 -m pytest scripts/rdc_analyzer/tests/test_extract_event_intermediate.py scripts/rdc_analyzer/tests/test_export_event_import_bundle.py -q`

---

## 6. 风险与阻塞

- Vulkan 的 DescriptorSet 展开需要状态机（vkUpdateDescriptorSets 的增量更新）；只看单 chunk 会漏资源。
- `spirv-cross` 不一定存在：需做可用性检测，缺失时降级输出 SPIR-V 摘要/反汇编。
- 纹理离线 payload 可能是 GPU-native layout（tiling），若你提供已还原的 RGBA bytes，可直接绕过该风险。

---

## 7. 决策点（需要你确认）

1) Vulkan `slot` 命名：你希望固定为 `setX.bindingY` 还是映射到语义名（albedo/normal）？
   - 建议先 `setX.bindingY`（稳定），语义映射后续由引擎规则做。

2) Texture `texture_id`：优先用 ImageViewId 还是 ImageId？
   - 建议：优先 ImageViewId（更贴近采样绑定），同时在条目里附带 imageId（可选）。

---

## 8. Task Checklist

- [x] Task 1: Vulkan DescriptorSet -> textures 绑定输出
- [x] Task 2: Vulkan pipeline -> shader stage -> spirv 导出
- [x] Task 3: D3D11 SRV/Sampler/Shader 绑定输出
- [x] Task 4: 端到端写入 intermediate + import_bundle 验证（真实样本 event_id=22149）



## 9. /do 执行记录

- 2026-02-07: 修复 `vkUpdateDescriptorSetWithTemplate` 的 `dstSet=0` 回退逻辑，避免 descriptor 写入被误丢弃。
- 2026-02-07: 增加 `vkCreateImageView` 输出名 `View` 兼容，补齐 `imageView -> image` 映射。
- 2026-02-07: `extract_event_intermediate.py` 已把 `textures/shaders` 从 bindings 注入 intermediate，并写出 `shaders/*.bin`。
- 2026-02-07: `xmlzip_event_extractor.py` 补齐 shader sidecar 字段：`bytecode_format`、`entry`。
- 2026-02-07: `export_event_import_bundle.py` 对空纹理 payload 标记 `missing_source`，避免误报 `decoded_rgba8_png`。
- 2026-02-07: 真实样本验证：`D:\backup\大远景_export.zip.xml + .zip`, `event_id=22149`。结果为 `texture_count=10`、`shader_count=2`、纹理状态为 `missing_source`（离线未拿到可解码像素 payload）。
- 2026-02-07: 新增 `--rgba-manifest` 外部 RGBA bytes 覆盖接口：支持 `texture_id/slot + rgba_path + width/height(+row_pitch)` 直出 PNG（状态 `rgba_bytes_png`），并补齐 schema 与回归测试。

- 2026-02-07: `--rgba-manifest` 真实烟测通过：`event_22149` 中 `texture_id=127279` 成功输出 `rgba_bytes_png`，其余仍按 `missing_source` 回退。

- 2026-02-07: 新增固定目录自动发现协议：默认查找 `event_<id>/rgba/rgba_manifest.json`，无 manifest 时回退 `tex_<texture_id>.rgba` 自动注入。

- 2026-02-07: 自动发现真实样本烟测通过（不传 `--rgba-manifest`）：`event_22149/rgba/rgba_manifest.json` 生效，`texture_id=127279` 输出 `rgba_bytes_png`。
