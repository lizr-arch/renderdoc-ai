#!/usr/bin/env python3
"""JSON Renderer - Output ReportDataContract as JSON.

This renderer serializes the ReportDataContract to JSON format for:
- Programmatic processing
- API responses
- Data interchange
- CI/CD pipelines

Usage:
    from rdc_analyzer.report_engine.renderers import JsonRenderer
    from rdc_analyzer.report_engine.contract import ReportDataContract
    
    renderer = JsonRenderer()
    json_str = renderer.render(contract)
    
    # Or save directly to file
    renderer.render_to_file(contract, "output.json")
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime

from ..contract import ReportDataContract, build_manifest


class JsonRenderer:
    """Renderer that outputs ReportDataContract as JSON.
    
    Features:
    - Pretty-printed or compact JSON output
    - Optional manifest embedding
    - Filtering to include only specific sections
    - Custom JSON encoder for special types
    """
    
    def __init__(self,
                 pretty: bool = True,
                 indent: int = 2,
                 include_manifest: bool = True,
                 sections: Optional[list] = None):
        """Initialize the JSON renderer.
        
        Args:
            pretty: Whether to format with indentation (default True)
            indent: Indentation level for pretty printing (default 2)
            include_manifest: Whether to include manifest metadata (default True)
            sections: Optional list of sections to include. If None, include all.
                     Valid sections: textures, shaders, events, buffers, issues,
                                    performance, pipeline_states, meta
        """
        self.pretty = pretty
        self.indent = indent if pretty else None
        self.include_manifest = include_manifest
        self.sections = sections
    
    def render(self, contract: ReportDataContract) -> str:
        """Render the contract to a JSON string.
        
        Args:
            contract: ReportDataContract to render
            
        Returns:
            JSON string representation
        """
        data = self._prepare_data(contract)
        return json.dumps(data, indent=self.indent, cls=_ContractEncoder, ensure_ascii=False)
    
    def render_to_file(self, contract: ReportDataContract, 
                       output_path: str) -> str:
        """Render the contract and save to a file.
        
        Args:
            contract: ReportDataContract to render
            output_path: Path to output JSON file
            
        Returns:
            Path to the created file
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        json_str = self.render(contract)
        path.write_text(json_str, encoding='utf-8')
        
        return str(path)
    
    def render_to_dict(self, contract: ReportDataContract) -> Dict[str, Any]:
        """Render the contract to a Python dict (no JSON serialization).
        
        Useful for embedding in other data structures or API responses.
        
        Args:
            contract: ReportDataContract to render
            
        Returns:
            Dictionary representation
        """
        return self._prepare_data(contract)
    
    def _prepare_data(self, contract: ReportDataContract) -> Dict[str, Any]:
        """Prepare the data dictionary from contract.
        
        Args:
            contract: ReportDataContract instance
            
        Returns:
            Dictionary ready for JSON serialization
        """
        # Get full contract data
        full_data = contract.to_dict()
        
        # Filter sections if specified
        if self.sections:
            data = {}
            for section in self.sections:
                if section in full_data:
                    data[section] = full_data[section]
                elif section == "meta" and hasattr(contract, "meta"):
                    data["meta"] = full_data.get("meta", {})
        else:
            data = full_data
        
        # Add manifest if requested
        if self.include_manifest:
            manifest = build_manifest(contract)
            data["_manifest"] = manifest
        
        # Add generation metadata
        data["_generated"] = {
            "timestamp": datetime.now().isoformat(),
            "renderer": "JsonRenderer",
            "version": "1.0.0",
        }
        
        return data


class _ContractEncoder(json.JSONEncoder):
    """Custom JSON encoder for ReportDataContract types."""
    
    def default(self, obj):
        # Handle datetime objects
        if isinstance(obj, datetime):
            return obj.isoformat()
        
        # Handle bytes (e.g., embedded thumbnails)
        if isinstance(obj, bytes):
            import base64
            return base64.b64encode(obj).decode('utf-8')
        
        # Handle sets
        if isinstance(obj, set):
            return list(obj)
        
        # Handle Path objects
        if isinstance(obj, Path):
            return str(obj)
        
        # Fallback to default behavior
        return super().default(obj)


# Convenience functions

def render_contract_to_json(contract: ReportDataContract,
                            output_path: Optional[str] = None,
                            pretty: bool = True) -> str:
    """Convenience function to render contract to JSON.
    
    Args:
        contract: ReportDataContract to render
        output_path: Optional path to save JSON file
        pretty: Whether to pretty-print (default True)
        
    Returns:
        JSON string (if output_path is None) or path to saved file
    """
    renderer = JsonRenderer(pretty=pretty)
    
    if output_path:
        return renderer.render_to_file(contract, output_path)
    else:
        return renderer.render(contract)


def contract_to_dict(contract: ReportDataContract,
                     sections: Optional[list] = None) -> Dict[str, Any]:
    """Convert contract to dictionary, optionally filtering sections.
    
    Args:
        contract: ReportDataContract to convert
        sections: Optional list of sections to include
        
    Returns:
        Dictionary representation
    """
    renderer = JsonRenderer(include_manifest=False, sections=sections)
    return renderer.render_to_dict(contract)
