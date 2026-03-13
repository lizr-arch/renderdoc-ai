# Skill Snapshot Consumer Brief

## Snapshot Facts
Source: snapshot.v1
- capture_name: g145_capture
- graphics_api: Vulkan
- schema_version: snapshot.v1
- action_count: 148

## Gap Analysis
Source: snapshot.v1
| field_path | reason_layer | supplementable | mcp_method | reason |
| --- | --- | --- | --- | --- |
| timings | schema_declared_gap | true | get_action_timings | Declared in snapshot availability/preflight as missing. |
| pipelines | schema_declared_gap | true | get_pipeline_state | Declared in snapshot availability/preflight as missing. |
| resources.textures.thumbnail | schema_declared_gap | true | get_texture_data | Declared in snapshot availability/preflight as missing. |
| passes | schema_declared_gap | false | None | Declared in snapshot availability/preflight as missing. |

## MCP Supplement
Source: MCP query
- execute: False
- status: dry_run
- planned_queries: 38
- bridge_calls: 0

## Command List
1. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_action_timings --params '{}'`
2. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_pipeline_state --params '{"event_id":1600}'`
3. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_pipeline_state --params '{"event_id":1604}'`
4. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_pipeline_state --params '{"event_id":1610}'`
5. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_pipeline_state --params '{"event_id":1614}'`
6. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_pipeline_state --params '{"event_id":1621}'`
7. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"101725","sample":0,"slice":0}'`
8. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"1097","sample":0,"slice":0}'`
9. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"114499","sample":0,"slice":0}'`
10. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"114508","sample":0,"slice":0}'`
11. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"114517","sample":0,"slice":0}'`
12. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"116949","sample":0,"slice":0}'`
13. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"118489","sample":0,"slice":0}'`
14. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"118491","sample":0,"slice":0}'`
15. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"118517","sample":0,"slice":0}'`
16. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"118523","sample":0,"slice":0}'`
17. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"118551","sample":0,"slice":0}'`
18. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"119202","sample":0,"slice":0}'`
19. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"119763","sample":0,"slice":0}'`
20. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"120007","sample":0,"slice":0}'`
21. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"120083","sample":0,"slice":0}'`
22. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"120238","sample":0,"slice":0}'`
23. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"128636","sample":0,"slice":0}'`
24. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"128645","sample":0,"slice":0}'`
25. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"129251","sample":0,"slice":0}'`
26. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"129253","sample":0,"slice":0}'`
27. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"130067","sample":0,"slice":0}'`
28. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"130069","sample":0,"slice":0}'`
29. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"130693","sample":0,"slice":0}'`
30. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"131325","sample":0,"slice":0}'`
31. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"132366","sample":0,"slice":0}'`
32. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"133174","sample":0,"slice":0}'`
33. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"133176","sample":0,"slice":0}'`
34. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"133187","sample":0,"slice":0}'`
35. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"133193","sample":0,"slice":0}'`
36. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"1359","sample":0,"slice":0}'`
37. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"136347","sample":0,"slice":0}'`
38. `py -3 scripts/rdc_analyzer/mcp_examples/run_query.py --method get_texture_data --params '{"mip":0,"resource_id":"1369","sample":0,"slice":0}'`
