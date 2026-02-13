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


def _write_minimal_aliasing_xml(path: Path) -> None:
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

  <chunk name=\"vkCreateImage\">
    <ResourceId name=\"Image\" typename=\"VkImage\" width=\"8\">200</ResourceId>
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

  <chunk name=\"vkBindImageMemory\">
    <ResourceId name=\"image\" typename=\"VkImage\" width=\"8\">200</ResourceId>
    <ResourceId name=\"memory\" typename=\"VkDeviceMemory\" width=\"8\">37</ResourceId>
    <uint name=\"memoryOffset\" typename=\"uint64_t\" width=\"8\">16</uint>
  </chunk>

  <chunk name=\"Internal::Initial Contents\">
    <enum name=\"type\" typename=\"VkResourceType\" width=\"4\" string=\"eResDeviceMemory\">5</enum>
    <ResourceId name=\"id\" typename=\"VkDeviceMemory\" width=\"8\">37</ResourceId>
    <bool name=\"IsSparse\" typename=\"bool\">false</bool>
    <uint name=\"ContentsSize\" typename=\"uint64_t\" width=\"8\">32</uint>
    <buffer name=\"Contents\" typename=\"Byte Buffer\" byteLength=\"32\">5</buffer>
  </chunk>
</root>
"""
    path.write_text(xml, encoding="utf-8")


def test_thumbnail_generator_respects_memory_offset_for_aliasing(tmp_path: Path):
    xml_path = tmp_path / "alias.zip.xml"
    zip_path = tmp_path / "alias.zip"

    _write_minimal_aliasing_xml(xml_path)

    # Two 2x2 RGBA8 images in one memory blob.
    red = bytes([255, 0, 0, 255] * 4)
    green = bytes([0, 255, 0, 255] * 4)
    blob = red + green
    assert len(blob) == 32

    import zipfile

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("000005", blob)

    gen = ThumbnailGenerator(xml_path, zip_path)
    assert gen.parse() is True

    extractable = gen.get_extractable_textures()
    mapping = {img.resource_id: (img, binding, ic) for img, binding, ic in extractable}

    assert 100 in mapping
    assert 200 in mapping

    img_a, bind_a, ic_a = mapping[100]
    img_b, bind_b, ic_b = mapping[200]

    thumb_a = gen.generate_thumbnail(img_a, bind_a, ic_a, max_size=128)
    thumb_b = gen.generate_thumbnail(img_b, bind_b, ic_b, max_size=128)

    assert thumb_a.success and thumb_a.base64_data.startswith("data:image/png;base64,")
    assert thumb_b.success and thumb_b.base64_data.startswith("data:image/png;base64,")

    def first_pixel(b64: str):
        raw = base64.b64decode(b64.split(",", 1)[1])
        im = Image.open(io.BytesIO(raw)).convert("RGBA")
        return im.getpixel((0, 0))

    assert first_pixel(thumb_a.base64_data) == (255, 0, 0, 255)
    assert first_pixel(thumb_b.base64_data) == (0, 255, 0, 255)
