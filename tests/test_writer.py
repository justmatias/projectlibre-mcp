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


def test_add_task_to_existing(sample_xml, tmp_path):
    from projectlibre_mcp import reader, writer
    out = str(tmp_path / "mas.xml")
    res = writer.add_task(sample_xml, name="Despliegue", duration_days=2, out=out)
    assert res["task_id"] >= 1
    names = sorted(t["name"] for t in reader.list_tasks(out))
    assert "Despliegue" in names


def test_update_task_changes_duration(sample_xml, tmp_path):
    from projectlibre_mcp import reader, writer
    tasks = {t["name"]: t for t in reader.list_tasks(sample_xml)}
    tid = tasks["Diseno"]["id"]
    out = str(tmp_path / "upd.xml")
    writer.update_task(sample_xml, tid, {"duration_days": 8, "percent_complete": 50}, out=out)
    updated = reader.get_task(out, tid)
    assert updated["duration_days"] == 8.0


def test_remove_task(sample_xml, tmp_path):
    from projectlibre_mcp import reader, writer
    tasks = {t["name"]: t for t in reader.list_tasks(sample_xml)}
    tid = tasks["Pruebas"]["id"]
    out = str(tmp_path / "rm.xml")
    writer.remove_task(sample_xml, tid, out=out)
    names = sorted(t["name"] for t in reader.list_tasks(out))
    assert "Pruebas" not in names


def test_update_task_missing_raises(sample_xml, tmp_path):
    import pytest
    from projectlibre_mcp import writer
    with pytest.raises(ValueError, match="no encontrada"):
        writer.update_task(sample_xml, 99999, {"name": "x"}, out=str(tmp_path / "o.xml"))


def test_set_dependency(sample_xml, tmp_path):
    from projectlibre_mcp import reader, writer
    tasks = {t["name"]: t for t in reader.list_tasks(sample_xml)}
    out = str(tmp_path / "dep.xml")
    writer.set_dependency(sample_xml, tasks["Diseno"]["id"], tasks["Pruebas"]["id"],
                          type="FS", out=out)
    pruebas = reader.get_task(out, tasks["Pruebas"]["id"])
    pred_ids = {pr["predecessor_id"] for pr in pruebas["predecessors"]}
    assert tasks["Diseno"]["id"] in pred_ids


def test_assign_resource_creates_resource(sample_xml, tmp_path):
    from projectlibre_mcp import reader, writer
    tasks = {t["name"]: t for t in reader.list_tasks(sample_xml)}
    out = str(tmp_path / "asg.xml")
    writer.assign_resource(sample_xml, tasks["Diseno"]["id"], "Ana", units=50, out=out)
    diseno = reader.get_task(out, tasks["Diseno"]["id"])
    assert "Ana" in diseno["resources"]
