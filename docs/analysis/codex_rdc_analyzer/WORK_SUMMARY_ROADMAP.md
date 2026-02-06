# WORK_SUMMARY_ROADMAP — 路线图与决策记录

- WHAT: P0/P1/P2 任务、关键决策与参考资料。
- WHY: 确保下一阶段优先级一致、决策可追溯。
- HOW: 以任务清单 + 决策日志 + 参考链接呈现。

---

## 9. 待办事项（交接给下一个 Agent）

### 高优先级（P0）

- [x] **P0-NEW-3**: 规范化 `suggestion.verification_plan` 的 schema ✅ 2025-02-05
  - ✅ 统一 `how_to_verify` → `how_to_capture`
  - ✅ 统一 `expected_direction` 枚举值 (`increase/decrease/unchanged`)
  - ✅ 文件: `main.py:_build_suggestions()` 已标准化
  - ✅ DOD 测试: `test_dod_compliance.py::TestVerificationPlanSchema` 4/4 通过

### 中优先级（P1）

- [x] **P1-NEW-2**: 清理 pytest warnings ✅ 2025-02-05
  - ✅ 完整测试套件 (682 tests) 无 `PytestReturnNotNoneWarning`
  - 问题可能已在先前会话中修复

- [x] **P1-NEW-3**: 跨页面证据链导航 ✅ 2025-02-05
  - ✅ Texture → Event 链接 (textures.html?id=X&highlight=true)
  - ✅ Event → Shader 链接 (shaders.html?shader_id=X)
  - ✅ Shader → Event 返回链接
  - ✅ ID 类型兼容性修复 (String vs Number 比较)
  - 文件: `report_bundle_generator.py`, `textures.html`, `events.html`, `shaders.html`

### 低优先级（P2）

- [x] 编译 `renderdoccmd export` 命令 ✅ 2025-02-05
  - ✅ 构建产物已存在: `x64/Development/renderdoccmd.exe` (v1.43)
  - ✅ 支持: `export --out=<dir> --format=png/jpg/dds --metadata --bindings`
- [x] 添加 Adreno GPU 专项分析（完成于 2025-01-26）
- [x] 添加 Tile-Based 效率分析（完成于 2025-01-26）

---


## 10. 关键设计决策记录

| 决策 | 原因 | 日期 |
|------|------|------|
| 使用 Canonical Schema v1.0 | 统一输出格式，便于 compare 和前端消费 | 2025-01-20 |
| Truthful Degradation 原则 | 宁可缺失不造假，保证分析可信度 | 2025-01-21 |
| 4 种采样策略 | 平衡数据覆盖度与性能开销 | 2025-01-21 |
| 本地配置文件模式 | 支持真实样本测试但不泄露用户路径 | 2025-01-21 |
| Schema Bridge 而非直接修改 DiffEngine | 保持 DiffEngine 稳定，在加载层做适配 | 2025-01-21 |

---


## 12. 参考文档

- 架构图: `scripts/rdc_analyzer/docs/ARCHITECTURE_V1.md`
- 执行计划: `plans/2025-01-20-152300-Codex-A-first-execution-plan.md`
- 项目 README: `scripts/rdc_analyzer/README.md`
- 规则文档: `scripts/rdc_analyzer/RULES.md`
- Mali 集成指南: `scripts/rdc_analyzer/docs/MALI_INTEGRATION_SUMMARY.md`
- **RenderDoc 官方文档离线索引**: `docs/offline_reference/RENDERDOC_DOCS_INDEX.md`

---


## 13. RenderDoc 官方文档离线参考

> 官方文档在线地址: https://renderdoc.org/docs/
> 
> 离线索引位置: `docs/offline_reference/RENDERDOC_DOCS_INDEX.md`

### 13.1 索引内容

该文件包含从官方文档中提取的核心内容，方便 AI/开发者快速查阅：

| 章节 | 说明 |
|------|------|
| 导入导出 | RDC 文件格式、XML 导出、Structured Data 访问 |
| Python API | 核心模块、常用类、使用示例 |
| 命令行工具 | `renderdoccmd convert`、`thumb`、`capture` 等 |
| Python API 入门 | 独立脚本加载模块、打开捕获、访问分析数据 |

### 13.2 本地文档构建

如需完整本地文档（含 API 参考），需先编译 RenderDoc 生成 `renderdoc` Python 模块：

```bash
# 1. 编译 RenderDoc（需要 VS 2015 v140 工具集）
cd /d d:\Code\git\renderdoc
"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
msbuild renderdoc.sln /p:Configuration=Development /p:Platform=x64 /t:renderdoc

# 2. 构建文档
cd docs
make.bat html

# 3. 查看文档
start ..\Documentation\html\index.html
```

**注意**: 本地构建依赖 `renderdoc.pyd` Python 模块，该模块通过编译生成。
