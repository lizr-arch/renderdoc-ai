# 完成一次任务/修改后的自检清单（本仓库 Agents.md + 官方贡献文档）

## 修改前
- 明确要改的行为/范围；大改动先写 plan（仓库 Agents.md 有 /spec /plan /do 约束与 plan 文件产物要求）。
- 避免触碰：`renderdoc/3rdparty/`、`build*/`（仓库 Agents.md 明确禁止）。

## 修改后（最小自检）
- C++：对改动文件运行 `clang-format`（RenderDoc 文档建议 clang-format 15.0，见 `docs/CONTRIBUTING.md`）。
- 测试：目前多为 ad-hoc（`docs/CONTRIBUTING/Testing.md`），至少手动覆盖你改动附近的功能路径。

## 交付
- 若进入 /do 阶段：按仓库 Agents.md 要求同步更新 `plans/*.md` 勾选项、记录风险/阻塞。
- Git：仓库 Agents.md 要求按 Conventional Commits 及时提交（每个独立任务完成就提交）。
