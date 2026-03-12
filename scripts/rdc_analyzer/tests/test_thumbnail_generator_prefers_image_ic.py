import base64
import io
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ThumbnailGenerator requires Pillow to generate PNG thumbnails.
pytest.importorskip("PIL")
from PIL import Image

from thumbnail_generator import ThumbnailGenerator


def _write_minimal_image_and_memory_ic_xml(path: Path) -> None:
    xml = """<root>
  <chunk name=\"vkCreateImage\">
    <ResourceId name=\"Image\" typename=\"VkImage\" width=\"8\">100</ResourceId>
    <struct name=\"CreateInfo\" typename=\"VkImageCreateInfo\">
      <enum name=\"imageType\" typename=\"VkImageType\" width=\"4\" string=\"VK_IMAGE_TYPE_2D\">1</enum>
      <enum name=\"format\" typename=\"VkFormat\" width=\"4\" string=\"VK_FORMAT_R8G8B8A8_UNORM\">37</enum>
      <struct name=\"extent\" typename=\"VkExtent3D\">
        <uint name=\"width\" typename=\"uint32_t\" width=\"4\">2</uint>
        <uint name=\"height\" typename=\"uint32_t\" width=\"4\">2</uint>
        <uint name=\"depth\" typename=\"uint32_t\" width=\"4\">1</uint>
      </struct>
    </struct>
  </chunk>

  <chunk name=\"vkBindImageMemory\">
    <ResourceId name=\"image\" typename=\"VkImage\" width=\"8\">100</ResourceId>
    <ResourceId name=\"memory\" typename=\"VkDeviceMemory\" width=\"8\">37</ResourceId>
    <uint name=\"memoryOffset\" typename=\"uint64_t\" width=\"8\">0</uint>
  </chunk>

  <chunk name=\"Internal::Initial Contents\">
    <enum name=\"type\" typename=\"VkResourceType\" width=\"4\" string=\"eResImage\">8</enum>
    <ResourceId name=\"id\" typename=\"VkImage\" width=\"8\">100</ResourceId>
    <bool name=\"IsSparse\" typename=\"bool\">false</bool>
    <uint name=\"ContentsSize\" typename=\"uint64_t\" width=\"8\">16</uint>
    <buffer name=\"Contents\" typename=\"Byte Buffer\" byteLength=\"16\">1</buffer>
  </chunk>

  <chunk name=\"Internal::Initial Contents\">
    <enum name=\"type\" typename=\"VkResourceType\" width=\"4\" string=\"eResDeviceMemory\">5</enum>
    <ResourceId name=\"id\" typename=\"VkDeviceMemory\" width=\"8\">37</ResourceId>
    <bool name=\"IsSparse\" typename=\"bool\">false</bool>
    <uint name=\"ContentsSize\" typename=\"uint64_t\" width=\"8\">16</uint>
    <buffer name=\"Contents\" typename=\"Byte Buffer\" byteLength=\"16\">2</buffer>
  </chunk>
</root>
"""
    path.write_text(xml, encoding="utf-8")


def test_thumbnail_generator_prefers_image_initial_contents_when_available(tmp_path: Path):
    xml_path = tmp_path / "mix.zip.xml"
    zip_path = tmp_path / "mix.zip"

    _write_minimal_image_and_memory_ic_xml(xml_path)

    # Image IC is RED, memory IC is GREEN. We should pick RED.
    red = bytes([255, 0, 0, 255] * 4)
    green = bytes([0, 255, 0, 255] * 4)

    import zipfile

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("000001", red)
        zf.writestr("000002", green)

    gen = ThumbnailGenerator(xml_path, zip_path)
    assert gen.parse() is True

    extractable = gen.get_extractable_textures()
    mapping = {img.resource_id: (img, binding, ic) for img, binding, ic in extractable}

    assert 100 in mapping

    img, binding, ic = mapping[100]

    # Ensure we selected per-image IC.
    assert ic.resource_id == 100
    assert "IMAGE" in (ic.resource_type or "").upper()
    assert binding.offset == 0

    thumb = gen.generate_thumbnail(img, binding, ic, max_size=128)
    assert thumb.success and thumb.base64_data.startswith("data:image/png;base64,")

    raw = base64.b64decode(thumb.base64_data.split(",", 1)[1])
    im = Image.open(io.BytesIO(raw)).convert("RGBA")
    assert im.getpixel((0, 0)) == (255, 0, 0, 255)
