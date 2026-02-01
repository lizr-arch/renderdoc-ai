from pathlib import Path


def write_repo_skeleton(out_dir, event_id):
    repo_root = (
        Path(out_dir) / "Package" / "Repository" / f"rdc_event_{event_id}.local"
    )
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "resource.repository").write_text("", encoding="utf-8")
    for folder_name in ("Mesh", "Texture", "Material", "Model"):
        (repo_root / folder_name).mkdir(exist_ok=True)
    return repo_root


def build_material_xml(shader_kind, fallback):
    template_name = "Unlit" if fallback == "unlit" else fallback
    return f"<Material Template=\"{template_name}\" />"
