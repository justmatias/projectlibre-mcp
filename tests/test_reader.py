# tests/test_reader.py
import pytest

from projectlibre_mcp import reader


def test_summarize_project(sample_xml):
    s = reader.summarize_project(sample_xml)
    assert s["name"] == "Demo"
    assert s["task_count"] == 3
    assert s["resource_count"] == 1


def test_list_tasks_returns_all(sample_xml):
    tasks = reader.list_tasks(sample_xml)
    names = sorted(t["name"] for t in tasks)
    assert names == ["Construccion", "Diseno", "Pruebas"]


def test_get_task_by_id(sample_xml):
    tasks = reader.list_tasks(sample_xml)
    first = tasks[0]
    detail = reader.get_task(sample_xml, first["id"])
    assert detail["id"] == first["id"]
    assert detail["name"] == first["name"]


def test_get_task_missing_raises(sample_xml):
    with pytest.raises(ValueError, match="no encontrada"):
        reader.get_task(sample_xml, 99999)


# tests/test_reader.py (agregar al final)
def test_list_resources(sample_xml):
    from projectlibre_mcp import reader
    res = reader.list_resources(sample_xml)
    assert len(res) == 1
    imanol = res[0]
    assert imanol["name"] == "Imanol"
    # tiene 1 asignación: a "Construccion"
    assert len(imanol["assignments"]) == 1
    assert imanol["assignments"][0]["task_name"] == "Construccion"


def test_critical_path_shape(sample_xml):
    from projectlibre_mcp import reader
    cp = reader.critical_path(sample_xml)
    assert set(cp) == {"critical_task_ids", "tasks"}
    assert len(cp["tasks"]) == 3
    for t in cp["tasks"]:
        assert set(t) >= {"id", "name", "is_critical", "total_slack", "free_slack"}


def test_summarize_includes_duration_and_percent(sample_xml):
    from projectlibre_mcp import reader
    s = reader.summarize_project(sample_xml)
    assert "duration_days" in s
    assert "percent_complete" in s
