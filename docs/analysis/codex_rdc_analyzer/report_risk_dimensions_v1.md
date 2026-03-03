# Analyzer Report 风险维度与定位标准（v1）

> 目标：把“发现风险 → 快速定位 → 解释证据”的动作固化为稳定流程，降低排查成本。  
> 适用范围：Native Qt Analyzer Report（本地 C++ 报告窗口）。  
> 说明：本文件对齐当前 GUI 目标，字段命名遵循数据来源原始命名，不新增自定义指标。

---

## 1. 总体方法（统一套路）

每个风险维度都必须包含 5 个元素：

1. **风险信号**：用户看到的“异常/热点”是什么  
2. **证据来源**：来自哪里（RDC / Replay / GPU Counters / Mali 等）  
3. **排序字段**：用哪一个数把风险排序  
4. **跳转入口**：点击后能直达哪个 GUI（Event / Resource / Shader）  
5. **置信度**：高 / 中 / 低（取决于数据来源可靠性）

---

## 2. 数据来源与置信度分级

| 来源 | 说明 | 置信度 |
|------|------|--------|
| RDC 元数据 | 纹理/资源规模、事件列表等 | 低 |
| Replay 状态 | Pipeline/Shader/资源绑定 | 中 |
| GPU Counters | EventGPUDuration / VS/PS invocations | 高 |
| Mali Offline | Shader 静态复杂度（移动端） | 中-高（依赖 malioc） |

---

## 3. 风险维度清单（v1）

### 3.1 Draw / Dispatch 密度（小批次）
- **风险信号**：大量小 Draw / Dispatch，CPU/GPU 提交开销上升  
- **证据字段**：numIndices / numInstances / dispatchDimension / dispatchThreadsDimension  
- **排序字段**：小批次数量、低顶点/实例优先  
- **跳转入口**：Event Browser  
- **置信度**：中（基于 ActionDescription 元数据）

### 3.2 资源/状态抖动（绑定频繁）
- **风险信号**：Shader / Resource 频繁切换  
- **证据字段**：ShaderChangeStats / ResourceBindStats  
- **排序字段**：变更次数降序  
- **跳转入口**：Event Browser / Pipeline State  
- **置信度**：中（D3D11 FrameStatistics 可用时较高）

### 3.3 Pipeline 带宽（MRT / MSAA / Blend）
- **风险信号**：MRT 数量多 / MSAA 过高 / Blend 热点  
- **证据字段**：RT 数 / samples / blend state  
- **排序字段**：MRT 数 / MSAA 等级  
- **跳转入口**：Event Browser + Pipeline State  
- **置信度**：中（Replay 状态）

### 3.4 Overdraw / Triangle Size
- **风险信号**：过度绘制、极小三角形  
- **证据字段**：Overlay 统计（Quad Overdraw / Triangle Size）  
- **排序字段**：覆盖面积或 overdraw 强度  
- **跳转入口**：Overlay 可视化  
- **置信度**：高（视觉直观）

### 3.5 Buffer/Texture 更新与内存压力（含大纹理）
- **风险信号**：更新次数过多 / 资源过大导致带宽与显存压力  
- **证据字段**：ResourceUpdateStats（calls/sizes/types）+ Texture/Buffer 字节数  
- **排序字段**：bytes / update calls  
- **跳转入口**：Resource Viewer / Event Browser  
- **置信度**：中（更新统计仅 D3D11）

### 3.6 GPU 计时与计数器（热点）
- **风险信号**：EventGPUDuration / PSInvocations 等异常高  
- **证据字段**：GPUCounter 结果（EventGPUDuration, VS/PS/CS invocations...）  
- **排序字段**：GPU 时间 / invocations  
- **跳转入口**：Event Browser  
- **置信度**：高（硬件计数器）

### 3.7 Shader 维度（Mali Offline）
- **风险信号**：cycles / registers / spill 等异常高  
- **证据字段**：malioc 输出字段（保持原名，不新增自定义指标）  
- **排序字段**：malioc 输出中最大负载字段（由用户选择）  
- **跳转入口**：Shader Viewer（选中 Shader + entrypoint）  
- **置信度**：中-高（依赖 malioc 与 GPU 目标）  
- **GPU 选择**：必须可选 Mali 核心（默认 `Mali-G78`）

---

## 4. UI 展示标准（统一模板）

每个 Tab/维度必须满足：
- **默认降序排序**（高风险在前）  
- **升/降序可切换**  
- **字段单位明确**（MB / cycles / regs）  
- **N/A 明确显示**（无数据不可伪装）  
- **跳转可用**（无跳转则提示原因）

---

## 5. 本次落地范围

本轮优先完成 **Shader 维度（Mali Offline）**，其余维度按追踪文档逐项落地。
