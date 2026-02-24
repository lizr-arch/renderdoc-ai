import json
from pathlib import Path
from typing import Union

from rdc_analyzer.bridge.analysis_to_bundle import analysis_to_bundle
from rdc_analyzer.report_bundle_generator import ReportBundleGenerator


def generate_report_from_analysis(
    analysis_path: Union[str, Path],
    output_dir: Union[str, Path],
    capture_name: str,
) -> None:
    analysis_path = Path(analysis_path)
    output_dir = Path(output_dir)
    data = json.loads(analysis_path.read_text(encoding="utf-8"))
    bundle = analysis_to_bundle(data)

    generator = ReportBundleGenerator(output_dir, capture_name)
    generator.set_events(bundle.events)
    generator.set_textures(bundle.textures)
    generator.set_shaders(bundle.shaders, mali_data=None, usage_map=bundle.shader_usage)
    generator.stats.update(bundle.stats)
    generator.generate_all()
