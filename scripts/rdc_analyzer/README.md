# RDC Analyzer - RenderDoc 帧分析工具

> 从 RenderDoc 捕获文件 (.rdc / .xml) 提取纹理、分析性能、对比回归、审计资源

## ✨ 功能概览

| 模式 | 命令 | 用途 |
|------|------|------|
| **A-first** | `analyze` | 单帧分析，生成 HTML 报告 + JSON 统计 |
| **B-mode** | `compare` | 双帧对比，检测性能回归/改进 |
| **C-mode** | `audit` | 资产审计，检测反模式（无需基线） |

## 🚀 快速开始

### 安装

```bash
pip install pillow scipy  # 可选依赖
```

### 基础用法

```bash
# 单帧分析
py -3 -m rdc_analyzer analyze capture.rdc -o report.html

# 双帧对比（回归检测）
py -3 -m rdc_analyzer compare baseline.xml current.xml -o diff.html

# 资产审计（移动端预设）
py -3 -m rdc_analyzer audit capture.json --platform mobile -o audit.html
```

---

## 📊 命令详解

### `analyze` - 单帧分析

从 RDC/XML/JSON 生成 HTML 报告，包含纹理列表、VRAM 分析、Draw Call 统计。

```bash
py -3 -m rdc_analyzer analyze capture.rdc [OPTIONS]

选项:
  -o, --output PATH      输出路径 (默认: capture.html)
  --json PATH            额外输出 JSON 统计数据
  --format html|json     输出格式
```

**输出内容**:
- 📊 VRAM 使用分布（格式/尺寸饼图）
- 🖼️ 纹理网格视图 + Lightbox 预览
- 🔗 Event ID 跳转
- 🔄 重复纹理检测
- 🧊 冷热分析

---

### `compare` - 双帧对比

比较两个捕获文件，检测纹理差异、性能回归、资源变化。

```bash
py -3 -m rdc_analyzer compare BASELINE CURRENT [OPTIONS]

选项:
  -o, --output PATH      输出 HTML 报告
  --json PATH            输出 JSON 对比结果
  --align-strategy       对齐策略: auto | index | marker (默认: auto)
  --threshold FLOAT      变化阈值百分比 (默认: 5.0)
  
CI 集成选项:
  --junit-xml PATH       输出 JUnit XML 格式报告
  --fail-on-regression   发现回归时返回非零退出码
  --fail-threshold FLOAT 触发失败的回归阈值 (默认: 10.0)
```

**回归检测规则**:
| 规则 ID | 说明 | 阈值 |
|---------|------|------|
| `REG_TEXTURE_COUNT` | 纹理数量增加 | >10% |
| `REG_VRAM_TOTAL` | VRAM 总量增加 | >10% |
| `REG_DUPLICATE_TEXTURES` | 新增重复纹理 | >0 |
| `REG_DRAWCALL_COUNT` | Draw Call 增加 | >15% |

**统计显著性检测** (多帧采样时):
- Welch's t-test 检验均值差异
- Cohen's d 效应量评估
- 95% 置信区间

---

### `audit` - 资产审计

检查单个捕获文件中的资源反模式，无需基线对比。

```bash
py -3 -m rdc_analyzer audit CAPTURE [OPTIONS]

选项:
  -o, --output PATH      输出路径 (JSON 或 HTML)
  --platform pc|mobile   目标平台 (默认: pc)
  --preset PRESET        审计预设: default|mobile|pc|strict
```

**预设阈值**:

| 预设 | 最大纹理尺寸 | VRAM 限制 | 检查 NPOT | 检查 Mipmap |
|------|-------------|-----------|-----------|-------------|
| `pc` | 4096 | 2048 MB | ❌ | ✅ |
| `mobile` | 2048 | 512 MB | ✅ | ✅ |
| `strict` | 2048 | 1024 MB | ✅ | ✅ |

**检测规则**:

| 规则 ID | 严重程度 | 说明 |
|---------|----------|------|
| `AUD_TEX_001` | WARNING/CRITICAL | 纹理尺寸超限 |
| `AUD_TEX_002` | WARNING | 缺少 Mipmap |
| `AUD_TEX_003` | CRITICAL | 非2次幂纹理 (NPOT) |
| `AUD_MEM_001` | CRITICAL | 单资源内存超限 |

**评级系统**: A-F（任何 CRITICAL 问题直接 F 级）

---

## 🔧 CI/CD 集成

### GitHub Actions 示例

```yaml
name: Graphics Regression

on: [push, pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Run Comparison
        run: |
          py -3 -m rdc_analyzer compare \
            baseline.xml current.xml \
            --junit-xml results.xml \
            --fail-on-regression \
            --fail-threshold 10.0
      
      - name: Upload Results
        uses: actions/upload-artifact@v4
        with:
          name: regression-report
          path: results.xml
```

### 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 成功，无回归 |
| 1 | 检测到回归 (`--fail-on-regression`) |
| 2 | 输入文件错误 |
| 3 | 解析/处理错误 |

---

## �️ HTML 报告交互功能

生成的 HTML 报告包含以下交互功能：

### Event Browser（事件浏览器）

| 功能 | 说明 |
|------|------|
| 🔍 搜索过滤 | 按名称/Event ID 搜索 |
| 📁 Pass 分组 | 按渲染 Pass 折叠/展开 |
| 🎯 点击选择 | 点击 Event 查看详情 |

### Event 详情面板

选中 Event 后可查看以下标签：

| 标签 | 内容 |
|------|------|
| **Pipeline State** | VS/FS/CS Shader 代码 + Vulkan Pipeline 对象 |
| **Resource Bindings** | Descriptor Set 绑定（纹理/Buffer/Sampler） |
| **Mesh Info** | Vertex Buffers / Index Buffer / Primitive Topology |
| **💾 导出** | 下载当前 Event 完整 JSON 数据 |

### 纹理-Event 交叉引用

在 **Texture Browser** 中点击任意纹理：

1. 右侧显示纹理属性（格式/尺寸/Mipmap 等）
2. 显示 **🔗 引用次数** 徽章
3. 列出使用该纹理的所有 Draw Call
4. 点击 Event 标签可跳转到 Event Browser

```
纹理属性面板:
┌─────────────────────────────────────┐
│ 📄 Properties                       │
│ ─────────────────                   │
│ Format: VK_FORMAT_R8G8B8A8_UNORM   │
│ Size: 1024 x 1024                   │
│ Mips: 10                            │
├─────────────────────────────────────┤
│ 🔗 被 3 个 Draw Call 使用           │
│ ─────────────────                   │
│ [Event #35] Set 0, Binding 1        │
│ [Event #42] Set 0, Binding 1        │
│ [Event #89] Set 1, Binding 0        │
└─────────────────────────────────────┘
```

---

## �📁 文件结构

```
scripts/rdc_analyzer/
├── __main__.py              # CLI 入口
├── analyzer.py              # 核心分析器
├── bridge.py                # XML 数据桥接
├── compare/                 # B-mode 对比模块
│   ├── comparator.py        # 对比引擎
│   ├── regression.py        # 回归检测规则
│   ├── reporter.py          # 报告生成器
│   └── align.py             # Pass/Marker 对齐
├── stats/                   # 统计分析模块
│   ├── sampler.py           # 多帧采样
│   ├── summary.py           # 统计汇总
│   └── significance.py      # 显著性检测
├── audit/                   # C-mode 审计模块
│   ├── engine.py            # 审计引擎
│   └── report.py            # 审计报告模型
├── ci/                      # CI 集成
│   └── junit_exporter.py    # JUnit XML 导出
└── tests/                   # 单元测试 (450+ 项)
```

---

## 📋 依赖

| 依赖 | 必需 | 用途 |
|------|------|------|
| Python 3.8+ | ✅ | 运行环境 |
| Pillow | ❌ | RGBA 通道分离 |
| scipy | ❌ | 统计显著性检测 |
| defusedxml | ❌ | 安全 XML 解析 |

---

## 🧪 测试样本

### 获取测试用 RDC 文件

测试套件中的部分测试需要真实的 `.rdc` 文件。这些文件因体积较大（通常 100MB+）未包含在仓库中。

**方法 1：手动截帧（推荐）**

1. 安装 RenderDoc（[下载地址](https://renderdoc.org/)）
2. 启动目标应用，使用 RenderDoc 进行帧捕获
3. 保存 `.rdc` 文件到 `tests/fixtures/` 目录

**方法 2：使用现有样本**

如果您有访问权限，可以从以下位置获取测试样本：
```
D:\renderdoc\goog pixel-9\g145.rdc  # Mali GPU (Pixel 9) 截帧
D:\renderdoc\pc_capture.rdc          # PC (D3D11/Vulkan) 截帧
```

### 配置测试样本路径

创建 `tests/conftest_local.py`（已加入 .gitignore）：

```python
# tests/conftest_local.py - 本地测试配置（不提交到 Git）
import pytest

# 真实 RDC 文件路径（根据您的环境修改）
SAMPLE_RDC_PATHS = {
    'mali': r'D:\renderdoc\goog pixel-9\g145.rdc',
    'pc': r'D:\renderdoc\pc_capture.rdc',
}

@pytest.fixture
def real_rdc_path(request):
    """获取真实 RDC 文件路径"""
    platform = getattr(request, 'param', 'mali')
    path = SAMPLE_RDC_PATHS.get(platform)
    if path and not os.path.exists(path):
        pytest.skip(f"样本文件不存在: {path}")
    return path
```

### 运行完整测试

```bash
# 跳过需要真实 RDC 的测试（默认）
py -3 -m pytest tests/

# 包含真实 RDC 测试（需要配置 conftest_local.py）
py -3 -m pytest tests/ --run-real-samples
```

---

## 📝 版本历史

### v3.1.0 - 交互式 HTML 报告增强

- ✨ **Event Browser**: Draw Call 列表 + Pass 分组
- ✨ **Pipeline State**: 显示 VS/FS/CS Shader + Vulkan Pipeline 对象
- ✨ **Resource Bindings**: Descriptor Set 绑定表格（纹理/Buffer/Sampler）
- ✨ **Mesh Info**: Vertex Buffers / Index Buffer / Primitive Topology
- ✨ **纹理-Event 交叉引用**: 点击纹理查看哪些 Draw Call 使用了它
- ✨ **导出功能**: 一键导出单个 Event 的完整 JSON 数据
- ✨ **Shader 语法高亮**: 支持 DXBC/HLSL/SPIRV 反汇编代码高亮

### v3.0.0 - 多模式架构

- ✨ **B-mode**: 双帧对比 + 回归检测
- ✨ **C-mode**: 资产审计 (无需基线)
- ✨ CI 集成: JUnit XML + 退出码
- ✨ 统计分析: 多帧采样 + 显著性检测
- ✨ 450+ 单元测试

### v2.0.0 - 高级分析

- ✨ VRAM 分析仪表盘
- ✨ 纹理对比视图
- ✨ 重复纹理检测
- ✨ 优化建议导出

### v1.0.0 - 初始版本

- 100% 离线 HTML 报告
- RGBA 通道分离
- 网格/表格视图

---

## 📄 License

MIT License - 与 RenderDoc 项目保持一致