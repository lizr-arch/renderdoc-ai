# RenderDoc 风格与约定

## C++ 代码风格（官方 + 仓库约束）
- 首选 clang-format 自动格式化（见 `docs/CONTRIBUTING/Developing-Change.md`）。
- 仓库根 `.clang-format`：
  - `IndentWidth: 2`
  - `ColumnLimit: 100`
  - `BreakBeforeBraces: Custom` + `BraceWrapping.AfterFunction: true`（Allman 风格大括号）

## 代码约束（官方文档）
来自 `docs/CONTRIBUTING/Developing-Change.md`：
- `auto` 仅用于 STL 迭代器和 lambda 等“类型太繁琐”的场景。
- 使用 `NULL`，不要用 `nullptr`。
- 一旦 if/else 某个分支用了大括号，其他分支也保持一致都用。
- 字符串默认 UTF-8（非 OS 特定代码中使用 `char*`/`rdcstr`，不要假设 ASCII）。
- 尽量少用 STL；用 `rdcarray` 替代 `std::vector`，用 `rdcstr` 替代 `std::string`。

## Python（仓库 Agents.md 约束）
- Python 缩进：4 空格（PEP8）。
- 本机执行：优先 `py -3`（避免 python 默认指向 2.7）。
