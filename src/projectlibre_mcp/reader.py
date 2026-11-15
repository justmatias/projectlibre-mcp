# src/projectlibre_mcp/reader.py
"""Lógica de lectura y análisis de proyectos."""
import jpype

from .io import load_project
from .model import duration_in_days, jfloat, jstr, task_to_dict


def _named_tasks(project):
    return [t for t in project.getTasks() if t.getName() is not None]


def _project_duration_days(props):
    """Días-calendario entre inicio y fin del proyecto (None si falta alguno)."""
    try:
        start = props.getStartDate()
        finish = props.getFinishDate()
        if start is None or finish is None:
            return None
        from java.time.temporal import ChronoUnit
        return int(ChronoUnit.DAYS.between(start, finish))
    except Exception:  # noqa: BLE001
        return None


def _avg_percent_complete(tasks):
    """Promedio de % de avance de las tareas con valor (None si ninguna)."""
    vals = [jfloat(t.getPercentageComplete()) for t in tasks]
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def summarize_project(path):
    p = load_project(path)
    props = p.getProjectProperties()
    tasks = _named_tasks(p)
    resources = [r for r in p.getResources() if r.getName() is not None]
    milestones = [str(t.getName()) for t in tasks if t.getMilestone()]
    return {
        "name": jstr(props.getName()),
        "start": jstr(props.getStartDate()),
        "finish": jstr(props.getFinishDate()),
        "duration_days": _project_duration_days(props),
        "percent_complete": _avg_percent_complete(tasks),
        "task_count": len(tasks),
        "resource_count": len(resources),
        "milestones": milestones,
    }


def list_tasks(path, only_critical=False):
    p = load_project(path)
    out = [task_to_dict(t) for t in _named_tasks(p)]
    if only_critical:
        out = [t for t in out if t["is_critical"]]
    return out


def get_task(path, task_id):
    p = load_project(path)
    t = p.getTaskByUniqueID(jpype.JInt(int(task_id)))
    if t is None or t.getName() is None:
        raise ValueError(f"Tarea no encontrada: id={task_id}")
    return task_to_dict(t)


def list_resources(path):
    p = load_project(path)
    # agrupar asignaciones por uniqueID de recurso (Resource no tiene getResourceAssignments)
    assigns_by_res = {}
    for t in p.getTasks():
        ras = t.getResourceAssignments()
        if ras is None:
            continue
        for a in ras:
            res = a.getResource()
            if res is None:
                continue
            rid = int(res.getUniqueID())
            task = a.getTask()
            assigns_by_res.setdefault(rid, []).append({
                "task_id": int(task.getUniqueID()) if task is not None else None,
                "task_name": jstr(task.getName()) if task is not None else None,
                "units": jfloat(a.getUnits()),
                "work": jstr(a.getWork()),
            })
    out = []
    for r in p.getResources():
        if r.getName() is None:
            continue
        rid = int(r.getUniqueID())
        out.append({
            "id": rid,
            "name": jstr(r.getName()),
            "type": jstr(r.getType()),
            "max_units": jfloat(r.getMaxUnits()),
            "assignments": assigns_by_res.get(rid, []),
        })
    return out


def critical_path(path):
    p = load_project(path)
    tasks = _named_tasks(p)
    rows = []
    crit_ids = []
    for t in tasks:
        crit = t.getCritical()
        is_crit = bool(crit) if crit is not None else False
        if is_crit:
            crit_ids.append(int(t.getUniqueID()))
        rows.append({
            "id": int(t.getUniqueID()),
            "name": jstr(t.getName()),
            "is_critical": is_crit,
            "total_slack": jstr(t.getTotalSlack()),
            "free_slack": jstr(t.getFreeSlack()),
            "total_slack_days": duration_in_days(t.getTotalSlack(), p),
            "free_slack_days": duration_in_days(t.getFreeSlack(), p),
        })
    return {"critical_task_ids": crit_ids, "tasks": rows}
