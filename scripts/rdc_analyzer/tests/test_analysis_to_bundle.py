from rdc_analyzer.bridge.analysis_to_bundle import analysis_to_bundle


def test_analysis_to_bundle_minimal():
    analysis = {
        "draw_calls": [
            {
                "event_id": 7,
                "name": "Draw",
                "draw_type": "DRAW",
                "vertex_count": 3,
                "instance_count": 1,
                "pipeline_state": {
                    "vs_bindings": {"shader_resource_id": 100, "shader_name": "VS_Main"},
                    "ps_bindings": {"shader_resource_id": 200, "shader_name": "PS_Main"},
                },
            }
        ]
    }
    bundle = analysis_to_bundle(analysis)
    assert len(bundle.events) == 1
    assert bundle.events[0]["eid"] == 7
    assert bundle.events[0]["type"] == "draw"
    assert len(bundle.shaders) == 2
