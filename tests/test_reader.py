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
