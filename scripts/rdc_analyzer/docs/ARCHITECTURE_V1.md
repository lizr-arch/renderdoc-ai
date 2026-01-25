# RDC Analyzer 架构文档 V1.0

> **创建时间**: 2025-01-21
> **状态**: Phase 1 完成，Phase 2 进行中
> **目的**: 可视化当前系统架构，识别 Gap

---

## 1. 系统总览流程图

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           RDC Analyzer 数据流程                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘

                                    ┌─────────────┐
                                    │   .rdc 文件  │
                                    │ (RenderDoc  │
                                    │  Capture)   │
                                    └──────┬──────┘
                                           │
                        ┌──────────────────┼──────────────────┐
                        │                  │                  │
                        ▼                  ▼                  ▼
              ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
              │  XML Export     │ │ Python API      │ │ renderdoccmd    │
              │  (RenderDoc UI) │ │ (renderdoc模块) │ │  export 命令    │
              └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
                       │                   │                   │
                       ▼                   ▼                   ▼
              ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
              │   XML Parser    │ │  core/bridge.py │ │  纹理文件+JSON  │
              │ (parse_rdc_xml) │ │ ReplayWrapper   │ │   元数据        │
              └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
                       │                   │                   │
                       └───────────────────┼───────────────────┘
                                           │
                                           ▼
                              ┌────────────────────────┐
                              │    main.py             │
                              │   AnalysisPipeline     │
                              │   ─────────────────    │
                              │   - parse()            │
                              │   - extract_data()     │
                              │   - analyze()          │
                              │   - export()           │
                              └───────────┬────────────┘
                                          │
          ┌───────────────────────────────┼───────────────────────────────┐
          │                               │                               │
          ▼                               ▼                               ▼
┌─────────────────────┐       ┌─────────────────────┐       ┌─────────────────────┐
│     Extractors      │       │     Analyzers       │       │     Exporters       │
│  ─────────────────  │       │  ─────────────────  │       │  ─────────────────  │
│  - EventParser      │       │  - FrameAnalyzer    │       │  - JSONExporter     │
│  - ShaderExtractor  │       │  - ResourceAnalyzer │       │  - HTMLExporter     │
│  - D3D11Extractor   │       │  - PerformanceAnal. │       │  - DiffHTMLExporter │
│  - ReplayWrapper    │       │  - MaliAnalyzer     │       │  - ConsoleReporter  │
└─────────────────────┘       │  - TileBasedAnalyzer│       └─────────────────────┘
                              │  - AdrenoAnalyzer  │
                              │  - ResourceTracker │
                              └─────────────────────┘
                                          │
                                          ▼
                              ┌────────────────────────┐
                              │   HTML/JSON Report     │
                              │   ──────────────────   │
                              │   - 纹理列表 + 预览    │
                              │   - Draw Call 列表    │
                              │   - 性能问题检测      │
                              │   - 资源生命周期      │
                              │   - 优化建议          │
                              └────────────────────────┘
```

---

## 2. 模块功能图

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              RDC Analyzer 模块架构                                   │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│  入口层 (Entry Points)                                                              │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  main.py              │ CLI 入口，AnalysisPipeline 编排器                          │
│  __main__.py          │ python -m rdc_analyzer 支持                                │
│  generate_*.py        │ 各种报告生成脚本 (演示/测试/真实数据)                       │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  核心层 (Core)                                                   [✅ Phase 1 完成]  │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  core/bridge.py       │ RenderDoc Python API 封装 (ReplayWrapper)                  │
│  core/context.py      │ 分析上下文管理                                             │
│  core/types.py        │ 数据类型定义 (TextureInfo, DrawCallInfo 等)                │
│  core/enums.py        │ 枚举类型定义                                               │
│  core/result.py       │ 分析结果封装                                               │
│  core/pipeline_state  │ Pipeline State 数据结构                                    │
│  core/duplicate_det.  │ 纹理重复检测                                               │
│  core/texture_usage   │ 纹理使用分析                                               │
│  core/resource_insp.  │ 资源详情检查                                               │
│  core/thumbnail_ext.  │ 缩略图提取                                                 │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  解析层 (Parsers)                                                [✅ Phase 1 完成]  │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  parsers/api_parser   │ API 调用解析 (Vulkan/D3D11/D3D12/GL)                       │
│  parsers/binary_parser│ RDC 二进制格式解析                                         │
│  parsers/dxbc_parser  │ DXBC Shader 指令解析                                       │
│  parsers/models/      │ 数据模型 (RDCFile, Shader, Texture)                        │
│  parse_rdc_xml.py     │ XML 格式解析                                               │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  提取层 (Extractors)                                             [✅ Phase 1 完成]  │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  extractors/base.py   │ 提取器基类                                                 │
│  extractors/event_*   │ 事件/Draw Call 提取                                        │
│  extractors/shader_*  │ Shader 源码/反汇编提取                                     │
│  extractors/d3d11_*   │ D3D11 特定数据提取                                         │
│  extractors/replay_*  │ Replay 回放数据提取                                        │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  分析层 (Analyzers)                                              [🚧 Phase 2 进行中]│
├─────────────────────────────────────────────────────────────────────────────────────┤
│  analyzers/frame.py   │ 帧级分析 (Draw Call 统计, Render Pass)                     │
│  analyzers/resource   │ 资源分析 (纹理/Buffer 使用情况)                             │
│  analyzers/state.py   │ Pipeline State 分析                                        │
│  analyzers/perf_*     │ 性能分析 (Overdraw, Batch, 带宽)                            │
│  analyzers/mali_*     │ Mali GPU 专项分析 (malioc 集成)           [✅ 已完成]       │
│  analyzers/tile_based │ Tile-Based GPU 分析 (TBDR 启发式)        [✅ 已完成]       │
│  analyzers/adreno_*   │ Adreno GPU 启发式 + Profiler 入口        [✅ 已完成]       │
│  analyzers/pass_*     │ Render Pass 分析                                           │
│  analysis/resource_*  │ 资源生命周期追踪 (RAW/WAR 依赖)           [✅ 已完成]       │
│  analysis/call_*      │ Draw Call 依赖分析                                         │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  规则层 (Rules)                                                  [🚧 Phase 2 进行中]│
├─────────────────────────────────────────────────────────────────────────────────────┤
│  rules/base.py        │ 规则基类 (IRule, Severity)                                 │
│  rules/texture.py     │ 纹理规则 (尺寸过大, 格式不当, 未使用)                       │
│  rules/buffer.py      │ Buffer 规则                                                │
│  rules/draw_call.py   │ Draw Call 规则 (小批次, 冗余状态切换)                       │
│  rules/state.py       │ 状态规则 (冗余 Blend/Depth 设置)                            │
│  rules/mobile.py      │ 移动端规则 (带宽敏感, 格式推荐)           [🚧 部分完成]     │
│  rules/tile_based.py  │ Tile-Based 规则 (Overdraw/Tile 内存)      [✅ 已完成]       │
│  rules/render_pass    │ Render Pass 规则                                           │
│  rules/runner.py      │ 规则执行器                                                 │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  导出层 (Exporters)                                              [✅ Phase 1 完成]  │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  exporters/json_*     │ JSON 格式导出                                              │
│  exporters/html_*     │ HTML 报告导出 (单文件, 离线可用)                            │
│  exporters/templates/ │ HTML 模板 (base.html, styles.css, main.js)                 │
│  reporters/console_*  │ 控制台输出                                                 │
│  reporters/csv_*      │ CSV 导出                                                   │
│  reporters/markdown_* │ Markdown 导出                                              │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  对比层 (Diff)                                                   [✅ Phase 1 完成]  │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  diff/diff_engine.py  │ 帧对比引擎                                                 │
│  diff/diff_types.py   │ 对比数据类型                                               │
│  diff/diff_html_*     │ 对比报告 HTML 导出                                         │
│  diff/regression_*    │ 性能回归检测                                               │
│  compare_rdc.py       │ RDC 文件对比 CLI                                           │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  工具层 (Utils)                                                  [✅ 已完成]        │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  utils/format_utils   │ 数据格式化                                                 │
│  utils/lz4_utils      │ LZ4 压缩/解压                                              │
│  utils/memory_utils   │ 内存计算                                                   │
│  config/platforms     │ 平台配置                                                   │
│  config/thresholds    │ 阈值配置                                                   │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 数据流详细图

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           详细数据流 (以 main.py 为核心)                             │
└─────────────────────────────────────────────────────────────────────────────────────┘

    输入                      处理                         输出
    ────                      ────                         ────

 ┌─────────┐
 │ .rdc    │───┐
 │ 文件    │   │
 └─────────┘   │
               │         ┌──────────────────────────────────────┐
 ┌─────────┐   │         │         AnalysisPipeline             │
 │ .xml    │───┼────────▶│                                      │
 │ 导出    │   │         │  ┌─────────────────────────────────┐ │
 └─────────┘   │         │  │ Step 1: parse()                 │ │
               │         │  │   - load_xml() / load_json()    │ │
 ┌─────────┐   │         │  │   - validate schema             │ │
 │ JSON    │───┘         │  └──────────────┬──────────────────┘ │
 │ 数据    │             │                 │                    │
 └─────────┘             │                 ▼                    │
                         │  ┌─────────────────────────────────┐ │       ┌─────────────┐
                         │  │ Step 2: extract_data()          │ │       │ capture.json│
                         │  │   - textures (id,name,size,fmt) │ │──────▶│ (JSON 导出) │
                         │  │   - draw_calls (eid,bindlings)  │ │       └─────────────┘
                         │  │   - shaders (source,disasm)     │ │
                         │  │   - buffers (cb,vb,ib)          │ │
                         │  └──────────────┬──────────────────┘ │
                         │                 │                    │
                         │                 ▼                    │
                         │  ┌─────────────────────────────────┐ │
                         │  │ Step 3: analyze()               │ │
                         │  │   - detect_issues()             │ │
                         │  │   - track_lifetimes()           │ │
                         │  │   - find_duplicates()           │ │
                         │  │   - check_rules()               │ │
                         │  └──────────────┬──────────────────┘ │
                         │                 │                    │
                         │                 ▼                    │
                         │  ┌─────────────────────────────────┐ │       ┌─────────────┐
                         │  │ Step 4: export()                │ │       │ report.html │
                         │  │   - json_exporter.export()      │ │──────▶│ (HTML 报告) │
                         │  │   - html_exporter.export()      │ │       └─────────────┘
                         │  └─────────────────────────────────┘ │
                         │                                      │
                         └──────────────────────────────────────┘
```

---

## 4. Phase 完成状态

> **最后更新**: 2025-01-21
> **注意**: 根据代码搜索验证，很多功能已在 `generate_offline_report.py` 中实现

### Phase 1 (核心集成) ✅ 完成

| 功能 | 文件 | 状态 |
|------|------|------|
| XML/JSON 解析 | `parse_rdc_xml.py`, `parsers/` | ✅ |
| RenderDoc API 桥接 | `core/bridge.py` | ✅ |
| 纹理提取 | `extractors/`, `core/thumbnail_extractor` | ✅ |
| Shader 提取 | `extractors/shader_extractor.py` | ✅ |
| Draw Call 解析 | `extractors/event_parser.py` | ✅ |
| JSON 导出 | `exporters/json_exporter.py` | ✅ |
| HTML 导出 | `exporters/html_exporter.py` | ✅ |
| 资源生命周期 | `analysis/resource_tracker.py` | ✅ |
| 帧对比 | `diff/diff_engine.py` | ✅ |
| CLI 入口 | `main.py` | ✅ |

### Phase 2 (分析增强) ✅ 大部分完成

| 功能 | 文件 | 状态 | 说明 |
|------|------|------|------|
| Mali GPU 分析 | `analyzers/mali_analyzer.py` | ✅ | malioc 集成完成 |
| 深色主题 | `generate_offline_report.py` | ✅ | CSS 变量已实现 |
| 纹理 Lightbox | `generate_offline_report.py` L1402-L9058 | ✅ | 完整实现含导航 |
| 纹理网格视图 | `generate_offline_report.py` L4933 | ✅ | Grid/Table 双视图 |
| 纹理对比视图 | `generate_offline_report.py` L2234, L5169 | ✅ | 并排对比 Lightbox |
| 缩略图加载 | `generate_offline_report.py`, `core/thumbnail_extractor` | ✅ | Base64 内嵌 |
| 虚拟滚动 | `generate_offline_report.py` | ✅ | 500+ 纹理流畅 |
| 搜索/筛选/排序 | `generate_offline_report.py` | ✅ | 多维度筛选 |
| Constant Buffer 检查 | `core/resource_inspector.py` | 🚧 | 基础功能，需要值展示 |
| Shader 源码高亮 | HTML 模板 | 🚧 | 有反汇编，缺语法高亮 |

### Phase 3 (UX 增强) � 部分完成

| 功能 | 说明 | 状态 |
|------|------|------|
| 缩略图占位符 | `generate_placeholder_thumbnail()` | ✅ |
| 真实缩略图提取 | `core/thumbnail_extractor.py` | ✅ |
| 纹理点击联动 | 右侧→中间→左侧 | � 部分实现 |
| EID 跳转 | 点击 Event ID | � 需要完善 |
| VRAM 饼图/柱状图 | 纯 CSS 实现 | 📋 计划中 |
| 导出优化清单 | JSON/CSV 导出 | ✅ 已有 CSV/JSON 导出 |

### Phase 4 (扩展) 📋 计划中

| 功能 | 说明 | 状态 |
|------|------|------|
| renderdoccmd export | C++ 命令行导出 | ✅ 代码已添加，待编译 |
| Adreno GPU 分析 | 类似 Mali | ✅ |
| Tile-Based 效率分析 | 移动 GPU Load/Store | ✅ |
| 自动化测试 | E2E 覆盖率 | 🚧 |

---

## 5. Gap 分析 (待完成功能)

### 5.1 数据提取 Gap

```
┌─────────────────────────────────────────────────────────────────┐
│  数据提取 - 已实现 vs 缺失                                       │
├─────────────────────────────────────────────────────────────────┤
│  ✅ 已实现                     │  ❌ 缺失                        │
│  ──────────────────────────── │  ────────────────────────────   │
│  纹理元数据 (name,size,fmt)   │  纹理 Mip 链完整信息             │
│  Draw Call 基础信息           │  GPU Timing (需要 Profiler)      │
│  Shader 源码/反汇编           │  Compute Shader 详情             │
│  Vertex/Index Buffer          │  Stream Output 信息              │
│  Render Target 绑定           │  Indirect Draw 参数              │
│  Pipeline State               │  Query 结果 (Occlusion等)        │
│  资源生命周期追踪             │  UAV/Storage Buffer 访问模式      │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 分析能力 Gap

```
┌─────────────────────────────────────────────────────────────────┐
│  分析能力 - 已实现 vs 缺失                                       │
├─────────────────────────────────────────────────────────────────┤
│  ✅ 已实现                     │  ❌ 缺失                        │
│  ──────────────────────────── │  ────────────────────────────   │
│  纹理重复检测                 │  Shader 复杂度分析               │
│  纹理使用追踪                 │  分支预测分析                    │
│  Draw Call 批次统计           │  寄存器压力分析                  │
│  基础性能规则                 │  带宽估算 (读/写)                │
│  Mali malioc 集成             │  热点函数定位                    │
│  Adreno GPU 专项              │  —                              │
│  Tile-Based 效率分析          │  —                              │
│  RAW/WAR 依赖检测             │  —                              │
│  帧对比/回归检测              │  —                              │
└─────────────────────────────────────────────────────────────────┘
```

### 5.3 UI/UX Gap

```
┌─────────────────────────────────────────────────────────────────┐
│  UI/UX - 已实现 vs 缺失                                          │
├─────────────────────────────────────────────────────────────────┤
│  ✅ 已实现                     │  ❌ 缺失 (V3.0 设计)             │
│  ──────────────────────────── │  ────────────────────────────   │
│  纹理列表 (虚拟滚动)          │  纹理网格视图 (Grid)             │
│  Draw Call 列表               │  Lightbox 全屏预览               │
│  问题面板                     │  Constant Buffer 值查看           │
│  资源生命周期面板             │  Shader 代码高亮显示             │
│  基础筛选                     │  高级筛选 (格式/尺寸/用途)       │
│  单文件 HTML                  │  暗色主题                        │
│  帧对比报告                   │  交互式差异查看器                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. 推荐下一步

### 优先级 1 (High) - 完善 Phase 2

1. **Shader 代码查看器** - HTML 中内联显示 Shader 源码，语法高亮
2. **Constant Buffer 值查看** - 展开显示 CB 内每个字段的值
3. **性能仪表盘** - VRAM 饼图，Draw Call 柱状图

### 优先级 2 (Medium) - Phase 3 UX

1. **真实缩略图提取** - 需要 `renderdoc` Python 模块或 `renderdoccmd export`
2. **纹理点击联动** - 右侧分析面板→中间预览→左侧列表
3. **暗色主题** - CSS 变量切换

### 优先级 3 (Low) - 扩展功能

1. **Adreno GPU 分析** - 类似 Mali，集成 Adreno Profiler
2. **Tile-Based 效率分析** - 针对移动 GPU 的 Load/Store 分析
3. **自动化测试** - E2E 测试覆盖率提升

---

## 7. 文件引用索引

| 类别 | 关键文件 |
|------|----------|
| **入口** | `main.py`, `__main__.py` |
| **核心** | `core/bridge.py`, `core/types.py`, `core/context.py` |
| **解析** | `parsers/api_parser.py`, `parse_rdc_xml.py` |
| **提取** | `extractors/event_parser.py`, `extractors/shader_extractor.py` |
| **分析** | `analyzers/frame.py`, `analysis/resource_tracker.py` |
| **规则** | `rules/texture.py`, `rules/draw_call.py`, `rules/mobile.py` |
| **导出** | `exporters/html_exporter.py`, `exporters/json_exporter.py` |
| **对比** | `diff/diff_engine.py`, `compare_rdc.py` |
| **配置** | `config/thresholds.py`, `config/platforms.py` |
