import os


def get_fbx_sdk_root():
    return os.environ.get("FBX_SDK_ROOT")


def resolve_fbx_backend():
    try:
        import fbx  # noqa: F401
        return "python"
    except Exception:
        if get_fbx_sdk_root():
            return "cli"
        return "none"
