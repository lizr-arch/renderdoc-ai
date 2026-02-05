import inspect

from rdc_analyzer.exporters import texture_batch_exporter as tbe


def _make_tex(resource_id: int, width: int, height: int) -> tbe.TextureInfo:
    return tbe.TextureInfo(
        resource_id=resource_id,
        width=width,
        height=height,
        format="VK_FORMAT_R8G8B8A8_UNORM",
    )


def test_select_textures_for_export_limits_and_order():
    assert hasattr(
        tbe,
        "select_textures_for_export",
    ), "select_textures_for_export() is missing"

    textures = [
        _make_tex(10, 256, 256),  # area 65536
        _make_tex(5, 128, 512),   # area 65536 (tie, smaller id wins)
        _make_tex(7, 64, 64),     # area 4096
        _make_tex(2, 512, 512),   # area 262144 (largest)
        _make_tex(9, 1, 1024),    # area 1024
    ]

    selected = tbe.select_textures_for_export(textures, limit=3)
    assert [t.resource_id for t in selected] == [2, 5, 10]


def test_export_all_accepts_limit_parameter():
    params = inspect.signature(tbe.BaseExportEngine.export_all).parameters
    assert "limit" in params
