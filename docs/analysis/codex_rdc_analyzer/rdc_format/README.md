# RDC 文件格式学习指南

> 🎯 **目标读者**：刚接触 RenderDoc 或图形调试的新人程序员
>
> ⏱️ **总学习时间**：约 30-45 分钟

---

## 📚 这是什么？

这是一套专为 **新人友好** 设计的 RDC 文件格式学习文档。

**RDC 文件** 是 RenderDoc 捕获的图形帧文件，记录了 GPU 渲染一帧画面的所有命令和数据。理解它的结构是进行图形性能分析的基础。

---

## 🎯 学完你将掌握

| 技能 | 说明 |
|------|------|
| ✅ 理解 RDC 概念 | 知道 RDC 文件"是什么"、"为什么需要" |
| ✅ 识别文件结构 | 能说出 FileHeader / Section / Chunk 的作用 |
| ✅ 阅读二进制数据 | 能用十六进制查看器分析 RDC 文件头 |
| ✅ 理解渲染流程 | 知道一帧画面是如何由多个 Draw Call 组成的 |
| ✅ 动手分析 RDC | 能用 `renderdoccmd` 把 RDC 转成可读的 XML |

---

## 📖 学习路径

按顺序阅读以下三篇文档：

### 第一步：入门概念（5 分钟）

📄 **[01_RDC_INTRO.md](./01_RDC_INTRO.md)**

- 用"游戏录像"类比解释 RDC 是什么
- 用"书籍"类比解释 RDC 的整体结构
- 介绍 Header / Section / Chunk 三层架构

**学完检验**：能向同事解释"RDC 就像一本书，有封面、目录和正文"

---

### 第二步：二进制结构（10 分钟）

📄 **[02_RDC_STRUCTURE.md](./02_RDC_STRUCTURE.md)**

- 逐字节解释 FileHeader（前 32 字节）
- 详解 Section 的布局和类型
- 展示 Chunk 的二进制格式
- 提供真实的十六进制示例

**学完检验**：能看懂 `52 44 4F 43` 代表 "RDOC" 魔数

---

### 第三步：实战示例（15 分钟）

📄 **[03_RDC_EXAMPLE.md](./03_RDC_EXAMPLE.md)**

- 用一个 3D 游戏场景（天空盒/地形/角色/粒子）作为例子
- 展示完整的 GPU 命令序列（20 个 Chunk）
- 展示转换后的 XML 格式
- 展示最终的 JSON 分析报告
- 包含可直接运行的 Python 代码

**学完检验**：能解释 `vkCmdDrawIndexed` 的 `indexCount=150000` 意味着画了 50000 个三角形

---

## 🛠️ 动手练习

学完文档后，试试以下练习：

### 练习 1：查看 RDC 文件头

用任意十六进制编辑器（如 HxD、VSCode 的 Hex Editor 插件）打开一个 `.rdc` 文件：

```
目标：找到前 4 个字节 "RDOC"
预期：看到 52 44 4F 43
```

### 练习 2：转换 RDC 为 XML

```powershell
# 使用 renderdoccmd 转换
renderdoccmd convert -c xml -o output.xml your_capture.rdc

# 用文本编辑器打开 output.xml，搜索 "vkCmdDraw"
```

### 练习 3：统计三角形数量

参考 `03_RDC_EXAMPLE.md` 中的 Python 代码，写一个脚本统计 RDC 中的总三角形数。

---

## 📂 文件清单

```
rdc_format/
├── README.md          ← 你正在看的这个文件（学习入口）
├── 01_RDC_INTRO.md    ← 入门概念（5分钟）
├── 02_RDC_STRUCTURE.md← 二进制结构（10分钟）
└── 03_RDC_EXAMPLE.md  ← 实战示例（15分钟）
```

---

## 🔗 延伸阅读

学完本系列后，可以继续阅读：

| 文档 | 说明 |
|------|------|
| [RDC_FORMAT_AND_PARSING_GUIDE.md](../RDC_FORMAT_AND_PARSING_GUIDE.md) | 更深入的技术参考（面向有经验开发者） |
| [WORK_SUMMARY_ROUTES.md](../WORK_SUMMARY_ROUTES.md) | 项目的三条解析路线（A/B/C） |
| [scripts/rdc_analyzer/README.md](../../../../scripts/rdc_analyzer/README.md) | RDC Analyzer CLI 工具使用指南 |

---

## ❓ 常见问题

### Q: 我没有 RDC 文件怎么办？

用 RenderDoc 捕获任意游戏或图形应用：
1. 下载 [RenderDoc](https://renderdoc.org/)
2. 启动后选择"Launch Application"
3. 运行游戏，按 `F12` 或 `Print Screen` 捕获
4. 保存 `.rdc` 文件

### Q: renderdoccmd 在哪里？

- Windows: `C:\Program Files\RenderDoc\renderdoccmd.exe`
- 或者在 RenderDoc 安装目录下

### Q: XML 文件太大打不开怎么办？

1. 用流式解析（Python 的 `iterparse`）
2. 或只搜索特定关键词：`rg "vkCmdDraw" output.xml`

---

## 🎉 完成学习后...

恭喜！你已经掌握了 RDC 文件格式的基础知识。

**下一步建议**：
1. 用 `rdc_analyzer` 工具分析一个真实的游戏 RDC
2. 尝试找出哪个 Draw Call 消耗了最多三角形
3. 学习如何用规则引擎检测性能问题

---

> 💡 **反馈**：如果文档有任何不清楚的地方，欢迎提 Issue 或 PR！
