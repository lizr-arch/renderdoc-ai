"""
RDC/SPIR-V 常量定义
===================

包含 RDC 文件格式和 SPIR-V 二进制的常量。

从 rdc_parser.py 提取，用于模块化解析。
"""

# ============================================================================
# RDC 文件格式常量
# ============================================================================

RDC_MAGIC = 0x434F4452  # 'RDOC' in little-endian (实际存储为 RDOC)
RDC_MAGIC_BYTES = b'RDOC'

# 文件版本
RDC_VERSION_1_0 = 0x00000100
RDC_VERSION_1_1 = 0x00000101
RDC_VERSION_1_2 = 0x00000102

# Chunk 标志
CHUNK_INDEX_MASK = 0x0000FFFF
CHUNK_CALLSTACK = 0x00010000
CHUNK_THREAD_ID = 0x00020000
CHUNK_DURATION = 0x00040000
CHUNK_TIMESTAMP = 0x00080000
CHUNK_64BIT_SIZE = 0x00100000

# 对齐
CHUNK_ALIGNMENT = 64

# ============================================================================
# SPIR-V 常量
# ============================================================================

SPIRV_MAGIC = 0x07230203

# SPIR-V OpCodes (重要的)
SPIRV_OP_NAME = 5           # OpName: 给ID命名
SPIRV_OP_ENTRY_POINT = 15   # OpEntryPoint: 入口点定义
SPIRV_OP_SOURCE = 3         # OpSource: 源语言信息

# SPIR-V Execution Model (用于识别 shader 类型)
SPIRV_EXEC_VERTEX = 0
SPIRV_EXEC_TESSELLATION_CONTROL = 1
SPIRV_EXEC_TESSELLATION_EVALUATION = 2
SPIRV_EXEC_GEOMETRY = 3
SPIRV_EXEC_FRAGMENT = 4
SPIRV_EXEC_GLCOMPUTE = 5
SPIRV_EXEC_KERNEL = 6
SPIRV_EXEC_TASK_NV = 5267
SPIRV_EXEC_MESH_NV = 5268
SPIRV_EXEC_RAY_GENERATION_KHR = 5313
SPIRV_EXEC_INTERSECTION_KHR = 5314
SPIRV_EXEC_ANY_HIT_KHR = 5315
SPIRV_EXEC_CLOSEST_HIT_KHR = 5316
SPIRV_EXEC_MISS_KHR = 5317
SPIRV_EXEC_CALLABLE_KHR = 5318

SPIRV_EXEC_MODEL_NAMES = {
    SPIRV_EXEC_VERTEX: "Vertex",
    SPIRV_EXEC_TESSELLATION_CONTROL: "TessControl",
    SPIRV_EXEC_TESSELLATION_EVALUATION: "TessEval",
    SPIRV_EXEC_GEOMETRY: "Geometry",
    SPIRV_EXEC_FRAGMENT: "Fragment",
    SPIRV_EXEC_GLCOMPUTE: "Compute",
    SPIRV_EXEC_KERNEL: "Kernel",
    SPIRV_EXEC_TASK_NV: "TaskNV",
    SPIRV_EXEC_MESH_NV: "MeshNV",
    SPIRV_EXEC_RAY_GENERATION_KHR: "RayGen",
    SPIRV_EXEC_INTERSECTION_KHR: "Intersection",
    SPIRV_EXEC_ANY_HIT_KHR: "AnyHit",
    SPIRV_EXEC_CLOSEST_HIT_KHR: "ClosestHit",
    SPIRV_EXEC_MISS_KHR: "Miss",
    SPIRV_EXEC_CALLABLE_KHR: "Callable",
}

# ============================================================================
# Driver Chunk Base
# ============================================================================

FIRST_DRIVER_CHUNK = 1000
