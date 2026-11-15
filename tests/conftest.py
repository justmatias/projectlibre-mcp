# tests/conftest.py
import importlib

import mpxj  # noqa: F401
import jpype
import pytest


@pytest.fixture(scope="session", autouse=True)
def _jvm():
    if not jpype.isJVMStarted():
        jpype.startJVM()


@pytest.fixture()
def sample_xml(tmp_path, _jvm):
    """Crea un proyecto MSPDI de muestra: 3 tareas encadenadas + 1 recurso.

    Diseno(3d) -> Construccion(5d, recurso Imanol) -> Pruebas(2d).
    """
    c = importlib.import_module("org.mpxj")
    from java.time import LocalDateTime

    p = c.ProjectFile()
    props = p.getProjectProperties()
    props.setName("Demo")
    props.setStartDate(LocalDateTime.of(2026, 6, 9, 8, 0))
    p.addDefaultBaseCalendar()

    t1 = p.addTask(); t1.setName("Diseno"); t1.setDuration(c.Duration.getInstance(3, c.TimeUnit.DAYS))
    t2 = p.addTask(); t2.setName("Construccion"); t2.setDuration(c.Duration.getInstance(5, c.TimeUnit.DAYS))
    t3 = p.addTask(); t3.setName("Pruebas"); t3.setDuration(c.Duration.getInstance(2, c.TimeUnit.DAYS))

    t2.addPredecessor(c.Relation.Builder().predecessorTask(t1).type(c.RelationType.FINISH_START))
    t3.addPredecessor(c.Relation.Builder().predecessorTask(t2).type(c.RelationType.FINISH_START))

    r = p.addResource(); r.setName("Imanol")
    a = t2.addResourceAssignment(r); a.setUnits(jpype.JDouble(100.0))

    w = importlib.import_module("org.mpxj.writer")
    out = str(tmp_path / "demo.xml")
    w.UniversalProjectWriter(w.FileFormat.MSPDI).write(p, out)
    return out


@pytest.fixture()
def hours_xml(tmp_path, _jvm):
    """Proyecto MSPDI con duracion y lag expresados en horas (jornada de 8h).

    Tarea A (16h) -> Tarea B (8h) con lag FS de 8h; Tarea C con duracion en
    ELAPSED_DAYS (2). A tiene holgura total de 16h y libre de 8h.
    """
    c = importlib.import_module("org.mpxj")
    from java.time import LocalDateTime

    p = c.ProjectFile()
    p.getProjectProperties().setStartDate(LocalDateTime.of(2026, 6, 9, 8, 0))
    p.addDefaultBaseCalendar()

    task_a = p.addTask(); task_a.setName("A"); task_a.setDuration(c.Duration.getInstance(16, c.TimeUnit.HOURS))
    task_b = p.addTask(); task_b.setName("B"); task_b.setDuration(c.Duration.getInstance(8, c.TimeUnit.HOURS))
    task_c = p.addTask(); task_c.setName("C"); task_c.setDuration(c.Duration.getInstance(2, c.TimeUnit.ELAPSED_DAYS))
    task_a.setTotalSlack(c.Duration.getInstance(16, c.TimeUnit.HOURS))
    task_a.setFreeSlack(c.Duration.getInstance(8, c.TimeUnit.HOURS))
    task_b.addPredecessor(
        c.Relation.Builder()
        .predecessorTask(task_a)
        .type(c.RelationType.FINISH_START)
        .lag(c.Duration.getInstance(8, c.TimeUnit.HOURS))
    )

    w = importlib.import_module("org.mpxj.writer")
    out = str(tmp_path / "hours.xml")
    w.UniversalProjectWriter(w.FileFormat.MSPDI).write(p, out)
    return out


@pytest.fixture()
def in_memory_project(_jvm):
    """(org.mpxj, ProjectFile) en memoria con calendario por defecto."""
    org_mpxj = importlib.import_module("org.mpxj")
    project = org_mpxj.ProjectFile()
    project.addDefaultBaseCalendar()
    return org_mpxj, project
