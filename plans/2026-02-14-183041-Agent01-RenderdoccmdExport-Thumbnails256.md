# Plan: renderdoccmd export PNG 缩略图接入 Bundle（默认 max-size=256）

> Created: 2026-02-14 18:30:41
> Agent: Agent01
> Stage: /plan（read-only）
> User decision: 缩略图只用于展示，默认 --max-size 256，优先'快 + 可读'。

## Scope / Goal

- 在 scripts/rdc_analyzer/one_click_bundle_report.py 一键流程中自动执行 renderdoccmd export。
- 将导出的 textures/textures.json + PNG 文件接入 bundle textures 页，缩略图用文件路径引用（不再 base64 内嵌）。
- 用户验收：打开 textures.html 至少能看到 10 张明显可读缩略图；不需要任何按钮/服务/手动环节。
- 回退策略：export 不可用或 replay 失败时，自动回退 ZIP+XML ThumbnailGenerator（base64，最多 N 张）。

## Non-goals（本轮不做）

- 不做'服务挂载 + 按需生成'缩略图（后续任务）。
- 不做 shaders.html 的 HLSL-only / AI Shader 优化 UI 重做（后续任务）。
- 不修改 renderdoc/3rdparty/，不触发编译。

## Assumptions

- 仓库内存在可用 x64/Development/renderdoccmd.exe（本机已确认存在）。
- renderdoccmd export 可能需要 GPU replay（或 software render），因此必须允许失败并回退。
## Navigation Evidence（Required）

### Codemap Queries（<=3）

1) codemap 'renderdoccmd export' -Num 20 -Repo renderdoc
2) codemap 'zip.xml' -Num 50 -Repo renderdoc
3) codemap 'ThumbnailGenerator' -Num 20

### Candidate Hits（>=3）

- [renderdoc] renderdoccmd/renderdoccmd.cpp:656
  - struct ExportCommand : public Command
- [renderdoc] renderdoccmd/renderdoccmd.cpp:681
  - parser.add('metadata', ...)  # textures.json
- [renderdoc] scripts/rdc_analyzer/one_click_bundle_report.py:213
  - build_convert_command(..., convert_format='zip.xml')
- [renderdoc] scripts/rdc_analyzer/xml_to_bundle.py:360
  - def generate_thumbnails_from_zip(...)
- [renderdoc] scripts/rdc_analyzer/report_bundle_generator.py:239
  - _normalize_thumbnail: 支持 .png 路径（可直接引用 textures/xxx.png）

说明：codemap 对部分 scripts/rdc_analyzer/*.py 文件名检索偶发 No matches（索引覆盖不全）；脚本行号以 Serena/本地读取定位为准。

### Follow Up（1-2 Hits）

- scripts/rdc_analyzer/one_click_bundle_report.py：插入 export 步骤 + 传 --texture-dir 给 xml_to_bundle
- scripts/rdc_analyzer/xml_to_bundle.py：新增 --texture-dir，并把 thumbnail 设为 textures/<file>.png（成功后跳过 ZIP base64 生成）

### Next Step

- OpenGrok: http://127.0.0.1:8080/source/xref/renderdoc/renderdoccmd/renderdoccmd.cpp#656
- Serena: find_file(one_click_bundle_report.py), search_for_pattern('generate_thumbnails_from_zip', scripts/rdc_analyzer/xml_to_bundle.py)

## File List（行号锚点）

- scripts/rdc_analyzer/one_click_bundle_report.py:117（parse_args）
- scripts/rdc_analyzer/one_click_bundle_report.py:187（main）
- scripts/rdc_analyzer/xml_to_bundle.py:267（parse_args）
- scripts/rdc_analyzer/xml_to_bundle.py:360（generate_thumbnails_from_zip）
- scripts/rdc_analyzer/xml_to_bundle.py:687（当前缩略图生成调用点）
- scripts/rdc_analyzer/report_bundle_generator.py:239（thumbnail 规范化逻辑）
- scripts/rdc_analyzer/tests/test_one_click_bundle_report.py:42（bundle cmd 单测）
- 新增：scripts/rdc_analyzer/tests/test_xml_to_bundle_export_thumbnails.py

## Design

### Output Layout（新增 textures/ 作为缩略图资产目录）

`
<report_dir>/
  index.html
  events.html
  textures.html
  shaders.html
  recommendations.html
  textures_data.json
  textures/
    textures.json
    *.png
`

### Thumbnail Precedence（优先级）

1) 若 xml_to_bundle.py 收到 --texture-dir <dir>，且 <dir>/textures.json 存在：
   - thumbnail 写相对路径：textures/<file>.png（避免 base64）
   - 若成功映射 >=1 张：默认跳过 ZIP base64 缩略图生成（更快、更小）
2) 否则：
   - 回退到现有 --zip + ThumbnailGenerator（base64，受 --max-thumbnails 限制）

## Implementation Checklist（2-5 分钟粒度）

- [x] 1) xml_to_bundle.py: 新增参数 --texture-dir
  - 位置：scripts/rdc_analyzer/xml_to_bundle.py:267 (parse_args)

`python
parser.add_argument(
    '--texture-dir',
    dest='texture_dir',
    default=None,
    help=(
        'Directory produced by renderdoccmd export (contains textures.json + PNG). '
        'When provided, thumbnails are mapped to PNG paths and ZIP-based base64 thumbnails are skipped by default.'
    ),
)
`

- [x] 2) xml_to_bundle.py: 实现 textures.json -> thumbnail 映射函数（纯文件映射，无 GPU 依赖）
  - 新增函数建议放在 generate_thumbnails_from_zip 附近

`python
def apply_exported_texture_thumbnails(
    textures: List[Dict],
    texture_dir: Path,
    output_dir: Path,
    verbose: bool = False,
) -> int:
    import json

    textures_json = texture_dir / 'textures.json'
    if not textures_json.exists():
        if verbose:
            print(f'      [INFO] export textures.json not found: {textures_json}')
        return 0

    try:
        payload = json.loads(textures_json.read_text(encoding='utf-8'))
        entries = payload.get('textures', []) if isinstance(payload, dict) else []
    except Exception as e:
        if verbose:
            print(f'      [WARN] Failed to read textures.json: {e}')
        return 0

    # Prefer relative URLs for portability; fallback to file URI when outside report dir
    try:
        rel_prefix = texture_dir.resolve().relative_to(output_dir.resolve()).as_posix()
    except Exception:
        rel_prefix = texture_dir.resolve().as_uri()

    id_to_file: Dict[str, str] = {}
    for e in entries:
        if not isinstance(e, dict):
            continue
        tid = e.get('id')
        fname = e.get('file')
        if tid is None or not fname:
            continue
        if (texture_dir / fname).exists():
            id_to_file[str(tid)] = fname

    updated = 0
    for tex in textures:
        if not isinstance(tex, dict):
            continue
        tex_id = str(tex.get('id', ''))
        fname = id_to_file.get(tex_id)
        if not fname:
            continue
        tex['thumbnail'] = f'{rel_prefix}/{fname}'
        updated += 1

    if verbose:
        print(f'      [INFO] Mapped {updated} thumbnails from renderdoccmd export')
    return updated
`

- [x] 3) xml_to_bundle.py: 主流程接入映射并控制回退
  - 位置：scripts/rdc_analyzer/xml_to_bundle.py:687 (当前调用 generate_thumbnails_from_zip)
  - 目标：当 export 映射成功 >= 1 时，默认不再生成 ZIP base64 缩略图（更快、更小）

`python
exported_count = 0
if args.texture_dir:
    exported_count = apply_exported_texture_thumbnails(
        textures=textures,
        texture_dir=Path(args.texture_dir),
        output_dir=output_dir,
        verbose=args.verbose,
    )

if exported_count > 0:
    thumbnail_count = exported_count
else:
    thumbnail_count = generate_thumbnails_from_zip(
        xml_path=xml_path,
        zip_path=zip_path,
        textures=textures,
        max_count=args.max_thumbnails,
        max_size=args.thumbnail_size,
        verbose=args.verbose,
    )
`

- [x] 4) one_click_bundle_report.py: 增加 texture export CLI 参数（默认启用，max-size=256）
  - 位置：scripts/rdc_analyzer/one_click_bundle_report.py:117 (parse_args)

`python
parser.add_argument('--no-texture-export', action='store_true', help='Skip renderdoccmd export for texture thumbnails')
parser.add_argument('--texture-max-size', type=int, default=256, help='Max exported texture dimension (default: 256)')
parser.add_argument('--force-texture-export', action='store_true', help='Re-run export even if textures/textures.json exists')
`

- [x] 5) one_click_bundle_report.py: 解析 export 能力并选择 renderdoccmd
  - 目标：系统安装版可能没有 export；优先使用支持 export 的二进制（优先 args.renderdoccmd，其次 repo x64/Development）

`python
def supports_export(renderdoccmd: str) -> bool:
    try:
        res = subprocess.run([renderdoccmd, 'export', '--help'], capture_output=True, text=True)
    except Exception:
        return False
    return res.returncode == 0

def resolve_export_renderdoccmd(convert_renderdoccmd: str, script_dir: Path) -> Optional[str]:
    if convert_renderdoccmd and supports_export(convert_renderdoccmd):
        return convert_renderdoccmd

    repo_root = script_dir.parent.parent
    candidate = repo_root / 'x64' / 'Development' / 'renderdoccmd.exe'
    if candidate.exists() and supports_export(str(candidate)):
        return str(candidate)

    return None
`

- [x] 6) one_click_bundle_report.py: 插入 export 步骤 + 传 --texture-dir
  - 插入位置：resolve_zip_sidecar 之后，build_bundle_command 之前（当前约 242-258 行之间）
  - 约定：输出目录固定为 <report_dir>/textures

`python
export_dir = output_dir / 'textures'
textures_json = export_dir / 'textures.json'
texture_dir_arg: Optional[Path] = None

if not args.no_texture_export:
    export_renderdoccmd = resolve_export_renderdoccmd(renderdoccmd, script_dir)
    if export_renderdoccmd:
        if args.force_texture_export or not textures_json.exists():
            export_cmd = [
                export_renderdoccmd,
                'export',
                str(rdc_path),
                '--out',
                str(export_dir),
                '--format',
                'png',
                '--metadata',
                '--max-size',
                str(args.texture_max_size),
            ]
            try:
                run_checked(export_cmd, 'export-textures')
            except subprocess.CalledProcessError as exc:
                print(f'[WARN] export failed (code {exc.returncode}); fallback to ZIP thumbnails')

        if textures_json.exists():
            texture_dir_arg = export_dir
    else:
        print('[INFO] renderdoccmd export not supported; fallback to ZIP thumbnails')

# Pass to xml_to_bundle
bundle_cmd = build_bundle_command(..., texture_dir=texture_dir_arg, ...)
`

- [x] 7) one_click_bundle_report.py: build_bundle_command 增加可选 texture_dir

`python
def build_bundle_command(..., texture_dir: Optional[Path], ...) -> List[str]:
    cmd = [python_exec, str(xml_to_bundle_script), str(xml_path), '-o', str(output_dir), '--rdc', str(rdc_path)]
    ...
    if texture_dir is not None:
        cmd.extend(['--texture-dir', str(texture_dir)])
    return cmd
`

- [x] 8) Tests
  - 更新 scripts/rdc_analyzer/tests/test_one_click_bundle_report.py：覆盖 build_bundle_command 新增 --texture-dir
  - 新增 scripts/rdc_analyzer/tests/test_xml_to_bundle_export_thumbnails.py：对 apply_exported_texture_thumbnails 做 tmpdir 单测

## Verification / Acceptance（/do 执行；此处仅记录命令与预期）

### Unit Tests

`ash
py -3 -m pytest scripts/rdc_analyzer/tests/test_one_click_bundle_report.py -v --tb=short
py -3 -m pytest scripts/rdc_analyzer/tests/test_xml_to_bundle_export_thumbnails.py -v --tb=short
`

预期：exit code 0。

### Integration Test（Endfield）

建议开发阶段先关掉 smoke，加快迭代（不影响最终用户打开 HTML 做视觉验收）：

`ash
py -3 scripts/rdc_analyzer/one_click_bundle_report.py D:/backup/EndfieldTBeta2_2025.12.18_14.36_frame42231.rdc ^
  -o D:/backup/endfield_report ^
  --renderdoccmd D:/Code/git/renderdoc/x64/Development/renderdoccmd.exe ^
  --texture-max-size 256 ^
  --no-smoke
`

预期产物：
- D:/backup/endfield_report/textures/textures.json 存在
- D:/backup/endfield_report/textures/*.png 数量 > 10
- 打开 file:///D:/backup/endfield_report/textures.html：缩略图可见且可读（抽查前 10 张）
- textures_data.json 中 thumbnail 字段多数为路径形式（例如以 textures/ 开头），而不是 data:image base64

## Impact Analysis

- 优点
  - 缩略图可读性显著提升（走 replay 导出，更接近 RenderDoc GUI）。
  - HTML 体积显著变小（不再内嵌大段 base64）。
  - 加载更快：浏览器按需读取 PNG 文件。
- 代价
  - export 依赖 replay 环境（GPU 或 software render），可能失败；因此必须 fallback。
  - 输出目录会生成较多 PNG 文件（max-size=256 控制体积）。

## Risks / Blockers

- Local replay not supported / 驱动不兼容：export 失败，脚本必须不中断并回退 ZIP 缩略图。
- renderdoccmd 版本差异：系统安装版可能没有 export；必须检测 export --help 支持并优先 repo 版本。
- 路径形式：写入 thumbnail 的 URL 需要是 posix 风格（建议用 Path.as_posix 或 file URI）。

## Rollback Strategy

- export 不可用或失败：保持现状（ZIP base64 缩略图）。
- 若用户反馈导出耗时或文件太多：后续再做按需生成 + 后台服务（本轮明确不做）。

---

> Ready for approval: 如你确认按此方案实施，请回复 /do。

## /do Log

- Completed: xml_to_bundle.py add --texture-dir and exported PNG thumbnail mapping
- Completed: one_click_bundle_report.py auto run renderdoccmd export and pass --texture-dir
- Tests: py -3 -m pytest scripts/rdc_analyzer/tests/test_one_click_bundle_report.py -v --tb=short (pass)
- Tests: py -3 -m pytest scripts/rdc_analyzer/tests/test_xml_to_bundle_export_thumbnails.py -v --tb=short (pass)
- Integration: Endfield capture generated D:/backup/endfield_report with path thumbnails 154/154 at size 256
