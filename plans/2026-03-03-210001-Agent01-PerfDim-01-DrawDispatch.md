# Perf Dimension 01 - Draw/Dispatch 密度（小批次）

**Version:** 2026-03-03  
**Owner:** Agent01  
**Plan File:** `plans/2026-03-03-210001-Agent01-PerfDim-01-DrawDispatch.md`

## Scope / Assumptions

### Scope (In)
- 提取每个 Draw/Dispatch 的规模指标（indices/instances/dispatch dims）
- 生成“Draw/Dispatch 密度”排序列表（小批次优先）
- 支持跳转到对应 Event

### Scope (Out)
- GPU 时间与硬件计数器（由维度 06 处理）

### Assumptions
- `ActionDescription::numIndices` 表示“indices 或 vertices（按调用类型）”  
  证据：`renderdoc/api/replay/data_types.h:2072-2076`

---

## Build / Test / Lint Quick Guide (记录，不在 /plan 执行)

### Build (需用户授权)
- `E:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe renderdoc.sln /p:Configuration=Development /p:Platform=x64 /m`

### Unit
- `D:\Code\git\renderdoc\x64\Development\qrenderdoc.exe --unittest "[analyzer]"`

### Manual Acceptance
- 打开 capture → Analyzer Report → Performance/DrawDispatch Tab  
- 验证默认降序、升/降序切换、跳转到 Event Browser

---

## File List (精确到行号范围)

- `renderdoc/api/replay/data_types.h:1983-2126`（ActionDescription 字段）
- `qrenderdoc/Code/Analyzer/AnalyzerTypes.h:56-133`（新增 Draw/Dispatch 数据结构 + Snapshot 扩展）
- `qrenderdoc/Code/Analyzer/FrameAnalyzer.h:31-49`（新增 PopulateDrawDispatch 声明）
- `qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp:82-140`（Build/FlattenActions 插入采集点）
- `qrenderdoc/Code/Analyzer/FrameAnalyzer.cpp:254-318`（新增 PopulateDrawDispatch 实现区）
- `qrenderdoc/Code/Analyzer/AnalyzerContract.cpp:72-175`（导出 draw_dispatch 数组）
- `qrenderdoc/Windows/AnalyzerModels.h:134-197`（新增 AnalyzerDrawDispatchModel）
- `qrenderdoc/Windows/AnalyzerModels.cpp:213-774`（model/排序实现）
- `qrenderdoc/Windows/AnalyzerReportViewer.ui:118-570`（新增 Performance Tab + 表格）
- `qrenderdoc/Windows/AnalyzerReportViewer.cpp:330-540`（绑定模型 + 跳转处理）

---

## Design / Pseudocode (完整实现草案)

### 1) 新增数据结构

```cpp
// AnalyzerTypes.h
struct AnalyzerDrawDispatchRow
{
  uint32_t eid = 0;
  rdcstr name;
  rdcstr type; // draw/dispatch
  uint32_t numIndices = 0;
  uint32_t numInstances = 0;
  rdcfixedarray<uint32_t, 3> dispatchDim = {0, 0, 0};
  rdcfixedarray<uint32_t, 3> dispatchThreads = {0, 0, 0};
  bool indirect = false;
};
```

### 2) 采集逻辑

```cpp
// FrameAnalyzer.cpp
void FrameAnalyzer::PopulateDrawDispatch(ICaptureContext &ctx, AnalyzerSnapshot &snap) const
{
  const rdcarray<ActionDescription> &roots = ctx.CurRootActions();
  rdcarray<const ActionDescription *> flat;
  FlattenActionPointers(roots, flat);

  for(const ActionDescription *action : flat)
  {
    if(!(action->flags & (ActionFlags::Drawcall | ActionFlags::Dispatch)))
      continue;

    AnalyzerDrawDispatchRow row;
    row.eid = action->eventId;
    row.name = action->GetName(ctx.CurStructuredFile());
    row.type = (action->flags & ActionFlags::Dispatch) ? "dispatch" : "draw";
    row.numIndices = action->numIndices;
    row.numInstances = action->numInstances;
    row.dispatchDim = action->dispatchDimension;
    row.dispatchThreads = action->dispatchThreadsDimension;
    row.indirect = (action->flags & ActionFlags::Indirect) != 0;
    snap.drawDispatch.push_back(row);
  }
}
```

### 3) UI 展示

```cpp
// AnalyzerModels.h/.cpp
class AnalyzerDrawDispatchModel : public QAbstractTableModel
{
  // columns: Type, Name, EID, Indices, Instances, DispatchDim, Threads, Indirect
};
```

---

## Impact Analysis

- **Performance**：一次性扫描 ActionDescription，开销可控  
- **UX**：新增 Performance/DrawDispatch Tab，默认降序排序  
- **Maintenance**：结构体与 UI 明确分离，后续规则可复用

---

## Risks / Blockers

1. 非 D3D11 捕获缺少额外统计，只能使用 ActionDescription 元数据  
2. `numIndices` 对非 indexed draw 的解释需验证

---

## Task Checklist (2-5 分钟粒度, TDD)

- [x] 新增失败单测：Draw/Dispatch model 排序（按 indices 升降序）
- [ ] 运行 `qrenderdoc.exe --unittest "[analyzer]"`，预期 FAIL
- [x] 实现 AnalyzerTypes / FrameAnalyzer / AnalyzerModels / UI
- [x] 再跑 unittest，预期 PASS
- [ ] 手工验收：排序 + 跳转
- [x] 提交（Conventional Commits）

---

## Verification / Acceptance (Definition of Done)

- Draw/Dispatch 表格可用、默认降序  
- 升/降序切换正确  
- 点击行可跳转到 Event Browser  
- MSBuild + unittest 通过

---

## /do Execution Log

### 2026-03-04

- [x] 新增 AnalyzerDrawDispatch 数据结构 + JSON 导出
- [x] 新增 AnalyzerDrawDispatchModel + 排序测试
- [x] Analyzer Report 增加 Performance Tab（Draw/Dispatch 表格 + 过滤 + 跳转）
- [x] 构建与 unittest 通过

偏差记录：
- 未先跑“失败单测”，因为模型结构未落地前无法构造有效测试；已补齐排序单测并通过。
