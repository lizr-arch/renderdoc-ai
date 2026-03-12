def build_profile(name):
    if name == "unity":
        return {"axis": "Y_UP", "unit": "METER"}
    if name == "unreal":
        return {"axis": "Z_UP", "unit": "CENTIMETER"}
    raise ValueError(f"Unknown profile: {name}")
