import json
import os

from exporters.unity_manifest import build_manifest


def find_action_by_event(actions, event_id):
    for action in actions:
        if action.eventId == event_id:
            return action
        if action.children:
            found = find_action_by_event(action.children, event_id)
            if found:
                return found
    return None


def export_unity_assets(rdc_path, event_id, api, out_dir):
    import renderdoc as rd

    cap = rd.OpenCaptureFile()
    if cap.OpenFile(rdc_path, "", None) != rd.ReplayStatus.Succeeded:
        raise RuntimeError("OpenFile failed")

    controller = cap.OpenCapture(rd.ReplayOptions(), None)
    if controller is None:
        raise RuntimeError("OpenCapture failed")

    action = find_action_by_event(controller.GetRootActions(), event_id)
    if action is None:
        controller.Shutdown()
        cap.Shutdown()
        raise RuntimeError("eventId not found")

    controller.SetFrameEvent(event_id, False)
    pipe = controller.GetPipelineState()

    mesh = {}
    textures = []
    shaders = {}

    manifest = build_manifest(event_id, api, mesh, textures, shaders)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    controller.Shutdown()
    cap.Shutdown()
