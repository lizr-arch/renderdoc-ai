# Deeper EID Mapping (Vulkan) - Plan

- Timestamp: 2026-02-14 12:54:09
- Agent: Agent01
- Scope: scripts/rdc_analyzer (Python-only)

## Goal
Make `analyze_rdc.py --json` export `events[].eventId` that matches RenderDoc EID semantics more robustly on real Vulkan captures by:
1) counting more non-draw event chunks (aux/resolve/etc) when building chunkIndex->EID mapping
2) recognizing additional draw variants (indirect-count + mesh shader draws) so event streams do not drift
3) adding an oracle-alignment integration test: `parse_rdc_xml.py` eventId == `build_vulkan_chunk_index_to_eid()`

## Non-Goals
- No RenderDoc C++ changes.
- No build steps (msbuild/cmake). Only unit tests.
- No changes under `renderdoc/3rdparty/` or `build*/`.

## Assumptions (explicit)
- Canonical semantics: `eventId` == EID (the value expected by `ReplayController.SetFrameEvent(eid)` and consumed as `eid` by full report generation).
- `chunkIndex` is preserved separately for debugging/backtrace.
- For correctness we keep `parse_rdc_xml.py` and `analyze_rdc.py` counting rules aligned.

## Tasks (2-5 min granularity)
- [x] Step 1: Expand Vulkan auxiliary event coverage
  - [x] Update `parse_rdc_xml.py` `auxiliary_calls` list to include missing Vulkan clear/copy/resolve-ish calls
  - [x] Update `analyze_rdc.py` `VULKAN_EID_EVENT_CHUNK_IDS` to match
  - [x] Add/adjust unit test to prove new chunk IDs shift EID as expected

- [x] Step 2: Add Vulkan draw variants (mesh + indirect-count)
  - [x] Update `parsers/enums.py` `VULKAN_DRAW_CHUNK_IDS` to include indirect-count + mesh draws
  - [x] Update `parsers/draw_event_parser.py` to treat these chunk IDs as draw events
  - [x] Update `parsers/models/base.py` `DrawEventContext.event_name` mapping for readable names
  - [x] Update `parse_rdc_xml.py` `vk_draw_calls` to include matching call names
  - [x] Update `analyze_rdc.py` EID-event chunk set to include these draw chunks
  - [x] Add unit tests for recognition + mapping

- [x] Step 3: Integration test (scientific oracle)
  - [x] Create a synthetic XML chunk stream with a mix of binding + auxiliary + marker + draw + resolve + mesh
  - [x] Assert `parse_rdc_xml.parse_rdc_xml()` eventId sequence matches `build_vulkan_chunk_index_to_eid()` for corresponding chunkIndex

## Impact Analysis
- JSON route: some Vulkan captures will see different `eventId` values (closer to real EID). `chunkIndex` remains stable.
- XML route: events list will include more auxiliary/draw variants (more correct / less missing events).
- Risk: downstream tools that incorrectly assumed `eventId == chunkIndex` may change behavior; that is why we keep `chunkIndex`.

## Risks / Blockers
- RenderDoc's definition of which Vulkan calls are "actions" may differ from our lists.
  - Mitigation: Step 3 oracle test and keeping lists unified.
- Zoekt/codemap index may be stale vs local modifications.
  - Mitigation: use local `rg` for newly-added identifiers.

## Verification (commands + expected)
- Targeted:
  - `py -3 -m pytest scripts/rdc_analyzer/tests/test_eventid_eid_mapping.py -q --tb=short` => pass
  - `py -3 -m pytest scripts/rdc_analyzer/tests/test_analyze_rdc_event_export.py -q --tb=short` => pass
- Full regression:
  - `py -3 -m pytest scripts/rdc_analyzer/tests -q --tb=short` => all pass

## Definition of Done
- `analyze_rdc.py` produces EID-aligned `eventId` for a wider set of real-world Vulkan captures.
- Mesh/indirect-count draws are recognized as draw events (no silent drop).
- Integration test locks XML oracle vs EID mapping behavior.
- All tests pass.

## /do log
- 2026-02-14: Step1 done
  - Updated `scripts/rdc_analyzer/parse_rdc_xml.py` Vulkan `auxiliary_calls` to include: vkCmdClearAttachments, vkCmdCopyImageToBuffer, vkCmdResolveImage, vkCmdUpdateBuffer, vkCmdFillBuffer.
  - Updated `scripts/rdc_analyzer/analyze_rdc.py` `VULKAN_EID_EVENT_CHUNK_IDS` to match.
  - Updated `scripts/rdc_analyzer/tests/test_eventid_eid_mapping.py` to assert these chunks consume EID.
  - Ran:
    - `py -3 -m pytest scripts/rdc_analyzer/tests/test_eventid_eid_mapping.py -q --tb=short`
    - `py -3 -m pytest scripts/rdc_analyzer/tests/test_analyze_rdc_event_export.py -q --tb=short`
- 2026-02-14: Step2 done
  - Added Vulkan draw chunk enums: vkCmdDrawIndirectCount(1116), vkCmdDrawIndexedIndirectCount(1117), vkCmdDrawMeshTasks*(1198-1200).
  - Updated parsers to recognize these chunk IDs as draw events and provide readable names.
  - Updated XML `vk_draw_calls` and JSON EID mapping set to include these draw variants.
  - Added unit tests: `scripts/rdc_analyzer/tests/test_vulkan_draw_variants.py`.
  - Ran:
    - `py -3 -m pytest scripts/rdc_analyzer/tests/test_vulkan_draw_variants.py -q --tb=short`
    - `py -3 -m pytest scripts/rdc_analyzer/tests/test_eventid_eid_mapping.py scripts/rdc_analyzer/tests/test_analyze_rdc_event_export.py -q --tb=short`
- 2026-02-14: Step3 done
  - Added integration test: `scripts/rdc_analyzer/tests/test_xml_oracle_eid_alignment.py`
    - Ensures XML oracle (`parse_rdc_xml.py`) eventId sequence matches `build_vulkan_chunk_index_to_eid()` keys/order.
  - Ran:
    - `py -3 -m pytest scripts/rdc_analyzer/tests/test_xml_oracle_eid_alignment.py -q --tb=short`
    - `py -3 -m pytest scripts/rdc_analyzer/tests -q --tb=short` (result: 824 passed, 6 skipped)
