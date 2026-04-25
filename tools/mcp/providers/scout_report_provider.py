from __future__ import annotations

from typing import Any, Dict, Optional

from .base import (
    PROVIDER_SCOUT_REPORT,
    ProviderContext,
    capability,
    provider_availability,
)


class ScoutReportProvider:
    name = PROVIDER_SCOUT_REPORT

    def availability(self, context: ProviderContext) -> Dict[str, Any]:
        missing = _scout_report_missing_reason(context.scout_report)
        if missing:
            return provider_availability(available=False, missing=missing)
        return provider_availability(
            available=True,
            capabilities=[
                capability(
                    "repo_recon_report",
                    ["implementation_candidates", "risk_report", "next_prompt"],
                )
            ],
        )


def _scout_report_missing_reason(scout_report: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(scout_report, dict) or not scout_report:
        return "scout report not provided"
    return None
