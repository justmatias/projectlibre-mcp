# src/projectlibre_mcp/model.py
"""Conversión de objetos Java de MPXJ a dicts serializables."""


def jstr(v):
    return None if v is None else str(v)


def jfloat(v):
    return None if v is None else float(v)


def jbool(v):
    return None if v is None else bool(v)


def relation_dict(rel):
    lag = rel.getLag()
    return {
        "predecessor_id": int(rel.getPredecessorTask().getUniqueID()),
        "type": jstr(rel.getType()),       # "FS", "SS", "FF", "SF"
        "lag_days": jfloat(lag.getDuration()) if lag is not None else None,
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
        "duration_days": jfloat(dur.getDuration()) if dur is not None else None,
        "percent_complete": jfloat(task.getPercentageComplete()),
        "is_milestone": jbool(task.getMilestone()),
        "is_critical": jbool(task.getCritical()),
        "predecessors": pred_list,
        "resources": resources,
    }
