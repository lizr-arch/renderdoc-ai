import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple


_STAGE_ENTRY_DEFAULTS = {
    "vs": "main_vs",
    "ps": "main_ps",
    "cs": "main_cs",
    "gs": "main_gs",
    "hs": "main_hs",
    "ds": "main_ds",
}


def _normalise_path(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    clean = str(value).strip().strip('"')
    if not clean:
        return None
    return str(Path(clean))


def _first_existing_path(paths: Iterable[Optional[str]]) -> str:
    for path in paths:
        if not path:
            continue
        candidate = Path(path)
        if candidate.is_file():
            return str(candidate)
    return ""


def _latest_windows_sdk_tool(tool_name: str) -> str:
    base_env = os.environ.get("PROGRAMFILES(X86)") or os.environ.get("ProgramFiles(x86)")
    if not base_env:
        return ""

    base_dir = Path(base_env) / "Windows Kits" / "10" / "bin"
    if not base_dir.exists():
        return ""

    version_dirs = sorted(
        [path for path in base_dir.iterdir() if path.is_dir()],
        key=lambda path: path.name,
        reverse=True,
    )

    for version_dir in version_dirs:
        for arch in ("x64", "x86", "arm64"):
            candidate = version_dir / arch / tool_name
            if candidate.is_file():
                return str(candidate)

    return ""


def resolve_dxbc_tool_paths(
    fxc_cli_path: Optional[str] = None,
    dxc_cli_path: Optional[str] = None,
) -> Dict[str, str]:
    fxc_path = _first_existing_path(
        [
            _normalise_path(fxc_cli_path),
            _normalise_path(os.environ.get("RDC_FXC")),
            _normalise_path(os.environ.get("FXC_PATH")),
            shutil.which("fxc"),
            shutil.which("fxc.exe"),
            _latest_windows_sdk_tool("fxc.exe"),
        ]
    )

    dxc_path = _first_existing_path(
        [
            _normalise_path(dxc_cli_path),
            _normalise_path(os.environ.get("RDC_DXC")),
            _normalise_path(os.environ.get("DXC_PATH")),
            shutil.which("dxc"),
            shutil.which("dxc.exe"),
            _latest_windows_sdk_tool("dxc.exe"),
        ]
    )

    return {"fxc": fxc_path, "dxc": dxc_path}


def _run_tool(command):
    proc = subprocess.run(command, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        stdout = (proc.stdout or "").strip()
        message = stderr or stdout or f"tool failed: {' '.join(command)}"
        raise RuntimeError(message)
    return proc


def dumpbin_dxbc_with_fxc(fxc_path: str, dxbc_bytes: bytes) -> str:
    if not fxc_path:
        raise RuntimeError("fxc path is empty")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxbc") as handle:
        handle.write(dxbc_bytes)
        input_path = Path(handle.name)

    asm_path = input_path.with_suffix(input_path.suffix + ".asm")

    try:
        _run_tool([
            fxc_path,
            "/dumpbin",
            "/nologo",
            "/Fc",
            str(asm_path),
            str(input_path),
        ])

        if not asm_path.exists():
            raise RuntimeError("fxc dumpbin did not generate asm output")

        return asm_path.read_text(encoding="utf-8", errors="replace")
    finally:
        try:
            input_path.unlink()
        except OSError:
            pass
        try:
            asm_path.unlink()
        except OSError:
            pass


def dumpbin_dxil_with_dxc(dxc_path: str, dxil_bytes: bytes) -> str:
    if not dxc_path:
        raise RuntimeError("dxc path is empty")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxil") as handle:
        handle.write(dxil_bytes)
        input_path = Path(handle.name)

    try:
        proc = _run_tool([dxc_path, "-dumpbin", str(input_path)])
        output = (proc.stdout or "").strip()
        if not output:
            output = (proc.stderr or "").strip()
        if not output:
            raise RuntimeError("dxc dumpbin produced empty output")
        return output + "\n"
    finally:
        try:
            input_path.unlink()
        except OSError:
            pass


def _count_decl_lines(disassembly: str, prefix: str) -> int:
    found = set()
    for raw_line in disassembly.splitlines():
        line = raw_line.strip().lower()
        if line.startswith(prefix):
            found.add(line)
    return len(found)


def _build_resources_section(cbuffer_count: int, texture_count: int, sampler_count: int) -> list[str]:
    lines = []

    for index in range(max(1, min(cbuffer_count, 4))):
        lines.append(f"cbuffer AutoCB{index} : register(b{index})")
        lines.append("{")
        lines.append(f"  float4 AutoCB{index}_Data[16];")
        lines.append("};")
        lines.append("")

    for index in range(min(texture_count, 8)):
        lines.append(f"Texture2D AutoTex{index} : register(t{index});")

    for index in range(min(sampler_count, 8)):
        lines.append(f"SamplerState AutoSmp{index} : register(s{index});")

    if texture_count or sampler_count:
        lines.append("")

    return lines


def _build_stage_body(stage: str, entry_name: str, texture_count: int, sampler_count: int) -> list[str]:
    stage = (stage or "").lower()

    if stage == "vs":
        return [
            "struct AutoVSInput",
            "{",
            "  float4 position : POSITION;",
            "};",
            "",
            "struct AutoVSOutput",
            "{",
            "  float4 position : SV_POSITION;",
            "};",
            "",
            f"AutoVSOutput {entry_name}(AutoVSInput input)",
            "{",
            "  AutoVSOutput output;",
            "  output.position = input.position;",
            "  return output;",
            "}",
        ]

    if stage == "cs":
        return [
            "[numthreads(8, 8, 1)]",
            f"void {entry_name}(uint3 dispatchThreadId : SV_DispatchThreadID)",
            "{",
            "  uint _unused = dispatchThreadId.x;",
            "  (void)_unused;",
            "}",
        ]

    if stage == "gs":
        return [
            "struct AutoGSInput",
            "{",
            "  float4 position : SV_POSITION;",
            "};",
            "",
            "struct AutoGSOutput",
            "{",
            "  float4 position : SV_POSITION;",
            "};",
            "",
            "[maxvertexcount(3)]",
            f"void {entry_name}(triangle AutoGSInput input[3], inout TriangleStream<AutoGSOutput> stream)",
            "{",
            "  AutoGSOutput output;",
            "  output.position = input[0].position;",
            "  stream.Append(output);",
            "}",
        ]

    if stage in {"hs", "ds"}:
        return [
            f"// Stage '{stage}' requires patch-domain specific signatures.",
            f"float4 {entry_name}() : SV_Target0",
            "{",
            "  return float4(1.0, 1.0, 1.0, 1.0);",
            "}",
        ]

    sample_line = "float4 color = float4(1.0, 1.0, 1.0, 1.0);"
    if texture_count > 0 and sampler_count > 0:
        sample_line = "float4 color = AutoTex0.Sample(AutoSmp0, float2(0.5, 0.5));"

    return [
        "struct AutoPSInput",
        "{",
        "  float4 position : SV_POSITION;",
        "};",
        "",
        f"float4 {entry_name}(AutoPSInput input) : SV_Target0",
        "{",
        f"  {sample_line}",
        "  return color;",
        "}",
    ]


def generate_hlsl_scaffold(
    disassembly: str,
    stage: str,
    entry_name: str = "",
    source_label: str = "",
) -> Tuple[str, Dict[str, int]]:
    cbuffer_count = _count_decl_lines(disassembly, "dcl_constantbuffer")
    texture_count = _count_decl_lines(disassembly, "dcl_resource")
    sampler_count = _count_decl_lines(disassembly, "dcl_sampler")
    input_count = _count_decl_lines(disassembly, "dcl_input")
    output_count = _count_decl_lines(disassembly, "dcl_output")

    entry = entry_name or _STAGE_ENTRY_DEFAULTS.get(stage, f"main_{stage or 'shader'}")

    lines = [
        "// Auto-generated HLSL scaffold",
        "// NOTE: DXBC/DXIL bytecode cannot be losslessly decompiled to original HLSL.",
        "// This file is a structured reconstruction for downstream material/shader assembly.",
        f"// Source: {source_label}",
        f"// Stage: {stage}",
        f"// Entry: {entry}",
        f"// DeclCounts: cbuffer={cbuffer_count}, texture={texture_count}, sampler={sampler_count}, in={input_count}, out={output_count}",
        "",
    ]

    lines.extend(_build_resources_section(cbuffer_count, texture_count, sampler_count))
    lines.extend(_build_stage_body(stage, entry, texture_count, sampler_count))

    snippet = []
    for raw_line in disassembly.splitlines()[:200]:
        snippet.append(raw_line.replace("*/", "* /"))

    lines.extend(
        [
            "",
            "/* ---- dumpbin snippet (first 200 lines) ----",
            *snippet,
            "---- end dumpbin snippet ---- */",
            "",
        ]
    )

    analysis = {
        "cbuffer_count": cbuffer_count,
        "texture_count": texture_count,
        "sampler_count": sampler_count,
        "input_count": input_count,
        "output_count": output_count,
    }

    return "\n".join(lines), analysis
