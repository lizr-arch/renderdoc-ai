def build_mesh_schema():
    return {
        "axis": "unknown",
        "unit_scale": 1.0,
        "topology": "triangle_list",
        "vertex_layout": [],
        "index_format": "uint16",
        "vertex_count": 0,
        "index_count": 0,
    }


def build_material_schema():
    return {
        "name": "",
        "shader": "",
        "textures": [],
        "constants": [],
    }


def build_shader_schema():
    return {
        "stage": "",
        "bytecode_format": "",
        "entry": "main",
        "disassembly": "",
    }


def build_texture_schema():
    return {
        "resource_id": 0,
        "format": "",
        "width": 0,
        "height": 0,
        "mips": 1,
        "colorspace": "",
    }
