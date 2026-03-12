# FBX Export Pipeline Design (OBJ Intermediate)

## Design Summary
- Version: v0.1
- Owner: Agent01 (Codex)
- Last Updated: 2026-02-03
- Problem: 从中间态导出 Unity/Unreal 可导入的 FBX 资产，满足 A+B+C 验收标准。
- Users: rdc_analyzer 导出工具链使用者
- Constraints:
  - FBX 版本固定为 2020.2
  - 中间态先输出 OBJ+MTL，再转换为各引擎 FBX
  - 不自动安装依赖；SDK/工具由用户提供
  - 法线/切线有则导出，无则交由引擎计算
  - 纹理输出为 RGBA8（PNG/TGA）
- Success Criteria (measurable):
  - A) Unity/Unreal 均可导入且无报错
  - B) 场景可见，材质/贴图正确绑定
  - C) 导入后顶点数/三角数与中间态一致
- Evaluation Plan (A):
  - 选择 1 个事件：从中间态目录中挑选 **最小 eventId** 且满足 mesh/material/texture 数据齐全
  - 导出 OBJ+MTL → Unity/Unreal FBX
  - 记录导出统计（顶点数/三角数/材质槽/贴图槽）
  - 手动导入 Unity China 1.6.9 与 Unreal，验证 A+B+C
- Value Check: Desirability=高, Feasibility=中, Viability=高
- Non-goals:
  - 骨骼/动画、蒙皮、BlendShape
  - 引擎内自动导入脚本与自动化验收
  - 非单事件批量导出
- Reasoning Trace:
  - 采用 OBJ+MTL 中间态可解耦坐标系与单位差异，降低引擎耦合
  - 使用 FBX SDK 能最大化保持顶点/材质/UV 的一致性
- Pre-mortem:
  - 风险：SDK 环境不匹配 → 缓解：允许 C++ CLI 与 Python 绑定双路径
  - 风险：坐标系错误导致模型颠倒 → 缓解：引擎 profile 明确 axis/unit 变换
  - 风险：材质槽/贴图槽丢失 → 缓解：导出统计 + 绑定清单比对

## Options (2–3)
- Option A: **FBX SDK Python 绑定**（`fbx` 模块）直接生成 FBX  
  - 优点：实现快、与现有 Python 工具链整合
  - 缺点：依赖 SDK 安装位置与 Python 版本匹配
- Option B: **FBX SDK C++ CLI**（小型转换器）由 Python 调用  
  - 优点：稳定、易控版本；性能更好
  - 缺点：需要一次性编译（需授权）
- Option C: **Blender CLI**（OBJ→FBX）  
  - 优点：通用、无需 SDK
  - 缺点：已被需求排除

## Trade-offs & Recommendation
- 取舍：A 更快接入但依赖环境，B 更稳定但需构建
- 推荐：**优先 A**（若 Python 绑定可用），**不可用则 B**（C++ CLI）

## Architecture (High Level)
1. **Intermediate Reader**：读取中间态 mesh/material/texture 数据与统计
2. **OBJ+MTL Writer**：输出统一中间态（用于记录与调试）
3. **FBX Converter**：
   - Unity Profile：Y-up / meter，输出 FBX 2020.2
   - Unreal Profile：Z-up / centimeter，输出 FBX 2020.2
4. **Exporter Orchestrator**：单事件导出管线 + 统计与日志输出

## Data Flow
```
intermediate/mesh|materials|textures
    -> OBJ+MTL (intermediate)
    -> FBX (Unity profile)
    -> FBX (Unreal profile)
    -> stats.json (vertex/tri/material/texture counts)
```

## Error Handling
- 缺 mesh/material/texture：直接失败并提示缺失类型
- 法线/切线缺失：记录 warning，导出不阻断
- 贴图缺失：材质槽保留但指向占位贴图

## Verification & Logging
- 生成 `stats.json`：顶点/三角数/材质槽/贴图槽
- 记录 axis/unit 变换信息
- 人工导入 Unity/Unreal 验证 A+B+C

