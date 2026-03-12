import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import xml_to_bundle as xb


def test_apply_exported_texture_thumbnails_maps_relative_urls(tmp_path: Path):
    output_dir = tmp_path / "report"
    output_dir.mkdir(parents=True)

    texture_dir = output_dir / "textures"
    texture_dir.mkdir(parents=True)

    # Create a couple of fake exported files.
    spaced = "My Tex.png"
    (texture_dir / spaced).write_text("", encoding="utf-8")
    (texture_dir / "B.png").write_text("", encoding="utf-8")

    payload = {
        "textures": [
            {"id": 1, "file": spaced},
            {"id": "2", "file": "B.png"},
        ]
    }
    (texture_dir / "textures.json").write_text(json.dumps(payload), encoding="utf-8")

    textures = [
        {"id": "1", "thumbnail": ""},
        {"id": 2, "thumbnail": ""},
        {"id": 3, "thumbnail": ""},
    ]

    updated = xb.apply_exported_texture_thumbnails(
        textures=textures,
        texture_dir=texture_dir,
        output_dir=output_dir,
        verbose=True,
    )

    assert updated == 2
    assert textures[0]["thumbnail"] == "textures/My%20Tex.png"
    assert textures[1]["thumbnail"] == "textures/B.png"
    assert textures[2]["thumbnail"] == ""
