#!/usr/bin/env python3
"""One-click RDC -> bundle report pipeline.

Steps:
1) Convert RDC -> ZIP+XML when possible (fallback to plain XML)
2) Generate bundle report via xml_to_bundle.py
3) Optionally run headless UI smoke checks
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from parsers.rdc_loader import find_renderdoccmd


def downscale_exported_textures(texture_dir: Path, max_size: int, verbose: bool) -> int:
    """Downscale exported texture PNGs to max_size (largest edge).

    Returns number of files resized.
    """
    textures_json = texture_dir / "textures.json"
    files: List[str] = []
    if textures_json.exists():
        try:
            payload = json.loads(textures_json.read_text(encoding="utf-8"))
            entries = payload.get("textures", []) if isinstance(payload, dict) else []
            for entry in entries:
                fname = entry.get("file") if isinstance(entry, dict) else None
                if fname:
                    files.append(fname)
        except Exception as exc:
            if verbose:
                print(f"[WARN] Failed to parse textures.json for downscale: {exc}")

    if not files:
        files = [p.name for p in texture_dir.glob("*.png")]

    try:
        from PIL import Image
    except Exception as exc:
        if verbose:
            print(f"[WARN] PIL not available for downscale: {exc}")
        return 0

    resized = 0
    for fname in files:
        path = texture_dir / fname
        if not path.exists():
            continue
        try:
            with Image.open(path) as img:
                width, height = img.size
                max_dim = max(width, height)
                if max_dim <= max_size:
                    continue
                scale = max_size / float(max_dim)
                new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
                img = img.resize(new_size, Image.LANCZOS)
                img.save(path, format="PNG")
                resized += 1
        except Exception as exc:
            if verbose:
                print(f"[WARN] Downscale failed for {path}: {exc}")
            continue

    return resized


def build_convert_command(
    renderdoccmd: str,
    rdc_path: Path,
    output_path: Path,
    convert_format: str,
) -> List[str]:
    return [
        renderdoccmd,
        "convert",
        "-f",
        str(rdc_path),
        "-o",
        str(output_path),
        "-c",
        convert_format,
    ]


def build_bundle_command(
    python_exec: str,
    xml_to_bundle_script: Path,
    xml_path: Path,
    output_dir: Path,
    rdc_path: Path,
    zip_path: Optional[Path],
    texture_dir: Optional[Path],
    spirv_cross: Optional[str],
    verbose: bool,
) -> List[str]:
    cmd = [
        python_exec,
        str(xml_to_bundle_script),
        str(xml_path),
        "-o",
        str(output_dir),
        "--rdc",
        str(rdc_path),
    ]
    if zip_path is not None:
        cmd.extend(["--zip", str(zip_path)])
    if texture_dir is not None:
        cmd.extend(["--texture-dir", str(texture_dir)])
    if spirv_cross:
        cmd.extend(["--spirv-cross", spirv_cross])
    if verbose:
        cmd.append("-v")
    return cmd


def default_output_dir_for_rdc(rdc_path: Path) -> Path:
    return rdc_path.parent / f"{rdc_path.stem}_report"


def default_intermediate_paths(output_dir: Path, rdc_path: Path) -> Tuple[Path, Path]:
    zipxml_path = output_dir / f"{rdc_path.stem}.zip.xml"
    xml_path = output_dir / f"{rdc_path.stem}.xml"
    return zipxml_path, xml_path


def resolve_requested_xml_paths(requested_path: Optional[str], output_dir: Path, rdc_path: Path) -> Tuple[Path, Path]:
    if not requested_path:
        return default_intermediate_paths(output_dir, rdc_path)

    explicit = Path(requested_path).resolve()
    if explicit.name.endswith(".zip.xml"):
        base = explicit.name[: -len(".zip.xml")]
        return explicit, explicit.with_name(base + ".xml")

    return explicit.with_suffix(".zip.xml"), explicit


def resolve_zip_sidecar(xml_path: Path, rdc_path: Path) -> Optional[Path]:
    candidates: List[Path] = []

    if xml_path.name.endswith(".zip.xml"):
        base = xml_path.name[: -len(".zip.xml")]
        candidates.append(xml_path.with_name(base + ".zip"))

    candidates.append(xml_path.with_suffix(".zip"))
    candidates.append(rdc_path.with_suffix(".zip"))

    seen = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists():
            return candidate

    return None


def run_checked(cmd: Sequence[str], stage: str) -> None:
    print(f"[RUN] {stage}: {' '.join(cmd)}")
    subprocess.run(list(cmd), check=True)

def build_export_command(
    renderdoccmd: str,
    rdc_path: Path,
    output_dir: Path,
    max_size: int,
) -> List[str]:
    return [
        renderdoccmd,
        "export",
        "--out",
        str(output_dir),
        "--format",
        "png",
        "--metadata",
        "--max-size",
        str(max_size),
        str(rdc_path),
    ]


def build_thumbnail_audit_command(
    python_exec: str,
    audit_script: Path,
    report_dir: Path,
    texture_dir: Path,
    sentinel_count: int,
    verbose: bool,
) -> List[str]:
    cmd = [
        python_exec,
        str(audit_script),
        "--report-dir",
        str(report_dir),
        "--texture-dir",
        str(texture_dir),
        "--count",
        str(int(sentinel_count)),
    ]
    if verbose:
        cmd.append("-v")
    return cmd

def resolve_export_renderdoccmd_candidates(renderdoccmd: str, script_dir: Path) -> List[str]:
    repo_candidate = script_dir.parent.parent / "x64" / "Development" / "renderdoccmd.exe"
    candidates = [renderdoccmd]
    if repo_candidate.exists():
        candidates.append(str(repo_candidate))

    deduped: List[str] = []
    seen = set()
    for candidate in candidates:
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def try_export_textures(
    renderdoccmd: str,
    script_dir: Path,
    rdc_path: Path,
    export_dir: Path,
    max_size: int,
    force: bool,
) -> Optional[Path]:
    textures_json = export_dir / "textures.json"
    if textures_json.exists() and not force:
        print(f"[INFO] Reuse exported textures: {textures_json}")
        return export_dir

    export_dir.mkdir(parents=True, exist_ok=True)
    for idx, candidate in enumerate(resolve_export_renderdoccmd_candidates(renderdoccmd, script_dir), start=1):
        try:
            run_checked(
                build_export_command(candidate, rdc_path, export_dir, max_size),
                f"export-textures[{idx}]",
            )
        except subprocess.CalledProcessError as exc:
            print(f"[WARN] renderdoccmd export failed ({candidate}, code {exc.returncode})")
            continue

        if textures_json.exists():
            return export_dir

    return export_dir if textures_json.exists() else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="One-click RDC -> bundle report (xml_to_bundle + optional UI smoke)",
    )
    parser.add_argument("rdc_file", help="Path to input .rdc file")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output report directory (default: <rdc_stem>_report)",
    )
    parser.add_argument(
        "--xml-path",
        default=None,
        help="Intermediate XML path (default: <output>/<rdc_stem>.zip.xml)",
    )
    parser.add_argument(
        "--renderdoccmd",
        default=None,
        help="Path to renderdoccmd executable (auto-detect when omitted)",
    )
    parser.add_argument(
        "--spirv-cross",
        default=None,
        help="Optional path to spirv-cross executable",
    )
    parser.add_argument(
        "--no-export-all",
        action="store_true",
        help="Skip initial ZIP+XML conversion attempt",
    )
    parser.add_argument(
        "--no-zipxml",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--no-smoke",
        action="store_true",
        help="Skip headless UI smoke verification",
    )
    parser.add_argument(
        "--no-texture-export",
        action="store_true",
        help="Skip renderdoccmd export texture thumbnails",
    )
    parser.add_argument(
        "--texture-max-size",
        type=int,
        default=512,
        help="Max texture export dimension in pixels (default: 512)",
    )
    parser.add_argument(
        "--force-texture-export",
        action="store_true",
        help="Force rerun renderdoccmd export even when textures.json exists",
    )
    parser.add_argument(
        "--no-thumbnail-audit",
        action="store_true",
        help="Skip thumbnail sentinel audit generation",
    )
    parser.add_argument(
        "--thumbnail-sentinel-count",
        type=int,
        default=10,
        help="Sentinel thumbnail count for audit sheet (default: 10)",
    )
    parser.add_argument(
        "--smoke-out",
        default=None,
        help="UI smoke artifact directory",
    )
    parser.add_argument(
        "--smoke-viewports",
        default="1366x768,1536x864,1920x1080",
        help="Viewport list passed to ui_headless_smoke.py",
    )
    parser.add_argument(
        "--smoke-no-fail",
        action="store_true",
        help="Pass --no-fail to UI smoke script",
    )
    parser.add_argument(
        "--smoke-no-screenshots",
        action="store_true",
        help="Pass --no-screenshots to UI smoke script",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose mode",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    script_dir = Path(__file__).resolve().parent
    xml_to_bundle_script = script_dir / "xml_to_bundle.py"
    smoke_script = script_dir / "tools" / "ui_headless_smoke.py"
    thumbnail_audit_script = script_dir / "thumbnail_audit.py"

    rdc_path = Path(args.rdc_file).resolve()
    if not rdc_path.exists():
        print(f"[ERROR] RDC file not found: {rdc_path}")
        return 2

    output_dir = Path(args.output).resolve() if args.output else default_output_dir_for_rdc(rdc_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    zipxml_path, xml_path = resolve_requested_xml_paths(args.xml_path, output_dir, rdc_path)

    renderdoccmd = args.renderdoccmd or find_renderdoccmd()
    if not renderdoccmd:
        print("[ERROR] renderdoccmd not found. Set --renderdoccmd or configure PATH/RENDERDOC_CMD.")
        return 2

    convert_errors: List[str] = []
    produced_xml_path: Optional[Path] = None
    skip_zipxml = args.no_export_all or args.no_zipxml

    if not skip_zipxml:
        try:
            run_checked(
                build_convert_command(renderdoccmd, rdc_path, zipxml_path, convert_format="zip.xml"),
                "convert-zipxml",
            )
            produced_xml_path = zipxml_path
        except subprocess.CalledProcessError as exc:
            convert_errors.append(f"zip.xml convert failed with code {exc.returncode}")
            print("[WARN] renderdoccmd convert -c zip.xml failed, retrying with -c xml...")

    if produced_xml_path is None:
        try:
            run_checked(
                build_convert_command(renderdoccmd, rdc_path, xml_path, convert_format="xml"),
                "convert-xml",
            )
            produced_xml_path = xml_path
        except subprocess.CalledProcessError as exc:
            convert_errors.append(f"xml convert failed with code {exc.returncode}")
            print("[ERROR] convert failed:")
            for msg in convert_errors:
                print(f"  - {msg}")
            return 3

    if not produced_xml_path.exists():
        print(f"[ERROR] XML conversion did not produce output: {produced_xml_path}")
        return 3

    zip_path = resolve_zip_sidecar(produced_xml_path, rdc_path)
    if zip_path is None:
        print("[INFO] ZIP sidecar not found; thumbnails may be placeholders")
    else:
        print(f"[INFO] ZIP sidecar: {zip_path}")

    texture_dir: Optional[Path] = None
    if args.no_texture_export:
        print("[INFO] Texture export disabled by --no-texture-export")
    else:
        export_dir = output_dir / "textures"
        texture_dir = try_export_textures(
            renderdoccmd=renderdoccmd,
            script_dir=script_dir,
            rdc_path=rdc_path,
            export_dir=export_dir,
            max_size=args.texture_max_size,
            force=args.force_texture_export,
        )
        if texture_dir is None:
            print("[WARN] Texture export unavailable; fallback to ZIP thumbnail generation")
        else:
            print(f"[INFO] Texture export metadata: {texture_dir / 'textures.json'}")
            resized = downscale_exported_textures(texture_dir, args.texture_max_size, args.verbose)
            if resized:
                print(f"[INFO] Downscaled {resized} textures to max {args.texture_max_size}px")

    bundle_cmd = build_bundle_command(
        python_exec=sys.executable,
        xml_to_bundle_script=xml_to_bundle_script,
        xml_path=produced_xml_path,
        output_dir=output_dir,
        rdc_path=rdc_path,
        zip_path=zip_path,
        texture_dir=texture_dir,
        spirv_cross=args.spirv_cross,
        verbose=args.verbose,
    )

    try:
        run_checked(bundle_cmd, "xml-to-bundle")
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] xml_to_bundle failed with code {exc.returncode}")
        return 4

    if args.no_thumbnail_audit:
        print("[INFO] Thumbnail audit disabled by --no-thumbnail-audit")
    elif texture_dir is None:
        print("[WARN] Thumbnail audit skipped: texture export unavailable")
    elif not thumbnail_audit_script.exists():
        print(f"[WARN] Thumbnail audit script not found: {thumbnail_audit_script}")
    else:
        audit_cmd = build_thumbnail_audit_command(
            python_exec=sys.executable,
            audit_script=thumbnail_audit_script,
            report_dir=output_dir,
            texture_dir=texture_dir,
            sentinel_count=args.thumbnail_sentinel_count,
            verbose=args.verbose,
        )
        try:
            run_checked(audit_cmd, "thumbnail-audit")
            print(f"[INFO] Thumbnail audit: {output_dir / 'thumbnail_sentinel.html'}")
        except subprocess.CalledProcessError as exc:
            print(f"[WARN] Thumbnail audit failed with code {exc.returncode}; continue")

    if not args.no_smoke:
        if args.smoke_out:
            smoke_out = Path(args.smoke_out).resolve()
        else:
            stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
            smoke_out = Path("docs/analysis/codex_rdc_analyzer/ui_smoke_artifacts") / f"{rdc_path.stem}_{stamp}"

        smoke_cmd = [
            sys.executable,
            str(smoke_script),
            "--report-dir",
            str(output_dir),
            "--out-dir",
            str(smoke_out),
            "--viewports",
            args.smoke_viewports,
        ]
        if args.smoke_no_fail:
            smoke_cmd.append("--no-fail")
        if args.smoke_no_screenshots:
            smoke_cmd.append("--no-screenshots")

        try:
            run_checked(smoke_cmd, "ui-headless-smoke")
        except subprocess.CalledProcessError as exc:
            print(f"[ERROR] UI smoke failed with code {exc.returncode}")
            return 5

    print("=" * 64)
    print("[DONE] One-click bundle pipeline finished")
    print(f"  Report: {output_dir}")
    print(f"  Open: file:///{output_dir / 'index.html'}")
    print(f"  XML: {produced_xml_path}")
    if zip_path is not None:
        print(f"  ZIP: {zip_path}")
    sentinel_html = output_dir / "thumbnail_sentinel.html"
    validation_json = output_dir / "thumbnail_validation.json"
    if sentinel_html.exists():
        print(f"  Thumbnail Sentinel: file:///{sentinel_html}")
    if validation_json.exists():
        print(f"  Thumbnail Validation JSON: {validation_json}")
    print("=" * 64)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
