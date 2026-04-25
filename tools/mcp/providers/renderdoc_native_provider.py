from __future__ import annotations

from typing import Any, Dict

from .base import (
    PROVIDER_RENDERDOC_NATIVE,
    ProviderContext,
    capability,
    provider_availability,
)


class RenderDocNativeProvider:
    name = PROVIDER_RENDERDOC_NATIVE

    def availability(self, context: ProviderContext) -> Dict[str, Any]:
        if not context.renderdoc_native_available:
            return provider_availability(
                available=False,
                missing="RenderDoc native provider disabled or unavailable",
            )
        return provider_availability(
            available=True,
            capabilities=[
                capability(
                    "native_capture_queries",
                    ["capture_status", "actions", "textures", "buffers"],
                    ["Existing RenderDoc Python/bridge surfaces; independent from EAP sidecar."],
                )
            ],
        )
