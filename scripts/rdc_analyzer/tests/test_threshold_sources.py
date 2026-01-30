#!/usr/bin/env python3
"""Threshold source coverage tests."""

from rdc_analyzer.scripts.generate_rules_doc import collect_rules


def test_threshold_sources_cover_rule_keys():
    """All rule threshold keys must have a source entry."""
    from rdc_analyzer.config import get_threshold_sources

    sources = get_threshold_sources("pc")
    rules = collect_rules()
    for rule in rules:
        for threshold in rule.get("thresholds", []):
            key = threshold["key"]
            assert key in sources, f"missing source for {key}"
