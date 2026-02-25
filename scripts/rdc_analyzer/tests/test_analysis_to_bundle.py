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


def test_analysis_to_bundle_normalizes_ids():
    analysis = {
        "textures": [
            {"resourceId": 11, "name": "TexA"},
            {"id": 22, "name": "TexB"},
        ],
        "draw_calls": [
            {
                "event_id": 1,
                "pipeline_state": {
                    "vs_bindings": {"resourceId": 77, "shader_name": "VS_Main"}
                },
            }
        ],
    }

    bundle = analysis_to_bundle(analysis)
    assert bundle.textures[0]["resource_id"] == 11
    assert bundle.textures[0]["id"] == 11
    assert bundle.textures[1]["resource_id"] == 22
    assert bundle.textures[1]["id"] == 22
    assert bundle.shaders[0]["id"] == 77
