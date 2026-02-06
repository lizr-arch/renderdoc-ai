"""Report Engine Adapters - Data source converters.

Adapters transform various input formats into ReportDataContract:
- XmlAdapter: RDC XML exports
- RdcAdapter: Direct RDC file parsing via Python API

Usage:
    from rdc_analyzer.report_engine.adapters import XmlAdapter, RdcAdapter
    
    # Load XML into ReportDataContract
    contract = XmlAdapter().from_xml_file("path/to/file.xml")
    
    # Load RDC directly (requires renderdoc module)
    contract = RdcAdapter().from_rdc_file("path/to/file.rdc")
    
    # Auto-detect file type
    from rdc_analyzer.report_engine.adapters import load_auto
    contract = load_auto("path/to/file.rdc")  # or .xml
"""

from .xml_adapter import XmlAdapter, load_xml_to_contract
from .rdc_adapter import (
    RdcAdapter, 
    load_rdc_to_contract, 
    load_auto,
    is_renderdoc_available
)

__all__ = [
    # XML Adapter
    "XmlAdapter",
    "load_xml_to_contract",
    # RDC Adapter
    "RdcAdapter",
    "load_rdc_to_contract",
    # Utilities
    "load_auto",
    "is_renderdoc_available",
]