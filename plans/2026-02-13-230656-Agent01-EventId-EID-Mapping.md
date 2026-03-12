# Plan: EventId EID Mapping (analyze_rdc JSON ↔ parse_rdc_xml 语义对齐)

> Plan File: `plans/2026-02-13-230656-Agent01-EventId-EID-Mapping.md`
> Stage: `/plan`
> Date: 2026-02-13
> Agent: Agent01

## Scope / Assumptions

- **目标 (WHAT)**：将 `scripts/rdc_analyzer/analyze_rdc.py` 导出的 `events[].eventId` 语义从 **chunkIndex** 调整为 **EID (Event ID)**，并与 `scripts/rdc_analyzer/parse_rdc_xml.py` 的 eventId 递增规则保持一致：
  - 只对“事件”递增（Draw/Dispatch + Marker + Aux 事件）。
  - **binding**（如 `vkCmdBindPipeline`）不占 eventId。
  - marker/aux 也占 eventId。
- **兼容策略**：新增字段 `events[].chunkIndex` 保留原 chunk 序号，用于调试/反查。
- **范围 (IN)**：先聚焦 Vulkan 路径（因为 `analyze_rdc.py` 的 draw event 提取和 pipeline 映射以 Vulkan 为主）。
- **非目标 (OUT)**：
  - 不改 RenderDoc C++ 侧 chunk 生成逻辑。
  - 不在本轮实现“全量事件导出（包含所有 marker/aux 的完整 events 列表）”，除非验证表明 consumer 强依赖。
  - 不引入新依赖、不触碰 `renderdoc/3rdparty/`、不修改 `build*/`。

### Definitions

- **chunkIndex**：FrameCapture 内 chunk 的顺序索引（0-based）。
- **EID / eventId**：只对“事件”递增的索引（0-based），用于 UI/报告侧按事件定位。

## Problem Statement (Evidence)

现状存在“同名字段不同语义”的契约风险：

1) consumer 将 `eventId` 直接当成报告侧 `eid`。
2) `parse_rdc_xml.py` 的 eventId 是“事件序号”，binding 不递增。
3) `analyze_rdc.py` 当前将 eventId 写成 chunkIndex（包含 binding 等非事件 chunk），导致与 (2) 语义不一致。

## Navigation Evidence（codemap-first）

### codemap queries used (max 3)

1. `codemap "load_rdc_data eventId" -Num 20`
2. `codemap "parse_rdc_xml.py binding_calls eventId" -Num 20`
3. `codemap "analyze_rdc.py events" -Num 20`

### candidate hits (>=3)

- `[renderdoc] scripts/rdc_analyzer/generate_real_report.py:613`
  - `"eid": event.get("eventId", 0),`
- `[renderdoc] scripts/rdc_analyzer/parse_rdc_xml.py:932`
  - `"eventId": event_id,`
- `[renderdoc] scripts/rdc_analyzer/parse_rdc_xml.py:1024`
  - `elif chunk_name in binding_calls:` （该分支不 append event、不 event_id += 1）
- `[renderdoc] scripts/rdc_analyzer/analyze_rdc.py:398`
  - `"eventId": int(draw_event.chunk_index),`

### follow-up targets (1-2)

- `scripts/rdc_analyzer/analyze_rdc.py:386`（`convert_draw_events_to_capture_events`）
  - 这里是 `eventId` 的实际写入点，且是 full report 的输入事件列表。
- `scripts/rdc_analyzer/rdc_parser.py:263`（`RDCParser.parse_frame_chunks`）
  - 这里拿到 chunk 序列，是构建 chunkIndex→EID 映射的输入。

### next step links

- http://127.0.0.1:8080/source/xref/renderdoc/scripts/rdc_analyzer/analyze_rdc.py#386
- http://127.0.0.1:8080/source/xref/renderdoc/scripts/rdc_analyzer/parse_rdc_xml.py#900
- http://127.0.0.1:8080/source/xref/renderdoc/scripts/rdc_analyzer/generate_real_report.py#600

## Gate Priority（按重要性排序，面向本任务）

1. **Gate-1 真实性（Truthfulness / Semantic Correctness）**：Vulkan 路径下 `eventId` 必须与 `parse_rdc_xml.py` 的 EID 语义一致。
2. **Gate-2 全量质量（Regression Gate）**：`py -3 -m pytest scripts/rdc_analyzer/tests -q --tb=short` 必须全绿。
3. **Gate-3 契约一致（Schema/Consumer Contract）**：`generate_real_report.py`/full report 对输入 JSON 的消费不回归（`eid` 定位仍有效）。
4. **Gate-4 可复现性（Determinism）**：同一 capture 重复导出 JSON，eventId 不受环境/机器差异影响。
5. **Gate-5 文档一致（Docs SSOT Consistency）**：若文档中描述 eventId 语义，需要同步更新并写清楚 EID vs chunkIndex。

## Scientific Evaluation Protocol（科学评估方案）

### 1) 研究问题与假设

- **RQ1**：`analyze_rdc.py` 的 `events[].eventId` 当前是否等价于“事件序号”？
  - **H0**：eventId == EID（与 XML 一致）。
  - **H1**：eventId == chunkIndex（与 XML 不一致）。

- **RQ2**：将 eventId 改为 EID 后，consumer（full report）是否仍能正确生成报告并按 eid 导航？
  - **H0**：consumer 与 eventId 语义无关，只要唯一即可。
  - **H1**：consumer 语义上依赖 EID（例如按 eventId 构建索引/跳转）。

### 2) Ground Truth（可验证的参照系）

- **Primary oracle**：`scripts/rdc_analyzer/parse_rdc_xml.py` 的 eventId 递增规则：
  - `events.append(event); event_id += 1` 仅发生在 draw/aux/marker 分支；binding 分支不递增。
- **Secondary oracle**：consumer 明确将 `eventId` 映射为 `eid`（`generate_real_report.py`）。

### 3) 可量化指标（Metrics）

- M1: `eventId` 单调递增（对导出的 draw events 列表）。
- M2: 给定 chunk 序列，`chunkIndex -> eventId` 映射满足：
  - eventId 只对 event-chunk 递增；binding-chunk 不递增。
- M3: 在 synthetic chunks 测试中，EID mapping 与预期完全一致（强断言）。
- M4: 回归测试全绿。

### 4) 反例/混淆因素（Confounders）

- VulkanChunk 枚举可能不包含某些新扩展 chunk（例如 mesh tasks）。
  - 处理策略：本轮先以“现有 parser 已识别的 chunk 集合”为准，缺失项在 Risks 记录并可增量补齐。

## Repo / File List（精确到行号范围）

- `scripts/rdc_analyzer/analyze_rdc.py:386`：`convert_draw_events_to_capture_events`（eventId 写入点）
- `scripts/rdc_analyzer/analyze_rdc.py:430`：`analyze_rdc_file`（可拿到 chunks，并将映射注入 exporter）
- `scripts/rdc_analyzer/rdc_parser.py:263`：`RDCParser.parse_frame_chunks`（chunk 序列来源）
- `scripts/rdc_analyzer/parse_rdc_xml.py:932`：event dict 构建与 `eventId = event_id`
- `scripts/rdc_analyzer/parse_rdc_xml.py:1016`：binding_calls 分支（不递增）/marker/aux 分支（递增）
- `scripts/rdc_analyzer/generate_real_report.py:613`：consumer 映射 `eventId -> eid`
- `scripts/rdc_analyzer/tests/test_analyze_rdc_event_export.py:1`：现有单测需更新

## Approach (Pseudo-code + Complete snippets)

### A) 新增 Vulkan chunkIndex→EID 映射 helper

核心思想：扫描 `chunks`（顺序即 chunkIndex），遇到“事件 chunk”就给它分配下一个 eid。

伪代码：

```python
def build_vulkan_chunk_index_to_eid(chunks: list[ChunkInfo]) -> dict[int, int]:
    eid = 0
    mapping = {}
    for chunk_index, chunk in enumerate(chunks):
        if chunk.chunk_id in VULKAN_EVENT_CHUNK_IDS:
            mapping[chunk_index] = eid
            eid += 1
    return mapping
```

完整代码片段（计划写入 `scripts/rdc_analyzer/analyze_rdc.py`，位置：`convert_draw_events_to_capture_events` 之前）：

```python
from rdc_parser import ChunkInfo, VulkanChunk

VULKAN_EVENT_CHUNK_IDS = {
    # Draw
    VulkanChunk.vkCmdDraw,
    VulkanChunk.vkCmdDrawIndirect,
    VulkanChunk.vkCmdDrawIndexed,
    VulkanChunk.vkCmdDrawIndexedIndirect,
    # Dispatch
    VulkanChunk.vkCmdDispatch,
    VulkanChunk.vkCmdDispatchIndirect,
    # Marker (debug utils)
    VulkanChunk.vkCmdBeginDebugUtilsLabelEXT,
    VulkanChunk.vkCmdEndDebugUtilsLabelEXT,
    VulkanChunk.vkCmdInsertDebugUtilsLabelEXT,
    # Aux (clear/copy) — 对齐 parse_rdc_xml.py 的 auxiliary_calls
    VulkanChunk.vkCmdClearColorImage,
    VulkanChunk.vkCmdClearDepthStencilImage,
    VulkanChunk.vkCmdBlitImage,
    VulkanChunk.vkCmdCopyBuffer,
    VulkanChunk.vkCmdCopyImage,
    VulkanChunk.vkCmdCopyBufferToImage,
}


def build_vulkan_chunk_index_to_eid(chunks: List[ChunkInfo]) -> Dict[int, int]:
    eid = 0
    mapping: Dict[int, int] = {}
    for chunk_index, chunk in enumerate(chunks):
        if chunk.chunk_id in VULKAN_EVENT_CHUNK_IDS:
            mapping[chunk_index] = eid
            eid += 1
    return mapping
```

### B) 调整 exporter：eventId 写 EID，同时保留 chunkIndex

完整代码片段（替换 `convert_draw_events_to_capture_events` 的 eventId 赋值逻辑）：

```python
def convert_draw_events_to_capture_events(
    draw_events: List[DrawEventContext],
    pipelines: Dict[int, PipelineInfo],
    chunk_index_to_eid: Dict[int, int] | None = None,
) -> List[Dict[str, Any]]:
    capture_events: List[Dict[str, Any]] = []

    for draw_event in draw_events:
        chunk_index = int(draw_event.chunk_index)
        eid = chunk_index
        if chunk_index_to_eid is not None:
            eid = int(chunk_index_to_eid.get(chunk_index, chunk_index))

        event_payload: Dict[str, Any] = {
            "eventId": eid,
            "chunkIndex": chunk_index,
            "chunkId": int(draw_event.chunk_id),
            "name": draw_event.event_name,
            "type": _normalize_report_event_type(draw_event.event_type),
            "subtype": draw_event.event_type,
            "pipeline": int(draw_event.pipeline_resource_id),
            "markerPath": draw_event.marker_path,
            "flags": [],
            "params": [],
        }

        # pipelineState 保持不变...

        capture_events.append(event_payload)

    return capture_events
```

### C) 在 analyze_rdc_file() 里注入映射

思路：在 Vulkan 分支里已经解析了 chunks（`extract_draw_events()` 依赖 `parse_frame_chunks()`），因此可直接取 `parser.chunks`。

完整代码片段（计划修改 `analyze_rdc_file()`，在 `with RDCParser(...) as parser:` 内保存 `chunk_index_to_eid`，并在函数末尾传入 converter）：

```python
chunk_index_to_eid = None
with RDCParser(rdc_path) as parser:
    info = parser.parse_header()
    ...
    if is_vulkan:
        ...
        draw_events, pipelines = parser.extract_draw_events()
        chunks = parser.chunks or []
        chunk_index_to_eid = build_vulkan_chunk_index_to_eid(chunks)

...
event_details = convert_draw_events_to_capture_events(draw_events, pipelines, chunk_index_to_eid)
```

## Task Checklist（2-5 分钟粒度）

- [x] 1. 在 `scripts/rdc_analyzer/analyze_rdc.py` 增加 `build_vulkan_chunk_index_to_eid()` + `VULKAN_EVENT_CHUNK_IDS`（仅 Vulkan）
- [x] 2. 修改 `convert_draw_events_to_capture_events()`：
  - [x] 2.1 新增可选参数 `chunk_index_to_eid`
  - [x] 2.2 `eventId` 写 eid；新增 `chunkIndex`
- [x] 3. 修改 `analyze_rdc_file()`：
  - [x] 3.1 Vulkan 分支取 `parser.chunks` 并计算 mapping
  - [x] 3.2 调用 converter 时传入 mapping
- [x] 4. 更新/新增测试：
  - [x] 4.1 更新 `scripts/rdc_analyzer/tests/test_analyze_rdc_event_export.py`：显式传 mapping，断言 `eventId` 与 `chunkIndex`
  - [x] 4.2 新增 `scripts/rdc_analyzer/tests/test_eventid_eid_mapping.py`：构造 synthetic chunks（包含 binding/marker/aux/draw），断言 mapping 精确匹配
- [x] 5. 运行 targeted tests（见下方命令）
- [x] 6. 运行全量 tests
- [x] 7. Git commit（Conventional Commits）

## Build / Test / Lint Quick Guide（命令仅记录，/do 执行）

### 1) Fail-first（预期失败：在修改前跑）

```bash
py -3 -m pytest \
  scripts/rdc_analyzer/tests/test_analyze_rdc_event_export.py \
  -q --tb=short
```

预期（修改前）：`1 failed`（因为当前 eventId==chunkIndex，测试将被更新为 EID 语义）。

### 2) Gate-2（targeted 回归）

```bash
py -3 -m pytest \
  scripts/rdc_analyzer/tests/test_analyze_rdc_event_export.py \
  scripts/rdc_analyzer/tests/test_eventid_eid_mapping.py \
  -q --tb=short
```

预期：`all passed`。

### 3) 全量回归（Gate-2）

```bash
py -3 -m pytest scripts/rdc_analyzer/tests -q --tb=short
```

预期：`0 failed`。

## Impact Analysis

- 正向影响：
  - eventId 语义统一后，report linking（texture/shader/issue → event）将更稳定，跨脚本互操作减少“同字段不同语义”的隐性 bug。
  - 新增 `chunkIndex` 可用于调试、回溯 chunk 原始位置，避免信息丢失。
- 潜在破坏：
  - 若现有 consumer/脚本隐式依赖 `eventId == chunkIndex`，可能出现行为变化。
  - 缓解：保留 `chunkIndex`，并在必要处改为使用 `chunkIndex`。

## Risks / Blockers

1. VulkanChunk 枚举缺失的事件 chunk（例如 mesh tasks）会导致 mapping 不完整。
2. 事件定义集合与 `parse_rdc_xml.py` 不一致会造成“对齐失败”。
3. 若 full report 需要完整 events（marker/aux）而不仅 draw_events，本计划需要扩展范围。

## Verification / Acceptance（Definition of Done）

- [x] `eventId` 的递增规则与 `parse_rdc_xml.py` 对齐（binding 不占号；marker/aux 占号）。
- [x] `scripts/rdc_analyzer/tests` 全量通过。
- [x] `analyze_rdc.py --json` 产物仍可被 `generate_real_report.py`/full report 消费。

## Next Step

你确认此 /plan 后我进入 `/do` 开始改动代码与补测试，并在本 plan 文件末尾追加 `/do Execution Log`（逐项勾选）。

## /do Execution Log（2026-02-13）

- 代码实现（Vulkan 路径）：
  - `scripts/rdc_analyzer/analyze_rdc.py:395` 新增 `build_vulkan_chunk_index_to_eid()`，扫描 chunks 构建 chunkIndex→EID。
  - `scripts/rdc_analyzer/analyze_rdc.py:443` `convert_draw_events_to_capture_events()`：写入 `eventId=eid` 并新增 `chunkIndex`。
  - `scripts/rdc_analyzer/analyze_rdc.py:540` `analyze_rdc_file()` Vulkan 分支注入 mapping，并传入 converter。
- 测试（命令级证据）：
  - targeted: `py -3 -m pytest scripts/rdc_analyzer/tests/test_analyze_rdc_event_export.py scripts/rdc_analyzer/tests/test_eventid_eid_mapping.py -q --tb=short` → `2 passed`
  - full: `py -3 -m pytest scripts/rdc_analyzer/tests -q --tb=short` → `820 passed, 6 skipped`
- 备注：Vulkan EID event-chunk 集合当前与 `parse_rdc_xml.py` 的 marker/aux 列表对齐（debug utils markers + clear/copy aux）。
