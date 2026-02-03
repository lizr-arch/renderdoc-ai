# Shader & Texture Report UI Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Version:** 2026-02-03
**Owner:** Codex
**Last Updated:** 2026-02-03

**Goal:** Refactor the bundle report UI so textures load thumbnails only after a user action, and the shader viewer is HLSL-focused with “查看 HLSL 代码” and “AI Shader 优化” controls.

**Architecture:** Keep the report static (HTML/CSS/JS templates) and update data extraction to populate HLSL source when available via RenderDoc disassembly targets. UI behaviors are implemented via template JS and CSS class toggles (no backend).

**Tech Stack:** Python (rdc_analyzer), RenderDoc Python API, HTML/CSS/JS templates.

**Success Criteria (measurable):**
- textures.html 初次打开不渲染缩略图；点击“显示缩略图”后才显示缩略图与预览。
- shaders.html 不再出现 GLSL / SPIR-V / Disassembly 标签；“查看 HLSL 代码”按钮可展示 HLSL（无可用时有明确提示）。
- “AI Shader 优化”按钮可切换 UI 聚焦模式（可视布局变化可见）。

**Acceptance Criteria:**
- 纹理页与 Shader 页按钮文案与布局符合需求，并在本地 HTML（file://）可用。
- HLSL 仅作为主代码视图内容，其他格式不再显示。

**Verification Commands:**
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -v` (Expected: PASS)
- `py -3 -m pytest scripts/rdc_analyzer/tests/test_shader_extractor.py -v` (Expected: PASS)

**Evidence:**
- `D:\backup\dayuanjing_report\textures.html`
- `D:\backup\dayuanjing_report\shaders.html`

**Estimation:**
- Effort: 0.5 day
- Story Points: 3
- Original Estimate: 0.5 day

**Risk Register (impact/likelihood/mitigation):**
| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| HLSL 反编译工具未配置 | Medium | Medium | UI 显示引导提示；仍可展示原始反汇编 |
| 大量缩略图导致 HTML 仍偏大 | Low | Medium | 默认不渲染，减少首屏 DOM 成本 |
| file:// 环境限制 | Low | Medium | 不使用 fetch 载入外部文件，避免 CORS |

---

## Game Dev: Memory & Resource Budget (Leak Checks)
- 缩略图默认不渲染，避免一次性创建大量 `<img>`；验证首屏 DOM 节点数与渲染耗时可接受。

## Game Dev: Asset Pipeline
- 继续沿用 RDC → XML → bundle HTML；仅修改模板与渲染逻辑，不新增外部资源依赖。

## Game Dev: Crash Repro + Dumps/Symbols
- Repro steps: 生成 bundle 报告并打开 textures/shaders 页面操作按钮。
- Dump/Core: (minidump | core dump) N/A（纯脚本/HTML）
- Symbols: (PDB | dSYM | ELF | DWARF) N/A
- Build identity: (build id | commit hash | git commit) TBD

---

## Repo / File List
- Modify `scripts/rdc_analyzer/report_bundle_generator.py:500-560` (纹理列表 HTML 输出策略)
- Modify `scripts/rdc_analyzer/templates/textures.html:380-840` (列表/按钮/JS 逻辑)
- Modify `scripts/rdc_analyzer/templates/shaders.html:500-760, 960-1015` (主视图/按钮/JS)
- Modify `scripts/rdc_analyzer/extractors/shader_extractor.py:100-320, 380-420` (HLSL 目标选择 + Disassemble)
- Modify `scripts/rdc_analyzer/tests/test_bundle_report_assets.py:1-120`
- Modify `scripts/rdc_analyzer/tests/test_shader_extractor.py:160-210`
- Reference `docs/how/how_edit_shader.rst:27-38`
- Reference `docs/window/settings_window.rst:247-261`

---

## Approach (Pseudo-code)
```python
# shader_extractor.py
def pick_hlsl_target(targets):
    for t in targets:
        if "hlsl" in t.lower():
            return t
    return ""

def _get_hlsl_source(reflection, pipe_state):
    target = pick_hlsl_target(get_disassembly_targets())
    if not target:
        return ""
    return controller.DisassembleShader(pipeline_id, reflection, target) or ""
```

```js
// textures.html
let thumbnailsEnabled = false;
function enableThumbnails() {
  thumbnailsEnabled = true;
  renderListThumbnails();
  if (currentTexture) updatePreview(currentTexture);
}
```

```js
// shaders.html
function showHlsl() {
  const code = currentShader?.source_hlsl || "";
  renderCode(code || hlslHelpText);
}
function toggleAiOptimize() { document.body.classList.toggle('ai-optimize'); }
```

---

## Impact Analysis
- 数据层：新增 HLSL 反编译尝试，若工具不可用则回退空字符串。
- UI 层：减少默认渲染负担；Shader 页面更聚焦；新增按钮与 CSS 模式切换。

---

## Action Items

### Task 1: 支持 HLSL 反编译输出

**Files:**
- Modify `scripts/rdc_analyzer/extractors/shader_extractor.py:100-320, 380-420`
- Modify `scripts/rdc_analyzer/tests/test_shader_extractor.py:160-210`

**Step 1: Write the failing test**
```python
def test_pick_hlsl_target():
    from rdc_analyzer.extractors.shader_extractor import pick_hlsl_target
    targets = ["SPIR-V", "HLSL (SPIRV-Cross)", "DXBC"]
    assert pick_hlsl_target(targets) == "HLSL (SPIRV-Cross)"
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_shader_extractor.py -k pick_hlsl_target -v`
Expected: FAIL (ImportError or assertion)

**Step 3: Write minimal implementation**
```python
def pick_hlsl_target(targets):
    for t in targets:
        if "hlsl" in t.lower():
            return t
    return ""

def _get_hlsl_source(self, reflection, pipe_state):
    target = pick_hlsl_target(self.get_disassembly_targets())
    if not target or self.controller is None:
        return ""
    pipeline_id = self._get_pipeline_id(pipe_state)
    disasm = self.controller.DisassembleShader(pipeline_id, reflection, target)
    return str(disasm) if disasm else ""
```

**Step 4: Run tests to verify pass**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_shader_extractor.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/extractors/shader_extractor.py scripts/rdc_analyzer/tests/test_shader_extractor.py
git commit -m "feat(rdc-analyzer): extract HLSL source when available

- add HLSL target selection for DisassembleShader
- surface source_hlsl in ShaderInfo"
```

**Status:** ✅ Completed  
**Tests:** `py -3 -m pytest scripts/rdc_analyzer/tests/test_shader_extractor.py -v` (PASS)  
**Notes:** subagent任务执行无响应，改为主会话手动完成（已记录）  

---

### Task 2: 纹理缩略图按需显示

**Files:**
- Modify `scripts/rdc_analyzer/report_bundle_generator.py:500-560`
- Modify `scripts/rdc_analyzer/templates/textures.html:380-840`
- Modify `scripts/rdc_analyzer/tests/test_bundle_report_assets.py:1-120`

**Step 1: Write the failing test**
```python
def test_textures_has_enable_thumbnail_button(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_textures([{"id": "1", "name": "Tex", "width": 1, "height": 1, "thumbnail": "AAAA"}])
    html = Path(gen.generate_all()["textures"]).read_text(encoding="utf-8")
    assert "显示缩略图" in html
    assert "enableThumbnails" in html
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k enable_thumbnail -v`
Expected: FAIL

**Step 3: Write minimal implementation**
```python
# report_bundle_generator.py
texture_list_html += """
  <div class="texture-thumb">
    <div class='thumb-placeholder'>?</div>
  </div>
"""
```
```js
// textures.html
let thumbnailsEnabled = false;
function enableThumbnails() {
  if (thumbnailsEnabled) return;
  thumbnailsEnabled = true;
  document.getElementById('enableThumbsBtn').classList.add('active');
  renderListThumbnails();
  if (currentTexture) updatePreview(currentTexture);
}
```

**Step 4: Run tests to verify pass**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/report_bundle_generator.py scripts/rdc_analyzer/templates/textures.html scripts/rdc_analyzer/tests/test_bundle_report_assets.py
git commit -m "feat(rdc-analyzer): lazy-enable texture thumbnails

- add enable-thumbnails control to textures.html
- render placeholders before user action"
```

**Status:** ✅ Completed  
**Tests:** `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -v` (PASS)  

---

## /do Execution Notes (2026-02-03)

- CLI `py -3 -m rdc_analyzer analyze ...` 在 repo 根目录不可用（包路径不在 sys.path，且 CLI 无 `--ui-version`）。  
- 已改用 RenderDoc CLI 转换 + XML 报告生成流程：  
  - `renderdoccmd convert -f D:\backup\大远景.rdc -o D:\backup\dayuanjing.zip.xml -c zip.xml`  
  - `py -3 analyze_xml_report.py D:\backup\dayuanjing.zip.xml -o D:\backup\dayuanjing_report --ui-version bundle`  
- 结果：bundle 报告已生成；缩略图阶段提示 “No thumbnails generated (textures may not match)”，如需缩略图需继续排查 ZIP 资源匹配或改用 RenderDoc Python Shell 直连方式。  

---

## Change Request (2026-02-03)

**New Requirements:**
1. 支持 **headless 模式**（无需 GUI 点击）启动 RT 预览服务。
2. 纹理缩略图需 **在点击后按需生成**（点击按钮/选择纹理时发起请求）。
3. 用新 RDC 验证流程：`D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc`
4. 用户确认采用 **“服务挂载 + 按需生成”** 方案（浏览器不可直接调用本地 Python）。

**Updated Success Criteria:**
- textures.html 在点击“显示缩略图”后，若本地无 thumbnail，则自动向本地 RT 预览服务请求并渲染缩略图。
- RT 预览服务可在 headless 模式下启动（无 GUI 交互）。
- 使用新 RDC 走完「convert → analyze_xml_report(bundle) → 打开 textures.html」流程。

---

## Task 4: 纹理缩略图按需拉取（RT 预览服务）

**Files:**
- Modify `scripts/rdc_analyzer/templates/textures.html`
- Modify `scripts/rdc_analyzer/report_bundle_generator.py`
- Modify `scripts/rdc_analyzer/rt_preview_server.py`
- Modify `scripts/rdc_analyzer/tests/test_bundle_report_assets.py`

**Step 1: Write the failing test**
```python
def test_textures_has_rt_thumbnail_fetch(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_textures([{"id": "1", "name": "Tex", "width": 1, "height": 1}])
    html = Path(gen.generate_all()["textures"]).read_text(encoding="utf-8")
    assert "fetchTextureThumbnail" in html
    assert "RT_SERVER_BASE" in html
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k rt_thumbnail_fetch -v`  
Expected: FAIL

**Step 3: Write minimal implementation**
```js
// textures.html
const RT_SERVER_BASE = "http://127.0.0.1:8765";
async function fetchTextureThumbnail(texId) {
  const resp = await fetch(`${RT_SERVER_BASE}/api/texture/${texId}`);
  const data = await resp.json();
  if (data.success && data.image) {
    texture.thumbnail = data.image;
    renderListThumbnails();
    updateTexturePreview(texture);
  }
}
```
```py
# report_bundle_generator.py
# README 中新增纹理缩略图说明；start_rt_server 脚本优先走 python headless 模式
```
```py
# rt_preview_server.py
# 增加 --mock 解析（与生成脚本一致），并在帮助中说明 headless 方式
```

**Step 4: Run tests to verify pass**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -v`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/templates/textures.html \
        scripts/rdc_analyzer/report_bundle_generator.py \
        scripts/rdc_analyzer/rt_preview_server.py \
        scripts/rdc_analyzer/tests/test_bundle_report_assets.py
git commit -m "feat(rdc-analyzer): fetch texture thumbnails on demand

- add RT server fetch logic to textures.html
- document headless start in RT server scripts"
```

**Status:** ✅ Completed  
**Tests:** `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -v` (PASS)

---

## Task 5: Headless 模式 + 新 RDC 验证

**Files:**
- No code changes expected (verification only)

**Steps:**
1. 生成 zip.xml：
   ```powershell
   & "C:\Program Files\RenderDoc\renderdoccmd.exe" convert -f "D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc" -o "D:\backup\endfield.zip.xml" -c zip.xml
   ```
2. 生成 bundle：
   ```powershell
   py -3 analyze_xml_report.py "D:\backup\endfield.zip.xml" -o "D:\backup\endfield_report" --ui-version bundle
   ```
3. 启动 RT 预览服务（headless，优先 Python 模式）：
   ```powershell
   py -3 "D:\Code\git\renderdoc\scripts\rdc_analyzer\rt_preview_server.py" --rdc "D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc" --port 8765
   ```
   若 renderdoc Python 模块不可用，再尝试 qrenderdoc（需确认是否支持 headless 参数）。
4. 打开 `D:\backup\endfield_report\textures.html`，点击“显示缩略图”，确认缩略图能按需加载。

**Status:** ⏳ In Progress  
**Notes:** 已完成步骤 1-2（convert + bundle）。输出目录：`D:\backup\endfield_report`。  
XML 缩略图阶段提示 “No thumbnails generated (textures may not match)”；需依赖本地服务按需拉取。  
步骤 3-4 需手动启动服务并在浏览器点击验证。

---

## Task 6: 自动预载 N 张纹理缩略图（无手动点击）

**Files:**
- Modify `scripts/rdc_analyzer/templates/textures.html:590-760`
- Modify `scripts/rdc_analyzer/report_bundle_generator.py:470-560`
- Modify `scripts/rdc_analyzer/tests/test_bundle_report_assets.py:90-140`

**Step 1: Write the failing test**
```python
def test_textures_auto_preload_config(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_textures([{"id": "1", "name": "Tex", "width": 1, "height": 1}])
    html = Path(gen.generate_all()["textures"]).read_text(encoding="utf-8")
    assert "RT_PRELOAD_COUNT" in html
    assert "autoPreloadThumbnails" in html
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k auto_preload -v`  
Expected: FAIL

**Step 3: Write minimal implementation**
```js
// textures.html
const RT_PRELOAD_COUNT = {{RT_PRELOAD_COUNT}};
function autoPreloadThumbnails() {
  if (!thumbnailsEnabled) enableThumbnails();
  textureData.slice(0, RT_PRELOAD_COUNT).forEach(t => ensureTextureThumbnail(t));
}
window.addEventListener('load', autoPreloadThumbnails);
```
```py
# report_bundle_generator.py
# TEXTURE_DATA_JSON 旁添加 RT_PRELOAD_COUNT（默认 12，可配置）
```

**Step 4: Run test to verify pass**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -v`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/templates/textures.html \
        scripts/rdc_analyzer/report_bundle_generator.py \
        scripts/rdc_analyzer/tests/test_bundle_report_assets.py
git commit -m "feat(rdc-analyzer): auto preload texture thumbnails

- add configurable RT preload count
- auto fetch first N thumbnails on page load"
```

**Status:** ✅ Completed  
**Tests:** `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -v` (PASS)

---

## Task 7: 生成报告时自动启动服务（Option C）

**Files:**
- Modify `scripts/rdc_analyzer/analyze_xml_report.py:2100-2185`
- Modify `scripts/rdc_analyzer/tests/test_bundle_report_assets.py:120-170`
- Modify `scripts/rdc_analyzer/report_bundle_generator.py:1640-1700` (README 说明自动启动服务)

**Step 1: Write the failing test**
```python
def test_analyze_xml_report_has_auto_rt_flag():
    text = Path(__file__).resolve().parents[1] / "analyze_xml_report.py"
    content = text.read_text(encoding="utf-8")
    assert "--auto-start-rt-server" in content
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k auto_rt_flag -v`  
Expected: FAIL

**Step 3: Write minimal implementation**
```python
# analyze_xml_report.py
parser.add_argument("--auto-start-rt-server", action="store_true",
                    help="Start RT preview server after bundle generation")
parser.add_argument("--auto-open-textures", action="store_true",
                    help="Open textures.html after bundle generation")

if args.auto_start_rt_server:
    # start rt_preview_server.py as detached process
    subprocess.Popen([sys.executable, "rt_preview_server.py", "--rdc", rdc_path, "--port", "8765"])
```

**Step 4: Run test to verify pass**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -v`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/analyze_xml_report.py \
        scripts/rdc_analyzer/report_bundle_generator.py \
        scripts/rdc_analyzer/tests/test_bundle_report_assets.py
git commit -m "feat(rdc-analyzer): auto start RT server for bundle generation

- add --auto-start-rt-server flag
- optional auto-open textures.html"
```

**Status:** ✅ Completed  
**Tests:** `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -v` (PASS)

### Task 3: Shader 页面 HLSL 聚焦 + AI Shader 优化按钮

**Files:**
- Modify `scripts/rdc_analyzer/templates/shaders.html:500-760, 960-1015`
- Modify `scripts/rdc_analyzer/tests/test_bundle_report_assets.py:1-120`

**Step 1: Write the failing test**
```python
def test_shader_ui_hlsl_only(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_shaders([{"id": "1", "name": "S", "source_hlsl": "float4 main() : SV_Target { return 0; }"}])
    html = Path(gen.generate_all()["shaders"]).read_text(encoding="utf-8")
    assert "查看 HLSL 代码" in html
    assert "AI Shader 优化" in html
    assert "GLSL" not in html and "SPIR-V" not in html and "Disassembly" not in html
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k shader_ui_hlsl_only -v`
Expected: FAIL

**Step 3: Write minimal implementation**
```html
<!-- shaders.html toolbar -->
<button class="toolbar-btn" id="hlslBtn">查看 HLSL 代码</button>
<button class="toolbar-btn" id="aiOptimizeBtn">AI Shader 优化</button>
```
```js
function updateCodeViewer(shader) {
  const code = shader.source_hlsl || "";
  renderCode(code || hlslHelpText);
}
function toggleAiOptimize() {
  document.body.classList.toggle('ai-optimize');
}
```

**Step 4: Run tests to verify pass**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/templates/shaders.html scripts/rdc_analyzer/tests/test_bundle_report_assets.py
git commit -m "feat(rdc-analyzer): focus shader viewer on HLSL

- remove non-HLSL tabs
- add HLSL view and AI optimize controls"
```

**Status:** ✅ Completed  
**Tests:** `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -v` (PASS)  
