#!/usr/bin/env python3
"""RULES.md generator tests."""

from rdc_analyzer.config import get_thresholds
from rdc_analyzer.rules import RuleRegistry, register_all_rules
from rdc_analyzer.scripts.generate_rules_doc import collect_rules, render_markdown


def test_collect_rules_matches_registry():
    """Generated rules should match RuleRegistry contents."""
    register_all_rules()
    rules = collect_rules()
    registry_ids = set(RuleRegistry.all().keys())
    output_ids = {rule["rule_id"] for rule in rules}
    assert registry_ids == output_ids


def test_collect_rules_threshold_values_follow_config():
    """Threshold values should follow config for each platform."""
    rules = collect_rules()
    pc_thresholds = get_thresholds("pc")
    mobile_thresholds = get_thresholds("mobile")

    for rule in rules:
        for threshold in rule["thresholds"]:
            key = threshold["key"]
            default = threshold["default"]
            assert threshold["pc"] == pc_thresholds.get(key, default)
            assert threshold["mobile"] == mobile_thresholds.get(key, default)


def test_render_markdown_contains_all_rules_and_under_limit():
    """Rendered markdown should include every rule and stay under 800 lines."""
    rules = collect_rules()
    content = render_markdown(rules)

    for rule in rules:
        assert rule["rule_id"] in content

    assert len(content.splitlines()) < 800


def test_rules_doc_includes_metadata_and_sources():
    """Rendered markdown should include metadata and source sections."""
    content = render_markdown(collect_rules())
    assert "**WHAT**" in content
    assert "**WHY**" in content
    assert "**HOW**" in content
    assert "**标准来源**" in content
