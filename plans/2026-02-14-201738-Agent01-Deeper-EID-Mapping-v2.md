# Deeper EID Mapping (Vulkan) v2 — Plan (*2 variants + legacy markers)

- Timestamp: 2026-02-14 20:17:38
- Agent: Agent01
- Scope: `scripts/rdc_analyzer` (Python-only)

## Scope
Extend the existing EID contract (eventId == EID, chunkIndex preserved separately) to reduce drift on modern Vulkan captures:
1) Add Vulkan `*2` Copy/Blit/Resolve chunks as EID-consuming events.
2) Add legacy Vulkan markers (VK_EXT_debug_marker) as EID-consuming marker events.
3) Lock XML oracle (`parse_rdc_xml.py`) and JSON mapping (`analyze_rdc.py`) via tests.

## Non-Goals
- No RenderDoc C++ changes.
- No build steps (msbuild/cmake). Only Python tests.
- No changes under `renderdoc/3rdparty/` or `build*/`.

## Scientific Contract (SSOT)
- Canonical semantics: `events[].eventId` MUST represent RenderDoc's EID semantics (the value consumed as `eid` by downstream full report and by `ReplayController.SetFrameEvent(eid)`).
- `chunkIndex` remains a debugging/backtrace coordinate.
- Two routes must stay aligned:
  - XML route: `scripts/rdc_analyzer/parse_rdc_xml.py` (oracle)
  - JSON route: `scripts/rdc_analyzer/analyze_rdc.py` (`build_vulkan_chunk_index_to_eid`)

## Evidence (verified from RenderDoc source)
Chunk IDs (derived from `renderdoc/driver/vulkan/vk_common.h` enum order):
- `vkCmdCopyBuffer2 = 1153`
- `vkCmdCopyImage2 = 1154`
- `vkCmdCopyBufferToImage2 = 1155`
- `vkCmdCopyImageToBuffer2 = 1156`
- `vkCmdBlitImage2 = 1157`
- `vkCmdResolveImage2 = 1158`

Legacy marker call names (already present as chunks):
- `vkCmdDebugMarkerBeginEXT`
- `vkCmdDebugMarkerInsertEXT`
- `vkCmdDebugMarkerEndEXT`

## Tasks (2-5 min granularity)
- [x] Step 1: Add Vulkan `*2` auxiliary events (copy/blit/resolve)
  - [x] Update `scripts/rdc_analyzer/parsers/enums.py`
    - Add `VulkanChunk` IntEnum members for `vkCmdCopyBuffer2`, `vkCmdCopyImage2`, `vkCmdCopyBufferToImage2`, `vkCmdCopyImageToBuffer2`, `vkCmdBlitImage2`, `vkCmdResolveImage2` with exact values 1153-1158.
  - [x] Update `scripts/rdc_analyzer/parse_rdc_xml.py`
    - Add these `vkCmd*2` names to Vulkan `auxiliary_calls`.
  - [x] Update `scripts/rdc_analyzer/analyze_rdc.py`
    - Add these chunks to `VULKAN_EID_EVENT_CHUNK_IDS`.
  - [x] Tests
    - [x] New/updated test to assert enum values are correct and `build_vulkan_chunk_index_to_eid()` counts them.

- [x] Step 2: Add legacy Vulkan markers (VK_EXT_debug_marker)
  - [x] Update `scripts/rdc_analyzer/parse_rdc_xml.py`
    - Extend `vk_marker_names` to include `vkCmdDebugMarkerBeginEXT`, `vkCmdDebugMarkerInsertEXT`, `vkCmdDebugMarkerEndEXT`.
  - [x] Update `scripts/rdc_analyzer/analyze_rdc.py`
    - Count these marker chunks as EID-consuming events.
  - [x] Tests
    - [x] Extend `test_eventid_eid_mapping.py` to include at least one legacy marker chunk and assert it consumes EID.

- [ ] Step 3: Oracle-alignment integration test extension
  - [ ] Extend `scripts/rdc_analyzer/tests/test_xml_oracle_eid_alignment.py`
    - Add `*2` auxiliary chunks + legacy marker chunks into the synthetic XML stream.
    - Assert XML oracle eventId sequence still matches `build_vulkan_chunk_index_to_eid()`.

## Impact Analysis
- JSON route: more chunks consume EID => eventId values for some Vulkan captures may shift (closer to real RenderDoc EID).
- XML route: events list gains additional event kinds (more complete capture event stream).
- Risk: any downstream consumer that incorrectly assumed `eventId == chunkIndex` could behave differently.
  - Mitigation: `chunkIndex` remains exported.

## Verification (commands + expected output)
- Targeted:
  - `py -3 -m pytest scripts/rdc_analyzer/tests/test_eventid_eid_mapping.py -q --tb=short` => pass
  - `py -3 -m pytest scripts/rdc_analyzer/tests/test_xml_oracle_eid_alignment.py -q --tb=short` => pass
- Full regression:
  - `py -3 -m pytest scripts/rdc_analyzer/tests -q --tb=short` => all pass (no failures)

## Definition of Done
- `*2` auxiliary chunks and legacy marker chunks are consistently counted as EID-consuming events in BOTH routes.
- Tests enforce enum values + EID mapping + oracle alignment.
- Full test suite passes.

## /do log
- 2026-02-14: Step1 done
  - Added VulkanChunk enum values for `vkCmd*2` copy/blit/resolve (1153-1158) in `scripts/rdc_analyzer/parsers/enums.py`.
  - Added `vkCmd*2` names to Vulkan `auxiliary_calls` in `scripts/rdc_analyzer/parse_rdc_xml.py`.
  - Counted these chunks as EID-consuming events in `scripts/rdc_analyzer/analyze_rdc.py` `VULKAN_EID_EVENT_CHUNK_IDS`.
  - Extended `scripts/rdc_analyzer/tests/test_vulkan_draw_variants.py` to lock enum values and mapping behavior.
  - Ran:
    - `py -3 -m pytest scripts/rdc_analyzer/tests/test_vulkan_draw_variants.py -q --tb=short` (5 passed)
    - `py -3 -m pytest scripts/rdc_analyzer/tests/test_eventid_eid_mapping.py -q --tb=short` (1 passed)
- 2026-02-15: Step2 done
  - Extended Vulkan marker name list in `scripts/rdc_analyzer/parse_rdc_xml.py` to include VK_EXT_debug_marker calls.
  - Counted `vkCmdDebugMarker*EXT` chunks as EID-consuming events in `scripts/rdc_analyzer/analyze_rdc.py`.
  - Extended `scripts/rdc_analyzer/tests/test_eventid_eid_mapping.py` to ensure legacy markers consume EID.
  - Ran:
    - `py -3 -m pytest scripts/rdc_analyzer/tests/test_eventid_eid_mapping.py -q --tb=short` (1 passed)

