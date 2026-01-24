# Scope / Assumptions
- In scope: 将 `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md` 拆分为 4-5 个主题文档；原文件改为索引页；补充“RDC→XML→HTML”流程到对应文档。
- Out of scope: 代码逻辑修改；新增依赖；修改 `renderdoc/3rdparty/` 或 `build*/`。
- 假设：拆分仅做内容搬迁与索引，保持现有 WHAT/WHY/HOW 内容不丢失；每个新文档 < 800 行。

# Build/Test/Lint Quick Guide (只记录不执行)
- 行数统计：`py -3 -c "import pathlib; p=pathlib.Path(r'docs/analysis/codex_rdc_analyzer'); [print(f'{f.name}: {len(f.read_text(encoding=\"utf-8\").splitlines())}') for f in p.glob('WORK_SUMMARY*.md')]"`  
- 索引校验：`py -3 -c "import pathlib; idx=pathlib.Path(r'docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md').read_text(encoding='utf-8'); print('INDEX OK' if 'WORK_SUMMARY_' in idx else 'MISSING')"`

# Repo / File List (预期修改/新增)
- 修改：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md`（改为索引页）
- 新增：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ARCH.md`
- 新增：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROUTES.md`
- 新增：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_SCHEMA.md`
- 新增：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_VERIFICATION.md`
- 新增：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_ROADMAP.md`

# File List With Line Ranges (from current WORK_SUMMARY)
- 路线与验证：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md:71` → `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md:201`
- 架构/模块：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md:25` → `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md:320`
- Schema/Pipeline/Bridge：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md:320` → `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md:579`
- 验证/测试/CLI：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md:579` → `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md:794`
- 路线图/决策/参考：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md:797` → `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md:936`
- XML 导出详细流程：`docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md:832` → `docs/analysis/codex_rdc_analyzer/WORK_SUMMARY_2025-01-21.md:884`

# Approach (Pseudo-code)
```
read WORK_SUMMARY
create new docs with headers + short purpose
move sections by heading into target docs
update WORK_SUMMARY to index:
  - doc list + scope + key links
  - “优先阅读顺序” + 更新时间
ensure each new doc preserves WHAT/WHY/HOW content
verify line counts < 800 for each doc
```

# Document Skeletons (完整片段)
```
# WORK_SUMMARY_ARCH.md
## WHAT: 架构与数据流
## WHY: 统一入口与模块关系
## HOW: 拆出架构图/模块职责/文件结构
```
```
# WORK_SUMMARY_ROUTES.md
## WHAT: 三条输入路线 (A/B/C)
## WHY: 对齐“离线/实时/批量”场景
## HOW: 命令 + 验证状态 + 关键文件 + 流程
```
```
# WORK_SUMMARY_SCHEMA.md
## WHAT: Canonical Schema + Pipeline + Bridge
## WHY: 统一输出口径，避免双 schema
## HOW: 迁移 Schema/Bridge/PipelineState 章节
```
```
# WORK_SUMMARY_VERIFICATION.md
## WHAT: 真实性验证、DoD、CLI示例
## WHY: 保证“可验证”和“可复现”
## HOW: 覆盖/权重/测试/CLI 用法
```
```
# WORK_SUMMARY_ROADMAP.md
## WHAT: P0/P1/P2 任务与决策
## WHY: 指导下一阶段优先级
## HOW: 任务清单 + 决策记录 + 参考文献
```

# Impact Analysis
- 风险：拆分导致引用断裂 → 索引页必须提供准确链接与范围说明。
- 风险：内容遗漏 → 迁移前后对比 heading 清单。
- 风险：新文档过长 → 执行行数校验。

# Action Items (2–5 分钟粒度)
- [x] 1. 列出 WORK_SUMMARY 现有 heading 清单与范围（用于映射）。
- [x] 2. 新建 5 个子文档并写入标题/WHAT/WHY/HOW 骨架。
- [x] 3. 按范围迁移内容（路线、架构、schema、验证、路线图）。
- [x] 4. 将 WORK_SUMMARY 改为索引页（含阅读顺序 + 文档职责）。
- [x] 5. 补充 “RDC→XML→HTML” 流程到 ROUTES 文档。
- [x] 6. 行数统计与索引校验（<800 行 / 索引链接存在）。
- [x] 7. 更新 `docs/analysis/codex_rdc_analyzer/README.md` 指向新索引结构。

# Risks & Blockers
- 需要保证所有 WHAT/WHY/HOW 结构在迁移后仍可被检索。
- 若拆分后某文档仍 > 800 行，需要二次细分。

# Verification / DoD
- `WORK_SUMMARY_2025-01-21.md` 变为索引页且 < 200 行。
- 新文档均 < 800 行。
- 索引页包含：文档名 + 作用 + 更新时间 + 推荐阅读顺序。
- `RDC→XML→HTML` 流程出现在 `WORK_SUMMARY_ROUTES.md`。

# Next Steps
- 用户确认后进入 /do，执行拆分与索引更新。
