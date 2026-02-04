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
**Follow-up:** Added `--rdc-path` to allow auto-start RT server with explicit RDC when XML stem does not match capture name.

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

**Status:** ✅ Completed  
**Notes:** 已完成步骤 1-4（convert + bundle + auto-start RT + auto-open）。  
执行命令：  
`py -3 scripts/rdc_analyzer/analyze_xml_report.py D:\backup\endfield.zip.xml -o D:\backup\endfield_report --ui-version bundle --auto-start-rt-server --auto-open-textures --rdc-path D:\backup\EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc`  
RT 预览服务已自动启动并打开 textures.html；XML 缩略图阶段仍提示 “No thumbnails generated (textures may not match)”，后续通过 RT 服务按需拉取缩略图。

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

---

## Change Request (2026-02-03, v2)

**New Requirements:**
1. Shader 页面搜索框无效：必须能按名称搜索（data-* 缺失导致）。
2. Shader 左侧列表需要稳定滚动条（当前可视区不足无法滑动）。
3. Shader 页面“查看 HLSL 代码 / AI Shader 优化”布局需要 **专业 + 仪表盘风格**。
4. 纹理页面“显示缩略图”按钮需要更明显；自动预载需要**可见反馈**（进度/状态）。

**Updated Success Criteria:**
- Shader 搜索框输入名称时，列表可过滤出匹配项。
- 左侧 Shader 列表在小窗口下出现滚动条并可滚动。
- HLSL/AI 按钮有明确主次层级与更优视觉排布（专业 + 仪表盘风格）。
- 纹理页面自动预载在 UI 上可见“预载中/完成/失败”状态。

---

## Task 8: 修复 Shader 搜索（data-* 与类名对齐）

**Files:**
- Modify `scripts/rdc_analyzer/report_bundle_generator.py:640-670`
- Modify `scripts/rdc_analyzer/tests/test_bundle_report_assets.py:1-220`

**Step 1: Write the failing test**
```python
def test_shader_list_has_search_attrs(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_shaders([{"id": "1", "name": "MainVS", "type": "vertex", "usedBy": [{"eid": 1}]}])
    html = Path(gen.generate_all()["shaders"]).read_text(encoding="utf-8")
    assert 'data-name="MainVS"' in html
    assert 'data-type="vertex"' in html
    assert 'shader-item-name' in html
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k shader_list_has_search_attrs -v`  
Expected: FAIL (missing data-name/data-type/class)

**Step 3: Write minimal implementation**
```python
# report_bundle_generator.py
usage_count = len(shader.get("usedBy", []) or [])
has_issue = bool(shader.get("issues") or shader.get("suggestions"))

shader_list_html += f'''
  <div class="shader-item"
       data-id="{shader_id}"
       data-name="{name}"
       data-type="{shader_type.lower()}"
       data-usage="{usage_count}"
       data-has-issue="{str(has_issue).lower()}"
       onclick="selectShader('{shader_id}')">
    <span class="shader-item-type">{icon}</span>
    <div class="shader-item-info">
      <div class="shader-item-name">{name}</div>
      <div class="shader-item-meta">
        <span class="shader-meta-tag {shader_type.lower()}">{shader_type}</span>
        {mali_badge}
      </div>
    </div>
  </div>'''
```

**Step 4: Run tests to verify pass**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k shader_list_has_search_attrs -v`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/report_bundle_generator.py scripts/rdc_analyzer/tests/test_bundle_report_assets.py
git commit -m "fix(rdc-analyzer): make shader search data-driven"
```

**Status:** ✅ Completed  
**Tests:** `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k shader_list_has_search_attrs -v` (PASS)

---

## Task 9: Shader 左侧滚动与专业/仪表盘布局

**Files:**
- Modify `scripts/rdc_analyzer/templates/shaders.html:1-120, 518-540`
- Modify `scripts/rdc_analyzer/templates/common.css:100-160`
- Modify `scripts/rdc_analyzer/tests/test_bundle_report_assets.py:1-240`

**Step 1: Write the failing test**
```python
def test_shader_toolbar_primary_secondary(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_shaders([{"id": "1", "name": "S", "source_hlsl": "float4 main() : SV_Target { return 0; }"}])
    html = Path(gen.generate_all()["shaders"]).read_text(encoding="utf-8")
    assert "toolbar-btn primary" in html
    assert "toolbar-btn secondary" in html
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k shader_toolbar_primary_secondary -v`  
Expected: FAIL (classes missing)

**Step 3: Write minimal implementation**
```html
<!-- shaders.html toolbar -->
<div class="toolbar-group">
  <button class="toolbar-btn primary" id="hlslBtn" title="查看 HLSL 代码">查看 HLSL 代码</button>
  <button class="toolbar-btn secondary" id="aiOptimizeBtn" title="AI Shader 优化">AI Shader 优化</button>
</div>
```
```css
/* shaders.html (or common.css) */
.toolbar-btn.primary {
  background: linear-gradient(180deg, #2f81f7, #1f6feb);
  color: #fff;
  border: 1px solid #1f6feb;
}
.toolbar-btn.secondary {
  background: rgba(255,255,255,0.06);
  color: var(--text-primary);
  border: 1px solid var(--border);
}
.panel-left .shader-list { min-height: 0; }
.app-container.fixed { height: 100vh; }
```
```html
<!-- shaders.html root container -->
<div class="app-container fixed">
```

**Step 4: Run tests to verify pass**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k shader_toolbar_primary_secondary -v`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/templates/shaders.html scripts/rdc_analyzer/templates/common.css scripts/rdc_analyzer/tests/test_bundle_report_assets.py
git commit -m "style(rdc-analyzer): polish shader toolbar and scrolling"
```

**Status:** ✅ Completed  
**Tests:** `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k shader_toolbar_primary_secondary -v` (PASS)

---

## Task 10: 纹理页按钮强化 + 自动预载可见反馈

**Files:**
- Modify `scripts/rdc_analyzer/templates/textures.html:180-260, 392-410, 600-690`
- Modify `scripts/rdc_analyzer/tests/test_bundle_report_assets.py:1-260`

**Step 1: Write the failing test**
```python
def test_textures_has_thumb_status(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_textures([{"id": "1", "name": "Tex", "width": 1, "height": 1}])
    html = Path(gen.generate_all()["textures"]).read_text(encoding="utf-8")
    assert "thumbStatus" in html
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k thumb_status -v`  
Expected: FAIL

**Step 3: Write minimal implementation**
```html
<div class="thumb-toggle-row">
  <button class="filter-chip thumb-toggle primary" id="enableThumbsBtn" onclick="enableThumbnails()">加载缩略图</button>
  <span class="thumb-status" id="thumbStatus">自动预载：待开始</span>
</div>
```
```js
let preloadTotal = 0;
let preloadDone = 0;
function updateThumbStatus(text) {
  const el = document.getElementById('thumbStatus');
  if (el) el.textContent = text;
}
function autoPreloadThumbnails() {
  if (!textureData || !textureData.length) return;
  enableThumbnails();
  const count = Math.max(0, Math.min(RT_PRELOAD_COUNT, textureData.length));
  preloadTotal = count;
  preloadDone = 0;
  updateThumbStatus(`自动预载：${preloadDone}/${preloadTotal}`);
  for (let i = 0; i < count; i++) {
    textureData[i]._preloadTracked = true;
    ensureTextureThumbnail(textureData[i]);
  }
}
// 在 ensureTextureThumbnail 的 finally 中：
if (texture._preloadTracked) {
  preloadDone += 1;
  updateThumbStatus(`自动预载：${preloadDone}/${preloadTotal}`);
}
```
```css
.thumb-toggle.primary { background: var(--accent-blue); color: #fff; }
.thumb-status { font-size: 10px; color: var(--text-muted); }
```

**Step 4: Run tests to verify pass**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k thumb_status -v`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/templates/textures.html scripts/rdc_analyzer/tests/test_bundle_report_assets.py
git commit -m "feat(rdc-analyzer): show thumbnail preload status"
```

**Status:** ✅ Completed  
**Tests:** `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k thumb_status -v` (PASS)

---

## Change Request (2026-02-03, v3)

**New Requirements:**
1. **改为全量纹理加载（B 方案）**：生成报告时导出 PNG 并在页面直接引用，不再使用 RT 动态加载。
2. **纹理页面移除“动态加载按钮”**，改为“已全部加载”提示（或加载中状态）。
3. Shader 页 HLSL 按钮视觉错误/丑，需要**专业 + 仪表盘风格**重排。
4. 仍需保持左侧列表可滚动，搜索可用。

**Updated Success Criteria:**
- textures.html 打开即可看到缩略图（不依赖 RT 服务）。
- 页面中不再出现“加载缩略图/预载”按钮。
- Shader 工具栏主次按钮视觉清晰，无遮挡/错位。
- 左侧 Shader 列表可滚动、搜索可过滤。

---

## Task 11: 生成 bundle 时全量导出纹理 PNG（B 方案）

**Files:**
- Modify `scripts/rdc_analyzer/analyze_xml_report.py:1900-2200`
- Add helper in `scripts/rdc_analyzer/analyze_xml_report.py`
- Modify `scripts/rdc_analyzer/tests/test_bundle_report_assets.py:1-260`

**Step 1: Write the failing test**
```python
def test_map_exported_textures_sets_thumbnail(tmp_path):
    from analyze_xml_report import map_exported_textures

    textures = [
        {"resource_id": "123", "width": 4, "height": 4},
        {"resource_id": "456", "width": 8, "height": 8},
    ]
    export_dir = tmp_path / "textures"
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "tex_123_4x4.png").write_bytes(b"PNG")

    map_exported_textures(textures, export_dir)
    assert textures[0]["thumbnail"] == "textures/tex_123_4x4.png"
    assert "thumbnail" not in textures[1]
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k map_exported_textures -v`  
Expected: FAIL (function missing)

**Step 3: Write minimal implementation**
```python
# analyze_xml_report.py
def map_exported_textures(textures, export_dir):
    for tex in textures:
        rid = tex.get("resource_id") or tex.get("id")
        w = tex.get("width")
        h = tex.get("height")
        if not rid or not w or not h:
            continue
        filename = f"tex_{rid}_{w}x{h}.png"
        if (export_dir / filename).exists():
            tex["thumbnail"] = f"textures/{filename}"

# in run_analysis (bundle branch)
export_dir = Path(output_path).with_suffix("") / "textures"
export_dir.mkdir(parents=True, exist_ok=True)
from exporters.texture_batch_exporter import create_export_engine
engine = create_export_engine(xml_path)
summary = engine.export_all(output_dir=export_dir, save_png=True, save_bin=False)
engine.close()
map_exported_textures(textures, export_dir)
```

**Step 4: Run tests to verify pass**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k map_exported_textures -v`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/analyze_xml_report.py scripts/rdc_analyzer/tests/test_bundle_report_assets.py
git commit -m "feat(rdc-analyzer): export full textures for bundle"
```

**Status:** ✅ Completed  
**Tests:** `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -v` (PASS)  
**Notes:** 支持 id/resource_id 映射并回退匹配；bundle 生成时输出 textures/ PNG 并回写缩略图路径。  

---

## Task 12: 纹理页面改为“全量显示”（移除动态按钮）

**Files:**
- Modify `scripts/rdc_analyzer/templates/textures.html:380-740`
- Modify `scripts/rdc_analyzer/tests/test_bundle_report_assets.py:1-280`

**Step 1: Write the failing test**
```python
def test_textures_no_dynamic_buttons(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_textures([{"id": "1", "name": "Tex", "width": 1, "height": 1, "thumbnail": "textures/tex_1_1x1.png"}])
    html = Path(gen.generate_all()["textures"]).read_text(encoding="utf-8")
    assert "加载缩略图" not in html
    assert "autoPreloadThumbnails" not in html
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k no_dynamic_buttons -v`  
Expected: FAIL

**Step 3: Write minimal implementation**
```html
<!-- textures.html: 移除按钮与预载状态 -->
<!-- 删除 enableThumbsBtn / thumbStatus -->
```
```js
// textures.html: 删除 enableThumbnails/autoPreloadThumbnails/RT fetch 逻辑
// renderListThumbnails() 默认渲染图片（只要 texture.thumbnail 存在）
```

**Step 4: Run tests to verify pass**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k no_dynamic_buttons -v`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/templates/textures.html scripts/rdc_analyzer/tests/test_bundle_report_assets.py
git commit -m "refactor(rdc-analyzer): show all textures by default"
```

**Status:** ✅ Completed  
**Tests:** `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -v` (PASS)  
**Notes:** 移除动态加载/预载按钮与 RT fetch；列表与预览默认使用导出 PNG。  

---

## Task 13: Shader 工具栏重排（专业 + 仪表盘风格）

**Files:**
- Modify `scripts/rdc_analyzer/templates/shaders.html:520-560`
- Modify `scripts/rdc_analyzer/templates/common.css:100-180`
- Modify `scripts/rdc_analyzer/tests/test_bundle_report_assets.py:1-300`

**Step 1: Write the failing test**
```python
def test_shader_toolbar_layout_tokens(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")
    gen.set_shaders([{"id": "1", "name": "S", "source_hlsl": "float4 main() : SV_Target { return 0; }"}])
    html = Path(gen.generate_all()["shaders"]).read_text(encoding="utf-8")
    assert "toolbar-btn primary" in html
    assert "toolbar-btn ghost" in html
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k shader_toolbar_layout_tokens -v`  
Expected: FAIL

**Step 3: Write minimal implementation**
```html
<div class="toolbar-group">
  <button class="toolbar-btn primary" id="hlslBtn">HLSL 源码</button>
  <button class="toolbar-btn ghost" id="aiOptimizeBtn">AI Shader 优化</button>
</div>
```
```css
.toolbar-btn.ghost {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-secondary);
}
```

**Step 4: Run tests to verify pass**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k shader_toolbar_layout_tokens -v`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/templates/shaders.html scripts/rdc_analyzer/templates/common.css scripts/rdc_analyzer/tests/test_bundle_report_assets.py
git commit -m "style(rdc-analyzer): refine shader toolbar layout"
```

**Status:** ✅ Completed  
**Tests:** `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -v` (PASS)  
**Notes:** 主次按钮放入 primary-actions 组并强化样式（CSS 在 shaders.html 内）。  

---

## Change Request (2026-02-04, v4)

**New Requirements:**
1. 修复 bundle 生成时的 `[Texture Export] Warning: attempted relative import beyond top-level package`，确保全量 PNG 导出可用。
2. 继续保持无需 GUI / 手动步骤，生成时直接输出可用 PNG。

**Updated Success Criteria:**
- `analyze_xml_report.py --ui-version bundle` 执行时不再出现相对导入越级错误。
- `output_dir/textures/` 生成 PNG，textures.html 可直接引用。

---

## Task 14: 修复 Texture Export 导入链（避免相对导入越级）

**Files:**
- Modify `scripts/rdc_analyzer/analyze_xml_report.py:1860-1895`
- Modify `scripts/rdc_analyzer/tests/test_bundle_report_assets.py:1-220`
- Reference `scripts/rdc_analyzer/batch_export_textures.py:41-70` (fallback import pattern)

**Step 1: Write the failing test**
```python
def test_load_texture_exporter_fallback(tmp_path):
    from analyze_xml_report import load_texture_exporter
    create_export_engine = load_texture_exporter(force_fallback=True)
    assert callable(create_export_engine)
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k load_texture_exporter_fallback -v`  
Expected: FAIL (helper missing)

**Step 3: Write minimal implementation**
```python
# analyze_xml_report.py
def load_texture_exporter(force_fallback: bool = False):
    if not force_fallback:
        try:
            from exporters.texture_batch_exporter import create_export_engine
            return create_export_engine
        except Exception:
            pass
    export_path = Path(__file__).parent / "exporters" / "texture_batch_exporter.py"
    spec = importlib.util.spec_from_file_location("rdc_texture_batch_exporter", export_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.create_export_engine
```

**Step 4: Run test to verify pass**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k load_texture_exporter_fallback -v`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/analyze_xml_report.py scripts/rdc_analyzer/tests/test_bundle_report_assets.py
git commit -m "fix(rdc-analyzer): robust texture exporter import"
```

**Status:** ✅ Completed  
**Tests:** `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k load_texture_exporter_fallback -v` (PASS)  
**Notes:** 已补充 importlib 回退路径并提交（commit: a6b613331）。  

---

## Task 15: 使用新导入路径执行全量 PNG 导出

**Files:**
- Modify `scripts/rdc_analyzer/analyze_xml_report.py:1860-1895` (use helper)

**Step 1: Write the failing test**
```python
def test_analyze_xml_report_uses_texture_export_helper():
    from pathlib import Path
    script_path = Path(__file__).resolve().parents[1] / "analyze_xml_report.py"
    content = script_path.read_text(encoding="utf-8")
    assert "load_texture_exporter" in content
```

**Step 2: Run test to verify it fails**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k uses_texture_export_helper -v`  
Expected: FAIL (not wired)

**Step 3: Write minimal implementation**
```python
# analyze_xml_report.py (bundle branch)
create_export_engine = load_texture_exporter()
engine = create_export_engine(xml_path)
```

**Step 4: Run test to verify pass**
Run: `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k uses_texture_export_helper -v`  
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/rdc_analyzer/analyze_xml_report.py scripts/rdc_analyzer/tests/test_bundle_report_assets.py
git commit -m "fix(rdc-analyzer): wire texture exporter helper"
```

**Status:** ✅ Completed  
**Tests:** `py -3 -m pytest scripts/rdc_analyzer/tests/test_bundle_report_assets.py -k uses_texture_export_helper -v` (PASS)  
**Notes:** bundle 分支改为 `load_texture_exporter()`，避免直接相对导入。  

---

## Task 16: 生成 Endfield 报告并验证 PNG 产出

**Files:**
- None (run command only)

**Step 1: Run bundle generation**
Run: `py -3 scripts/rdc_analyzer/analyze_xml_report.py "D:\backup\endfield.zip.xml" -o "D:\backup\endfield_report" --ui-version bundle`  
Expected: log includes `[Texture Export] Done:` and **no** relative import warning

**Step 2: Verify output**
Check: `D:\backup\endfield_report\textures\` contains PNGs  
Expected: PNG count > 0

**Status:** ⏳ Running  
**Tests:** `py -3 scripts/rdc_analyzer/analyze_xml_report.py "D:\backup\endfield.zip.xml" -o "D:\backup\endfield_report" --ui-version bundle` (running)  
**Notes:** 已观察到 `D:\backup\endfield_report\textures\` 产出 PNG，但生成进程仍在运行，等待最终日志与 HTML 更新时间。  
