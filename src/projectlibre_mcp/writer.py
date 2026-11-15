# src/projectlibre_mcp/writer.py
"""Lógica de creación y edición de proyectos. Escribe MSPDI XML."""
import datetime
import math
import re

import jpype

from .io import load_project, save_xml
from .jvm import core
from .model import is_real_task

_RELTYPE = {
    "FS": "FINISH_START",
    "SS": "START_START",
    "FF": "FINISH_FINISH",
    "SF": "START_FINISH",
}


_SPEC_KEYS = (
    "name", "duration_days", "predecessors", "resource", "percent_complete", "is_milestone",
)
_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


def _reltype(code):
    key = str(code).strip().upper()
    if key not in _RELTYPE:
        raise ValueError(
            f"Tipo de dependencia inválido: {code!r}. Válidos: {', '.join(_RELTYPE)}"
        )
    return getattr(core().RelationType, _RELTYPE[key])


def _number(value, label, minimum=None, maximum=None, exclusive_minimum=False):
    """Convierte a float validando que sea numérico finito y esté en rango."""
    if isinstance(value, bool):
        raise ValueError(f"{label} debe ser numérico, se recibió {value!r}")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} debe ser numérico, se recibió {value!r}") from None
    if not math.isfinite(number):
        raise ValueError(f"{label} debe ser un número finito, se recibió {value!r}")
    if minimum is not None and (number <= minimum if exclusive_minimum else number < minimum):
        relation = "mayor que" if exclusive_minimum else "mayor o igual a"
        raise ValueError(f"{label} debe ser {relation} {minimum:g}, se recibió {value!r}")
    if maximum is not None and number > maximum:
        raise ValueError(f"{label} debe ser menor o igual a {maximum:g}, se recibió {value!r}")
    return number


def _parse_bool(value, label):
    """Booleano estricto: bool, 0/1 o los textos true/false/1/0."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("true", "1"):
            return True
        if text in ("false", "0"):
            return False
    raise ValueError(
        f"{label} debe ser booleano (true/false, 1/0), se recibió {value!r}"
    )


def _parse_date(value, label):
    """Fecha estricta YYYY-MM-DD, devuelta como (año, mes, día)."""
    text = value if isinstance(value, str) else ""
    try:
        if not _DATE_PATTERN.fullmatch(text.strip()):
            raise ValueError
        parsed = datetime.date.fromisoformat(text.strip())
    except ValueError:
        raise ValueError(
            f"{label} inválida: {value!r}. Usa el formato YYYY-MM-DD con una fecha real"
        ) from None
    return parsed.year, parsed.month, parsed.day


def _require_name(value, label):
    """Nombre de tarea: texto no vacío."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} es obligatorio y debe ser un texto no vacío")
    return value


def _validate_spec(index, spec):
    """Valida la forma de una tarea de create_project (index 1-based)."""
    label = f"Tarea {index}"
    if not isinstance(spec, dict):
        raise ValueError(f"{label}: debe ser un objeto/dict, se recibió {type(spec).__name__}")
    unknown = set(spec) - set(_SPEC_KEYS)
    if unknown:
        raise ValueError(
            f"{label}: claves no reconocidas {sorted(unknown, key=str)}. "
            f"Válidas: {list(_SPEC_KEYS)}"
        )
    _require_name(spec.get("name"), f"{label}: 'name'")
    predecessors = spec.get("predecessors")
    if predecessors is not None and not isinstance(predecessors, list):
        raise ValueError(
            f"{label}: 'predecessors' debe ser una lista de índices 1-based o nombres, "
            f"se recibió {predecessors!r}"
        )
    resource = spec.get("resource")
    if resource is not None and (not isinstance(resource, str) or not resource.strip()):
        raise ValueError(f"{label}: 'resource' debe ser un texto no vacío, se recibió {resource!r}")
    _number(spec.get("duration_days", 1), f"{label}: duration_days", minimum=0)
    if spec.get("percent_complete") is not None:
        _number(spec["percent_complete"], f"{label}: percent_complete", minimum=0, maximum=100)
    _parse_bool(spec.get("is_milestone", False), f"{label}: is_milestone")


def _next_id(items, getter):
    """Siguiente entero libre = max(getter(x)) + 1 sobre items (1 si no hay ninguno)."""
    return max((int(getter(x)) for x in items if getter(x) is not None), default=0) + 1


def _make_task(project, name, duration_days, percent_complete=None, is_milestone=False):
    duration_days = _number(duration_days, "duration_days", minimum=0)
    if percent_complete is not None:
        percent_complete = _number(percent_complete, "percent_complete", minimum=0, maximum=100)
    is_milestone = _parse_bool(is_milestone, "is_milestone")
    c = core()
    t = project.addTask()
    t.setName(name)
    t.setDuration(c.Duration.getInstance(float(duration_days), c.TimeUnit.DAYS))
    if percent_complete is not None:
        t.setPercentageComplete(jpype.JDouble(float(percent_complete)))
    if is_milestone:
        t.setMilestone(True)
    return t


def _task_label(task):
    return f"{task.getName()!s} (id={int(task.getUniqueID())})"


def _predecessor_graph(project):
    """Grafo UID de tarea -> set de UIDs de sus predecesores."""
    graph = {}
    for task in project.getTasks():
        if task.getUniqueID() is None:
            continue
        relations = task.getPredecessors() or []
        graph[int(task.getUniqueID())] = {
            int(r.getPredecessorTask().getUniqueID())
            for r in relations
            if r.getPredecessorTask() is not None
            and r.getPredecessorTask().getUniqueID() is not None
        }
    return graph


_CYCLE_LABEL_LIMIT = 10


def _check_new_dependency(project, pred, succ, graph=None):
    """Valida que añadir pred como predecesor de succ no sea auto-dependencia,
    duplicado ni cree un ciclo. Lanza ValueError en español."""
    pred_uid, succ_uid = int(pred.getUniqueID()), int(succ.getUniqueID())
    if pred_uid == succ_uid:
        raise ValueError(f"Una tarea no puede depender de sí misma: {_task_label(pred)}")
    if graph is None:
        graph = _predecessor_graph(project)
    if pred_uid in graph.get(succ_uid, set()):
        raise ValueError(
            f"La dependencia ya existe: {_task_label(pred)} -> {_task_label(succ)} "
            "(solo se admite un vínculo por par de tareas; no se puede cambiar su tipo ni lag)"
        )
    # Ciclo si pred depende (transitivamente) de succ: buscar succ hacia atrás desde pred.
    parent = {pred_uid: None}
    stack = [pred_uid]
    while stack:
        node = stack.pop()
        if node == succ_uid:
            path = []
            while node is not None:
                path.append(node)
                node = parent[node]
            # path: succ ... pred en orden de flujo; la nueva relación pred -> succ cierra el ciclo
            cycle = path + [path[0]]
            if len(cycle) > _CYCLE_LABEL_LIMIT:
                half = _CYCLE_LABEL_LIMIT // 2
                shown = cycle[:half] + [None] + cycle[-half:]
            else:
                shown = cycle
            labels = [
                f"… ({len(path)} tareas en total)" if uid is None
                else _task_label(project.getTaskByUniqueID(jpype.JInt(uid)))
                for uid in shown
            ]
            raise ValueError("La dependencia crearía un ciclo: " + " -> ".join(labels))
        for before in graph.get(node, ()):
            if before not in parent:
                parent[before] = node
                stack.append(before)


def _link(project, predecessor_id, successor_id, rtype="FS", lag_days=0):
    relation_type = _reltype(rtype)
    lag_days = _number(lag_days, "lag_days")
    c = core()
    pred = project.getTaskByUniqueID(jpype.JInt(int(predecessor_id)))
    succ = project.getTaskByUniqueID(jpype.JInt(int(successor_id)))
    if pred is None or succ is None or not is_real_task(pred) or not is_real_task(succ):
        raise ValueError(f"Tarea no encontrada: pred={predecessor_id} succ={successor_id}")
    _check_new_dependency(project, pred, succ)
    builder = c.Relation.Builder().predecessorTask(pred).type(relation_type)
    if lag_days:
        builder = builder.lag(c.Duration.getInstance(float(lag_days), c.TimeUnit.DAYS))
    succ.addPredecessor(builder)


def _assign(project, task, resource_name, units=100):
    units = _number(units, "units", minimum=0, exclusive_minimum=True)
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
    start = _parse_date(start_date, "start_date") if start_date else None
    for index, spec in enumerate(tasks, start=1):
        _validate_spec(index, spec)
    names = [spec["name"] for spec in tasks]

    c = core()
    from java.time import LocalDateTime

    p = c.ProjectFile()
    props = p.getProjectProperties()
    if name:
        props.setName(name)
    if start:
        y, m, d = start
        props.setStartDate(LocalDateTime.of(y, m, d, 8, 0))
    p.addDefaultBaseCalendar()

    created = []
    for spec in tasks:
        created.append(_make_task(
            p, spec["name"], spec.get("duration_days", 1),
            spec.get("percent_complete"), spec.get("is_milestone", False),
        ))

    name_to_task = {str(t.getName()): t for t in created}
    graph = _predecessor_graph(p)  # se mantiene en Python para no recorrer el proyecto por vínculo
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
                if names.count(key) > 1:
                    raise ValueError(
                        f"Predecesor por nombre ambiguo: {key!r} aparece en "
                        f"{names.count(key)} tareas; usa el índice 1-based"
                    )
                pred_task = name_to_task[key]
            _check_new_dependency(p, pred_task, created[i], graph)
            builder = c.Relation.Builder().predecessorTask(pred_task).type(_reltype("FS"))
            created[i].addPredecessor(builder)
            graph.setdefault(int(created[i].getUniqueID()), set()).add(int(pred_task.getUniqueID()))
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
    if t is None or not is_real_task(t):
        raise ValueError(f"Tarea no encontrada: id={task_id}")
    return t


def add_task(file, name, duration_days, predecessors=None, resource=None, out=None):
    _require_name(name, "name")
    _number(duration_days, "duration_days", minimum=0)
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
    if not fields:
        raise ValueError(f"update_task requiere al menos un campo. Válidos: {sorted(allowed)}")
    if "duration_days" in fields:
        duration = _number(fields["duration_days"], "duration_days", minimum=0)
    if "percent_complete" in fields:
        percent = _number(fields["percent_complete"], "percent_complete", minimum=0, maximum=100)
    if "is_milestone" in fields:
        milestone = _parse_bool(fields["is_milestone"], "is_milestone")
    if "start" in fields:
        start = _parse_date(fields["start"], "start")
    c = core()
    p = load_project(file)
    t = _get_task_or_raise(p, task_id)
    if "name" in fields:
        t.setName(_require_name(fields["name"], "name"))
    if "duration_days" in fields:
        t.setDuration(c.Duration.getInstance(duration, c.TimeUnit.DAYS))
    if "percent_complete" in fields:
        t.setPercentageComplete(jpype.JDouble(percent))
    if "is_milestone" in fields:
        t.setMilestone(milestone)
    if "start" in fields:
        from java.time import LocalDateTime
        y, m, d = start
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
