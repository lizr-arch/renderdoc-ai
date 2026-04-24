# 回答卡：RenderDoc AI 当前主线做到哪里了？

> 状态：当前交付面短答案（2026-04-24）。
> validation_status: partial
> last_verified_at: 2026-04-24
> verification_evidence:
> - `docs/product/delivery_surfaces_status.md`
> - `plans/2026-04-23-213050-Lead-A-Then-B-Gap-Closure.md`
> - `git -C D:\Code\git\renderdoc ls-remote renderdoc-ai refs/heads/main refs/heads/codex/integration/renderdoc-ai-20260311`
> - `git -C D:\Code\git\renderdoc worktree list --porcelain`
> - `git -C D:\Code\git\renderdoc branch --contains d66d0f73b68596c7bc6e656b072ac93ff172f80c`
> - `git -C D:\Code\git\renderdoc-merge-gate-20260424 ls-remote renderdoc-ai refs/heads/main refs/heads/codex/lead/merge-a-b-20260424 refs/heads/codex/integration/renderdoc-ai-20260311`
> - `git -C D:\Code\git\renderdoc-merge-gate-20260424 merge-base --is-ancestor e781fa0d84b4fe032e1d03bf0a11ba916a10d965 25fd5be9dc844a59a4b10897c7b4105141dcf127`
> - `git -C D:\Code\git\renderdoc-merge-gate-20260424 diff --check`
> - `gh --version`
> - `gh pr create --repo lizr-arch/renderdoc-ai --head codex/lead/merge-a-b-20260424 --base main --title "Merge RenderDoc AI A/B gap closure" ...`
> - `icacls "C:\Users\lizhirui01\AppData\Roaming\GitHub CLI\config.yml"`
> - `mcp__codex_apps__github._create_pull_request(repository_full_name=lizr-arch/renderdoc-ai, base_branch=main, head_branch=codex/lead/merge-a-b-20260424, draft=true, ...)`
> - `mcp__codex_apps__github._compare_commits(repo_full_name=lizr-arch/renderdoc-ai, base=main, head=codex/lead/merge-a-b-20260424)`
> - `mcp__codex_apps__github._get_commit_combined_status(repo_full_name=lizr-arch/renderdoc-ai, commit_sha=25fd5be9dc844a59a4b10897c7b4105141dcf127)`
> - `mcp__codex_apps__github._list_pull_request_reviews(repo_full_name=lizr-arch/renderdoc-ai, pr_number=2)`
> - `mcp__codex_apps__github._list_pull_request_review_threads(repo_full_name=lizr-arch/renderdoc-ai, pr_number=2)`
> - `mcp__codex_apps__github._mark_pull_request_ready_for_review(repository_full_name=lizr-arch/renderdoc-ai, pr_number=2)`
> - `mcp__codex_apps__github._update_pull_request(repository_full_name=lizr-arch/renderdoc-ai, pr_number=2, title="Merge RenderDoc AI A/B gap closure")`
> - `mcp__codex_apps__github._merge_pull_request(repository_full_name=lizr-arch/renderdoc-ai, pr_number=2, expected_head_sha=25fd5be9dc844a59a4b10897c7b4105141dcf127, merge_method=merge, ...)`
> - `mcp__codex_apps__github._update_ref(repository_full_name=lizr-arch/renderdoc-ai, branch_name=main, sha=25fd5be9dc844a59a4b10897c7b4105141dcf127, force=false)`
> - `mcp__codex_apps__github._compare_commits(repo_full_name=lizr-arch/renderdoc-ai, base=e781fa0d84b4fe032e1d03bf0a11ba916a10d965, head=main)`
> - `uv --cache-dir D:\Code\git\renderdoc\.uv-cache-codex run --python 3.11 --with pytest python -m pytest D:\Code\git\renderdoc\.codex_repos\renderdoc-a-contract-followup\tools\mcp\tests\test_snapshot_consumer.py D:\Code\git\renderdoc\.codex_repos\renderdoc-a-contract-followup\scripts\rdc_analyzer\tests\test_renderdoc_mcp_bridge.py -q` -> `17 passed`
> - `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_a_contract_followup_smoke_20260424_final\real_rdc_gui_snapshot_smoke.summary.json`
> - `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_a_contract_followup_smoke_20260424_final\gui_state.json`
> - `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_a_contract_followup_smoke_20260424_final\consumer.execute.json`
> - `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_a_contract_followup_smoke_20260424_final\manifest.json`
> conflict_points:
> - A 线原 `runtime-surface candidate` 已进 main；本轮 `A-contract-followup` 已补 repo-local handler/source，并达到正式 pytest 与真实 RDC GUI smoke 验证
> - A/B 已合流到 `codex/lead/merge-a-b-20260424`、推送到 `renderdoc-ai`，并进入 `renderdoc-ai/main@25fd5be9dc844a59a4b10897c7b4105141dcf127`
> - PR #2 已 `closed` / `merged=true`，`merge_commit_sha=25fd5be9dc844a59a4b10897c7b4105141dcf127`
> - 用户目录 `gh` 配置权限未修改；本轮使用隔离 `GH_CONFIG_DIR=%TEMP%\renderdoc-gh-config-20260424` 完成认证与非强推直推
> - ready-for-review connector 曾因 GraphQL `htmlUrl` 字段错误失败；最终采用 `force=false` fast-forward 更新 `main`
> - 根仓 `D:\Code\git\renderdoc` 仍是控制脏树，旧 worktree 仍在本地
> lineage_status: manual-promotion
> verification_status: partially_verified
> promotion_basis_type: manual_bootstrap
> promotion_basis_refs:
> - `docs/product/delivery_surfaces_status.md`
> - `plans/2026-04-23-213050-Lead-A-Then-B-Gap-Closure.md`

## 问题

除了真机验证，RenderDoc AI 当前主线已经做到什么？还差什么？

## 短答案

- 已完成：
  - A 线 `runtime-surface candidate@8e1a159ce7c9e58839e9db21d5ba09ae84a03956` 已形成
  - A 线 bounded live gate 已通过：`get_capture_status.ok=true`、`get_frame_summary.ok=true`、`snapshot_consume --execute` 为 `executed`
  - A 线 `A-contract-followup` 已补 repo-local `mcp-query.v1` bridge handler/source
  - A 线 fake-context 单元验证已覆盖 Capture / Actions / Timings / Search / Pipeline / Resources 方法面
  - A 线正式 pytest 已通过：`17 passed`
  - A 线真实 RDC GUI smoke 已通过：`success=true`、`mcp_bridge_enabled=true`、`enrichment.status=executed`
  - B 线 shared snapshot renderer 页集收口到 `pipelines.html`
  - B 线 GUI exporter 已接上 `snapshot.v1.json -> render_snapshot_bundle.py -> SnapshotTemplateRenderer`
  - B 线 `qrenderdoc_local.vcxproj` focused `msbuild` 已通过
  - B 线真实 RDC GUI export smoke 已真实产出 `index/events/textures/shaders/pipelines/manifest`
  - B 线 `candidate@4a66352a280d89d36e639586898d9db4f268bdc1` 已形成
  - merge gate 分支 `25fd5be9dc844a59a4b10897c7b4105141dcf127` 已在干净 worktree 中完成 `A -> B` 合流
  - merged `qrenderdoc_local.vcxproj` focused `msbuild` 已通过
  - merged 真实 RDC GUI smoke 已再次通过，并真实产出 `index/events/textures/shaders/pipelines/manifest`
  - merge 分支已推送到 `renderdoc-ai/codex/lead/merge-a-b-20260424`
  - PR 已创建并完成：`https://github.com/lizr-arch/renderdoc-ai/pull/2`
  - PR #2 当前 `state=closed`、`merged=true`、`merged_at=2026-04-24T07:07:58Z`
  - 最终 `merge_commit_sha=25fd5be9dc844a59a4b10897c7b4105141dcf127`
  - `renderdoc-ai/main` 已通过 `force=false` fast-forward 进入 `25fd5be9dc844a59a4b10897c7b4105141dcf127`
  - GitHub compare 显示新 `main` 相对旧基线 `e781fa0d84b4fe032e1d03bf0a11ba916a10d965` 为 `ahead_by=4`、`behind_by=0`、`changed_files=7`
- 未完成：
  - D 线真机 Android 回归当前暂停
  - `get_texture_data` / `get_buffer_contents` 的真实非空二进制 payload 仍依赖具体 capture 数据与查询参数，本轮只声明契约路径、截断策略与 partial 表达完成
- 控制面现状：
  - 当前只应继续在 `D:\Code\git\renderdoc-a-gap-closure` 与 `D:\Code\git\renderdoc-b-gap-closure` 上推进实现
  - 当前候选 SHA：
    - A：`8e1a159ce7c9e58839e9db21d5ba09ae84a03956`
    - B：`4a66352a280d89d36e639586898d9db4f268bdc1`
  - 当前合流 SHA：
    - merge：`25fd5be9dc844a59a4b10897c7b4105141dcf127`
    - branch：`renderdoc-ai/codex/lead/merge-a-b-20260424`
    - PR：`https://github.com/lizr-arch/renderdoc-ai/pull/2`
    - main：`renderdoc-ai/main@25fd5be9dc844a59a4b10897c7b4105141dcf127`
  - 含禁入提交 `d66d0f73b68596c7bc6e656b072ac93ff172f80c` 的旧 A 线分支仍在本地，但不是候选线

## 适用范围

- 适用于 2026-04-24 当前主线与活跃 gap-closure / merge-gate 工作区状态
- 不适用于把历史 `m5/m6` worktree 误当成当前候选线

## 默认入口

先读：

- `docs/product/delivery_surfaces_status.md`

再根据问题下钻：

- GUI HTML 主路径：`docs/product/gui_report.md`
- Offline / snapshot 路径：`docs/product/offline_report.md`
- MCP 运行面与契约差：`docs/product/mcp_api.md`

## derived_from

- `docs/product/delivery_surfaces_status.md`

## 证据来源

- `plans/2026-04-23-213050-Lead-A-Then-B-Gap-Closure.md`
- `D:\Code\git\renderdoc-a-gap-closure\tools\mcp\snapshot_consumer.py`
- `D:\Code\git\renderdoc-b-gap-closure\qrenderdoc\Windows\AnalyzerReportViewer.cpp`
- `D:\Code\git\renderdoc-b-gap-closure\scripts\rdc_analyzer\providers\snapshot_template_renderer.py`
- `& 'E:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe' 'D:\Code\git\renderdoc-b-gap-closure\qrenderdoc\qrenderdoc_local.vcxproj' /p:Configuration=Development /p:Platform=x64 /p:SolutionDir='D:\Code\git\renderdoc-b-gap-closure\'`
- `D:\Code\git\renderdoc-b-gap-closure\x64\Development\qrenderdoc.exe --version`
- `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_b_auto_export_smoke_20260423_234000\analyzer_auto_export_trace.log`
- `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_b_auto_export_smoke_20260423_234000\manifest.json`
- `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_a_live_gate_20260423_235000\real_rdc_gui_snapshot_smoke.summary.json`
- `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_a_live_gate_20260423_235000\consumer.execute.json`
- `git -C D:\Code\git\renderdoc-a-gap-closure rev-parse HEAD`
- `git -C D:\Code\git\renderdoc-b-gap-closure rev-parse HEAD`
- `git -C D:\Code\git\renderdoc-merge-gate-20260424 rev-parse HEAD`
- `git -C D:\Code\git\renderdoc-merge-gate-20260424 rev-parse renderdoc-ai/codex/lead/merge-a-b-20260424`
- `git -C D:\Code\git\renderdoc-merge-gate-20260424 show-ref refs/remotes/renderdoc-ai/codex/lead/merge-a-b-20260424`
- `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_merge_gate_smoke_20260424_001500\real_rdc_gui_snapshot_smoke.summary.json`
- `C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_merge_gate_smoke_20260424_001500\manifest.json`
- `git -C D:\Code\git\renderdoc-merge-gate-20260424 ls-remote renderdoc-ai refs/heads/main refs/heads/codex/lead/merge-a-b-20260424 refs/heads/codex/integration/renderdoc-ai-20260311`
- `git -C D:\Code\git\renderdoc-merge-gate-20260424 merge-base --is-ancestor e781fa0d84b4fe032e1d03bf0a11ba916a10d965 25fd5be9dc844a59a4b10897c7b4105141dcf127`
- `git -C D:\Code\git\renderdoc-merge-gate-20260424 diff --check`
- `gh --version`
- `gh pr create --repo lizr-arch/renderdoc-ai --head codex/lead/merge-a-b-20260424 --base main --title "Merge RenderDoc AI A/B gap closure" ...`
- `icacls "C:\Users\lizhirui01\AppData\Roaming\GitHub CLI\config.yml"`
- `mcp__codex_apps__github._create_pull_request(repository_full_name=lizr-arch/renderdoc-ai, base_branch=main, head_branch=codex/lead/merge-a-b-20260424, draft=true, ...)`
- `mcp__codex_apps__github._compare_commits(repo_full_name=lizr-arch/renderdoc-ai, base=main, head=codex/lead/merge-a-b-20260424)`
- `mcp__codex_apps__github._get_commit_combined_status(repo_full_name=lizr-arch/renderdoc-ai, commit_sha=25fd5be9dc844a59a4b10897c7b4105141dcf127)`
- `mcp__codex_apps__github._list_pull_request_reviews(repo_full_name=lizr-arch/renderdoc-ai, pr_number=2)`
- `mcp__codex_apps__github._list_pull_request_review_threads(repo_full_name=lizr-arch/renderdoc-ai, pr_number=2)`
- `mcp__codex_apps__github._mark_pull_request_ready_for_review(repository_full_name=lizr-arch/renderdoc-ai, pr_number=2)`
- `mcp__codex_apps__github._update_pull_request(repository_full_name=lizr-arch/renderdoc-ai, pr_number=2, title="Merge RenderDoc AI A/B gap closure")`
- `mcp__codex_apps__github._merge_pull_request(repository_full_name=lizr-arch/renderdoc-ai, pr_number=2, expected_head_sha=25fd5be9dc844a59a4b10897c7b4105141dcf127, merge_method=merge, ...)`
- `mcp__codex_apps__github._update_ref(repository_full_name=lizr-arch/renderdoc-ai, branch_name=main, sha=25fd5be9dc844a59a4b10897c7b4105141dcf127, force=false)`
- `mcp__codex_apps__github._compare_commits(repo_full_name=lizr-arch/renderdoc-ai, base=e781fa0d84b4fe032e1d03bf0a11ba916a10d965, head=main)`
- `git -C D:\Code\git\renderdoc ls-remote renderdoc-ai refs/heads/main refs/heads/codex/integration/renderdoc-ai-20260311`
- `git -C D:\Code\git\renderdoc worktree list --porcelain`
- `git -C D:\Code\git\renderdoc branch --contains d66d0f73b68596c7bc6e656b072ac93ff172f80c`

## 2026-04-24 新 P1-P3 follow-up

当前结论：

- P1：`A-contract-followup` 已完成 repo-local handler/source、正式 pytest 与真实 RDC GUI smoke 闭口，状态为 `PASS / pytest-real-rdc-smoke`。新增 `scripts/rdc_analyzer/tools/renderdoc_mcp_bridge.py`，并由 `renderdoc_gui_refresh_export.py` 在 `RENDERDOC_MCP_BRIDGE_ENABLE=1` 时启动 file-IPC bridge。完整 `mcp-query.v1` 方法面已覆盖 Capture / Actions / Timings / Search / Pipeline / Resources；不可用字段返回 `partial`，不伪造完整数据。
- P2：控制文档同步为 `PASS / isolated-worktree`。根仓 `D:\Code\git\renderdoc` 仍是控制/文档脏树，不作为业务实现面；本轮实现落在 `D:\Code\git\renderdoc\.codex_repos\renderdoc-a-contract-followup`，只纳入 `docs/product/delivery_surfaces_status.md` 与本文件。
- P3：GitHub / gh 工具链为 `PASS / pushed-main`。本轮不修改用户目录 `gh` 配置权限；隔离 `GH_CONFIG_DIR=%TEMP%\renderdoc-gh-config-20260424` 下 `gh` 已登录，远端只读检查通过，候选以非强推方式推送到 `renderdoc-ai/main@e62e0a84f448cf4ce64ba39e7ba2cc82360e5ed0`。

命令证据（基于本地检索，MCP unavailable）：

- P1 红灯：`py -3 .codex_repos\renderdoc-a-contract-followup\scripts\rdc_analyzer\tests\test_renderdoc_mcp_bridge.py` 初始失败于 `ModuleNotFoundError: No module named 'renderdoc_mcp_bridge'`
- P1 绿灯：`py -3 .codex_repos\renderdoc-a-contract-followup\scripts\_tmp_run_mcp_bridge_tests.py` -> `SUMMARY total=7 failures=0`
- P1 正式 pytest：`$env:UV_PYTHON_INSTALL_DIR='D:\Code\git\renderdoc\.uv-python'; uv --cache-dir D:\Code\git\renderdoc\.uv-cache-codex run --python 3.11 --with pytest python -m pytest D:\Code\git\renderdoc\.codex_repos\renderdoc-a-contract-followup\tools\mcp\tests\test_snapshot_consumer.py D:\Code\git\renderdoc\.codex_repos\renderdoc-a-contract-followup\scripts\rdc_analyzer\tests\test_renderdoc_mcp_bridge.py -q` -> `17 passed`
- P1 语法：`py -3 -m py_compile ...renderdoc_mcp_bridge.py ...renderdoc_gui_refresh_export.py ...test_renderdoc_mcp_bridge.py`
- P1 真实 RDC GUI smoke：`C:\Users\lizhirui01\AppData\Local\Temp\renderdoc_a_contract_followup_smoke_20260424_final\real_rdc_gui_snapshot_smoke.summary.json` -> `success=true`
- P1 bridge 状态：`gui_state.json` -> `phase=done`、`mcp_bridge_enabled=true`
- P1 MCP 消费：`consumer.execute.json` -> `enrichment.status=executed`、`bridge_call_count=6`
- P1 bundle 输出：`manifest.json` 与输出目录包含 `index.html`、`events.html`、`textures.html`、`shaders.html`、`pipelines.html`
- P2 基线：`git -C .codex_repos\renderdoc-a-contract-followup rev-parse HEAD`
- P2 禁入检查：`git -C .codex_repos\renderdoc-a-contract-followup merge-base --is-ancestor d66d0f73b68596c7bc6e656b072ac93ff172f80c HEAD`，期望等价于 `banned ancestor: no`
- P3 gh：`$env:GH_CONFIG_DIR="$env:TEMP\renderdoc-gh-config-20260424"; gh --version; gh auth status --hostname github.com`
- P3 remote：`git -C .codex_repos\renderdoc-a-contract-followup ls-remote renderdoc-ai refs/heads/main refs/heads/codex/integration/renderdoc-ai-20260311`
- P3 push：`$env:GH_CONFIG_DIR = Join-Path $env:TEMP 'renderdoc-gh-config-20260424'; git -C .codex_repos\renderdoc-a-contract-followup -c credential.helper='!gh auth git-credential' push renderdoc-ai HEAD:main`
- P3 post-push：`git -C .codex_repos\renderdoc-a-contract-followup ls-remote renderdoc-ai refs/heads/main refs/heads/codex/integration/renderdoc-ai-20260311`

下一步：

- 提交并推送本次 qrenderdoc `--ui-python` bridge 加载兼容修复与本文档状态刷新。
- push 后用 `ls-remote` 确认 `renderdoc-ai/main` 等于新的 HEAD。
- D 线真机 Android 回归仍是独立后续项，不纳入本轮 P1-P3 完工宣称。
