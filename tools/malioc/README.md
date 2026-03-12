# Mali Offline Compiler (Arm Performance Studio 2026.0)

**Version (verified):** Mali Offline Compiler v8.8.1 (Build 73b41e)

## Location
- Repo copy: 	ools/malioc/2026.0/mali_offline_compiler/
- Executable: 	ools/malioc/2026.0/mali_offline_compiler/malioc.exe

## Typical usage

### Check version
`
 tools/malioc/2026.0/mali_offline_compiler/malioc.exe --version
`

### List supported GPU cores
`
tools/malioc/2026.0/mali_offline_compiler/malioc.exe --list
`

### Show GPU core details
`
tools/malioc/2026.0/mali_offline_compiler/malioc.exe --info --core Mali-G78
`

### Analyze a SPIR-V shader (JSON)
`
tools/malioc/2026.0/mali_offline_compiler/malioc.exe --spirv shader.spv --core Mali-G78 --format json
`

### Analyze a SPIR-V shader (text)
`
tools/malioc/2026.0/mali_offline_compiler/malioc.exe --spirv shader.spv --core Mali-G78
`

## Notes
- For Vulkan SPIR-V only (DXBC/DXIL not supported).
- Performance data is static analysis (no runtime counters).
- Texture unit timing in reports assumes bilinear filtering.
