from pathlib import Path


def test_datatables_dependency_has_fallback():
    text = Path('scripts/rdc_analyzer/analyze_rdc.py').read_text(encoding='utf-8')
    uses_datatable = 'DataTable(' in text or '.DataTable(' in text
    has_fallback = (
        'initDataTableFallback' in text
        or 'renderTableFallback' in text
        or 'initDataTable(' in text
    )
    assert not uses_datatable or has_fallback, (
        'analyze_rdc.py uses DataTable without a fallback renderer.'
    )
