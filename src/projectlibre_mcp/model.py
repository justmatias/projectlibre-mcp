# src/projectlibre_mcp/model.py
"""Conversión de objetos Java de MPXJ a dicts serializables."""
from .jvm import pkg


def jstr(v):
    return None if v is None else str(v)


def jfloat(v):
    return None if v is None else float(v)


def jbool(v):
    return None if v is None else bool(v)


def duration_in_days(duration, project):
    """Convierte una Duration de MPXJ a días (float) usando las propiedades del proyecto.

    Las unidades transcurridas (ELAPSED_*) se convierten a días transcurridos
    (24 h por día); el resto, a días laborables según horas/día y días/semana
    del archivo. Devuelve None si no hay duración.
    """
    if duration is None:
        return None
    time_unit = pkg("org.mpxj").TimeUnit
    target = time_unit.ELAPSED_DAYS if duration.getUnits().isElapsed() else time_unit.DAYS
    converted = duration.convertUnits(target, project.getProjectProperties())
    return round(float(converted.getDuration()), 4)


def relation_dict(rel):
    lag = rel.getLag()
    return {
        "predecessor_id": int(rel.getPredecessorTask().getUniqueID()),
        "type": jstr(rel.getType()),       # "FS", "SS", "FF", "SF"
        "lag_days": duration_in_days(lag, rel.getSuccessorTask().getParentFile()),
    }


def task_to_dict(task):
    dur = task.getDuration()
    preds = task.getPredecessors()
    pred_list = [relation_dict(r) for r in preds] if preds is not None else []
    assigns = task.getResourceAssignments()
    resources = []
    if assigns is not None:
        for a in assigns:
            res = a.getResource()
            if res is not None and res.getName() is not None:
                resources.append(str(res.getName()))
    return {
        "id": int(task.getUniqueID()),
        "name": jstr(task.getName()),
        "start": jstr(task.getStart()),
        "finish": jstr(task.getFinish()),
        "duration": jstr(dur),
        "duration_days": duration_in_days(dur, task.getParentFile()),
        "percent_complete": jfloat(task.getPercentageComplete()),
        "is_milestone": jbool(task.getMilestone()),
        "is_critical": jbool(task.getCritical()),
        "predecessors": pred_list,
        "resources": resources,
    }
