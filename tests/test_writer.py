# tests/test_writer.py
import pytest

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


def test_add_task_no_id_collision_after_remove(tmp_path):
    """Regresión C1: cargar -> remove_task -> add_task no debe producir IDs duplicados
    aunque MPXJ deje IDs no-densos tras el remove."""
    import jpype
    from projectlibre_mcp import io, writer
    base = str(tmp_path / "base.xml")
    writer.create_project(
        "Reg", "2026-01-01",
        [{"name": f"T{i}", "duration_days": 1} for i in range(1, 6)],
        out=base,
    )
    removed = str(tmp_path / "removed.xml")
    writer.remove_task(base, 2, out=removed)  # deja IDs no-densos
    out = str(tmp_path / "added.xml")
    writer.add_task(removed, name="Nueva", duration_days=1, out=out)
    p = io.load_project(out)
    ids = [int(t.getID()) for t in p.getTasks()
           if t.getName() is not None and t.getID() is not None]
    assert len(ids) == len(set(ids)), f"IDs duplicados tras add_task: {sorted(ids)}"


def test_create_project_bad_predecessor_index_raises(tmp_path):
    """M3: índice de predecesor fuera de rango -> ValueError claro (no IndexError)."""
    import pytest
    from projectlibre_mcp import writer
    with pytest.raises(ValueError, match="rango"):
        writer.create_project(
            "X", "2026-01-01",
            [{"name": "a", "duration_days": 1},
             {"name": "b", "duration_days": 1, "predecessors": [9]}],
            out=str(tmp_path / "x.xml"),
        )


def test_update_task_rejects_unknown_field(sample_xml, tmp_path):
    import pytest
    from projectlibre_mcp import reader, writer
    tasks = {t["name"]: t for t in reader.list_tasks(sample_xml)}
    tid = tasks["Diseno"]["id"]
    with pytest.raises(ValueError, match="no reconocidos"):
        writer.update_task(sample_xml, tid, {"duration": 8}, out=str(tmp_path / "o.xml"))


def _first_task_id(sample_xml):
    from projectlibre_mcp import reader
    return {t["name"]: t for t in reader.list_tasks(sample_xml)}["Diseno"]["id"]


def test_set_dependency_rejects_unknown_type(sample_xml, tmp_path):
    import pytest
    from projectlibre_mcp import writer
    with pytest.raises(ValueError, match="FS, SS, FF, SF"):
        writer.set_dependency(sample_xml, 1, 3, type="XX", out=str(tmp_path / "o.xml"))


def test_set_dependency_accepts_lowercase_type(sample_xml, tmp_path):
    from projectlibre_mcp import reader, writer
    task_ids = {task["name"]: task["id"] for task in reader.list_tasks(sample_xml)}
    out = str(tmp_path / "output.xml")
    writer.set_dependency(sample_xml, task_ids["Diseno"], task_ids["Pruebas"], type="ss", out=out)
    predecessors = reader.get_task(out, task_ids["Pruebas"])["predecessors"]
    assert {"predecessor_id": task_ids["Diseno"], "type": "SS"} in [
        {"predecessor_id": relation["predecessor_id"], "type": relation["type"]}
        for relation in predecessors
    ]


def test_set_dependency_rejects_non_numeric_lag(sample_xml, tmp_path):
    import pytest
    from projectlibre_mcp import writer
    with pytest.raises(ValueError, match="lag_days"):
        writer.set_dependency(sample_xml, 1, 3, lag_days="mucho", out=str(tmp_path / "o.xml"))


def test_update_task_is_milestone_false_string_is_false(sample_xml, tmp_path):
    from projectlibre_mcp import reader, writer
    task_id = _first_task_id(sample_xml)
    out = str(tmp_path / "o.xml")
    writer.update_task(sample_xml, task_id, {"is_milestone": "false"}, out=out)
    assert reader.get_task(out, task_id)["is_milestone"] is False


def test_update_task_is_milestone_rejects_garbage(sample_xml, tmp_path):
    import pytest
    from projectlibre_mcp import writer
    with pytest.raises(ValueError, match="is_milestone"):
        writer.update_task(sample_xml, _first_task_id(sample_xml), {"is_milestone": "maybe"},
                           out=str(tmp_path / "o.xml"))


def test_create_project_is_milestone_false_string_is_false(tmp_path):
    from projectlibre_mcp import reader, writer
    out = str(tmp_path / "n.xml")
    writer.create_project("X", "2026-01-01",
                          [{"name": "a", "duration_days": 1, "is_milestone": " False "}], out=out)
    assert reader.list_tasks(out)[0]["is_milestone"] is False


def test_create_project_rejects_unknown_spec_key(tmp_path):
    import pytest
    from projectlibre_mcp import writer
    with pytest.raises(ValueError, match="Tarea 2.*duration"):
        writer.create_project("X", "2026-01-01",
                              [{"name": "a"}, {"name": "b", "duration": 5}],
                              out=str(tmp_path / "n.xml"))


def test_create_project_rejects_non_dict_spec(tmp_path):
    import pytest
    from projectlibre_mcp import writer
    with pytest.raises(ValueError, match="Tarea 1"):
        writer.create_project("X", "2026-01-01", ["a"], out=str(tmp_path / "n.xml"))


def test_create_project_requires_task_name(tmp_path):
    import pytest
    from projectlibre_mcp import writer
    with pytest.raises(ValueError, match="name"):
        writer.create_project("X", "2026-01-01", [{"duration_days": 2}],
                              out=str(tmp_path / "n.xml"))


def test_create_project_rejects_blank_task_name(tmp_path):
    import pytest
    from projectlibre_mcp import writer
    with pytest.raises(ValueError, match="name"):
        writer.create_project("X", "2026-01-01", [{"name": "  "}], out=str(tmp_path / "n.xml"))


def test_create_project_duration_defaults_to_one_day(tmp_path):
    from projectlibre_mcp import reader, writer
    out = str(tmp_path / "n.xml")
    writer.create_project("X", "2026-01-01", [{"name": "a"}], out=out)
    assert reader.list_tasks(out)[0]["duration_days"] == 1.0


def test_create_project_rejects_ambiguous_predecessor_name(tmp_path):
    import pytest
    from projectlibre_mcp import writer
    with pytest.raises(ValueError, match="ambiguo"):
        writer.create_project(
            "X", "2026-01-01",
            [{"name": "a"}, {"name": "a"}, {"name": "b", "predecessors": ["a"]}],
            out=str(tmp_path / "n.xml"))


def test_create_project_rejects_impossible_start_date(tmp_path):
    import pytest
    from projectlibre_mcp import writer
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        writer.create_project("X", "2026-02-30", [{"name": "a"}], out=str(tmp_path / "n.xml"))


def test_create_project_rejects_slash_start_date(tmp_path):
    import pytest
    from projectlibre_mcp import writer
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        writer.create_project("X", "2026/06/01", [{"name": "a"}], out=str(tmp_path / "n.xml"))


def test_update_task_rejects_invalid_start_date(sample_xml, tmp_path):
    import pytest
    from projectlibre_mcp import writer
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        writer.update_task(sample_xml, _first_task_id(sample_xml), {"start": "2026-13-01"},
                           out=str(tmp_path / "o.xml"))


def test_update_task_valid_start_date(sample_xml, tmp_path):
    from projectlibre_mcp import reader, writer
    task_id = _first_task_id(sample_xml)
    out = str(tmp_path / "o.xml")
    writer.update_task(sample_xml, task_id, {"start": "2026-06-15"}, out=out)
    assert str(reader.get_task(out, task_id)["start"]).startswith("2026-06-15")


def test_create_project_rejects_negative_duration(tmp_path):
    import pytest
    from projectlibre_mcp import writer
    with pytest.raises(ValueError, match="duration_days"):
        writer.create_project("X", "2026-01-01", [{"name": "a", "duration_days": -1}],
                              out=str(tmp_path / "n.xml"))


def test_create_project_rejects_non_numeric_duration(tmp_path):
    import pytest
    from projectlibre_mcp import writer
    with pytest.raises(ValueError, match="duration_days"):
        writer.create_project("X", "2026-01-01", [{"name": "a", "duration_days": "abc"}],
                              out=str(tmp_path / "n.xml"))


def test_create_project_rejects_percent_out_of_range(tmp_path):
    import pytest
    from projectlibre_mcp import writer
    with pytest.raises(ValueError, match="percent_complete"):
        writer.create_project("X", "2026-01-01", [{"name": "a", "percent_complete": 101}],
                              out=str(tmp_path / "n.xml"))


def test_add_task_rejects_negative_duration(sample_xml, tmp_path):
    import pytest
    from projectlibre_mcp import writer
    with pytest.raises(ValueError, match="duration_days"):
        writer.add_task(sample_xml, "Nueva", -2, out=str(tmp_path / "o.xml"))


def test_update_task_rejects_negative_duration(sample_xml, tmp_path):
    import pytest
    from projectlibre_mcp import writer
    with pytest.raises(ValueError, match="duration_days"):
        writer.update_task(sample_xml, _first_task_id(sample_xml), {"duration_days": -1},
                           out=str(tmp_path / "o.xml"))


def test_update_task_rejects_percent_out_of_range(sample_xml, tmp_path):
    import pytest
    from projectlibre_mcp import writer
    with pytest.raises(ValueError, match="percent_complete"):
        writer.update_task(sample_xml, _first_task_id(sample_xml), {"percent_complete": -5},
                           out=str(tmp_path / "o.xml"))


def test_update_task_rejects_empty_fields(sample_xml, tmp_path):
    import pytest
    from projectlibre_mcp import writer
    out = tmp_path / "o.xml"
    with pytest.raises(ValueError, match="al menos un campo"):
        writer.update_task(sample_xml, _first_task_id(sample_xml), {}, out=str(out))
    assert not out.exists()


def test_assign_resource_rejects_non_positive_units(sample_xml, tmp_path):
    import pytest
    from projectlibre_mcp import writer
    with pytest.raises(ValueError, match="units"):
        writer.assign_resource(sample_xml, _first_task_id(sample_xml), "Ana", units=0,
                               out=str(tmp_path / "o.xml"))


def test_create_project_rejects_predecessors_not_a_list(tmp_path):
    with pytest.raises(ValueError, match="predecessors"):
        writer.create_project("P", "2026-06-09", [
            {"name": "A"},
            {"name": "B", "predecessors": "A"},
        ], str(tmp_path / "output.xml"))


def test_create_project_rejects_non_text_resource(tmp_path):
    with pytest.raises(ValueError, match="resource"):
        writer.create_project("P", "2026-06-09", [{"name": "A", "resource": 5}],
                              str(tmp_path / "output.xml"))


def test_add_task_rejects_empty_name(sample_xml, tmp_path):
    output = tmp_path / "output.xml"
    with pytest.raises(ValueError, match="name"):
        writer.add_task(sample_xml, "  ", 1, out=str(output))
    assert not output.exists()


def test_update_task_rejects_empty_name(sample_xml, tmp_path):
    output = tmp_path / "output.xml"
    with pytest.raises(ValueError, match="name"):
        writer.update_task(sample_xml, _first_task_id(sample_xml), {"name": ""}, out=str(output))
    assert not output.exists()
def _task_ids(path):
    return {t["name"]: t["id"] for t in reader.list_tasks(path)}


def test_set_dependency_rejects_self_dependency(sample_xml, tmp_path):
    import pytest
    ids = _task_ids(sample_xml)
    out = tmp_path / "self.xml"
    with pytest.raises(ValueError, match="sí misma"):
        writer.set_dependency(sample_xml, ids["Diseno"], ids["Diseno"], out=str(out))
    assert not out.exists()


def test_set_dependency_rejects_direct_cycle(sample_xml, tmp_path):
    import pytest
    ids = _task_ids(sample_xml)
    out = tmp_path / "cycle.xml"
    # Diseno -> Construccion ya existe; el inverso cierra un ciclo de 2.
    with pytest.raises(ValueError, match="ciclo"):
        writer.set_dependency(sample_xml, ids["Construccion"], ids["Diseno"], out=str(out))
    assert not out.exists()


def test_set_dependency_rejects_transitive_cycle(sample_xml, tmp_path):
    import pytest
    ids = _task_ids(sample_xml)
    out = tmp_path / "transitive.xml"
    # Diseno -> Construccion -> Pruebas; Pruebas -> Diseno cierra un ciclo de 3.
    with pytest.raises(ValueError, match="ciclo") as error:
        writer.set_dependency(sample_xml, ids["Pruebas"], ids["Diseno"], out=str(out))
    assert "Diseno" in str(error.value) and "Construccion" in str(error.value)
    assert not out.exists()


def test_set_dependency_rejects_duplicate(sample_xml, tmp_path):
    import pytest
    ids = _task_ids(sample_xml)
    out = tmp_path / "duplicate.xml"
    with pytest.raises(ValueError, match="ya existe"):
        writer.set_dependency(sample_xml, ids["Diseno"], ids["Construccion"], out=str(out))
    assert not out.exists()


def test_set_dependency_valid_dag_still_works(sample_xml, tmp_path):
    ids = _task_ids(sample_xml)
    out = str(tmp_path / "dag.xml")
    writer.set_dependency(sample_xml, ids["Diseno"], ids["Pruebas"], out=out)
    pruebas = reader.get_task(out, ids["Pruebas"])
    assert ids["Diseno"] in {pr["predecessor_id"] for pr in pruebas["predecessors"]}


def test_add_task_with_valid_predecessors(sample_xml, tmp_path):
    ids = _task_ids(sample_xml)
    out = str(tmp_path / "added.xml")
    result = writer.add_task(sample_xml, "Nueva", 1, predecessors=[ids["Pruebas"]], out=out)
    nueva = reader.get_task(out, result["task_id"])
    assert ids["Pruebas"] in {pr["predecessor_id"] for pr in nueva["predecessors"]}


def test_create_project_rejects_self_reference(tmp_path):
    import pytest
    out = tmp_path / "self.xml"
    with pytest.raises(ValueError, match="sí misma"):
        writer.create_project(
            "X", "2026-01-01",
            [{"name": "a", "duration_days": 1, "predecessors": [1]}],
            out=str(out),
        )
    assert not out.exists()


def test_create_project_rejects_cycle(tmp_path):
    import pytest
    out = tmp_path / "cycle.xml"
    with pytest.raises(ValueError, match="ciclo"):
        writer.create_project(
            "X", "2026-01-01",
            [{"name": "a", "duration_days": 1, "predecessors": ["c"]},
             {"name": "b", "duration_days": 1, "predecessors": ["a"]},
             {"name": "c", "duration_days": 1, "predecessors": [2]}],
            out=str(out),
        )
    assert not out.exists()


def test_create_project_valid_dag_with_forward_reference(tmp_path):
    out = str(tmp_path / "dag.xml")
    writer.create_project(
        "X", "2026-01-01",
        [{"name": "a", "duration_days": 1, "predecessors": [2]},
         {"name": "b", "duration_days": 1}],
        out=out,
    )
    tasks = {t["name"]: t for t in reader.list_tasks(out)}
    assert len(tasks["a"]["predecessors"]) == 1


def test_set_dependency_accepts_diamond(sample_xml, tmp_path):
    task_ids = {task["name"]: task["id"] for task in reader.list_tasks(sample_xml)}
    output = str(tmp_path / "output.xml")
    writer.set_dependency(sample_xml, task_ids["Diseno"], task_ids["Pruebas"], out=output)
    predecessor_ids = {
        relation["predecessor_id"] for relation in reader.get_task(output, task_ids["Pruebas"])["predecessors"]
    }
    assert predecessor_ids == {task_ids["Diseno"], task_ids["Construccion"]}


def test_set_dependency_cycle_leaves_input_unchanged(sample_xml):
    task_ids = {task["name"]: task["id"] for task in reader.list_tasks(sample_xml)}
    with open(sample_xml, encoding="utf-8") as handle:
        before = handle.read()
    with pytest.raises(ValueError, match="ciclo"):
        writer.set_dependency(sample_xml, task_ids["Pruebas"], task_ids["Diseno"])
    with open(sample_xml, encoding="utf-8") as handle:
        assert handle.read() == before


def test_create_project_long_cycle_message_is_truncated(tmp_path):
    task_count = 50
    tasks = [{"name": f"T{number}", "predecessors": [number - 1] if number > 1 else [task_count]}
             for number in range(1, task_count + 1)]
    with pytest.raises(ValueError, match="ciclo") as error:
        writer.create_project("P", "2026-06-09", tasks, str(tmp_path / "output.xml"))
    assert "50 tareas en total" in str(error.value)
    assert len(str(error.value)) < 1000


def test_create_project_large_chain_is_fast(tmp_path):
    import time
    tasks = [{"name": f"T{number}", "predecessors": [number - 1] if number > 1 else []}
             for number in range(1, 1001)]
    started = time.perf_counter()
    writer.create_project("P", "2026-06-09", tasks, str(tmp_path / "output.xml"))
    assert time.perf_counter() - started < 10

def test_update_unnamed_task(special_rows_xml, tmp_path):
    out = str(tmp_path / "updated.xml")
    writer.update_task(special_rows_xml, 2, {"name": "Con nombre", "duration_days": 6}, out=out)
    task = reader.get_task(out, 2)
    assert task["name"] == "Con nombre"
    assert task["duration_days"] == 6.0


def test_assign_resource_to_unnamed_task(special_rows_xml, tmp_path):
    out = str(tmp_path / "assigned.xml")
    writer.assign_resource(special_rows_xml, 2, "Imanol", out=out)
    assert reader.get_task(out, 2)["resources"] == ["Imanol"]


def test_remove_unnamed_task(special_rows_xml, tmp_path):
    out = str(tmp_path / "removed.xml")
    writer.remove_task(special_rows_xml, 2, out=out)
    assert [t["id"] for t in reader.list_tasks(out)] == [1]


def test_writer_rejects_summary_and_null_rows(special_rows_xml, tmp_path):
    out = str(tmp_path / "never.xml")
    for task_id in (0, 3):
        with pytest.raises(ValueError):
            writer.remove_task(special_rows_xml, task_id, out=out)


def test_set_dependency_rejects_summary_and_null_rows(special_rows_xml, tmp_path):
    output = tmp_path / "output.xml"
    for task_id in (0, 3):
        with pytest.raises(ValueError, match="no encontrada"):
            writer.set_dependency(special_rows_xml, task_id, 1, out=str(output))
    assert not output.exists()
