from __future__ import annotations

from typing import Any, Dict, List

from .base import (
    PROVIDER_RULES,
    ProviderCapability,
    ProviderContext,
    capability,
    ensure_list,
    provider_availability,
)


class RulesProvider:
    name = PROVIDER_RULES

    def availability(self, context: ProviderContext) -> Dict[str, Any]:
        capabilities = _rules_capabilities(
            snapshot=context.snapshot if isinstance(context.snapshot, dict) else {},
            eap_sidecar=context.eap_sidecar if isinstance(context.eap_sidecar, dict) else {},
            rules_payload=context.rules_payload if isinstance(context.rules_payload, dict) else {},
        )
        if capabilities:
            return provider_availability(available=True, capabilities=capabilities)
        return provider_availability(
            available=False,
            missing="No rules payload, EAP rule results, or snapshot findings provided",
        )


def _rules_capabilities(
    *,
    snapshot: Dict[str, Any],
    eap_sidecar: Dict[str, Any],
    rules_payload: Dict[str, Any],
) -> List[ProviderCapability]:
    capabilities: List[ProviderCapability] = []
    if _has_rules_payload(rules_payload):
        capabilities.append(capability("external_rule_results", ["rules_payload"]))
    rules = eap_sidecar.get("rules", {}) or {}
    if isinstance(rules, dict) and ensure_list(rules.get("results")):
        capabilities.append(capability("eap_sidecar_rule_results", ["rules.results"]))
    if ensure_list(snapshot.get("findings")):
        capabilities.append(capability("snapshot_findings", ["findings", "recommendations"]))
    return capabilities


def _has_rules_payload(payload: Dict[str, Any]) -> bool:
    if not payload:
        return False
    if ensure_list(payload.get("results")):
        return True
    if ensure_list(payload.get("findings")):
        return True
    if ensure_list(payload.get("rules")):
        return True
    return False
