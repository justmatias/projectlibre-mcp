# tests/test_server_smoke.py
import asyncio


def test_tools_registered_with_correct_schema():
    from projectlibre_mcp.server import mcp

    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    expected = {
        "summarize_project", "list_tasks", "get_task", "list_resources", "critical_path",
        "create_project", "add_task", "update_task", "remove_task",
        "set_dependency", "assign_resource",
    }
    assert expected <= names, f"faltan tools: {expected - names}"

    by = {t.name: t for t in tools}
    # el schema NO debe colapsar a {kwargs} (lección osu-mcp): verificar properties reales
    sd = by["set_dependency"].inputSchema.get("properties", {})
    assert "predecessor_id" in sd and "successor_id" in sd, sd
    cp = by["create_project"].inputSchema.get("properties", {})
    assert "name" in cp and "tasks" in cp and "out" in cp, cp
    st = by["summarize_project"].inputSchema.get("properties", {})
    assert "file" in st, st
