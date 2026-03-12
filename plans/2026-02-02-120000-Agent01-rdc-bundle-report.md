# RDC Bundle Report (Textures + Shaders UI) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-02-02  
**Owner:** Agent01  
**Last Updated:** 2026-02-02  

**Goal:** 确保 4 页面 bundle 报告中的纹理缩略图与 Shader HLSL 源码真实可见，并提供可读的语法高亮展示。  

**Architecture:** 保持现有 `rdc_to_bundle_report.py` 数据抽取流程不变，补充在 `report_bundle_generator.py` 中对缩略图 data URL 的归一化与模板注入；在 `templates/shaders.html` 内改造代码展示为 `<pre><code>` + highlight.js（可用则高亮、不可用则回退到现有正则高亮）。  

**Tech Stack:** Python (RenderDoc Python API), HTML/JS templates, ReportBundleGenerator.  

**Success Criteria (measurable):**
- `textures.html` 中至少 1 个纹理缩略图可见（data URL，浏览器无报错）。
- `shaders.html` 点击列表项时显示完整 HLSL 源码，且高亮生效（hljs 或回退高亮）。
- `rdc_to_bundle_report.py` 运行无异常，输出 `report_data.json` 与 4 页面 HTML。  

**Acceptance Criteria:**
- 纹理详情面板与 lightbox 均能显示缩略图（非空白）。
- Shader 详情侧栏显示完整源码，复制/下载功能仍可用。
- 不破坏现有统计与导航链接。  

**Verification Commands:**
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -v` (Expected: PASS)
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k shaders -v` (Expected: PASS)
- 手动：用 RenderDoc Python Shell 运行 `rdc_to_bundle_report.py`，打开 `output/textures.html` 与 `output/shaders.html` (Expected: 缩略图与源码可见)  

**Evidence:**
- `scripts/rdc_analyzer/output/textures.html`
- `scripts/rdc_analyzer/output/shaders.html`
- 控制台日志包含 `[OK] Extracted ...` 与 `[OK] With source ...`  

**Estimation:**
- Effort: 0.5–1 天
- Story Points: 2
- Original Estimate: 4 小时  

**Risk Register (impact/likelihood/mitigation):**
- 缩略图仍为空（中/中）：在 generator 层添加 data URL 归一化 + 模板回退提示。
- highlight.js 依赖不可用（中/中）：保留现有 `highlightCode()` 作为回退。
- Python 文件 AST 无法解析（低/中）：改用最小文本范围修改，避免符号级编辑。  

## Game Dev: Memory & Resource Budget (Leak Checks)
- 纹理缩略图 Base64 可能造成内存膨胀；仅在 HTML 中引用并限制单张预览尺寸，避免额外缓存。

## Game Dev: Asset Pipeline
- 纹理缩略图作为报告产物，不进入资产管线；确保 `output/` 作为唯一输出目录，避免污染源素材。

## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: RenderDoc 打开捕获 → Python Shell 执行脚本 → 打开 HTML。  
- Dump/Core: (minidump | core dump) TBD  
- Symbols: (PDB | dSYM | ELF | DWARF) TBD  
- Build identity: (build id | commit hash | git commit) TBD  

## Repo / File List
- `scripts/rdc_analyzer/rdc_to_bundle_report.py:176,198,203-204,441-448`
- `scripts/rdc_analyzer/report_bundle_generator.py:484,507,537,613-670`
- `scripts/rdc_analyzer/templates/textures.html:589-611`
- `scripts/rdc_analyzer/templates/shaders.html:672-713`
- `scripts/rdc_analyzer/tests/test_bundle_report_assets.py` (new)

## Approach (Pseudo-code)

**Normalize thumbnail data URL in generator:**
```python
def _normalize_thumbnail(thumbnail: str) -> str:
    if not thumbnail:
        return ""
    if thumbnail.startswith("data:"):
        return thumbnail
    return f"data:image/png;base64,{thumbnail}"

thumb = _normalize_thumbnail(tex.get("thumbnail", ""))
tex_copy["thumbnail"] = thumb
```

**Shader code viewer with highlight.js + fallback:**
```javascript
function updateCodeViewer(shader) {
  const content = document.getElementById('codeContent');
  const code = shader[currentCodeTab] || shader.glsl || shader.source || '';
  content.innerHTML = '<pre><code id="codeBlock" class="language-hlsl"></code></pre>';
  const codeEl = document.getElementById('codeBlock');
  codeEl.textContent = code || '';
  if (window.hljs) {
    hljs.highlightElement(codeEl);
  } else {
    codeEl.innerHTML = highlightCode(code || '');
  }
}
```

**Shader details sidebar (HLSL section):**
```html
<div class="detail-card">
  <div class="detail-title">HLSL 源码</div>
  <pre class="shader-source" id="shaderSource"></pre>
</div>
```
```javascript
document.getElementById('shaderSource').textContent = shader.source || '';
```

## Build/Test/Lint Quick Guide (commands only)
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -v`

## Task Checklist

- [x] Task 1: 纹理缩略图 data URL 归一化（TDD）
- [x] Task 2: Shader 页面代码展示 + 高亮（TDD）
- [x] Task 3: 纹理页面缩略图显示回归验证

### Task 1: 纹理缩略图 data URL 归一化（TDD）
**Files:**
- Modify: `scripts/rdc_analyzer/report_bundle_generator.py:484,507,537`
- Create: `scripts/rdc_analyzer/tests/test_bundle_report_assets.py`

**Step 1: Write the failing test**
```python
def test_texture_thumbnail_data_url(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_textures([{
        "id": "1",
        "name": "Tex",
        "width": 1,
        "height": 1,
        "thumbnail": "AAAA"
    }])
    outputs = gen.generate_all()
    html = Path(outputs["textures"]).read_text(encoding="utf-8")
    assert "data:image/png;base64,AAAA" in html
```

**Step 2: Run test to verify it fails**
- Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py::test_texture_thumbnail_data_url -v`
- Expected: FAIL (missing data URL prefix)

**Step 3: Write minimal implementation**
```python
def _normalize_thumbnail(thumbnail: str) -> str:
    if not thumbnail:
        return ""
    if thumbnail.startswith("data:"):
        return thumbnail
    return f"data:image/png;base64,{thumbnail}"
```

**Step 4: Run test to verify it passes**
- Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py::test_texture_thumbnail_data_url -v`
- Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/report_bundle_generator.py scripts/rdc_analyzer/tests/test_bundle_report_assets.py
git commit -m "fix(rdc-analyzer): normalize texture thumbnail data URL

- ensure thumbnails are data:image/png;base64 for HTML rendering
- add test for textures.html output"
```

### Task 2: Shader 页面代码展示 + 高亮（TDD）
**Files:**
- Modify: `scripts/rdc_analyzer/templates/shaders.html:672-713`
- Modify: `scripts/rdc_analyzer/report_bundle_generator.py:613-670`
- Update test: `scripts/rdc_analyzer/tests/test_bundle_report_assets.py`

**Step 1: Write the failing test**
```python
def test_shader_source_rendered(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_shaders([{"id": "1", "name": "S", "source": "float4 main() : SV_Target { return 0; }"}])
    outputs = gen.generate_all()
    html = Path(outputs["shaders"]).read_text(encoding="utf-8")
    assert "float4 main()" in html
    assert "codeBlock" in html
```

**Step 2: Run test to verify it fails**
- Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py::test_shader_source_rendered -v`
- Expected: FAIL (no codeBlock or HLSL injected)

**Step 3: Write minimal implementation**
```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css">
```
```javascript
content.innerHTML = '<pre><code id="codeBlock" class="language-hlsl"></code></pre>';
```

**Step 4: Run test to verify it passes**
- Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py::test_shader_source_rendered -v`
- Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/templates/shaders.html scripts/rdc_analyzer/tests/test_bundle_report_assets.py
git commit -m "feat(rdc-analyzer): improve shader viewer with hljs highlighting

- render shader source in code block
- add tests for shaders.html output"
```

### Task 3: 纹理页面缩略图显示回归验证
**Files:**
- Modify: `scripts/rdc_analyzer/templates/textures.html:589-611` (if needed)

**Step 1: Write the failing test**
```python
def test_texture_preview_uses_thumbnail(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_textures([{"id": "1", "name": "Tex", "width": 1, "height": 1,
                       "thumbnail": "data:image/png;base64,AAAA"}])
    outputs = gen.generate_all()
    html = Path(outputs["textures"]).read_text(encoding="utf-8")
    assert "previewImg" in html and "thumbnail" in html
```

**Step 2: Run test to verify it fails**
- Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py::test_texture_preview_uses_thumbnail -v`
- Expected: FAIL (if template missing binding)

**Step 3: Write minimal implementation**
```javascript
if (texture.thumbnail) {
  previewImg.src = texture.thumbnail;
}
```

**Step 4: Run test to verify it passes**
- Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py::test_texture_preview_uses_thumbnail -v`
- Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/templates/textures.html scripts/rdc_analyzer/tests/test_bundle_report_assets.py
git commit -m "fix(rdc-analyzer): ensure texture preview uses thumbnail"
```

## Risks & Blockers
- `rdc_to_bundle_report.py` 与 `report_bundle_generator.py` 在 LSP 中解析失败，可能需要文本级小范围修改。
- highlight.js CDN 在离线环境不可用；必须保留回退高亮。

## Decisions
- 优先在 generator 层做缩略图 data URL 归一化，避免上游遗漏导致模板失效。
- Shader 高亮：优先 hljs，回退使用现有 `highlightCode()`。

## Verification / Acceptance (Definition of Done)
- 所有新增测试通过；HTML 中能看到缩略图与 HLSL。
- `rdc_to_bundle_report.py` 可在 RenderDoc Python Shell 正常运行。
- 报告 4 页面无 JS 报错，主导航可用。

## Open Questions
- 是否需要将 highlight.js 资源本地化（避免 CDN）？
- Shader 页面侧栏布局是否需要固定宽度（UI 细节）？

## Next Steps
- 等待 /do 批准后实施变更。
