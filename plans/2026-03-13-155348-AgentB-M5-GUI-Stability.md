# 计划：AgentB / M5 GUI Snapshot Export Stability

时间：2026-03-13 15:53:48 | 负责人：AgentB

## Scope / Assumptions

- 范围限定为 `qrenderdoc/Code/Analyzer/*`、`qrenderdoc/Windows/AnalyzerReportViewer.*` 与本计划文件。
- 不新增 schema、模板或报告系统，不让 `analysis.json` 成为 `snapshot.v1` 的事实来源。
- M5 不临时合成 `pipelines[]`；仅修复缺口表达、字段口径与导出稳定性。

## Build / Test / Lint Quick Guide

- 构建命令仅记录，未获授权前不执行：`msbuild renderdoc.sln /p:Configuration=Development /p:Platform=x64`
- 代码级验证：`rg -n "pipeline_ref|missing_fields|analysis.json|snapshot.v1" qrenderdoc/Code/Analyzer qrenderdoc/Windows/AnalyzerReportViewer.cpp`
- 可选格式化：`clang-format -i qrenderdoc/Code/Analyzer/AnalyzerSnapshotAdapter.cpp qrenderdoc/Code/Analyzer/AnalyzerExporter.cpp`

## Task Checklist

- [x] 新增内部 gap helper，统一根级 `availability.missing_fields`、`preflight.missing_data` 与 section 状态。
- [x] 将关键子对象的 `availability` 统一为可预测口径，区分结构缺失与语义降级。
- [x] 修复 `actions[].pipeline_ref` 对空 `pipelines[]` 的悬空引用。
- [x] 在 exporter 中明确 `analysis.json` 为兼容 sidecar，而非 `snapshot.v1` 的事实来源。
- [x] 完成代码级验证并记录未执行构建的原因。

## Risks / Blockers

- `snapshot.v1` 契约仍在与离线路径对齐阶段，GUI 线不能自行扩展 `pipelines[]` 字段面。
- 当前轮未获构建授权，验证将以代码级静态检查为主。
- 已定位 `git.exe`：`D:\Program Files\Git\cmd\git.exe`。

## Verification / Acceptance

- `snapshot.v1` 顶层字段仍为 `snapshot_schema_v1` 规定集合。
- `availability` 与 `preflight` 的缺口字段来源一致，命名稳定。
- `actions[].pipeline_ref` 不再在 `pipelines[]` 为空时写出。
- `snapshot.v1` 继续由 `AnalyzerSnapshot + captureContext` 直接生成。
- 若未执行构建，最终回报明确写出“未执行构建，仅代码级验证”。

## /do Progress

- 2026-03-13 15:53:48：创建执行计划，准备修改 `AnalyzerSnapshotAdapter.cpp` 与 `AnalyzerExporter.cpp`。
- 2026-03-13 15:58:30：在 `AnalyzerSnapshotAdapter.cpp` 新增统一缺口 helper，收束根级/预检/对象级 availability 口径。
- 2026-03-13 15:59:20：移除空 `pipelines[]` 下的 `actions[].pipeline_ref` 写出，保留 `pipeline_ref` 为显式缺口字段。
- 2026-03-13 16:00:10：在 `AnalyzerExporter.cpp` 添加注释，固定 `analysis.json` 为兼容 sidecar，不参与 `snapshot.v1` 事实生成。
- 2026-03-13 16:01:05：执行 `clang-format -i` 格式化 `AnalyzerSnapshotAdapter.cpp` 与 `AnalyzerExporter.cpp`。
- 2026-03-13 16:02:51：完成代码级验证；本轮未执行构建，仅静态验证导出链与字段口径。
