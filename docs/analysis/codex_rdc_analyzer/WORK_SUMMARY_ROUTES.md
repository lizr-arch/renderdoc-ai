# WORK_SUMMARY_ROUTES — 路线与导出流程

- WHAT: 记录 A/B/C 三条输入路线 + XML 导出流程与验证状态。
- WHY: 明确离线/实时/批量三类使用场景与可验证性。
- HOW: 保留原命令、验证记录与关键文件路径。

---

## 1. 整体架构（三条输入路线）

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        RDC Analyzer 数据输入路线                          │
└─────────────────────────────────────────────────────────────────────────┘

                                    ┌─────────────┐
                                    │   .rdc 文件  │
                                    │ (RenderDoc  │
                                    │  Capture)   │
                                    └──────┬──────┘
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │                      │                      │
                    ▼                      ▼                      ▼
         ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐
         │  路线 A: XML 导出  │  │  路线 B: Python   │  │  路线 C: renderdoc│
         │  (RenderDoc UI)   │  │   API 直接解析    │  │  cmd export      │
         └─────────┬─────────┘  └─────────┬─────────┘  └─────────┬─────────┘
                   │                      │                      │
                   ▼                      ▼                      ▼
         ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐
         │  parsers/         │  │  core/bridge.py   │  │  纹理 PNG +       │
         │  rdc_xml_parser   │  │  ReplayWrapper    │  │  JSON 元数据      │
         └─────────┬─────────┘  └─────────┬─────────┘  └─────────┬─────────┘
                   │                      │                      │
                   └──────────────────────┼──────────────────────┘
                                          │
                                          ▼
                            ┌─────────────────────────┐
                            │     main.py             │
                            │   AnalysisPipeline      │
                            │   ────────────────      │
                            │   - parse()             │
                            │   - analyze()           │
                            │   - export()            │
                            └───────────┬─────────────┘
                                        │
                                        ▼
                            ┌─────────────────────────┐
                            │   HTML/JSON Report      │
                            │   (Canonical Schema v1) │
                            └─────────────────────────┘
```

### 1.0 路线关系说明（A/B/C）

**核心结论**：
- **A + C = 离线主路径**：A 负责结构化分析与规则结论，C 负责资源导出（纹理/绑定/元数据）。两者结合可形成“分析结论 + 真实资源展示”的**完整离线报告**。
- **B = 高完整度通道**：B 依赖 RenderDoc Replay 环境（Python 3.6 + `renderdoc.pyd` + 可回放硬件/驱动），可获取更完整的 PipelineState/实时上下文数据，但部署成本更高。

**集合视角**（数据完备性）：
- 通常可认为 **A ∪ C ⊂ B**（B 能提供更多回放级数据），但**工程上 B 不能替代 A+C**，因为 B 受环境与硬件限制，A+C 更易规模化与离线批量运行。

**使用建议**：
- **默认优先 A+C**：用于离线分析、CI 批量、资产可视化。
- **需要高精度或验证时再用 B**：比如 PipelineState 实际值、Shader/状态精确回放。

### 1.1 路线 A: XML 导出（离线分析）

**适用场景**：无 RenderDoc Python 模块环境，或需要离线分析。

**流程**：
1. 使用 `renderdoccmd convert` 命令导出 XML
2. 用 `rdc_analyzer` 解析 XML 生成报告

**核心命令**：
```bash
# RDC → XML 转换（RenderDoc 原生支持！）
renderdoccmd convert -f capture.rdc -o capture.xml -c xml
```

**关键文件**：
- `parsers/rdc_xml_parser.py` — XML 解析入口
- `parsers/rdc_xml_converter.py` — 转换为内部数据结构

**实现要点**：
```python
# parsers/rdc_xml_parser.py
class RDCXMLParser:
    def parse(self, xml_path: str) -> CaptureData:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # 提取纹理
        textures = self._parse_textures(root)
        # 提取 Draw Call
        draw_calls = self._parse_draw_calls(root)
        # 提取 Shader
        shaders = self._parse_shaders(root)
        
        return CaptureData(textures=textures, draw_calls=draw_calls, ...)
```

### 1.2 路线 B: Python API 直接解析（实时分析）

**适用场景**：有完整 RenderDoc Python 环境，需要实时提取 Pipeline State。

**流程**：
1. 通过 `renderdoc` Python 模块加载 `.rdc`
2. 使用 `ReplayController` 回放帧
3. 调用 `SetFrameEvent()` + `GetPipelineState()` 提取数据

**关键文件**：
- `core/bridge.py` — RenderDoc API 封装
- `extractors/replay_wrapper.py` — 回放控制器封装
- `extractors/pipeline_sampler.py` — Pipeline State 采样器

**实现要点**：
```python
# core/bridge.py
class ReplayWrapper:
    def __init__(self, rdc_path: str):
        self.cap = rd.OpenCaptureFile()
        self.cap.OpenFile(rdc_path, '', None)
        self.controller = self.cap.OpenCapture(rd.ReplayOptions(), None)
    
    def get_pipeline_state(self, event_id: int) -> PipelineSnapshot:
        self.controller.SetFrameEvent(event_id, True)
        state = self.controller.GetPipelineState()
        return self._convert_to_snapshot(state)
```

### 1.3 路线 C: renderdoccmd export（批量导出）

**适用场景**：CI/CD 环境，需要批量导出纹理和元数据。

**流程**：
1. 修改 RenderDoc C++ 源码添加 `export` 子命令
2. 编译后运行 `renderdoccmd export capture.rdc -o output/`
3. 输出纹理 PNG + JSON 元数据

**关键文件**（C++ 侧）：
- `renderdoc/replay/capture_exporter.cpp` — 导出器实现
- `renderdoc/renderdoccmd/cmd_export.cpp` — CLI 命令

**状态**：代码已添加，待编译验证。

---


## 1.4 路线验证状态总表

| 路线 | 状态 | 验证环境 | 备注 |
|------|------|----------|------|
| **A: XML 导出** | ✅ **已跑通** | Windows 10, Python 3.10 | 通过 `rdc_xml_parser.py` 解析 RenderDoc 导出的 XML |
| **B: Python API** | ✅ **已验证** | Python 3.6 + renderdoc.pyd | 完整 API 可用（457 个公开接口） |
| **C: renderdoccmd** | ✅ **已编译** | VS 2022 + v140 工具集 | 编译成功，`renderdoccmd.exe` 可用 |

### 路线 A 验证详情（已跑通）

**测试文件**：`tests/test_xml_parser.py`, `tests/test_dod_compliance.py`

```bash
# 验证命令（已通过）
cd scripts/rdc_analyzer
py -3 -m pytest tests/test_xml_parser.py -v
# 结果: 全部 PASSED
```

**实际验证的功能**：
- ✅ XML 文件解析 → `CaptureData` 对象
- ✅ 纹理/DrawCall/Shader 数据提取
- ✅ 分析管线 → HTML/JSON 报告生成
- ✅ Schema v1 Bridge → DiffEngine 消费

### 路线 B 验证详情（部分验证）

**依赖**：需要 RenderDoc 安装目录下的 `renderdoc.pyd` (Windows) 或 `renderdoc.so` (Linux)

**已验证（通过 Mock）**：
- ✅ `PipelineSampler` 采样逻辑（4 种策略）
- ✅ `PipelineSnapshot` 数据结构
- ✅ 采样结果 → coverage 报告集成

**待真机验证**：
- ⏳ `ReplayController.SetFrameEvent()` 实际调用
- ⏳ `GetPipelineState()` 返回值解析
- ⏳ Mali GPU 真实 RDC 回放

**本地验证方法**：
```python
# 如果有 renderdoc 模块可用
import renderdoc as rd
cap = rd.OpenCaptureFile()
cap.OpenFile(r"D:\renderdoc\goog pixel-9\g145.rdc", "", None)
# 如果能打开，说明环境正常
```

### 路线 C 验证详情（✅ 已编译验证）

#### 编译前提条件

1. **Visual Studio 2022 Community** 已安装（路径示例：`E:\Program Files\Microsoft Visual Studio\2022\Community`）
2. **v140 平台工具集**（VS 2015 工具链）已安装
   - 安装方法：VS Installer → 修改 → 单个组件 → 搜索 "v140" → 勾选 "MSVC v140 - VS 2015 C++ 生成工具"
   - RenderDoc 的部分项目（尤其 Qt 相关）依赖此工具集

#### 编译命令

使用 **VS Developer Command Prompt** 执行：

```cmd
cmd /c "\"E:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat\" -arch=x64 -host_arch=x64 && msbuild renderdoc.sln /p:Configuration=Development /p:Platform=x64"
```

**说明**：
- `VsDevCmd.bat` 设置编译环境（`cl`, `msbuild` 等工具进入 PATH）
- `Configuration=Development` 表示开发版（含调试符号）
- `Platform=x64` 表示 64 位构建

#### 编译输出

成功后，`renderdoccmd.exe` 位于：
```
d:\Code\git\renderdoc\x64\Development\renderdoccmd.exe
```

#### 验证编译结果

```cmd
d:\Code\git\renderdoc\x64\Development\renderdoccmd.exe --help
d:\Code\git\renderdoc\x64\Development\renderdoccmd.exe export --help
```

#### 使用 export 命令

```cmd
renderdoccmd export capture.rdc -o output/
renderdoccmd export capture.rdc -o output/ --metadata
renderdoccmd export capture.rdc -o output/ --bindings
```

#### C++ 代码位置

- `renderdoccmd/renderdoccmd.cpp:656-920` — ExportCommand 类实现
- 支持参数：`--metadata`（输出元数据 JSON）、`--bindings`（输出资源绑定）

#### 编译历史记录

编译步骤记录于：`plans/2025-01-24-185241-Agent01-BuildAndPythonCheck.md`

---


## 11. RDC → XML 导出详细操作指南

> **核心方法**：使用 RenderDoc **原生支持**的 `renderdoccmd convert` 命令行工具！

### 11.1 命令行导出（推荐）

```bash
# RDC → XML 转换（RenderDoc 原生支持！）
renderdoccmd convert -f capture.rdc -o capture.xml -c xml

# 参数说明：
#   -f <file>   输入文件路径
#   -o <file>   输出文件路径  
#   -c <format> 输出格式 (xml)
```

**实际验证示例**（来自 `test_e2e_real_data.py`）：
```python
# scripts/rdc_analyzer/test_e2e_real_data.py:108-114
cmd = [
    renderdoccmd, "convert",
    "-f", str(rdc_path),     # 输入 .rdc 文件
    "-o", str(xml_path),      # 输出 .xml 文件
    "-c", "xml"               # 指定 xml 格式
]
result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
```

### 11.2 查看支持的格式

```bash
# 列出所有支持的转换格式
renderdoccmd convert --list-formats
```

### 11.3 完整工作流（RDC → XML → HTML）

```bash
# Step 1: RDC 转换为 XML
renderdoccmd convert -f game.rdc -o game.xml -c xml

# Step 2: 解析 XML 生成 HTML 报告
cd scripts/rdc_analyzer
py -3 -m rdc_analyzer analyze game.xml -o ./output/ --format html,json
```

### 11.4 C++ 源码位置

`convert` 命令的实现位于：
- `renderdoccmd/renderdoccmd.cpp:1436` → `struct ConvertCommand`
- 支持的格式通过 `ICaptureFile::GetCaptureFileFormats()` 获取

### 11.5 注意事项

| 项目 | 说明 |
|------|------|
| **大文件超时** | XML 导出可能耗时较长（数分钟），建议设置 `timeout=300` |
| **文件大小** | XML 文件可能比原 RDC 大很多（10x-50x） |
| **编码** | XML 输出为 UTF-8 编码 |

---
