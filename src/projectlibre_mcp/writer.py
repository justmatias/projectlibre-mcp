# src/projectlibre_mcp/writer.py
"""Lógica de creación y edición de proyectos. Escribe MSPDI XML."""
import jpype

from .io import load_project, save_xml
from .jvm import core

_RELTYPE = {
    "FS": "FINISH_START",
    "SS": "START_START",
    "FF": "FINISH_FINISH",
    "SF": "START_FINISH",
}


def _reltype(code):
    name = _RELTYPE.get(str(code).upper(), "FINISH_START")
    return getattr(core().RelationType, name)


def _next_id(items, getter):
    """Siguiente entero libre = max(getter(x)) + 1 sobre items (1 si no hay ninguno)."""
    return max((int(getter(x)) for x in items if getter(x) is not None), default=0) + 1


def _make_task(project, name, duration_days, percent_complete=None, is_milestone=False):
    c = core()
    t = project.addTask()
    t.setName(name)
    t.setDuration(c.Duration.getInstance(float(duration_days), c.TimeUnit.DAYS))
    if percent_complete is not None:
        t.setPercentageComplete(jpype.JDouble(float(percent_complete)))
    if is_milestone:
        t.setMilestone(True)
    return t


def _link(project, predecessor_id, successor_id, rtype="FS", lag_days=0):
    c = core()
    pred = project.getTaskByUniqueID(jpype.JInt(int(predecessor_id)))
    succ = project.getTaskByUniqueID(jpype.JInt(int(successor_id)))
    if pred is None or succ is None:
        raise ValueError(f"Tarea no encontrada: pred={predecessor_id} succ={successor_id}")
    builder = c.Relation.Builder().predecessorTask(pred).type(_reltype(rtype))
    if lag_days:
        builder = builder.lag(c.Duration.getInstance(float(lag_days), c.TimeUnit.DAYS))
    succ.addPredecessor(builder)


def _assign(project, task, resource_name, units=100):
    res = None
    for r in project.getResources():
        if r.getName() is not None and str(r.getName()) == resource_name:
            res = r
            break
    if res is None:
        # MPXJ no auto-asigna UniqueID a recursos nuevos en un proyecto cargado.
        new_ruid = _next_id(list(project.getResources()), lambda r: r.getUniqueID())
        res = project.addResource()
        res.setName(resource_name)
        res.setUniqueID(jpype.JInt(new_ruid))
    a = task.addResourceAssignment(res)
    a.setUnits(jpype.JDouble(float(units)))
    return res


def create_project(name, start_date, tasks, out):
    """Crea un proyecto desde cero y lo escribe como MSPDI .xml.

    tasks: lista de dicts con name, duration_days, y opcionales:
        predecessors (lista de índices 1-based o nombres), resource, percent_complete, is_milestone.
    """
    c = core()
    from java.time import LocalDateTime

    p = c.ProjectFile()
    props = p.getProjectProperties()
    if name:
        props.setName(name)
    if start_date:
        y, m, d = (int(x) for x in start_date.split("-"))
        props.setStartDate(LocalDateTime.of(y, m, d, 8, 0))
    p.addDefaultBaseCalendar()

    created = []
    for spec in tasks:
        created.append(_make_task(
            p, spec["name"], spec.get("duration_days", 1),
            spec.get("percent_complete"), spec.get("is_milestone", False),
        ))

    name_to_task = {str(t.getName()): t for t in created}
    for i, spec in enumerate(tasks):
        for pre in (spec.get("predecessors") or []):
            if isinstance(pre, bool):
                raise ValueError(f"predecessor inválido (bool): {pre!r}")
            if isinstance(pre, int):
                if not (1 <= pre <= len(created)):
                    raise ValueError(
                        f"Índice de predecesor fuera de rango: {pre} "
                        f"(hay {len(created)} tareas, índices válidos 1..{len(created)})"
                    )
                pred_task = created[pre - 1]
            else:
                key = str(pre)
                if key not in name_to_task:
                    raise ValueError(f"Predecesor por nombre no encontrado: {key!r}")
                pred_task = name_to_task[key]
            builder = c.Relation.Builder().predecessorTask(pred_task).type(_reltype("FS"))
            created[i].addPredecessor(builder)
        if spec.get("resource"):
            _assign(p, created[i], spec["resource"], 100)

    save_xml(p, out)
    return {"out": out, "task_count": len(created)}


def _resolve_out(file, out):
    """Determina la ruta de salida .xml. .pod nunca se sobrescribe."""
    if out:
        return out
    if file.lower().endswith(".xml"):
        return file  # sobrescribir el .xml de entrada
    raise ValueError(
        "La entrada no es .xml: especifica 'out' (.xml). No se sobrescribe .pod."
    )


def _get_task_or_raise(project, task_id):
    t = project.getTaskByUniqueID(jpype.JInt(int(task_id)))
    if t is None or t.getName() is None:
        raise ValueError(f"Tarea no encontrada: id={task_id}")
    return t


def add_task(file, name, duration_days, predecessors=None, resource=None, out=None):
    p = load_project(file)
    # En un proyecto cargado, MPXJ no auto-asigna UniqueID/ID; calcularlos con
    # max+1 (no con un conteo) para no colisionar con IDs existentes no-densos.
    existing = list(p.getTasks())
    new_uid = _next_id(existing, lambda t: t.getUniqueID())
    new_id = _next_id(existing, lambda t: t.getID())
    t = _make_task(p, name, duration_days)
    t.setUniqueID(jpype.JInt(new_uid))
    t.setID(jpype.JInt(new_id))
    for pid in (predecessors or []):
        _link(p, pid, new_uid, "FS", 0)
    if resource:
        _assign(p, t, resource, 100)
    out = _resolve_out(file, out)
    save_xml(p, out)
    return {"out": out, "task_id": new_uid}


def update_task(file, task_id, fields, out=None):
    allowed = {"name", "duration_days", "percent_complete", "is_milestone", "start"}
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(
            f"Campos no reconocidos en update_task: {sorted(unknown)}. "
            f"Válidos: {sorted(allowed)}"
        )
    c = core()
    p = load_project(file)
    t = _get_task_or_raise(p, task_id)
    if "name" in fields:
        t.setName(fields["name"])
    if "duration_days" in fields:
        t.setDuration(c.Duration.getInstance(float(fields["duration_days"]), c.TimeUnit.DAYS))
    if "percent_complete" in fields:
        t.setPercentageComplete(jpype.JDouble(float(fields["percent_complete"])))
    if "is_milestone" in fields:
        t.setMilestone(bool(fields["is_milestone"]))
    if "start" in fields:
        from java.time import LocalDateTime
        y, m, d = (int(x) for x in str(fields["start"]).split("-"))
        t.setStart(LocalDateTime.of(y, m, d, 8, 0))
    out = _resolve_out(file, out)
    save_xml(p, out)
    return {"out": out, "task_id": int(task_id)}


def remove_task(file, task_id, out=None):
    p = load_project(file)
    t = _get_task_or_raise(p, task_id)
    p.removeTask(t)
    out = _resolve_out(file, out)
    save_xml(p, out)
    return {"out": out, "removed": int(task_id)}


def set_dependency(file, predecessor_id, successor_id, type="FS", lag_days=0, out=None):
    p = load_project(file)
    _link(p, predecessor_id, successor_id, type, lag_days)
    out = _resolve_out(file, out)
    save_xml(p, out)
    return {"out": out, "predecessor_id": int(predecessor_id), "successor_id": int(successor_id)}


def assign_resource(file, task_id, resource_name, units=100, out=None):
    p = load_project(file)
    t = _get_task_or_raise(p, task_id)
    _assign(p, t, resource_name, units)
    out = _resolve_out(file, out)
    save_xml(p, out)
    return {"out": out, "task_id": int(task_id), "resource": resource_name}
