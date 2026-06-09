# tests/test_writer.py
from projectlibre_mcp import reader, writer


def test_create_project_round_trip(tmp_path):
    out = str(tmp_path / "nuevo.xml")
    result = writer.create_project(
        name="Tesis",
        start_date="2026-07-01",
        tasks=[
            {"name": "Investigar", "duration_days": 5},
            {"name": "Escribir", "duration_days": 10, "predecessors": [1]},
            {"name": "Defender", "duration_days": 1, "predecessors": ["Escribir"], "is_milestone": True},
        ],
        out=out,
    )
    assert result["task_count"] == 3

    s = reader.summarize_project(out)
    assert s["name"] == "Tesis"
    assert s["task_count"] == 3

    tasks = {t["name"]: t for t in reader.list_tasks(out)}
    assert tasks["Investigar"]["duration_days"] == 5.0
    assert len(tasks["Escribir"]["predecessors"]) == 1
    assert tasks["Defender"]["is_milestone"] is True
    assert len(tasks["Defender"]["predecessors"]) == 1


def test_create_project_rejects_pod_output(tmp_path):
    import pytest
    with pytest.raises(ValueError, match="pod"):
        writer.create_project("X", "2026-01-01", [{"name": "a", "duration_days": 1}],
                              out=str(tmp_path / "x.pod"))
