import pathlib
import sys

import pytest

SCRIPT_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))


def test_extract_mesh_shader_requires_event():
    from extract_mesh_shader import extract_mesh_shader

    with pytest.raises(ValueError):
        extract_mesh_shader(rdc_path="x.rdc", event_id=None, out_dir="out")


class _FakeBuffer:
    def __init__(self, resource_id, byte_offset, byte_size, byte_stride=0):
        self.resourceId = resource_id
        self.byteOffset = byte_offset
        self.byteSize = byte_size
        self.byteStride = byte_stride


class _FakeD3D11InputAssembly:
    def __init__(self, vertex_buffers, index_buffer):
        self.vertexBuffers = vertex_buffers
        self.indexBuffer = index_buffer


class _FakeD3D11Pipe:
    def __init__(self, ia):
        self.inputAssembly = ia


class _FakeVKVertexInput:
    def __init__(self, vertex_buffers):
        self.vertexBuffers = vertex_buffers


class _FakeVKInputAssembly:
    def __init__(self, index_buffer):
        self.indexBuffer = index_buffer


class _FakeVKPipe:
    def __init__(self, vi, ia):
        self.vertexInput = vi
        self.inputAssembly = ia


class _FakePipeState:
    def __init__(self, d3d11=None, vk=None):
        self._d3d11 = d3d11
        self._vk = vk

    def GetD3D11PipelineState(self):
        return self._d3d11

    def GetVulkanPipelineState(self):
        return self._vk


class _FakeAPIProps:
    def __init__(self, pipeline_type):
        self.pipelineType = pipeline_type


class _FakeController:
    def __init__(self, pipeline_type, pipe_state):
        self._props = _FakeAPIProps(pipeline_type)
        self._pipe = pipe_state
        self._last_event = None

    def SetFrameEvent(self, event_id, _apply):
        self._last_event = event_id

    def GetPipelineState(self):
        return self._pipe

    def GetAPIProperties(self):
        return self._props

    def GetBufferData(self, _resource_id, _offset, length):
        return bytes([0xAB]) * int(length)


def _make_fake_d3d11_controller():
    vbs = [_FakeBuffer(10, 0, 16, 8)]
    ib = _FakeBuffer(20, 0, 12)
    ia = _FakeD3D11InputAssembly(vbs, ib)
    pipe = _FakePipeState(d3d11=_FakeD3D11Pipe(ia))
    return _FakeController("D3D11", pipe)


def _make_fake_vk_controller():
    vbs = [_FakeBuffer(11, 4, 20, 12)]
    ib = _FakeBuffer(21, 2, 10)
    vi = _FakeVKVertexInput(vbs)
    ia = _FakeVKInputAssembly(ib)
    pipe = _FakePipeState(vk=_FakeVKPipe(vi, ia))
    return _FakeController("Vulkan", pipe)


def test_extract_mesh_shader_writes_vb_ib(tmp_path):
    from extract_mesh_shader import _extract_buffers

    controller = _make_fake_d3d11_controller()
    _extract_buffers(controller, event_id=100, out_dir=tmp_path)

    assert (tmp_path / "vertex_buffers").exists()
    assert (tmp_path / "index_buffers").exists()
