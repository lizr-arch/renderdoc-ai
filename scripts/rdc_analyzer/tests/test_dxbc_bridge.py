import os
import sys

TEST_DIR = os.path.dirname(__file__)
EXPORTERS_DIR = os.path.join(TEST_DIR, "..", "exporters")
sys.path.insert(0, os.path.abspath(EXPORTERS_DIR))

import dxbc_bridge as bridge


def test_resolve_dxbc_tool_paths_prefers_cli(monkeypatch, tmp_path):
    monkeypatch.setattr(bridge.shutil, "which", lambda _: None)
    monkeypatch.setattr(bridge, "_latest_windows_sdk_tool", lambda _: "")

    fxc = tmp_path / "fxc.exe"
    dxc = tmp_path / "dxc.exe"
    fxc.write_bytes(b"MZ")
    dxc.write_bytes(b"MZ")

    result = bridge.resolve_dxbc_tool_paths(
        fxc_cli_path=str(fxc),
        dxc_cli_path=str(dxc),
    )

    assert result["fxc"] == str(fxc)
    assert result["dxc"] == str(dxc)


def test_resolve_dxbc_tool_paths_uses_sdk_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("RDC_FXC", raising=False)
    monkeypatch.delenv("RDC_DXC", raising=False)
    monkeypatch.delenv("FXC_PATH", raising=False)
    monkeypatch.delenv("DXC_PATH", raising=False)
    monkeypatch.setattr(bridge.shutil, "which", lambda _: None)

    fxc = tmp_path / "sdk_fxc.exe"
    dxc = tmp_path / "sdk_dxc.exe"
    fxc.write_bytes(b"MZ")
    dxc.write_bytes(b"MZ")

    def fake_latest(name: str) -> str:
        if name == "fxc.exe":
            return str(fxc)
        if name == "dxc.exe":
            return str(dxc)
        return ""

    monkeypatch.setattr(bridge, "_latest_windows_sdk_tool", fake_latest)

    result = bridge.resolve_dxbc_tool_paths()
    assert result == {"fxc": str(fxc), "dxc": str(dxc)}


def test_generate_hlsl_scaffold_extracts_decl_counts():
    disasm = """
ps_5_0
dcl_globalFlags refactoringAllowed
dcl_input v0.xyzw
dcl_output o0.xyzw
dcl_constantbuffer cb0[8], immediateIndexed
dcl_resource_texture2d (float,float,float,float) t0
dcl_sampler s0, mode_default
sample r0.xyzw, v0.xyxx, t0.xyzw, s0
ret
"""

    text, analysis = bridge.generate_hlsl_scaffold(
        disassembly=disasm,
        stage="ps",
        entry_name="main_ps",
        source_label="intermediate/shaders/ps.bin",
    )

    assert analysis["cbuffer_count"] == 1
    assert analysis["texture_count"] == 1
    assert analysis["sampler_count"] == 1
    assert analysis["input_count"] == 1
    assert analysis["output_count"] == 1

    assert "Auto-generated HLSL scaffold" in text
    assert "Texture2D AutoTex0" in text
    assert "SamplerState AutoSmp0" in text
    assert "float4 main_ps" in text
    assert "dumpbin snippet" in text
