#!/usr/bin/env python3
"""RDC Adapter - Convert RDC file directly to ReportDataContract.

This adapter uses the RenderDoc Python API to load .rdc files directly,
bypassing the XML intermediate format for richer data extraction.

Requirements:
    - renderdoc Python module (bundled with RenderDoc)
    - Compatible GPU hardware for replay

Usage:
    from rdc_analyzer.report_engine.adapters.rdc_adapter import RdcAdapter
    
    adapter = RdcAdapter()
    contract = adapter.from_rdc_file("capture.rdc")

Fallback:
    If renderdoc module is not available, use XmlAdapter instead:
    
    from rdc_analyzer.report_engine.adapters import XmlAdapter
    # First convert: renderdoccmd convert -c xml -o out.xml in.rdc
    contract = XmlAdapter().from_xml_file("out.xml")
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import base64
import io

from ..contract import MetaData, ReportDataContract

# Track whether renderdoc is available
_renderdoc_available: Optional[bool] = None
_renderdoc_module = None


def is_renderdoc_available() -> bool:
    """Check if the renderdoc Python module is available.
    
    Returns:
        True if renderdoc module can be imported, False otherwise.
    """
    global _renderdoc_available, _renderdoc_module
    
    if _renderdoc_available is None:
        try:
            import renderdoc as rd
            _renderdoc_module = rd
            _renderdoc_available = True
        except ImportError:
            _renderdoc_available = False
    
    return _renderdoc_available


def _get_renderdoc():
    """Get the renderdoc module, raising ImportError if not available."""
    if not is_renderdoc_available():
        raise ImportError(
            "renderdoc Python module not available. "
            "Please install RenderDoc or use XmlAdapter as a fallback:\n"
            "  1. Install RenderDoc from https://renderdoc.org\n"
            "  2. Add RenderDoc's Python module path to PYTHONPATH\n"
            "  3. Or use: renderdoccmd convert -c xml -o out.xml in.rdc\n"
            "     Then: XmlAdapter().from_xml_file('out.xml')"
        )
    return _renderdoc_module


class RdcAdapter:
    """Adapter to load RDC files directly via RenderDoc Python API.
    
    This adapter provides:
    1. Direct RDC file loading without intermediate XML
    2. Full shader source code extraction
    3. Pipeline state extraction
    4. Texture thumbnail generation
    5. Resource usage tracking
    
    Note: Requires compatible GPU and renderdoc Python module.
    """
    
    def __init__(self, 
                 extract_thumbnails: bool = True,
                 extract_shaders: bool = True,
                 thumbnail_size: Tuple[int, int] = (128, 128)):
        """Initialize the RDC adapter.
        
        Args:
            extract_thumbnails: Whether to generate texture thumbnails
            extract_shaders: Whether to extract shader source code
            thumbnail_size: Size of generated thumbnails (width, height)
        """
        self.extract_thumbnails = extract_thumbnails
        self.extract_shaders = extract_shaders
        self.thumbnail_size = thumbnail_size
        
        # These will be set when loading
        self._cap: Any = None
        self._controller: Any = None
    
    def from_rdc_file(self, rdc_path: str) -> ReportDataContract:
        """Load an RDC file and convert to ReportDataContract.
        
        Args:
            rdc_path: Path to the .rdc file
            
        Returns:
            ReportDataContract populated with capture data
            
        Raises:
            ImportError: If renderdoc module is not available
            FileNotFoundError: If RDC file doesn't exist
            RuntimeError: If replay initialization fails
        """
        rd = _get_renderdoc()
        
        path = Path(rdc_path)
        if not path.exists():
            raise FileNotFoundError(f"RDC file not found: {rdc_path}")
        
        # Open capture
        self._cap = rd.OpenCaptureFile()
        status = self._cap.OpenFile(str(path), '', None)
        
        if status != rd.ResultCode.Succeeded:
            raise RuntimeError(f"Failed to open RDC file: {status}")
        
        try:
            # Create replay
            status, self._controller = self._cap.OpenCapture(
                rd.ReplayOptions(), None
            )
            
            if status != rd.ResultCode.Succeeded:
                raise RuntimeError(f"Failed to create replay: {status}")
            
            # Extract data
            return self._extract_to_contract(path.stem)
            
        finally:
            # Cleanup
            if self._controller:
                self._controller.Shutdown()
            if self._cap:
                self._cap.Shutdown()
    
    def _extract_to_contract(self, capture_name: str) -> ReportDataContract:
        """Extract all data from the replay controller.
        
        Args:
            capture_name: Name of the capture for metadata
            
        Returns:
            Populated ReportDataContract
        """
        rd = _get_renderdoc()
        
        # Detect API type
        api = self._detect_api()
        
        # Build metadata
        meta = MetaData(
            capture_name=capture_name,
            api=api,
            source="rdc",
            generated_at=datetime.now().isoformat(),
            frame_thumbnail=self._extract_frame_thumbnail()
        )
        
        # Extract resources
        textures = self._extract_textures()
        buffers = self._extract_buffers()
        
        # Extract events/draw calls
        events = self._extract_events()
        
        # Extract shaders if enabled
        shaders = []
        if self.extract_shaders:
            shaders = self._extract_shaders()
        
        # Extract pipeline states
        pipeline_states = self._extract_pipeline_states()
        
        # Build performance stats
        performance = {
            "total_draw_calls": len([e for e in events if e.get("is_draw", False)]),
            "total_dispatches": len([e for e in events if e.get("is_dispatch", False)]),
            "total_textures": len(textures),
            "total_buffers": len(buffers),
            "total_shaders": len(shaders),
        }
        
        # Build texture usage map
        texture_usage_map = self._build_texture_usage_map(events, textures)
        
        return ReportDataContract(
            meta=meta,
            textures=textures,
            buffers=buffers,
            events=events,
            shaders=shaders,
            pipeline_states=pipeline_states,
            performance=performance,
            texture_usage_map=texture_usage_map,
        )
    
    def _detect_api(self) -> str:
        """Detect the graphics API used in the capture."""
        rd = _get_renderdoc()
        
        api_props = self._controller.GetAPIProperties()
        api_name = str(api_props.pipelineType)
        
        # Map to friendly name
        api_map = {
            "GraphicsAPI.D3D11": "D3D11",
            "GraphicsAPI.D3D12": "D3D12",
            "GraphicsAPI.OpenGL": "OpenGL",
            "GraphicsAPI.Vulkan": "Vulkan",
        }
        
        return api_map.get(api_name, api_name)
    
    def _extract_frame_thumbnail(self) -> str:
        """Extract a thumbnail of the final frame output.
        
        Returns:
            Base64-encoded PNG image, or empty string on failure
        """
        if not self.extract_thumbnails:
            return ""
        
        try:
            rd = _get_renderdoc()
            
            # Get all actions and find the last draw
            actions = self._controller.GetRootActions()
            if not actions:
                return ""
            
            # Navigate to last action
            last_action = self._find_last_action(actions)
            if last_action:
                self._controller.SetFrameEvent(last_action.eventId, True)
            
            # Get output texture
            textures = self._controller.GetTextures()
            for tex in textures:
                if tex.creationFlags & rd.TextureCategory.SwapBuffer:
                    return self._texture_to_base64(tex.resourceId)
            
            return ""
        except Exception:
            return ""
    
    def _find_last_action(self, actions: List[Any]) -> Optional[Any]:
        """Recursively find the last action in the tree."""
        result = None
        for action in actions:
            result = action
            if action.children:
                child_result = self._find_last_action(action.children)
                if child_result:
                    result = child_result
        return result
    
    def _texture_to_base64(self, resource_id: Any) -> str:
        """Convert a texture to base64-encoded PNG.
        
        Args:
            resource_id: RenderDoc resource ID
            
        Returns:
            Base64 string or empty on failure
        """
        try:
            rd = _get_renderdoc()
            
            # Save texture to bytes
            data = self._controller.GetTextureData(
                resource_id, 
                rd.Subresource(0, 0, 0)
            )
            
            if not data:
                return ""
            
            # Convert to PNG using PIL if available
            try:
                from PIL import Image
                
                tex_info = self._controller.GetTexture(resource_id)
                width = tex_info.width
                height = tex_info.height
                
                # Create image from raw data (assuming RGBA)
                img = Image.frombytes('RGBA', (width, height), bytes(data))
                img.thumbnail(self.thumbnail_size)
                
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                return base64.b64encode(buffer.getvalue()).decode('utf-8')
                
            except ImportError:
                # PIL not available, return empty
                return ""
                
        except Exception:
            return ""
    
    def _extract_textures(self) -> List[Dict[str, Any]]:
        """Extract all texture resources."""
        rd = _get_renderdoc()
        textures = []
        
        for tex in self._controller.GetTextures():
            tex_dict = {
                "id": int(tex.resourceId),
                "resource_id": int(tex.resourceId),
                "name": tex.name or f"Texture_{tex.resourceId}",
                "width": tex.width,
                "height": tex.height,
                "depth": tex.depth,
                "format": str(tex.format.Name()),
                "mip_levels": tex.mips,
                "array_size": tex.arraysize,
                "type": self._get_texture_type(tex),
                "samples": tex.msSamp,
                "creation_flags": int(tex.creationFlags),
                "thumbnail": "",  # Will be populated on demand
            }
            
            # Calculate approximate size
            tex_dict["size_bytes"] = self._estimate_texture_size(tex)
            
            textures.append(tex_dict)
        
        return textures
    
    def _get_texture_type(self, tex: Any) -> str:
        """Determine texture type from properties."""
        rd = _get_renderdoc()
        
        if tex.cubemap:
            return "TextureCube"
        elif tex.depth > 1:
            return "Texture3D"
        elif tex.arraysize > 1:
            return "Texture2DArray"
        else:
            return "Texture2D"
    
    def _estimate_texture_size(self, tex: Any) -> int:
        """Estimate texture size in bytes."""
        # Get bytes per pixel from format
        bpp = self._get_format_bpp(str(tex.format.Name()))
        
        # Calculate total pixels across all mips
        total_pixels = 0
        w, h, d = tex.width, tex.height, max(1, tex.depth)
        
        for mip in range(tex.mips):
            total_pixels += max(1, w) * max(1, h) * max(1, d)
            w = max(1, w // 2)
            h = max(1, h // 2)
            d = max(1, d // 2)
        
        # Multiply by array size
        total_pixels *= tex.arraysize
        
        # Multiply by samples for MSAA
        total_pixels *= tex.msSamp
        
        return int(total_pixels * bpp)
    
    def _get_format_bpp(self, format_name: str) -> float:
        """Get bytes per pixel for a format."""
        # Common format BPP lookup
        bpp_map = {
            # Uncompressed
            "R8G8B8A8": 4,
            "B8G8R8A8": 4,
            "R16G16B16A16": 8,
            "R32G32B32A32": 16,
            "R32": 4,
            "R16": 2,
            "R8": 1,
            # Compressed (per 4x4 block)
            "BC1": 0.5,
            "BC2": 1,
            "BC3": 1,
            "BC4": 0.5,
            "BC5": 1,
            "BC6H": 1,
            "BC7": 1,
            "ASTC": 1,  # Varies
            "ETC2": 0.5,
        }
        
        for pattern, bpp in bpp_map.items():
            if pattern in format_name:
                return bpp
        
        return 4  # Default to 4 bytes
    
    def _extract_buffers(self) -> List[Dict[str, Any]]:
        """Extract all buffer resources."""
        rd = _get_renderdoc()
        buffers = []
        
        for buf in self._controller.GetBuffers():
            buf_dict = {
                "id": int(buf.resourceId),
                "resource_id": int(buf.resourceId),
                "name": buf.name or f"Buffer_{buf.resourceId}",
                "size": buf.length,
                "creation_flags": int(buf.creationFlags),
            }
            buffers.append(buf_dict)
        
        return buffers
    
    def _extract_events(self) -> List[Dict[str, Any]]:
        """Extract all draw calls and events."""
        rd = _get_renderdoc()
        events = []
        
        def process_action(action: Any, depth: int = 0, parent_marker: str = ""):
            """Recursively process action tree."""
            marker = action.customName or parent_marker
            
            # Check action type
            is_draw = bool(action.flags & rd.ActionFlags.Drawcall)
            is_dispatch = bool(action.flags & rd.ActionFlags.Dispatch)
            is_clear = bool(action.flags & rd.ActionFlags.Clear)
            is_marker = bool(action.flags & rd.ActionFlags.PushMarker)
            is_copy = bool(action.flags & rd.ActionFlags.Copy)
            
            if is_draw or is_dispatch or is_clear or is_copy:
                event = {
                    "event_id": action.eventId,
                    "name": action.GetName(self._controller.GetStructuredFile()),
                    "depth": depth,
                    "debug_marker": marker,
                    "is_draw": is_draw,
                    "is_dispatch": is_dispatch,
                    "is_clear": is_clear,
                    "is_copy": is_copy,
                }
                
                # Add draw-specific data
                if is_draw:
                    event.update({
                        "vertex_count": action.numIndices if action.numIndices > 0 else action.numInstances,
                        "index_count": action.numIndices,
                        "instance_count": action.numInstances,
                        "base_vertex": action.baseVertex,
                        "index_offset": action.indexOffset,
                        "vertex_offset": action.vertexOffset,
                    })
                
                # Add dispatch-specific data
                if is_dispatch:
                    event.update({
                        "dispatch_x": action.dispatchDimension[0],
                        "dispatch_y": action.dispatchDimension[1],
                        "dispatch_z": action.dispatchDimension[2],
                    })
                
                events.append(event)
            
            # Process children
            for child in action.children:
                process_action(child, depth + 1, marker)
        
        # Process all root actions
        for action in self._controller.GetRootActions():
            process_action(action)
        
        return events
    
    def _extract_shaders(self) -> List[Dict[str, Any]]:
        """Extract shader source code and metadata."""
        rd = _get_renderdoc()
        shaders = []
        seen_shaders = set()
        
        # Iterate through events to find unique shaders
        for action in self._controller.GetRootActions():
            self._collect_shaders_from_action(action, shaders, seen_shaders)
        
        return shaders
    
    def _collect_shaders_from_action(self, action: Any, 
                                     shaders: List[Dict], 
                                     seen: set):
        """Recursively collect shaders from actions."""
        rd = _get_renderdoc()
        
        # Only process draw calls
        if action.flags & rd.ActionFlags.Drawcall:
            self._controller.SetFrameEvent(action.eventId, True)
            
            try:
                state = self._controller.GetPipelineState()
                
                # Get shaders for each stage
                for stage in [rd.ShaderStage.Vertex, 
                              rd.ShaderStage.Fragment,
                              rd.ShaderStage.Geometry,
                              rd.ShaderStage.TessControl,
                              rd.ShaderStage.TessEval,
                              rd.ShaderStage.Compute]:
                    
                    shader = state.GetShader(stage)
                    if shader != rd.ResourceId.Null() and shader not in seen:
                        seen.add(shader)
                        
                        shader_info = self._extract_shader_info(shader, stage)
                        if shader_info:
                            shaders.append(shader_info)
                            
            except Exception:
                pass  # Skip if pipeline state not available
        
        # Process children
        for child in action.children:
            self._collect_shaders_from_action(child, shaders, seen)
    
    def _extract_shader_info(self, shader_id: Any, 
                             stage: Any) -> Optional[Dict[str, Any]]:
        """Extract detailed shader information."""
        rd = _get_renderdoc()
        
        try:
            reflection = self._controller.GetShaderReflection(shader_id)
            if not reflection:
                return None
            
            # Get disassembly (source code)
            disasm = self._controller.DisassembleShader(
                self._controller.GetPipelineState().GetGraphicsPipelineObject(),
                reflection,
                ""  # Target (empty for default)
            )
            
            stage_names = {
                rd.ShaderStage.Vertex: "Vertex",
                rd.ShaderStage.Fragment: "Fragment",
                rd.ShaderStage.Geometry: "Geometry",
                rd.ShaderStage.TessControl: "TessControl",
                rd.ShaderStage.TessEval: "TessEval",
                rd.ShaderStage.Compute: "Compute",
            }
            
            return {
                "id": int(shader_id),
                "resource_id": int(shader_id),
                "name": reflection.entryPoint or f"Shader_{shader_id}",
                "stage": stage_names.get(stage, str(stage)),
                "entry_point": reflection.entryPoint,
                "source": disasm if disasm else "",
                "input_count": len(reflection.inputSignature),
                "output_count": len(reflection.outputSignature),
                "cbuffer_count": len(reflection.constantBlocks),
                "texture_count": len(reflection.readOnlyResources),
            }
            
        except Exception:
            return None
    
    def _extract_pipeline_states(self) -> List[Dict[str, Any]]:
        """Extract pipeline states for key events."""
        rd = _get_renderdoc()
        pipeline_states = []
        
        # Sample pipeline states from draw calls
        draw_events = [e for e in self._controller.GetRootActions() 
                       if e.flags & rd.ActionFlags.Drawcall]
        
        # Sample up to 10 draw calls
        sample_events = draw_events[:10] if len(draw_events) > 10 else draw_events
        
        for action in sample_events:
            self._controller.SetFrameEvent(action.eventId, True)
            
            try:
                state = self._controller.GetPipelineState()
                
                ps = {
                    "event_id": action.eventId,
                    "viewport": self._extract_viewport(state),
                    "scissor": self._extract_scissor(state),
                    "rasterizer": self._extract_rasterizer_state(state),
                    "depth_stencil": self._extract_depth_stencil_state(state),
                    "blend": self._extract_blend_state(state),
                    "render_targets": self._extract_render_targets(state),
                }
                pipeline_states.append(ps)
                
            except Exception:
                pass
        
        return pipeline_states
    
    def _extract_viewport(self, state: Any) -> Dict[str, Any]:
        """Extract viewport state."""
        try:
            vp = state.GetViewport(0)
            return {
                "x": vp.x,
                "y": vp.y,
                "width": vp.width,
                "height": vp.height,
                "min_depth": vp.minDepth,
                "max_depth": vp.maxDepth,
            }
        except Exception:
            return {}
    
    def _extract_scissor(self, state: Any) -> Dict[str, Any]:
        """Extract scissor state."""
        try:
            sc = state.GetScissor(0)
            return {
                "x": sc.x,
                "y": sc.y,
                "width": sc.width,
                "height": sc.height,
                "enabled": sc.enabled,
            }
        except Exception:
            return {}
    
    def _extract_rasterizer_state(self, state: Any) -> Dict[str, Any]:
        """Extract rasterizer state."""
        try:
            rs = state.GetRasterizer()
            return {
                "fill_mode": str(rs.fillMode),
                "cull_mode": str(rs.cullMode),
                "front_ccw": rs.frontCCW,
                "depth_bias": rs.depthBias,
                "depth_bias_clamp": rs.depthBiasClamp,
                "slope_scaled_depth_bias": rs.slopeScaledDepthBias,
                "depth_clip": rs.depthClip,
                "scissor_enable": rs.scissorEnable,
                "multisample": rs.multisampleEnable,
                "antialiased_lines": rs.antialiasedLines,
            }
        except Exception:
            return {}
    
    def _extract_depth_stencil_state(self, state: Any) -> Dict[str, Any]:
        """Extract depth/stencil state."""
        try:
            ds = state.GetDepthState()
            return {
                "depth_enable": ds.depthEnable,
                "depth_write": ds.depthWrites,
                "depth_func": str(ds.depthFunction),
                "stencil_enable": ds.stencilEnable,
            }
        except Exception:
            return {}
    
    def _extract_blend_state(self, state: Any) -> Dict[str, Any]:
        """Extract blend state."""
        try:
            blend = state.GetBlend()
            return {
                "alpha_to_coverage": blend.alphaToCoverage,
                "independent_blend": blend.independentBlend,
            }
        except Exception:
            return {}
    
    def _extract_render_targets(self, state: Any) -> List[Dict[str, Any]]:
        """Extract render target information."""
        rd = _get_renderdoc()
        targets = []
        
        try:
            for i in range(8):  # Max 8 render targets
                rt = state.GetOutputTargets()[i] if i < len(state.GetOutputTargets()) else None
                if rt and rt.resourceId != rd.ResourceId.Null():
                    tex = self._controller.GetTexture(rt.resourceId)
                    targets.append({
                        "index": i,
                        "resource_id": int(rt.resourceId),
                        "width": tex.width if tex else 0,
                        "height": tex.height if tex else 0,
                        "format": str(tex.format.Name()) if tex else "",
                    })
        except Exception:
            pass
        
        return targets
    
    def _build_texture_usage_map(self, events: List[Dict], 
                                  textures: List[Dict]) -> Dict[str, Any]:
        """Build a map of texture usage across events."""
        # This is a simplified version - full implementation would
        # track actual bindings per event
        usage = {}
        
        for tex in textures:
            tex_id = str(tex.get("resource_id", tex.get("id")))
            usage[tex_id] = {
                "texture_id": tex_id,
                "name": tex.get("name", ""),
                "usage_count": 0,  # Would be populated by tracking bindings
                "events": [],
            }
        
        return {"textures": usage}


# Convenience function
def load_rdc_to_contract(rdc_path: str,
                         extract_thumbnails: bool = True,
                         extract_shaders: bool = True) -> ReportDataContract:
    """Convenience function to load RDC directly to contract.
    
    Args:
        rdc_path: Path to RDC file
        extract_thumbnails: Whether to extract texture thumbnails
        extract_shaders: Whether to extract shader source code
        
    Returns:
        ReportDataContract instance
        
    Raises:
        ImportError: If renderdoc module is not available
    """
    adapter = RdcAdapter(
        extract_thumbnails=extract_thumbnails,
        extract_shaders=extract_shaders
    )
    return adapter.from_rdc_file(rdc_path)


def load_auto(file_path: str) -> ReportDataContract:
    """Auto-detect file type and load to contract.
    
    Supports:
        - .rdc files (requires renderdoc module)
        - .xml files (always available)
    
    Args:
        file_path: Path to .rdc or .xml file
        
    Returns:
        ReportDataContract instance
    """
    path = Path(file_path)
    
    if path.suffix.lower() == ".xml":
        from .xml_adapter import XmlAdapter
        return XmlAdapter().from_xml_file(str(path))
    
    elif path.suffix.lower() == ".rdc":
        if is_renderdoc_available():
            return load_rdc_to_contract(str(path))
        else:
            raise ImportError(
                f"Cannot load .rdc file directly - renderdoc module not available.\n"
                f"Convert to XML first:\n"
                f"  renderdoccmd convert -c xml -o {path.stem}.xml {path}"
            )
    
    else:
        raise ValueError(f"Unsupported file type: {path.suffix}")
