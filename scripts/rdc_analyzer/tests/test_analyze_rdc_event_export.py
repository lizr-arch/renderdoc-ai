import importlib

from rdc_analyzer.rdc_parser import DrawEventContext, PipelineInfo

_analyze_rdc = importlib.import_module("rdc_analyzer.analyze_rdc")


def test_convert_draw_events_to_capture_events_minimal():
    draw_events = [
        DrawEventContext(
            chunk_index=5,
            chunk_id=123,
            event_type="draw_indexed",
            pipeline_resource_id=99,
            marker_stack=["PassA", "ObjB"],
        )
    ]
    pipelines = {
        99: PipelineInfo(
            resource_id=99,
            pipeline_type="graphics",
            shader_stages={"VS": 11, "FS": 22},
        )
    }

    events = _analyze_rdc.convert_draw_events_to_capture_events(draw_events, pipelines)

    assert len(events) == 1

    evt = events[0]
    assert evt["eventId"] == 5
    assert evt["type"] == "draw"
    assert evt["name"] == "DrawIndexed"
    assert evt["markerPath"] == "PassA/ObjB"
    assert evt["pipeline"] == 99

    pipeline_state = evt.get("pipelineState", {})
    shaders = pipeline_state.get("shaders", {})
    assert shaders.get("VS", {}).get("resourceId") == 11
    assert shaders.get("PS", {}).get("resourceId") == 22
