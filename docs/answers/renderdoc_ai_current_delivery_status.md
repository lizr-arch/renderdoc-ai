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
> conflict_points:
> - A 线仅按 `runtime-surface candidate` 收口；更大方法集的 repo-local handler/source 仍未确认
> - A/B 已合流到 `codex/lead/merge-a-b-20260424`、推送到 `renderdoc-ai`，并进入 `renderdoc-ai/main@25fd5be9dc844a59a4b10897c7b4105141dcf127`
> - PR #2 已 `closed` / `merged=true`，`merge_commit_sha=25fd5be9dc844a59a4b10897c7b4105141dcf127`
> - 本机 `gh` CLI 当前因 `C:\Users\lizhirui01\AppData\Roaming\GitHub CLI\config.yml` 权限失败；PR/GitHub/main 合流已改用 GitHub connector 完成
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
  - A 线更大方法集的 repo-local handler/source 仍未确认，当前保留为 `A-contract-followup`
  - D 线真机 Android 回归当前暂停
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

- P1：`A-contract-followup` 已完成缺口收敛，但仍是 `BLOCK / scoped`。完整 `mcp-query.v1` 方法面包括 Capture / Actions / Search / Pipeline / Resources 多组方法；当前 merge-gate 真实验证面主要覆盖 `get_capture_status`、`get_frame_summary`、`get_pipeline_state`、`get_texture_data`，所以 A 线仍只能宣称 `runtime-surface candidate`。
- P2：根仓控制文档同步为 `PASS / local-only`。`D:\Code\git\renderdoc` 仍是控制/文档脏树，不作为业务实现面；当前状态继续收敛在 `docs/product/delivery_surfaces_status.md` 与本文件，不新增第二套 current-status 文档。
- P3：GitHub / gh 工具链恢复为 `PARTIAL PASS`。默认 `gh` 仍被 `C:\Users\lizhirui01\AppData\Roaming\GitHub CLI\config.yml` 权限阻断；改用仓库内临时 `GH_CONFIG_DIR=D:\Code\git\renderdoc\.tmp-gh-config` 后 `gh --version` 可运行，但没有登录态。

命令证据（基于本地检索，MCP unavailable）：

- P1 契约面：`Select-String -Path D:\Code\git\renderdoc\docs\product\mcp_query_contract_v1.md -Pattern '^##|method|handler|source|get_capture_status|get_frame_summary|get_pipeline_state|get_draw|get_texture|get_buffer|request\.json|response\.json'`
- P1 实际 runtime-surface：`Get-ChildItem -LiteralPath D:\Code\git\renderdoc-merge-gate-20260424\tools\mcp -Recurse -File -Include *.py | Select-String -Pattern 'get_capture_status|get_frame_summary|get_pipeline_state|get_draw|get_texture|get_buffer|request\.json|response\.json|METHODS|method'`
- P1 smoke helper：`Get-ChildItem -LiteralPath D:\Code\git\renderdoc-merge-gate-20260424\scripts\rdc_analyzer\mcp_examples -Recurse -File -Include *.py | Select-String -Pattern 'get_capture_status|get_frame_summary|get_pipeline_state|get_draw|get_texture|get_buffer|request\.json|response\.json|METHODS|method'`
- P2 根仓状态：`git -C D:\Code\git\renderdoc status --short --branch`
- P2 控制文档状态：`git -C D:\Code\git\renderdoc status --short -- docs\product\delivery_surfaces_status.md docs\answers\renderdoc_ai_current_delivery_status.md plans\2026-04-23-213050-Lead-A-Then-B-Gap-Closure.md`
- P3 默认 gh 失败：`gh --version`
- P3 配置权限：`icacls "C:\Users\lizhirui01\AppData\Roaming\GitHub CLI\config.yml"`
- P3 临时配置可启动：`New-Item -ItemType Directory -Force -Path 'D:\Code\git\renderdoc\.tmp-gh-config' | Out-Null; $env:GH_CONFIG_DIR='D:\Code\git\renderdoc\.tmp-gh-config'; gh --version`
- P3 临时配置未认证：`$env:GH_CONFIG_DIR='D:\Code\git\renderdoc\.tmp-gh-config'; gh auth status --hostname github.com`

下一步：

- P1 后续如继续实现，应单开 `A-contract-followup` 分支或 worktree，从 `renderdoc-ai/main@25fd5be9dc844a59a4b10897c7b4105141dcf127` 追 repo-local handler/source。
- P2 后续如需要保留控制面记录，应单独做 docs/control 提交，不混入业务实现提交。
- P3 后续如继续走 CLI PR 操作，要么修复默认 GitHub CLI 配置文件权限，要么在临时 `GH_CONFIG_DIR` 下重新 `gh auth login`。
