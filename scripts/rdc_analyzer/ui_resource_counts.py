#!/usr/bin/env python3
"""Print texture/resource counts from RenderDoc UI or a capture file.

UI usage (Python Shell):
  exec(open(r'D:\Code\git\renderdoc\scripts\rdc_analyzer\ui_resource_counts.py').read())

CLI usage (renderdoccmd/qrenderdoc --python):
  ui_resource_counts.py <path_to.rdc>
"""

import os
import sys

try:
    import renderdoc as rd
except ImportError as exc:
    print(f"[ERROR] renderdoc module not available: {exc}")
    sys.exit(1)


def _get_controller_from_ui():
    if 'pyrenderdoc' not in globals():
        return None
    ctx = pyrenderdoc.GetCaptureContext()
    if not ctx:
        return None
    controller = ctx.GetReplayController()
    return controller


def _open_controller_from_file(path):
    cap = rd.OpenCaptureFile()
    status = cap.OpenFile(path, "", None)
    if status != rd.ResultCode.Succeeded:
        print(f"[ERROR] OpenFile failed: {status}")
        cap.Shutdown()
        return None, None

    if not cap.LocalReplaySupport():
        print("[ERROR] Capture cannot be replayed locally")
        cap.Shutdown()
        return None, None

    controller, status = cap.OpenCapture(rd.ReplayOptions(), None)
    if status != rd.ResultCode.Succeeded:
        print(f"[ERROR] OpenCapture failed: {status}")
        cap.Shutdown()
        return None, None

    return controller, cap


def main():
    controller = _get_controller_from_ui()
    cap = None

    if controller is None:
        if len(sys.argv) < 2:
            print("[ERROR] No active capture. Provide path to .rdc file.")
            print("Usage: ui_resource_counts.py <path_to.rdc>")
            return 1
        rdc_path = sys.argv[1]
        if not os.path.exists(rdc_path):
            print(f"[ERROR] File not found: {rdc_path}")
            return 1
        controller, cap = _open_controller_from_file(rdc_path)
        if controller is None:
            return 1

    textures = controller.GetTextures()
    resources = controller.GetResources()

    print(f"ui_texture_count: {len(textures)}")
    print(f"ui_resource_count: {len(resources)}")

    if cap is not None:
        controller.Shutdown()
        cap.Shutdown()

    return 0


if __name__ == "__main__":
    sys.exit(main())
