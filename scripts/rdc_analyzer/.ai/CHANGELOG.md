# 变更日志

> 记录所有 AI Agent 完成的任务和代码变更

---

## 2025-01-19

### Flux-0119 (Phase 2 Comparison Engine)

- **18:30** TASK-010~013: Phase 2 核心对比引擎完成
  - 新增: `diff/diff_engine.py` - 数据对比引擎
    - 支持 DrawCall/Geometry/Texture/Buffer/Shader 全维度对比
    - 自动处理 null viewport 等边界情况
  - 新增: `diff/regression_detector.py` - 性能回归检测器
    - 9 条回归规则（DrawCall +10%、Texture Memory +20% 等）
    - 自动生成回归报告和建议
  - 新增: `diff/diff_html_exporter.py` - HTML 对比报告生成
    - 红/绿标识新增/删除资源
    - 回归指标可视化展示
  - 新增: `compare_rdc.py` - RDC 对比入口脚本
    - 命令行: `py -3 compare_rdc.py <baseline.rdc> <current.rdc>`
  - 测试结果:
    - g145.rdc vs g145-battle-2.rdc 对比成功 ✅
    - 检测到 Draw Calls +360%, Texture Memory +108%
  - Commit: `48b770712`

### Agent-Initial (核心功能开发)

- **14:54** TASK-000: 完成核心功能实现
  - 新增: `renderdoccmd export` 命令
    - 文件: `renderdoccmd/renderdoccmd.cpp`
    - Commit: `67320aa feat(renderdoccmd): add 'export' command`
  - 新增: XML 解析器支持 D3D11/D3D12/Vulkan
    - 文件: `parse_rdc_xml.py` (+400 行)
    - Commit: `fix(e2e-test): 支持 D3D11/D3D12 API 解析`
  - 新增: 端到端测试脚本
    - 文件: `test_e2e_real_data.py` (+400 行)
  - 测试结果:
    - D3D11 RDC: 352 事件, 320 Draw Calls, 138 纹理 ✅
    - 报告大小: 204 MB

- **15:00** 创建多 AI 协同开发框架
  - 新增: `.ai/INDEX.md` (项目索引)
  - 新增: `.ai/TASKS.md` (任务看板)
  - 新增: `.ai/CONVENTIONS.md` (开发规范)
  - 新增: `.ai/CHANGELOG.md` (本文件)

---

## 模板

记录新完成的任务时，请使用以下格式：

```markdown
- **HH:MM** TASK-xxx: 任务标题
  - 修改: `文件名` (+行数 / -行数)
  - Commit: `commit message`
  - 测试结果: 描述
```