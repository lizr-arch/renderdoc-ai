#!/usr/bin/env python3
"""Pipeline thresholds injection tests."""


def test_pipeline_injects_thresholds(monkeypatch):
    """AnalysisPipeline should always provide thresholds to AnalysisContext."""
    from rdc_analyzer import pipeline as pl
    from rdc_analyzer.config import get_thresholds

    parsed = pl.ParsedData(api="D3D11", file_path="fake.rdc")

    monkeypatch.setattr(pl.AnalysisPipeline, "_parse", lambda self: parsed)

    captured = {}

    class DummyContext:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def to_result(self, issues):
            return {"issues": issues}

    monkeypatch.setattr(pl, "AnalysisContext", DummyContext)
    monkeypatch.setattr(pl.AnalysisPipeline, "_analyze", lambda self, context: None)
    monkeypatch.setattr(pl.AnalysisPipeline, "_check_rules", lambda self, context: [])

    pipeline = pl.AnalysisPipeline("fake.rdc", platform="mobile", use_api=False)
    pipeline.run()

    assert captured.get("thresholds") == get_thresholds("mobile")
