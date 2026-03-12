from rdc_analyzer.analyze_rdc import compute_reconcile_summary


def test_reconcile_summary_passes_at_threshold():
    summary = compute_reconcile_summary(
        shader_chunk_total=10,
        texture_chunk_total=20,
        shader_count=9,
        texture_count=18,
        threshold=0.9,
    )

    assert summary["shader_ratio"] == 0.9
    assert summary["texture_ratio"] == 0.9
    assert summary["approval_required"] is False
    assert summary["issues"] == []


def test_reconcile_summary_requires_approval_when_below_threshold():
    summary = compute_reconcile_summary(
        shader_chunk_total=10,
        texture_chunk_total=20,
        shader_count=5,
        texture_count=10,
        threshold=0.9,
    )

    assert summary["approval_required"] is True
    assert summary["issues"]
    assert "Shader ratio below threshold" in summary["issues"][0]
