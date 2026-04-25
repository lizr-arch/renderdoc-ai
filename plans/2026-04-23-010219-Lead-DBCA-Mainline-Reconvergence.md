# Lead / DBCA 主线收口补充计划

## Scope / Assumptions

- 主线目标：优先确认并收口已经落在 `renderdoc-ai/main@87c5a0b7a176a6fae40775b0b43d1e21c7740409` 的 D/B/C/A 能力，避免重复开发。
- 当前会话定位：`/plan`，只读审计 + 计划编排；不执行 merge，不执行 push，不修改业务代码。
- 基线口径：
  - 业务基线固定为 `renderdoc-ai/main@87c5a0b7a176a6fae40775b0b43d1e21c7740409`
  - integration 参考固定为 `codex/integration/renderdoc-ai-20260314-r2@87c5a0b7a176a6fae40775b0b43d1e21c7740409`
  - 历史 integration 仅作参考：`codex/integration/renderdoc-ai-20260311@a961caccec5fef47f5d78cb165dc96347d5c0706`
- 组织方式：不再恢复四人并行；改为我单人按 `D -> B -> C -> A` 顺序收口，但仍遵守四模块边界。
- 用户新优先级：
  - 人工测试后置，不作为当前第一优先级 blocker。
  - 当前最重要的是“对齐主线、避免遗漏、准备可放行候选”。
- 约束继承：
  - 不新增第二套 schema/template/report。
  - 不接受 `test_output` 或其他验证产物进入候选。
  - 禁入旧 A 线 `codex/agenta/mcp-skill-snapshot-consumer@d66d0f73b68596c7bc6e656b072ac93ff172f80c`。
  - merge/push 必须等待用户显式批准。
- 本计划基于本地检索（MCP unavailable）。

## Current State Snapshot

- 根仓 `D:\Code\git\renderdoc` 当前分支：`codex/local-clean-main@b8db8b4525f416549ec3c89682864c8024806aca`
- 根仓当前不是干净控制态，存在控制文档外的未解释本地改动：
  - `qrenderdoc/Code/Interface/PersistantConfig.cpp`
  - `qrenderdoc/Code/Interface/RemoteHost.cpp`
  - `qrenderdoc/Code/ReplayManager.cpp`
  - `qrenderdoc/Windows/Dialogs/LiveCapture.*`
  - `qrenderdoc/Windows/Dialogs/RemoteManager.*`
  - `qrenderdoc/qrenderdoc.pro`
  - `qrenderdoc/qrenderdoc_local.vcxproj`
  - `renderdoc/android/android.*`
  - `renderdoc/android/android_tools.cpp`
- 这批改动不纳入本计划执行面；执行面固定为四个 `r3` worktree。
- `r3` 状态：
  - `D:\Code\git\renderdoc-agentd-r3`：`HEAD=87c5...`，仅计划文件有未提交更新。
  - `D:\Code\git\renderdoc-agentb-r3`：`HEAD=87c5...`，工作树干净。
  - `D:\Code\git\renderdoc-agentc-r3`：`HEAD=64449316043714b0058f8e1175ca2972c4812b77`，仅 `docs(plan)` 提交。
  - `D:\Code\git\renderdoc-agenta-r3`：`HEAD=87c5...`，仅计划文件有未提交更新。

## Mainline Recovery Goal

- 不是从旧执行分支继续开发，而是确认：
  - 哪些业务能力已经在主线。
  - 哪些只是验证/环境/证据缺口。
  - 哪些真的还需要最小代码补差。
- 优先顺序：
  1. 主线事实确认
  2. 自动化验证补齐
  3. 仅在自动化验证暴露真实缺陷时做最小代码修改
  4. 显式候选 SHA 审计
  5. 等待用户批准 merge

## File List

- D 线边界：
  - `D:\Code\git\renderdoc\qrenderdoc\Windows\MainWindow.h:309`
  - `D:\Code\git\renderdoc\qrenderdoc\Windows\MainWindow.cpp:71-83`
  - `D:\Code\git\renderdoc\qrenderdoc\Windows\MainWindow.cpp:3365-3415`
- B 线边界：
  - `D:\Code\git\renderdoc\qrenderdoc\Code\Analyzer\AnalyzerSnapshotAdapter.cpp:71-112`
  - `D:\Code\git\renderdoc\qrenderdoc\Code\Analyzer\AnalyzerSnapshotAdapter.cpp:885-902`
  - `D:\Code\git\renderdoc\qrenderdoc\Code\Analyzer\AnalyzerExporter.cpp:45-75`
- C 线边界：
  - `D:\Code\git\renderdoc\scripts\rdc_analyzer\parsers\snapshot_compare_adapter.py:8-30`
  - `D:\Code\git\renderdoc\scripts\rdc_analyzer\compare_rdc.py:373-490`
  - `D:\Code\git\renderdoc\scripts\rdc_analyzer\compare_rdc.py:699-741`
  - `D:\Code\git\renderdoc\scripts\rdc_analyzer\diff\junit_exporter.py:21-31`
- A 线边界：
  - `D:\Code\git\renderdoc\tools\mcp\snapshot_consumer.py:463-540`
  - `D:\Code\git\renderdoc\tools\mcp\snapshot_consumer.py:647-739`
  - `D:\Code\git\renderdoc\tools\mcp\tests\test_snapshot_consumer.py:195-303`
  - `D:\Code\git\renderdoc\scripts\rdc_analyzer\mcp_examples\run_query.py`
  - `D:\Code\git\renderdoc\scripts\rdc_analyzer\mcp_examples\snapshot_consume.py:94-104`
- 计划与控制文档：
  - `D:\Code\git\renderdoc\docs\product\development_charter.md:43-65`
  - `D:\Code\git\renderdoc\docs\product\development_charter.md:73-127`
  - `D:\Code\git\renderdoc\docs\product\development_charter.md:178-185`
  - `D:\Code\git\renderdoc\docs\product\snapshot_schema_v1.md:19-56`
  - `D:\Code\git\renderdoc\docs\product\template_contract_v1.md:165-217`
  - `D:\Code\git\renderdoc\docs\product\mcp_query_contract_v1.md:25-34`
  - `D:\Code\git\renderdoc\plans\2026-03-11-170659-AgentD-M0C-Android-Launch-Diagnose.md`
  - `D:\Code\git\renderdoc\plans\2026-03-13-155348-AgentB-M5-GUI-Stability.md`
  - `D:\Code\git\renderdoc\plans\2026-03-13-155350-AgentC-M6-Compare-CI.md`
  - `D:\Code\git\renderdoc\plans\2026-03-13-155741-AgentA-M5-Skill-MVP.md`

## Build / Test / Lint Quick Guide

- `/plan` 阶段只记录，不在本文件中授权执行构建。
- Git / 边界 / 禁止项审计：
  - `git status --porcelain=v1 -b`
  - `git diff --name-only renderdoc-ai/main...HEAD`
  - `git diff --name-status renderdoc-ai/main...HEAD`
  - `git for-each-ref --contains=d66d0f73b68596c7bc6e656b072ac93ff172f80c --format='%(refname:short) %(objectname)' refs/heads`
- D 自动验证：
  - `git -C D:\Code\git\renderdoc-agentd-r3 diff --name-only renderdoc-ai/main...HEAD`
  - `rg -n "showAndroidLaunchFailure|JDWPFailure|AndroidLayerConfFailed|AndroidAPKInstallFailed|InjectionFailed" qrenderdoc/Windows/MainWindow.cpp qrenderdoc/Windows/MainWindow.h`
- B 自动验证：
  - `git -C D:\Code\git\renderdoc-agentb-r3 status --porcelain=v1 -b`
  - `Test-Path D:\Code\git\renderdoc-agentb-r3\x64\Development\qrenderdoc.exe`
  - `Get-Item D:\Code\git\renderdoc-agentb-r3\scripts\rdc_analyzer\test_captures\test_game.rdc | Select-Object Length`
  - 若存在有效 `.rdc`：`qrenderdoc.exe` + auto-export smoke
- C 自动验证：
  - `py -3 -m pytest D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tests\test_snapshot_compare_adapter.py -q`
  - `py -3 -m pytest D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tests\test_compare_rdc.py -q`
  - `py -3 -m pytest D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tests\test_compare_ci.py -q`
  - `py -3 -m pytest D:\Code\git\renderdoc-agentc-r3\scripts\rdc_analyzer\tests\test_junit_exporter.py -q`
- A 自动验证：
  - `py -3 -m pytest D:\Code\git\renderdoc-agenta-r3\tools\mcp\tests\test_snapshot_consumer.py -q`
  - `py -3 D:\Code\git\renderdoc-agenta-r3\scripts\rdc_analyzer\mcp_examples\run_query.py --method get_capture_status --params "{}"`
  - `py -3 D:\Code\git\renderdoc-agenta-r3\scripts\rdc_analyzer\mcp_examples\snapshot_consume.py --snapshot <snapshot> --execute --out-json <json> --out-md <md> --out-cmd <cmd>`

## Task Checklist

- [x] Gate-0：冻结执行面，只使用 `renderdoc-agentd-r3 / agentb-r3 / agentc-r3 / agenta-r3`，不在根仓执行 DBCA 业务收口。
- [x] Gate-0：重新审计根仓脏改，明确其与 DBCA 收口无关，只作为风险记录，不卷入候选判断。
- [x] D-1：在 `agentd-r3` 重新确认 `MainWindow.*` 相对主线无业务差异。
- [x] D-2：把 D 线剩余项降级为“人工/设备覆盖 backlog”，不再作为当前主线收口 blocker。
- [x] D-3：仅当自动审计发现 `MainWindow.*` 与主线预期不一致时，才回到 D 边界做最小修复。
- [x] B-1：在 `agentb-r3` 复核当前 GUI 导出链是否已经具备可执行二进制。
- [x] B-2：定位可用于 auto-export smoke 的有效 `.rdc` 样本；若仓内没有，明确记录为输入资产 blocker，而不是代码 blocker。
- [ ] B-3：若存在有效样本，执行最小 GUI export smoke，核对 `snapshot.v1 / availability / preflight / pipeline_ref`。
- [ ] B-4：仅当 smoke 暴露真实导出缺陷时，才回到 `AnalyzerSnapshotAdapter.cpp / AnalyzerExporter.cpp / AnalyzerReportViewer.*` 做最小修复。
- [x] C-1：把 `agentc-r3` 固定为回归线，默认不新增业务开发。
- [x] C-2：只有在 B/A 改动触及共享契约、compare 主链或 CI 输出时，才重跑 golden compare 并补收口记录。
- [x] A-1：在 `agenta-r3` 重新跑 `pytest + get_capture_status + snapshot_consume --execute`。
- [x] A-2：若 health probe 继续返回 `timeout` 或 `bridge_unavailable`，先按配置/运行态问题处理，不直接判定为实现缺陷。
- [x] A-3：仅当环境恢复后仍出现契约违背，才回到 `tools/mcp/* + mcp_examples/*` 边界做最小修复。
- [x] Gate-1：对四条线统一执行禁止项扫描，确认无第二套 schema/template/report，且无 `test_output` 候选增量。
- [x] Gate-2：只接受显式候选 SHA，不接受浮动 HEAD，不接受旧 A 禁入分支。
- [x] Gate-3：整理候选清单与 merge 草案，等待用户批准后再执行实际 merge。

## Pseudo-code

```text
for lane in [D, B, C, A] in order:
  audit git status / merge-base / mainline diff
  if lane has no business diff and only historical verification gaps:
    mark lane as "mainline already absorbed"
  else:
    run smallest automatic validation for that lane
    if validation exposes code defect within allowed boundary:
      prepare minimal patch scope
    else if validation only exposes environment/manual blocker:
      record blocker, do not create code delta

after all lanes:
  scan candidate diff for:
    - forbidden test_output
    - second schema/template/report
    - out-of-boundary files
  collect explicit SHA only
  draft merge order D -> B -> C -> A
  stop and wait for user approval before merge/push
```

## Impact Analysis

- D：
  - 预期影响：大概率 no-op；当前代码已在主线，剩余主要是真机覆盖缺口。
  - 风险：若误把设备覆盖问题当代码缺陷，会对 `MainWindow.*` 造成无意义改动。
- B：
  - 预期影响：最可能成为本轮唯一需要代码补差的模块，因为它既在主线、又最依赖真实导出 smoke。
  - 风险：当前仓内缺少有效 `.rdc` 样本时，容易把输入资产问题误判为导出器问题。
- C：
  - 预期影响：默认不改代码，只做 compare/CI 回归守门。
  - 风险：若 B/A 调整共享契约而不回归 compare，可能产生静默偏移。
- A：
  - 预期影响：可能只需环境恢复，不一定需要代码改动。
  - 风险：live bridge 的 `timeout` 目前更像配置/运行态问题，若直接改协议逻辑，容易越界造出第二套查询口径。

## Risks / Blockers

- 根仓存在未解释脏改，这是当前最大的控制风险；本计划不在根仓做 DBCA 代码收口。
- D 线尚未对 `JDWPFailure`、`AndroidLayerConfFailed` 完成完整真机覆盖；按用户新优先级，这两项降级为后置 backlog。
- B 线缺少有效 `.rdc` smoke 输入时，无法完成有意义的 GUI export 验证。
- A 线 live bridge 仍可能保持 `timeout`；若 `%TEMP%\renderdoc_mcp` 只有 `request.json` 没有 `response.json`，优先按环境恢复处理。
- 旧 A 线 `d66d0f73b...` 必须永久隔离；其内容仅是 `test_output/agenta_snapshot_smoke/*` 证据提交，不得并入候选。

## Decisions

- 决定 1：当前以“主线收口”而不是“旧分支串行合并”作为第一目标。
- 决定 2：人工测试与真机覆盖后置；当前只把自动化验证和代码边界审计作为前置 gate。
- 决定 3：C 线默认冻结为回归线，不再主动扩展 compare 功能面。
- 决定 4：如果 B/A 最终均未产生业务差异，则当前阶段可能没有新的业务候选 SHA，主线即为收口结果。
- 决定 5：任何 merge 操作都必须在显式候选 SHA + 用户批准后执行。

## Verification / Acceptance

- Definition of Done:
  - [ ] 四个 `r3` worktree 都重新完成 `git status --porcelain=v1 -b` 与 `git diff renderdoc-ai/main...HEAD` 审计。
  - [ ] D 被明确归类为“已进主线，仅余后置人工覆盖”或生成最小修复候选。
  - [ ] B 完成“有效样本存在性判断”与可执行 smoke，或明确记录为输入资产 blocker。
  - [ ] C 完成“冻结回归线”确认；若共享契约未变，则不新增代码候选。
  - [ ] A 完成 `pytest + health probe + execute` 复核，并把 `timeout` 明确分类为环境问题或代码问题。
  - [ ] 禁止项扫描通过：无第二套 schema/template/report，无 `test_output` 候选增量。
  - [ ] 如有候选，只保留显式 SHA，并附边界审计、验证命令和结果摘要。
  - [ ] merge 命令草案已准备，但未执行，等待用户批准。

## Merge Recommendation Draft

- 当前默认建议：先不 merge，先完成 Gate-0 / D-1 / B-1 / A-1 这四个快速确认步骤。
- 若后续 `/do` 结果显示：
  - D 无代码差异
  - B 无代码差异或仅最小修复
  - C 无代码差异
  - A 无代码差异或仅最小修复
  则 merge 顺序仍按 `D -> B -> C -> A`，但只 merge 真正存在的候选 SHA。
- 命令草案：
  - `git -C D:\Code\git\renderdoc-main-merge merge --no-ff <candidate-sha>`
  - `git -C D:\Code\git\renderdoc-main-merge log --oneline --decorate -n 5`
  - `git -C D:\Code\git\renderdoc-main-merge diff --name-only renderdoc-ai/main...HEAD`

## Next Steps

1. 进入 `/do` 后先做 Gate-0：重新审计四个 `r3` worktree 与根仓脏改边界。
2. 然后按 `D -> B -> C -> A` 做自动化收口，跳过人工测试项。
3. 只要某条线没有新的业务差异，就立刻从“待开发”降级为“已在主线”。
4. 出现新的业务候选 SHA 后，再向用户提交 merge 放行建议。

## /do Execution Log (Lead, 2026-04-23 - Gate-0 + Mainline Reconvergence)

- 执行范围：
  - 仅审计并验证：
    - `D:\Code\git\renderdoc-agentd-r3`
    - `D:\Code\git\renderdoc-agentb-r3`
    - `D:\Code\git\renderdoc-agentc-r3`
    - `D:\Code\git\renderdoc-agenta-r3`
  - 未在根仓 `D:\Code\git\renderdoc` 进行 DBCA 业务代码修改。
  - 未执行 merge / push。

- Gate-0 审计：
  - `git -C D:\Code\git\renderdoc-agentd-r3 status --porcelain=v1 -b`
    - 结果：仅 `plans/2026-03-11-170659-AgentD-M0C-Android-Launch-Diagnose.md` 本地修改。
  - `git -C D:\Code\git\renderdoc-agentb-r3 status --porcelain=v1 -b`
    - 结果：干净。
  - `git -C D:\Code\git\renderdoc-agentc-r3 status --porcelain=v1 -b`
    - 结果：`ahead 1`，候选差异仅 `plans/2026-03-13-155350-AgentC-M6-Compare-CI.md`。
  - `git -C D:\Code\git\renderdoc-agenta-r3 status --porcelain=v1 -b`
    - 结果：仅 `plans/2026-03-13-155741-AgentA-M5-Skill-MVP.md` 本地修改。
  - `git -C D:\Code\git\renderdoc status --short --branch`
    - 结果：根仓仍含 `qrenderdoc/Code/Interface/*`、`qrenderdoc/Windows/Dialogs/*`、`renderdoc/android/*` 等未解释脏改，仅作为风险记录，不纳入 DBCA 候选。

- D 收口：
  - `git -C D:\Code\git\renderdoc-agentd-r3 diff --name-only renderdoc-ai/main...HEAD`
    - 结果：空；无业务候选差异。
  - `git -C D:\Code\git\renderdoc-agentd-r3 diff -- plans/2026-03-11-170659-AgentD-M0C-Android-Launch-Diagnose.md`
    - 结果：仅计划日志补记，记录了设备覆盖与 Android 工件验证。
  - 结论：
    - D 线当前不需要代码补差。
    - `JDWPFailure` / `AndroidLayerConfFailed` 继续归类为人工/设备覆盖 backlog，不阻塞当前主线收口。

- B 收口：
  - `Test-Path D:\Code\git\renderdoc-agentb-r3\x64\Development\qrenderdoc.exe`
    - 结果：`True`
  - `Get-Item D:\Code\git\renderdoc-agentb-r3\scripts\rdc_analyzer\test_captures\test_game.rdc | Select-Object FullName,Length`
    - 结果：`Length=3`
  - `rg --files -g "*.rdc" D:\Code\git\renderdoc-agentb-r3 D:\Code\git`
    - 结果：仅发现多份 `test_game.rdc` 占位文件，未发现有效 GUI smoke 输入样本。
  - 结论：
    - B 线当前 blocker 是输入资产，不是已确认的导出器代码缺陷。
    - 在未获得有效 `.rdc` 样本前，不进入 `AnalyzerSnapshotAdapter.cpp / AnalyzerExporter.cpp / AnalyzerReportViewer.*` 修复。

- C 收口：
  - `git -C D:\Code\git\renderdoc-agentc-r3 diff --name-only renderdoc-ai/main...HEAD`
    - 结果：`plans/2026-03-13-155350-AgentC-M6-Compare-CI.md`
  - `py -3 -m pytest ...test_snapshot_compare_adapter.py -q` -> `3 passed`
  - `py -3 -m pytest ...test_compare_rdc.py -q` -> `14 passed`
  - `py -3 -m pytest ...test_compare_ci.py -q` -> `3 passed`
  - `py -3 -m pytest ...test_junit_exporter.py -q` -> `20 passed`
  - 结论：
    - C 线维持“回归线”定位。
    - 当前无新的 compare/CI 业务候选。

- A 收口：
  - `py -3 -m pytest D:\Code\git\renderdoc-agenta-r3\tools\mcp\tests\test_snapshot_consumer.py -q`
    - 结果：`10 passed in 0.06s`
  - `py -3 D:\Code\git\renderdoc-agenta-r3\scripts\rdc_analyzer\mcp_examples\run_query.py --method get_capture_status --params "{}"`
    - 结果：`ok=false`，`error.code=bridge_unavailable`
    - 附加证据：`ipc_dir_exists=false`、`request_present=false`、`response_present=false`
  - 通过测试夹具生成临时快照：
    - `C:\Users\lizhirui01\AppData\Local\Temp\m5_skill_contract_snapshot.json`
  - `py -3 ...snapshot_consume.py --snapshot C:\Users\lizhirui01\AppData\Local\Temp\m5_skill_contract_snapshot.json --execute ...`
    - 结果摘要：`gaps=3 detail_queries=5 commands=6 execute=True status=blocked health_ok=False`
    - `consumer.execute.json` 摘要：
      - `enrichment.status=blocked`
      - `blockers[0].code=bridge_unavailable`
      - `fanout.detail_query_count=5`
      - `fanout.command_count=6`
      - `commands[0]=get_capture_status`
      - `recovery_hint=Start RenderDoc GUI, enable the MCP Bridge extension, then retry get_capture_status.`
  - 结论：
    - A 线当前 blocker 是运行环境未启动，不是契约消费逻辑回归。
    - 在 RenderDoc GUI / MCP Bridge 可用前，不进入 `tools/mcp/*` 业务修复。

- Gate-1 / Gate-2：
  - `git -C D:\Code\git\renderdoc for-each-ref --contains=d66d0f73b68596c7bc6e656b072ac93ff172f80c --format='%(refname:short) %(objectname)' refs/heads`
    - 结果：仅 `codex/agenta/mcp-skill-snapshot-consumer d66d0f73b...`
  - 当前四条 `r3` 线的候选差异中：
    - 无 `test_output` 候选增量
    - 无新的第二套 schema/template/report 候选增量
    - 无越界业务文件候选
  - 结论：
    - 继续只接受显式候选 SHA。
    - 旧 A 禁入线保持隔离。

- 当前阶段结论：
  - D：主线已吸收，后置人工覆盖 backlog。
  - B：等待有效 `.rdc` 输入资产，暂无代码补差依据。
  - C：回归通过，无新业务候选。
  - A：自动化逻辑通过，运行环境 blocker 明确为 `bridge_unavailable`。

- 2026-04-23 真实 `.rdc` GUI + MCP 复核（基于本地检索（MCP unavailable））：
  - 输入样本：
    - `Get-Item D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc | Select-Object FullName,Length,LastWriteTime`
    - 结果：真实样本存在，`Length=1438627413`。
  - 代码链路复核：
    - `Get-Content D:\Code\git\renderdoc-agentb-r3\qrenderdoc\Windows\AnalyzerReportViewer.cpp | Select-Object -Skip 543 -First 132`
    - 结果：`OnCaptureLoaded()` 只重置状态，不会自动 build report。
    - `Get-Content D:\Code\git\renderdoc-agentb-r3\qrenderdoc\Windows\AnalyzerReportViewer.cpp | Select-Object -Skip 630 -First 48`
    - 结果：`RefreshReport()` 通过 `m_Ctx.Replay().AsyncInvoke(...)` 构建快照，并在 GUI 回调末尾调用 `TryAutoExport()`。
    - `Get-Content D:\Code\git\renderdoc-agentb-r3\qrenderdoc\Code\Interface\QRDInterface.h | Select-Object -Skip 1153 -First 16`
    - 结果：`IAnalyzerReportViewer::RefreshReport()` 是反射到 Python 的公开接口，可由 `pyrenderdoc.GetAnalyzerReportViewer().RefreshReport()` 直接触发。
    - `Get-Content C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_b_gui_poll.py`
    - 结果：旧脚本只调用 `ShowAnalyzerReportViewer()`，没有调用 `RefreshReport()`；上一轮 `viewer_present` 但无导出文件的现象，来自验证脚本遗漏关键 build 动作，不是导出器代码已证实失效。
  - 实际运行：
    - 启动命令：
      - `Start-Process D:\Code\git\renderdoc-agentb-r3\x64\Development\qrenderdoc.exe --python C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_b_gui_refresh_export.py D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc`
      - 环境：
        - `RENDERDOC_ANALYZER_AUTO_EXPORT_DIR=C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_b_gui_export_v2`
        - `RENDERDOC_ANALYZER_AUTO_EXPORT_EXIT=0`
    - `Get-Content C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_b_ui_state_v2.json`
    - 结果：
      - `phase=done`
      - `capture_loaded=true`
      - `viewer_present=true`
      - `refresh_called=true`
      - `snapshot_exists=true`
      - `snapshot_size=1822227`
    - `Get-ChildItem C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_b_gui_export_v2`
    - 结果：
      - `analysis.json` `Length=805711`
      - `capture_context.json` `Length=851`
      - `issues_export.csv` `Length=203`
      - `issues_export.md` `Length=207`
      - `snapshot.v1.json` `Length=1822227`
    - `tasklist /FI "PID eq 44684"`
    - 结果：`qrenderdoc.exe` 仍存活，验证时 `PID=44684`，`Mem Usage=2,954,380 K`。
  - A 线 live probe（同一 GUI 会话）：
    - `py -3 D:\Code\git\renderdoc-agenta-r3\scripts\rdc_analyzer\mcp_examples\run_query.py --method get_capture_status --params "{}"`
    - 结果：`ok=true`，`loaded=true`，`filename=D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc`
    - `py -3 D:\Code\git\renderdoc-agenta-r3\scripts\rdc_analyzer\mcp_examples\run_query.py --method get_frame_summary --params "{}"`
    - 结果：
      - `ok=true`
      - `statistics.draw_calls=281`
      - `statistics.dispatches=56`
      - `resource_counts.textures=157`
      - `resource_counts.buffers=215`
      - `total_actions=435`
    - 结论：A 线当前不仅 health probe 恢复，而且已能在真实 capture 上返回 frame summary 级别的实质查询结果。
  - A 线真实快照消费闭环：
    - `py -3 D:\Code\git\renderdoc-agenta-r3\scripts\rdc_analyzer\mcp_examples\snapshot_consume.py --snapshot C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_b_gui_export_v2\snapshot.v1.json --execute --out-json C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_a_consume_real.execute.json --out-md C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_a_consume_real.execute.md --out-cmd C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_a_consume_real.execute.cmds.txt`
    - 结果：`[SUMMARY] gaps=9 detail_queries=5 commands=6 execute=True status=executed health_ok=True`
    - `Get-Content C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_a_consume_real.execute.md -First 120`
    - 结果摘要：
      - `capture_name=EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc`
      - `schema_version=snapshot.v1`
      - `MCP Supplement status=executed`
      - `planned_queries=5`
      - `bridge_calls=6`
      - `health_probe: ok=True loaded=True`
    - `Get-Content C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_a_consume_real.execute.cmds.txt -First 120`
    - 结果：命令清单为 `get_capture_status + 5x get_pipeline_state(event_id=581/590/599/633/642)`。
  - 结论修正（覆盖前文 B/A blocker 判断）：
    - B：主链 GUI auto-export 已通过真实 `.rdc` 样本验证；上一轮 blocker 来自验证脚本缺少 `RefreshReport()`，不是已确认的业务代码缺陷。
    - A：主链 MCP/Skill consumer 已在同一 GUI 会话上恢复；上一轮 `timeout` 结论不能再单独归类为协议回归，更符合“旧验证路径未触发 build + 进程结束后遗留 IPC 目录”的运行态现象。
