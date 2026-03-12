def build_manifest(event_id: int, api: str, mesh: dict, textures: list, shaders: dict) -> dict:
    return {
        "eventId": event_id,
        "api": api,
        "mesh": mesh,
        "textures": textures,
        "shaders": shaders,
    }
