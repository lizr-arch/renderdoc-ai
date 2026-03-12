#!/usr/bin/env python3
"""Threshold schema alias tests."""


def test_threshold_alias_keys_present():
    """Config should expose all rule threshold keys."""
    from rdc_analyzer.config import get_thresholds

    thresholds = get_thresholds("pc")
    required_keys = {
        # draw_call rules
        "draw_call_count",
        "min_vertices_per_draw",
        "instancing_threshold",
        "max_vertices_per_draw",
        # texture rules
        "max_texture_size",
        "max_texture_memory_mb",
        "mipmap_required_size",
        "compression_required_size",
        "texture_array_threshold",
        # buffer rules
        "max_buffer_size_mb",
        "max_buffer_updates",
        "max_vertex_stride",
        # state rules
        "max_blend_changes",
        "max_depth_changes",
        "max_rasterizer_changes",
        "max_blend_draws",
        # render pass rules
        "max_rt_switches",
        "depth_prepass_threshold",
        "max_shadowmap_size",
        # mobile rules
        "mobile_max_overdraw",
        "mobile_texture_size",
        "mobile_max_alpha_test",
    }

    missing = required_keys.difference(set(thresholds.keys()))
    assert not missing, f"阈值缺失: {sorted(missing)}"


def test_threshold_alias_values_follow_primary():
    """Alias keys should match primary config values."""
    from rdc_analyzer.config import get_thresholds

    thresholds = get_thresholds("pc")

    assert thresholds["draw_call_count"] == thresholds["max_draw_calls"]
    assert thresholds["min_vertices_per_draw"] == thresholds["small_draw_vertex_threshold"]
    assert thresholds["instancing_threshold"] == thresholds["instancing_suggestion_threshold"]
    assert thresholds["max_buffer_size_mb"] == thresholds["large_buffer_threshold_mb"]
    assert thresholds["max_buffer_updates"] == thresholds["dynamic_buffer_update_threshold"]
    assert thresholds["max_rt_switches"] == thresholds["max_rt_changes"]
    assert thresholds["max_blend_changes"] == thresholds["max_blend_state_changes"]
