# RDC Analyzer 待改进事项

> 记录当前已知的问题和未来改进计划

---

## 🔮 Pass 依赖图（需重新设计）

**创建日期**: 2024-01
**优先级**: 低
**状态**: 待真实数据验证

### 问题描述

当前 Pass 依赖图的连接线功能使用**模拟数据**，无法体现真实的资源依赖关系。

用户反馈：
- "资源流向"概念不清晰
- 悬停连接线的 Tooltip 难以理解实际含义

### 当前实现

- 连接线表示"Pass A 的输出被 Pass B 读取"
- Tooltip 显示：源 Pass → 目标 Pass + 传递的资源名称/格式/缩略图

### 改进方向

1. **使用真实 RDC 数据**：
   - 分析 `StructuredFile` 中的资源读写关系
   - 追踪每个 DrawCall 实际绑定的纹理/缓冲区
   - 对比 Pass 之间的输出→输入匹配

2. **数据来源**：
   ```python
   # 从 StructuredFile 获取资源绑定信息
   structured_file = controller.GetStructuredFile()
   for chunk in structured_file.chunks:
       # 分析 vkCmdBindDescriptorSets / D3D11 PSSetShaderResources 等调用
       # 提取资源 ID 和绑定槽位
   ```

3. **重新设计 UI**：
   - 考虑是否保留连接线，或改为其他可视化方式
   - 可能改为"资源时间线"更直观

### 相关文件

- `generate_offline_report.py`: `renderPassGraph()` 函数
- `generate_145_demo_report.py`: Pass 依赖数据生成

---

## 📝 其他待办

### API 调用指令显示
- [ ] 在 Event 详情中添加完整的 API 调用签名
- [ ] 格式化参数显示（类似 IDE 调试器）

### UI 改进
- [ ] Event 列表支持拖拽调整宽度
- [ ] 增加默认列表宽度

---

*最后更新: 2024-01*
