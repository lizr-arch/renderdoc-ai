from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from .base import (
    DataAvailability,
    Provider,
    ProviderContext,
    infer_capture_id,
    stable_object,
)
from .eap_sidecar_provider import EAPSidecarProvider
from .live_renderdoc_provider import LiveRenderDocProvider
from .renderdoc_native_provider import RenderDocNativeProvider
from .rules_provider import RulesProvider
from .scout_report_provider import ScoutReportProvider
from .snapshot_provider import SnapshotProvider


CONTRACT_VERSION = "mcp-query.v1"

METHOD_PROVIDER_ORDER = {
    "get_capture_status": ("live_renderdoc", "renderdoc_native"),
    "get_frame_summary": ("snapshot", "live_renderdoc"),
    "get_pipeline_state": ("live_renderdoc", "snapshot"),
    "get_texture_info": ("snapshot", "renderdoc_native"),
    "get_eap_command": ("eap_sidecar",),
    "get_eap_resource": ("eap_sidecar",),
    "get_rule_results": ("rules",),
}


class ProviderRegistry:
    def __init__(self, providers: Sequence[Provider]):
        self._providers = list(providers)

    def data_availability(self, context: ProviderContext) -> DataAvailability:
        providers: Dict[str, Dict[str, object]] = {}
        limitations = []
        for provider in self._providers:
            payload = provider.availability(context)
            providers[provider.name] = payload
            if not payload.get("available"):
                missing = payload.get("missing")
                if missing:
                    limitations.append(f"{provider.name}: {missing}")
        return DataAvailability(
            capture_id=infer_capture_id(context),
            providers=providers,
            limitations=limitations,
        )

    def route(
        self,
        method: str,
        preferred_provider: Optional[str] = None,
        context: Optional[ProviderContext] = None,
    ) -> Dict[str, Any]:
        context = context or ProviderContext()
        owner_order = METHOD_PROVIDER_ORDER.get(method)
        if owner_order is None:
            return _route_error(
                method=method,
                code="unsupported_api",
                message=f"Unsupported MCP provider method: {method}",
                recovery_hint="Choose a supported MCP provider method.",
            )

        if preferred_provider:
            if preferred_provider not in owner_order:
                return _route_error(
                    method=method,
                    code="unsupported_api",
                    message=f"Provider {preferred_provider} cannot handle method {method}",
                    recovery_hint="Choose a provider that owns this method.",
                )
            owner_order = (preferred_provider,)

        availability = self.data_availability(context).as_dict()
        providers = availability.get("providers", {}) or {}
        for provider_name in owner_order:
            provider_payload = providers.get(provider_name, {}) or {}
            if provider_payload.get("available"):
                return _route_success(method=method, provider_name=provider_name)

        notes = []
        for provider_name in owner_order:
            provider_payload = providers.get(provider_name, {}) or {}
            missing = provider_payload.get("missing") or "provider unavailable"
            notes.append(f"{provider_name}: {missing}")
        return _route_error(
            method=method,
            code="data_unavailable",
            message=f"No available provider for method {method}",
            notes=notes,
            recovery_hint="Provide the required provider payload or choose another supported method.",
        )


def build_default_registry() -> ProviderRegistry:
    return ProviderRegistry(
        [
            RenderDocNativeProvider(),
            SnapshotProvider(),
            EAPSidecarProvider(),
            RulesProvider(),
            LiveRenderDocProvider(),
            ScoutReportProvider(),
        ]
    )


def data_availability(context: ProviderContext) -> DataAvailability:
    return build_default_registry().data_availability(context)


def _route_success(*, method: str, provider_name: str) -> Dict[str, Any]:
    return stable_object(
        {
            "ok": True,
            "contract_version": CONTRACT_VERSION,
            "data": {"provider": provider_name, "method": method},
            "availability": {"status": "full", "missing_fields": [], "notes": []},
            "evidence": [],
            "warnings": [],
            "recovery_hint": None,
            "error": None,
            "method": method,
            "params": {},
            "source": "provider_registry",
        }
    )


def _route_error(
    *,
    method: str,
    code: str,
    message: str,
    notes: Sequence[str] = (),
    recovery_hint: str,
) -> Dict[str, Any]:
    return stable_object(
        {
            "ok": False,
            "contract_version": CONTRACT_VERSION,
            "data": None,
            "availability": {
                "status": "unavailable",
                "missing_fields": [],
                "notes": list(notes),
            },
            "evidence": [],
            "warnings": [],
            "recovery_hint": recovery_hint,
            "error": {"code": code, "message": message},
            "method": method,
            "params": {},
            "source": "provider_registry",
        }
    )
