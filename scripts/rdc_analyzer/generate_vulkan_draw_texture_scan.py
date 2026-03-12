import argparse
import json
from pathlib import Path

from parsers.zipxml_event_parser import scan_vulkan_draw_texture_events


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate Vulkan draw texture scan JSON from RenderDoc zip.xml"
    )
    parser.add_argument("--xml", required=True, help="Path to capture zip.xml")
    parser.add_argument("--out", required=True, help="Output scan JSON path")
    parser.add_argument(
        "--preview-limit",
        required=False,
        type=int,
        default=8,
        help="Max texture records in textures_preview for each event",
    )
    parser.add_argument(
        "--min-textures",
        required=False,
        type=int,
        default=0,
        help="Only keep draws with texture_count >= this value",
    )
    args = parser.parse_args(argv)

    payload = scan_vulkan_draw_texture_events(
        xml_path=str(args.xml),
        preview_limit=max(0, int(args.preview_limit)),
        min_textures=max(0, int(args.min_textures)),
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    summary = payload.get("summary", {})
    print(
        "[OK] scan generated: "
        f"total={summary.get('total_draw_events', 0)} "
        f"textured={summary.get('textured_draw_events', 0)} "
        f"mesh_compatible={summary.get('mesh_compatible_events', 0)} "
        f"out={out_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
