# 🔄 RDC 分析工具 - 项目交接文档

> **日期**: 2025-01-22  
> **状态**: 可交接  
> **下一步**: 用户测试验证

---

## 📌 项目背景

**目标**：为 RenderDoc 的 `.rdc` 捕获文件创建自动化分析工具，生成**包含真实数据的 HTML 报告**（4 页面：概览、纹理、Shader、事件）。

**仓库路径**：`d:\Code\git\renderdoc`  
**工具目录**：`scripts/rdc_analyzer/`

---

## ✅ 已完成的工作

### 1. 纹理名称优化（问题 C）
- **问题**：纹理列表显示冗长技术名称如 `Texture2D_68x26_R8G8B8A8_TYPELESS`
- **解决**：简化为 `#tex_ID (宽×高)` 格式
- **修改文件**：
  - `report_bundle_generator.py` → `_format_texture_name()` 方法
  - `templates/textures.html` → JavaScript `selectTexture()` 函数

### 2. RDC → 4 页面报告一键脚本（核心功能）
- **新建文件**：`scripts/rdc_analyzer/rdc_to_bundle_report.py`
- **功能**：

| 步骤 | 功能 | 技术实现 |
|------|------|----------|
| Step 1 | 纹理 + **真实缩略图** | `controller.SaveTexture()` → PNG → Base64 |
| Step 2 | Shader + **真实 HLSL 源码** | `controller.DisassembleShader()` |
| Step 3 | Draw Call 事件列表 | 遍历 `GetRootActions()` |
| Step 4 | 生成 HTML 报告 | 调用 `ReportBundleGenerator` |

- **使用方式**（在 RenderDoc Python Shell 中）：
  ```python
  exec(open(r'd:\Code\git\renderdoc\scripts\rdc_analyzer\rdc_to_bundle_report.py').read())
  ```

---

## 📁 关键文件清单

| 文件 | 职责 |
|------|------|
| `rdc_to_bundle_report.py` | **新建** - RDC 一键生成 4 页面报告（主入口） |
| `report_bundle_generator.py` | 4 页面 HTML 生成器类 |
| `templates/textures.html` | 纹理页面模板 |
| `templates/shaders.html` | Shader 页面模板 |
| `templates/events.html` | 事件页面模板 |
| `templates/overview.html` | 概览页面模板 |
| `extract_shaders.py` | 独立 Shader 提取脚本（参考实现） |
| `generate_report_from_rdoc.py` | 旧版单页报告生成器（参考） |
| `rdc_to_html.py` | 纹理单页报告工具（参考） |

---

## ⏳ 待完成/可接续的任务

### 优先级 HIGH
1. **用户测试验证**
   - 在 RenderDoc 中运行 `rdc_to_bundle_report.py`
   - 验证纹理缩略图是否正确显示
   - 验证 Shader 源码是否正确提取

2. **Shader 页面 UI 优化**
   - 点击 Shader 列表项时，侧边栏显示完整 HLSL 源码
   - 添加语法高亮（可用 highlight.js）

3. **纹理页面缩略图显示**
   - 确保 `textures.html` 正确渲染 Base64 缩略图
   - 可能需要更新模板 JS 代码以支持 `thumbnail` 字段

### 优先级 MEDIUM
4. **性能分析集成**
   - 集成 Mali Offline Compiler 分析结果
   - 添加 Shader 性能警告

5. **重复纹理检测**
   - 已有 `DuplicateDetector` 类
   - 需要集成到 4 页面报告中

---

## 🔧 技术要点（供下一个 Agent 参考）

### RenderDoc Python API 核心方法
```python
# 获取纹理列表
textures = controller.GetTextures()

# 导出纹理为 PNG
save_data = rd.TextureSave()
save_data.resourceId = tex.resourceId
save_data.destType = rd.FileType.PNG
controller.SaveTexture(save_data, output_path)

# 获取 Shader 反汇编
targets = controller.GetDisassemblyTargets(True)  # 获取支持的格式
source = controller.DisassembleShader(pipeline, reflection, target)
```

### 报告生成器使用方式
```python
from report_bundle_generator import ReportBundleGenerator

generator = ReportBundleGenerator(output_dir="path", capture_name="file.rdc")
generator.set_textures(textures_list)
generator.set_shaders(shaders_list)
generator.set_events(events_list)
output_files = generator.generate_all()
```

---

## 🚀 快速恢复指令

下一个 Agent 可以直接使用以下命令查看关键代码：

```bash
# 查看主脚本
cat scripts/rdc_analyzer/rdc_to_bundle_report.py

# 查看报告生成器
cat scripts/rdc_analyzer/report_bundle_generator.py

# 查看模板文件
ls scripts/rdc_analyzer/templates/
```

---

## 📝 会话历史摘要

1. 用户反馈纹理/Shader 页面没有真实数据（只有占位符）
2. 发现原因：之前的流程基于 XML 导出，无法获取纹理缩略图和 Shader 源码
3. 解决方案：创建 `rdc_to_bundle_report.py`，直接从 RDC 文件提取真实数据
4. 用户确认纹理名称简化方案（`#tex_ID (尺寸)` 格式）
5. 当前状态：脚本已创建，待用户在 RenderDoc 中实际测试

---

**文档结束 - 可交接给下一个 Agent**
