# EAP Validator Fixtures

These fixtures are small synthetic `*.rmeta.json` samples for validator regression tests.

They are not real captures and intentionally avoid private project paths, real asset names, shader
source, screenshots, or `.rdc` binary data.

## Files

| File | Purpose |
|---|---|
| `valid_minimal.rmeta.json` | Smallest useful Engine Annotation Protocol sidecar shape. |
| `valid_fullish.rmeta.json` | Broader synthetic sidecar with render graph, commands, resources, assets, shaders, pipeline, rules, diagnostics, and security sections. |
| `invalid_wrong_schema.rmeta.json` | JSON object that is not an EAP sidecar; used to preserve `invalid_sidecar` behavior. |
| `golden/*.validator.json` | Normalized expected `eap_validator.py validate --json` results. Paths are replaced with `<FIXTURE_PATH>` by tests before comparison. |
