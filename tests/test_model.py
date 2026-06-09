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
