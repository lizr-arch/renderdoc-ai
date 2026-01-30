#!/usr/bin/env python3
"""Rule metadata completeness tests."""

from rdc_analyzer.rules import register_all_rules
from rdc_analyzer.scripts.generate_rules_doc import collect_rules


def test_rules_have_non_empty_metadata():
    """All rules must provide non-empty WHAT/WHY/HOW metadata."""
    register_all_rules()
    rules = collect_rules()
    for rule in rules:
        assert rule.get("what"), f"{rule['rule_id']} missing WHAT"
        assert rule.get("why"), f"{rule['rule_id']} missing WHY"
        assert rule.get("how"), f"{rule['rule_id']} missing HOW"
