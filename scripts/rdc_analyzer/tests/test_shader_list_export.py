import types

from rdc_analyzer.core.types import ShaderInfo
from rdc_analyzer.extractors.pipeline_sampler import PipelineSample, SamplingResult
from rdc_analyzer.main import AnalysisOptions, AnalysisPipeline


class FakeController:
    def __init__(self):
        self.events = []

    def SetFrameEvent(self, event_id, _):
        self.events.append(event_id)

    def GetPipelineState(self):
        return object()


class FakeExtractor:
    def __init__(self, shaders):
        self._shaders = shaders

    def extract_bound_shaders(self, _):
        result = types.SimpleNamespace()
        result.shaders = self._shaders
        result.unique_shader_count = len(self._shaders)
        result.by_stage = {}
        result.warnings = []
        return result


def test_build_shader_list_from_samples_populates_entries(monkeypatch):
    pipeline = AnalysisPipeline("dummy.rdc", AnalysisOptions())
    pipeline._controller = FakeController()
    pipeline._pipeline_sampling_result = SamplingResult(
        samples=[PipelineSample(event_id=10, name="draw", draw_type=None, snapshot=None)]
    )
    shaders = [
        ShaderInfo(
            resource_id="0x1",
            name="VS_main",
            type="VS",
            stage="Vertex",
            encoding="DXIL",
        ),
        ShaderInfo(
            resource_id="0x2",
            name="PS_main",
            type="PS",
            stage="Pixel",
            encoding="DXIL",
        ),
    ]

    def fake_factory(controller, rd_module):
        return FakeExtractor(shaders)

    monkeypatch.setattr(pipeline, "_create_shader_extractor", fake_factory)

    shader_list = pipeline._build_shader_list()
    assert len(shader_list) == 2
    assert shader_list[0]["resourceId"] == "0x1"


def test_build_shader_list_falls_back_to_sampled_ids(monkeypatch):
    pipeline = AnalysisPipeline("dummy.rdc", AnalysisOptions())
    pipeline._controller = FakeController()
    pipeline._pipeline_sampling_result = SamplingResult(
        samples=[
            PipelineSample(
                event_id=10,
                name="draw",
                draw_type=None,
                snapshot=None,
                vertex_shader_id=111,
                pixel_shader_id=222,
            )
        ]
    )

    def fake_factory(controller, rd_module):
        return FakeExtractor([])

    monkeypatch.setattr(pipeline, "_create_shader_extractor", fake_factory)

    shader_list = pipeline._build_shader_list()
    ids = {entry["resourceId"] for entry in shader_list}
    assert "111" in ids
    assert "222" in ids
