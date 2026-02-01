from typing import Any, Dict, List, Optional


def build_manifest(
    capture_id: str,
    source: str,
    counts: Dict[str, int],
    count_reason: Dict[str, str],
    missing: Optional[List[Dict[str, str]]],
    report_links: Dict[str, str],
) -> Dict[str, Any]:
    if not capture_id:
        raise ValueError("capture_id required")
    if source not in {"A", "B", "C"}:
        raise ValueError("source must be A/B/C")
    if not isinstance(counts, dict):
        raise ValueError("counts must be dict")
    if not isinstance(count_reason, dict):
        raise ValueError("count_reason must be dict")
    if not isinstance(report_links, dict) or not report_links:
        raise ValueError("report_links required")

    missing_reason = missing or []
    for item in missing_reason:
        if not item.get("field") or not item.get("reason"):
            raise ValueError("missing reason required")

    return {
        "capture_id": capture_id,
        "source": source,
        "counts": counts,
        "count_reason": count_reason,
        "missing_reason": missing_reason,
        "report_links": report_links,
    }
