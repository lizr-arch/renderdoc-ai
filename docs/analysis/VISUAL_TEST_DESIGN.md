# RDC Analyzer 视觉测试验证方案设计

> **版本**: 1.0.0 | **创建日期**: 2025-01-21 | **状态**: Draft
> 
> **目标**: 为 RDC Analyzer HTML 报告建立自动化视觉验证框架，确保 UI 布局、交互功能和数据展示的正确性。

---

## 1. 研究成果摘要

### 1.1 主流视觉测试方案对比

| 方案 | 类型 | 优势 | 劣势 | 适用场景 |
|------|------|------|------|----------|
| **Playwright toHaveScreenshot** | 像素级对比 | 精确、可自动化、支持 CI | 对字体/渲染敏感、需固定环境 | 回归测试 |
| **Claude Vision + MCP** | 语义理解 | 智能判断、理解布局意图 | 需 API 调用、成本 | 复杂 UI 验证 |
| **Chrome DevTools MCP** | DOM + 截图 | 实时交互、无需额外安装 | 依赖浏览器状态 | 开发期验证 |
| **Percy/Applitools** | 商业平台 | 跨浏览器、团队协作 | 成本高、配置复杂 | 企业级 CI/CD |
| **Computer Use Demo** | 全桌面自动化 | 完整环境模拟 | 重量级、延迟高 | E2E 系统测试 |

### 1.2 关键技术发现

**Claude Vision 最佳实践** (来自 anthropic-cookbook):
1. **Crop Tool 模式**: 允许 AI 主动裁剪图像特定区域进行细节分析
2. **Base64 图像输入**: 支持 JPEG/PNG，建议控制在 10MB 以内
3. **结构化提取**: 使用 Tools 定义期望输出格式
4. **迭代分析**: 支持多轮对话记忆，逐步深入分析

**Playwright 视觉对比要点**:
1. **基线快照**: 首次运行生成参考截图，后续对比
2. **maxDiffPixels**: 允许的像素差异阈值
3. **stylePath**: 可注入 CSS 隐藏动态元素
4. **平台差异**: 不同 OS/浏览器渲染结果可能不同

---

## 2. 推荐方案：混合视觉验证框架

### 2.1 方案架构

```
┌─────────────────────────────────────────────────────────────┐
│                   Visual Test Framework                      │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: DOM 结构验证 (Chrome DevTools MCP)                │
│  ├─ take_snapshot: 获取 A11Y 树，验证元素存在              │
│  ├─ evaluate_script: 执行 JS 检查数据/状态                 │
│  └─ 适用: 快速开发期验证                                    │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: 截图视觉对比 (Playwright / Chrome MCP)            │
│  ├─ take_screenshot: 捕获页面截图                          │
│  ├─ 像素对比: 与基线快照对比 (可选 Python Pillow)          │
│  └─ 适用: 回归测试                                          │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: AI 语义理解 (Claude Vision)                       │
│  ├─ 截图 → Base64 → Claude API                             │
│  ├─ 验证: 布局合理性、颜色正确性、交互状态                 │
│  └─ 适用: 复杂 UI 逻辑验证                                  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 分层策略

| 层级 | 验证内容 | 执行频率 | 工具 |
|------|----------|----------|------|
| **L1 DOM** | 元素存在、数据加载、基本结构 | 每次构建 | Chrome DevTools MCP |
| **L2 像素** | 布局一致性、样式回归 | PR 合并 | Playwright / PIL |
| **L3 语义** | 用户体验、复杂交互、颜色语义 | 里程碑发布 | Claude Vision API |

---

## 3. 验证项清单

### 3.1 shaders.html 页面

| 编号 | 验证项 | 层级 | 预期结果 |
|------|--------|------|----------|
| S1 | GPU 选择下拉框存在 | L1 | `#gpuSelector` 元素可见 |
| S2 | GPU 选项包含全档位 | L1 | 含 Mali-G720, G78, G52, G31 |
| S3 | Shader 列表渲染 | L1 | 55 个 `.shader-item` 元素 |
| S4 | Mali 分析徽章显示 | L1 | 10 个 `.mali-badge` 元素 |
| S5 | Health Badge 颜色正确 | L2/L3 | 绿色=good, 黄色=warning, 红色=critical |
| S6 | 点击 Shader 触发选中 | L1 | 元素获得 `.selected` 类 |
| S7 | GPU 切换触发重算 | L1 | 切换后 Mali 面板更新 |
| S8 | 整体布局美观 | L3 | 三栏布局清晰，无重叠 |

### 3.2 events.html 页面

| 编号 | 验证项 | 层级 | 预期结果 |
|------|--------|------|----------|
| E1 | 事件列表渲染 | L1 | 180 个 `.event-item` 元素 |
| E2 | 热力图显示 | L2 | 颜色渐变可见 |
| E3 | Pass 分组折叠 | L1 | 点击后子项隐藏 |
| E4 | 跨页跳转链接 | L1 | 点击 Shader 链接跳转 |

### 3.3 textures.html 页面

| 编号 | 验证项 | 层级 | 预期结果 |
|------|--------|------|----------|
| T1 | 纹理卡片渲染 | L1 | 100 个 `.texture-card` 元素 |
| T2 | 缩略图加载 | L2 | 无破损图像 |
| T3 | 尺寸标签显示 | L1 | 格式正确 (如 "1024x512") |

---

## 4. 实现方案

### 4.1 L1: DOM 结构验证 (当前可用)

使用已连接的 **Chrome DevTools MCP**:

```javascript
// 步骤 1: 打开报告页面
navigate_page({ type: "url", url: "file:///path/to/shaders.html" })

// 步骤 2: 获取 DOM 快照
take_snapshot({})
// 返回 A11Y 树，检查元素 uid

// 步骤 3: 执行 JS 验证
evaluate_script({
  function: `() => {
    const shaders = document.querySelectorAll('.shader-item');
    const maliBadges = document.querySelectorAll('.mali-badge');
    const gpuSelector = document.getElementById('gpuSelector');
    return {
      shaderCount: shaders.length,
      maliBadgeCount: maliBadges.length,
      gpuOptions: gpuSelector ? gpuSelector.options.length : 0
    };
  }`
})

// 步骤 4: 交互验证
click({ uid: "first-shader-item-uid" })
// 验证选中状态
```

### 4.2 L2: 截图对比 (可选实现)

**方案 A: Playwright (推荐)**

```javascript
// playwright.config.ts
import { defineConfig } from '@playwright/test';
export default defineConfig({
  expect: {
    toHaveScreenshot: { maxDiffPixels: 100 }
  }
});

// tests/visual.spec.ts
test('shaders page layout', async ({ page }) => {
  await page.goto('file:///path/to/shaders.html');
  await expect(page).toHaveScreenshot('shaders-layout.png');
});
```

**方案 B: Chrome MCP + Python PIL**

```python
# scripts/visual_test/screenshot_compare.py
from PIL import Image, ImageChops
import base64

def compare_screenshots(baseline_path: str, current_b64: str, threshold=100):
    """对比基线截图和当前截图"""
    baseline = Image.open(baseline_path)
    current = Image.open(io.BytesIO(base64.b64decode(current_b64)))
    
    diff = ImageChops.difference(baseline, current)
    diff_pixels = sum(1 for p in diff.getdata() if sum(p) > 10)
    
    return diff_pixels <= threshold
```

### 4.3 L3: Claude Vision 语义验证

```python
# scripts/visual_test/semantic_verify.py
import anthropic
import base64

def verify_ui_semantics(screenshot_path: str, checklist: list[str]) -> dict:
    """使用 Claude Vision 验证 UI 语义"""
    client = anthropic.Anthropic()
    
    with open(screenshot_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode()
    
    prompt = f"""分析这个 UI 截图，验证以下项目：
    
    {chr(10).join(f"- {item}" for item in checklist)}
    
    对每项返回: PASS/FAIL + 原因
    """
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_data}},
                {"type": "text", "text": prompt}
            ]
        }]
    )
    
    return parse_verification_result(response.content[0].text)
```

---

## 5. 推荐执行流程

### 5.1 开发期验证 (L1)

```
┌─────────────────────────────────────────┐
│ 1. 生成报告: py -3 generate_bundle.py  │
│ 2. Chrome 打开: shaders.html           │
│ 3. MCP 验证:                           │
│    - take_snapshot → 检查元素存在      │
│    - evaluate_script → 验证数据正确    │
│    - click → 验证交互响应              │
│ 4. 输出验证报告                        │
└─────────────────────────────────────────┘
```

### 5.2 里程碑发布验证 (L1+L2+L3)

```
┌─────────────────────────────────────────┐
│ 1. L1 DOM 验证 (自动)                   │
│ 2. L2 截图对比 (Playwright)             │
│ 3. L3 语义验证 (Claude Vision)          │
│ 4. 生成综合验证报告                     │
└─────────────────────────────────────────┘
```

---

## 6. 立即可执行的验证步骤

使用当前可用的 Chrome DevTools MCP，执行以下验证：

### 步骤 1: 打开报告页面
```
new_page({ url: "file:///d:/Code/git/renderdoc/scripts/rdc_analyzer/test_output_m43_real/shaders.html" })
```

### 步骤 2: 获取页面快照
```
take_snapshot({})
```

### 步骤 3: 截图保存
```
take_screenshot({ format: "png", filePath: "shaders_screenshot.png" })
```

### 步骤 4: 执行验证脚本
```javascript
evaluate_script({
  function: `() => {
    const results = {
      shaderCount: document.querySelectorAll('.shader-item').length,
      maliBadgeCount: document.querySelectorAll('.mali-badge').length,
      gpuSelectorExists: !!document.getElementById('gpuSelector'),
      gpuOptions: document.getElementById('gpuSelector')?.options.length || 0,
      healthBadges: document.querySelectorAll('.health-badge').length,
      pageTitle: document.title
    };
    return results;
  }`
})
```

### 步骤 5: 交互验证
```
click({ uid: "first-shader-item-uid", includeSnapshot: true })
```

---

## 7. 成本与收益分析

| 方案 | 实现成本 | 维护成本 | 覆盖率 | 推荐度 |
|------|----------|----------|--------|--------|
| L1 only | 低 (当前可用) | 低 | 60% | ⭐⭐⭐ 开发期 |
| L1 + L2 | 中 (需 Playwright) | 中 | 85% | ⭐⭐⭐⭐ PR 验证 |
| L1 + L2 + L3 | 高 (需 API) | 高 | 95% | ⭐⭐⭐⭐⭐ 发布前 |

---

## 8. 下一步行动

1. **立即执行 L1 验证**: 使用 Chrome DevTools MCP 验证 shaders.html
2. **可选**: 建立 Playwright 测试用例作为 L2 回归测试
3. **可选**: 为重要里程碑配置 Claude Vision L3 验证

---

## 附录 A: 验证脚本模板

见 `scripts/visual_test/` 目录 (待创建)
