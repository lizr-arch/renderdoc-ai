import os
from pathlib import Path


def find_fbx_cli():
    cli_path = os.environ.get("FBX_CLI_PATH")
    if cli_path and Path(cli_path).exists():
        return Path(cli_path)
    sdk_root = get_fbx_sdk_root()
    if sdk_root:
        candidate = Path(sdk_root) / "tools" / "fbx_cli.exe"
        if candidate.exists():
            return candidate
    return None


def get_fbx_sdk_root():
    return os.environ.get("FBX_SDK_ROOT")


def resolve_fbx_backend():
    try:
        import fbx  # noqa: F401
        return "python"
    except Exception:
        if find_fbx_cli() or get_fbx_sdk_root():
            return "cli"
        return "none"


def _load_obj(obj_path):
    positions = []
    indices = []
    for line in Path(obj_path).read_text(encoding="utf-8").splitlines():
        if line.startswith("v "):
            parts = line.split()
            positions.append((float(parts[1]), float(parts[2]), float(parts[3])))
        elif line.startswith("f "):
            parts = line.split()[1:]
            for part in parts:
                v_idx = part.split("/")[0]
                indices.append(int(v_idx) - 1)
    return positions, indices


def _apply_profile(scene, profile):
    import fbx

    axis = profile.get("axis")
    unit = profile.get("unit")
    if axis == "Y_UP":
        fbx.FbxAxisSystem.MayaYUp.ConvertScene(scene)
    elif axis == "Z_UP":
        fbx.FbxAxisSystem.DirectX.ConvertScene(scene)

    if unit == "METER":
        fbx.FbxSystemUnit.m.ConvertScene(scene)
    elif unit == "CENTIMETER":
        fbx.FbxSystemUnit.cm.ConvertScene(scene)


def _convert_with_python(obj_path, out_path, profile):
    import fbx

    positions, indices = _load_obj(obj_path)
    manager = fbx.FbxManager.Create()
    ios = fbx.FbxIOSettings.Create(manager, fbx.IOSROOT)
    manager.SetIOSettings(ios)

    scene = fbx.FbxScene.Create(manager, "Scene")
    mesh = fbx.FbxMesh.Create(scene, "mesh")
    mesh.InitControlPoints(len(positions))
    for idx, vertex in enumerate(positions):
        mesh.SetControlPointAt(fbx.FbxVector4(vertex[0], vertex[1], vertex[2]), idx)

    for idx in range(0, len(indices), 3):
        tri = indices[idx:idx + 3]
        if len(tri) < 3:
            break
        mesh.BeginPolygon()
        mesh.AddPolygon(tri[0])
        mesh.AddPolygon(tri[1])
        mesh.AddPolygon(tri[2])
        mesh.EndPolygon()

    node = fbx.FbxNode.Create(scene, "meshNode")
    node.SetNodeAttribute(mesh)
    scene.GetRootNode().AddChild(node)

    _apply_profile(scene, profile)

    exporter = fbx.FbxExporter.Create(manager, "")
    if not exporter.Initialize(str(out_path), -1, manager.GetIOSettings()):
        raise RuntimeError("Failed to initialize FBX exporter")
    exporter.Export(scene)
    exporter.Destroy()
    manager.Destroy()


def _convert_with_cli(obj_path, out_path, profile):
    cli_path = find_fbx_cli()
    if not cli_path:
        raise RuntimeError("FBX CLI not found. Set FBX_CLI_PATH.")
    axis = profile.get("axis", "Y_UP")
    unit = profile.get("unit", "METER")
    cmd = [str(cli_path), "--in", str(obj_path), "--out", str(out_path), "--axis", axis, "--unit", unit]
    raise RuntimeError(f"FBX CLI not implemented yet. Command: {' '.join(cmd)}")


def convert_obj_to_fbx(obj_path, out_path, profile, backend):
    if backend == "python":
        return _convert_with_python(obj_path, out_path, profile)
    if backend == "cli":
        return _convert_with_cli(obj_path, out_path, profile)
    raise RuntimeError("FBX backend not available")
