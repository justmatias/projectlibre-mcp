# tests/test_model.py
from projectlibre_mcp import io, model


def test_task_to_dict_has_expected_fields(sample_xml):
    p = io.load_project(sample_xml)
    by_name = {str(t.getName()): t for t in p.getTasks() if t.getName() is not None}
    d = model.task_to_dict(by_name["Construccion"])
    assert d["name"] == "Construccion"
    assert d["duration_days"] == 5.0
    assert d["id"] >= 1
    # Construccion depende de Diseno (FS)
    assert len(d["predecessors"]) == 1
    assert d["predecessors"][0]["type"] == "FS"
    # tiene recurso Imanol
    assert "Imanol" in d["resources"]


def test_relation_dict_shape(sample_xml):
    p = io.load_project(sample_xml)
    by_name = {str(t.getName()): t for t in p.getTasks() if t.getName() is not None}
    rels = list(by_name["Pruebas"].getPredecessors())
    rd = model.relation_dict(rels[0])
    assert set(rd) == {"predecessor_id", "type", "lag_days"}
    assert rd["type"] == "FS"
    assert rd["lag_days"] == 0.0


def _tasks_by_name(path):
    project = io.load_project(path)
    return {str(t.getName()): t for t in project.getTasks() if t.getName() is not None}


def test_duration_in_hours_is_reported_in_days(hours_xml):
    by_name = _tasks_by_name(hours_xml)
    assert model.task_to_dict(by_name["A"])["duration_days"] == 2.0
    assert model.task_to_dict(by_name["B"])["duration_days"] == 1.0


def test_lag_in_hours_is_reported_in_days(hours_xml):
    by_name = _tasks_by_name(hours_xml)
    predecessor = model.task_to_dict(by_name["B"])["predecessors"][0]
    assert predecessor["lag_days"] == 1.0


def test_elapsed_duration_is_reported_in_elapsed_days(hours_xml):
    by_name = _tasks_by_name(hours_xml)
    assert model.task_to_dict(by_name["C"])["duration_days"] == 2.0


def test_duration_days_none_when_duration_missing(hours_xml):
    assert model.duration_in_days(None, None) is None
