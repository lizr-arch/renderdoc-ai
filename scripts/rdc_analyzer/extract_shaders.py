#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Shader Extraction Script for RenderDoc Python Shell

This script should be run inside RenderDoc's Python Shell environment.
It extracts shader source code from the currently loaded capture.

Usage in RenderDoc Python Shell:
    exec(open(r'd:\Code\git\renderdoc\scripts\rdc_analyzer\extract_shaders.py').read())
"""

import os
import json

# Configuration
OUTPUT_DIR = r'd:\Code\git\renderdoc\scripts\rdc_analyzer\extracted_shaders'
MAX_SHADERS = 50  # Limit to avoid excessive processing

def ensure_dir(path):
    """Create directory if not exists"""
    if not os.path.exists(path):
        os.makedirs(path)

def get_shader_source(controller, shader_id, entry_point='main'):
    """Try to get shader source from reflection or disassembly"""
    try:
        # Try to get disassembly with source
        targets = controller.GetDisassemblyTargets(True)
        
        # Prefer GLSL or human-readable format
        preferred = ['GLSL', 'HLSL', 'SPIR-V']
        target = None
        
        for pref in preferred:
            for t in targets:
                if pref.lower() in str(t).lower():
                    target = t
                    break
            if target:
                break
        
        if not target and targets:
            target = targets[0]
        
        if target:
            source = controller.DisassembleShader(
                controller.GetPipelineState().GetShaderPipeline(),
                controller.GetPipelineState().GetShaderReflection(renderdoc.ShaderStage.Vertex),
                target
            )
            return source, str(target)
    except Exception as e:
        pass
    
    return None, None

def extract_all_shaders():
    """Main extraction function"""
    global pyrenderdoc
    
    # Access the global controller
    if 'pyrenderdoc' not in dir():
        print("[ERROR] This script must be run inside RenderDoc Python Shell")
        return
    
    ctx = pyrenderdoc.CurrentContext()
    if not ctx:
        print("[ERROR] No capture loaded. Please load an RDC file first.")
        return
    
    controller = pyrenderdoc.ReplayManager().GetCurrentController()
    if not controller:
        print("[ERROR] No replay controller available.")
        return
    
    ensure_dir(OUTPUT_DIR)
    
    # Get all draw actions
    actions = controller.GetRootActions()
    
    # Flatten action tree
    def flatten_actions(action_list):
        result = []
        for action in action_list:
            result.append(action)
            if len(action.children) > 0:
                result.extend(flatten_actions(action.children))
        return result
    
    all_actions = flatten_actions(actions)
    
    # Filter draw calls
    draw_actions = [a for a in all_actions if a.flags & renderdoc.ActionFlags.Drawcall]
    
    print(f"[INFO] Found {len(draw_actions)} draw calls")
    
    extracted = []
    seen_shaders = set()
    
    for i, action in enumerate(draw_actions[:MAX_SHADERS]):
        try:
            # Move to this event
            controller.SetFrameEvent(action.eventId, True)
            
            state = controller.GetPipelineState()
            
            # Get shader IDs
            vs_refl = state.GetShaderReflection(renderdoc.ShaderStage.Vertex)
            ps_refl = state.GetShaderReflection(renderdoc.ShaderStage.Fragment)
            
            shader_info = {
                'eventId': action.eventId,
                'drawName': action.customName if action.customName else f'Draw_{action.eventId}',
            }
            
            # Extract Vertex Shader
            if vs_refl:
                vs_id = str(state.GetShader(renderdoc.ShaderStage.Vertex))
                if vs_id not in seen_shaders:
                    seen_shaders.add(vs_id)
                    try:
                        targets = controller.GetDisassemblyTargets(True)
                        if targets:
                            vs_source = controller.DisassembleShader(
                                state.GetGraphicsPipelineObject(),
                                vs_refl,
                                targets[0]
                            )
                            if vs_source:
                                vs_file = f"vs_{action.eventId}.glsl"
                                vs_path = os.path.join(OUTPUT_DIR, vs_file)
                                with open(vs_path, 'w', encoding='utf-8') as f:
                                    f.write(vs_source)
                                shader_info['vertex_shader'] = vs_file
                                shader_info['vs_target'] = str(targets[0])
                    except Exception as e:
                        shader_info['vs_error'] = str(e)
            
            # Extract Fragment Shader  
            if ps_refl:
                ps_id = str(state.GetShader(renderdoc.ShaderStage.Fragment))
                if ps_id not in seen_shaders:
                    seen_shaders.add(ps_id)
                    try:
                        targets = controller.GetDisassemblyTargets(True)
                        if targets:
                            ps_source = controller.DisassembleShader(
                                state.GetGraphicsPipelineObject(),
                                ps_refl,
                                targets[0]
                            )
                            if ps_source:
                                ps_file = f"ps_{action.eventId}.glsl"
                                ps_path = os.path.join(OUTPUT_DIR, ps_file)
                                with open(ps_path, 'w', encoding='utf-8') as f:
                                    f.write(ps_source)
                                shader_info['fragment_shader'] = ps_file
                                shader_info['ps_target'] = str(targets[0])
                    except Exception as e:
                        shader_info['ps_error'] = str(e)
            
            if 'vertex_shader' in shader_info or 'fragment_shader' in shader_info:
                extracted.append(shader_info)
                print(f"[OK] Event {action.eventId}: Extracted shaders")
            
        except Exception as e:
            print(f"[WARN] Event {action.eventId}: {e}")
            continue
    
    # Save manifest
    manifest_path = os.path.join(OUTPUT_DIR, 'manifest.json')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump({
            'total_draws': len(draw_actions),
            'extracted': len(extracted),
            'shaders': extracted
        }, f, indent=2)
    
    print(f"\n[DONE] Extracted {len(extracted)} unique shader sets")
    print(f"[INFO] Output directory: {OUTPUT_DIR}")
    print(f"[INFO] Manifest: {manifest_path}")

# Auto-run when executed
if __name__ == '__main__' or 'pyrenderdoc' in dir():
    extract_all_shaders()
