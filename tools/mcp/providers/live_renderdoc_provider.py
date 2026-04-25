from __future__ import annotations

from typing import Any, Dict, Optional

from .base import (
    PROVIDER_LIVE_RENDERDOC,
    ProviderContext,
    capability,
    extract_capture_loaded,
    provider_availability,
)


class LiveRenderDocProvider:
    name = PROVIDER_LIVE_RENDERDOC

    def availability(self, context: ProviderContext) -> Dict[str, Any]:
        missing = _live_renderdoc_missing_reason(context.live_renderdoc_status, context.bridge_state)
        if missing:
            return provider_availability(available=False, missing=missing)
        return provider_availability(
            available=True,
            capabilities=[
                capability(
                    "live_capture_queries",
                    ["capture_status", "frame_summary", "pipeline_state", "texture_data"],
                )
            ],
        )


def _live_renderdoc_missing_reason(
    live_renderdoc_status: Optional[Dict[str, Any]],
    bridge_state: Optional[Dict[str, Any]],
) -> Optional[str]:
    if isinstance(live_renderdoc_status, dict) and live_renderdoc_status:
        if extract_capture_loaded(live_renderdoc_status):
            return None
        return "live RenderDoc capture is not loaded"
    if isinstance(bridge_state, dict) and bridge_state.get("ipc_dir_exists"):
        return "live RenderDoc bridge IPC present but capture status not loaded/probed"
    return "live RenderDoc bridge not probed"
