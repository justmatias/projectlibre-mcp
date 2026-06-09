# projectlibre-mcp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir un MCP server `projectlibre` que lea, analice, cree y modifique proyectos de ProjectLibre a través de la librería MPXJ.

**Architecture:** Servidor FastMCP en Python que usa la librería `mpxj` (vía JPype sobre el JDK 21 del sistema). Lee `.pod`/`.xml` directamente y escribe MSPDI `.xml` (que el usuario abre en ProjectLibre). Código en capas: `jvm` (arranque JVM) → `io` (cargar/guardar) → `model` (conversión Java→dict) → `reader`/`writer` (lógica) → `server` (superficie MCP).

**Tech Stack:** Python 3.12, uv, `mcp` (FastMCP), `mpxj==16.3.0`, `JPype1`, pytest, Microsoft OpenJDK 21.

---

## API de MPXJ verificada (spikes 2026-06-09 — usar EXACTAMENTE estas firmas)

- **Bootstrap:** `import mpxj` (agrega jars al classpath) → `import jpype` → `jpype.startJVM()`. La JVM arranca una sola vez por proceso; usar `jpype.isJVMStarted()`. Para hilos worker: `jpype.attachThreadToJVM()` si `not jpype.isThreadAttachedToJVM()`.
- **Namespace:** `org.mpxj` (NO `net.sf.mpxj`). Importar con `importlib.import_module("org.mpxj")`.
- **Fechas:** `java.time.LocalDateTime` (MPXJ 13+ abandonó `java.util.Date`). `LocalDateTime.of(y, m, d, h, min)`. Al leer, `str(value)` → ISO `"2026-06-09T08:00"`.
- **Crear proyecto:** `p = org.mpxj.ProjectFile()`; `props = p.getProjectProperties()`; `props.setName(...)`; `props.setStartDate(LocalDateTime)`; `p.addDefaultBaseCalendar()`.
- **Tareas:** `t = p.addTask()`; `t.setName(str)`; `t.setDuration(Duration.getInstance(float, TimeUnit.DAYS))`; `t.setMilestone(bool)`; `t.setPercentageComplete(jpype.JDouble)`; `t.setStart(LocalDateTime)`; `t.remove()`.
- **Lookups:** `p.getTaskByUniqueID(jpype.JInt(n))` (canónico) y `p.getTaskByID(jpype.JInt(n))`. El `id` que expone el MCP = `getUniqueID()` (1, 2, 3…).
- **Dependencias (API exacta):**
  ```python
  builder = core.Relation.Builder().predecessorTask(pred_task).type(core.RelationType.FINISH_START)
  builder = builder.lag(core.Duration.getInstance(0.0, core.TimeUnit.DAYS))   # opcional
  succ_task.addPredecessor(builder)   # el successorTask se auto-asigna a succ_task
  ```
  `Task.addPredecessor(...)` SOLO acepta un `Relation.Builder`. Builder tiene: `predecessorTask, successorTask, type, lag, notes, uniqueID, from_, build`.
- **RelationType:** `FINISH_START`→FS, `START_START`→SS, `FINISH_FINISH`→FF, `START_FINISH`→SF.
- **Recursos:** `r = p.addResource()`; `r.setName(...)`. `Resource` tiene `getUniqueID, getName, getType, getMaxUnits`. **`Resource` NO tiene `getResourceAssignments`** → para listar asignaciones de un recurso, iterar `task.getResourceAssignments()` y agrupar por `resource.getUniqueID()`.
- **Asignaciones:** `a = task.addResourceAssignment(resource)`; `a.setUnits(jpype.JDouble(100.0))`. `ResourceAssignment` tiene `getUnits, setUnits, getWork, getResource, getTask`.
- **Leer:** `org.mpxj.reader.UniversalProjectReader().read(path)` auto-detecta `.pod` y `.xml`. Existe `org.mpxj.projectlibre.ProjectLibreReader` para `.pod`.
- **Escribir:** `w = org.mpxj.writer; w.UniversalProjectWriter(w.FileFormat.MSPDI).write(project, out_path)`.
- **Slack/crítica:** `Task.getCritical()` (Boolean), `getTotalSlack()`/`getFreeSlack()` (Duration). Poblados solo si el archivo fue calendarizado (archivos reales de ProjectLibre sí; los que creamos nosotros pueden dar null → guardar con `None`).

**Gotcha de instalación:** `mpxj` NO declara `JPype1` como dependencia. Hay que instalarlo explícitamente.

**Ajuste de alcance (vs spec):** `list_resources` reporta asignaciones agrupadas por tarea, pero el flag automático de *sobreasignación* se difiere (requiere análisis time-phased). Documentar como trabajo futuro.

---

## File Structure

```
projectlibre-mcp/
├── pyproject.toml                     # uv project; deps: mcp, mpxj, jpype1; dev: pytest
├── .gitignore                         # .venv, __pycache__, *.xml de salida
├── README.md                          # qué es, instalar, registrar en Claude
├── src/projectlibre_mcp/
│   ├── __init__.py
│   ├── jvm.py                         # arranque JVM + acceso a org.mpxj
│   ├── io.py                          # load_project / save_xml / validación de rutas
│   ├── model.py                       # conversión Java→dict (task/resource/relation)
│   ├── reader.py                      # summarize_project, list_tasks, get_task, list_resources, critical_path
│   ├── writer.py                      # create_project, add/update/remove_task, set_dependency, assign_resource
│   └── server.py                      # FastMCP: define las 11 tools y main()
└── tests/
    ├── conftest.py                    # fixture sample_xml (mpxj directo, independiente del paquete)
    ├── test_io.py
    ├── test_model.py
    ├── test_reader.py
    ├── test_writer.py
    └── test_server_smoke.py           # tools cargan + inputSchema.properties correcto
```

---

## Task 1: Scaffold del proyecto (uv + paquete + gitignore)

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `src/projectlibre_mcp/__init__.py`

- [ ] **Step 1: Crear `.gitignore`**

```gitignore
.venv/
__pycache__/
*.pyc
*.egg-info/
.pytest_cache/
# salidas de proyectos generados durante pruebas manuales
/tmp_*.xml
*.pod
```

- [ ] **Step 2: Crear `pyproject.toml`**

```toml
[project]
name = "projectlibre-mcp"
version = "0.1.0"
description = "MCP server para leer/crear/editar proyectos de ProjectLibre vía MPXJ"
readme = "README.md"
requires-python = ">=3.12,<3.13"
dependencies = [
    "mcp>=1.2.0",
    "mpxj==16.3.0",
    "JPype1>=1.7.1",
]

[project.scripts]
projectlibre-mcp = "projectlibre_mcp.server:main"

[dependency-groups]
dev = ["pytest>=8.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/projectlibre_mcp"]
```

- [ ] **Step 3: Crear `src/projectlibre_mcp/__init__.py`**

```python
"""projectlibre-mcp: MCP server para ProjectLibre vía MPXJ."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Sincronizar el entorno**

Run: `uv sync`
Expected: instala mcp, mpxj, jpype1, pytest; crea/actualiza `.venv` sin errores.

- [ ] **Step 5: Verificar que el paquete importa**

Run: `uv run python -c "import projectlibre_mcp; print(projectlibre_mcp.__version__)"`
Expected: imprime `0.1.0`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore src/projectlibre_mcp/__init__.py
git commit -m "chore: scaffold uv + paquete projectlibre_mcp"
```

---

## Task 2: Arranque de la JVM (`jvm.py`)

**Files:**
- Create: `src/projectlibre_mcp/jvm.py`
- Test: `tests/test_jvm.py`

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_jvm.py
from projectlibre_mcp import jvm


def test_core_returns_org_mpxj_with_projectfile():
    core = jvm.core()
    # ProjectFile debe existir en el paquete org.mpxj
    assert hasattr(core, "ProjectFile")


def test_ensure_jvm_is_idempotent():
    jvm.ensure_jvm()
    jvm.ensure_jvm()  # segunda llamada no debe reventar
    import jpype
    assert jpype.isJVMStarted()


def test_pkg_loads_reader_and_writer():
    reader = jvm.pkg("org.mpxj.reader")
    writer = jvm.pkg("org.mpxj.writer")
    assert hasattr(reader, "UniversalProjectReader")
    assert hasattr(writer, "UniversalProjectWriter")
    assert hasattr(writer, "FileFormat")
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `uv run pytest tests/test_jvm.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'projectlibre_mcp.jvm'`

- [ ] **Step 3: Implementar `jvm.py`**

```python
# src/projectlibre_mcp/jvm.py
"""Arranque de la JVM y acceso a los paquetes de MPXJ.

La JVM solo puede arrancar una vez por proceso (limitación de JPype).
`import mpxj` agrega los jars de MPXJ al classpath; DEBE ir antes de startJVM.
"""
import importlib

import mpxj  # noqa: F401  -- agrega los jars de MPXJ al classpath de JPype
import jpype

_CORE = None


def ensure_jvm():
    """Arranca la JVM si no está corriendo y adjunta el hilo actual."""
    if not jpype.isJVMStarted():
        jpype.startJVM()  # usa JAVA_HOME (JDK 21)
    if not jpype.isThreadAttachedToJVM():
        jpype.attachThreadToJVM()


def core():
    """Devuelve el paquete `org.mpxj` (cargado de forma perezosa)."""
    global _CORE
    ensure_jvm()
    if _CORE is None:
        _CORE = importlib.import_module("org.mpxj")
    return _CORE


def pkg(name):
    """Devuelve un subpaquete de MPXJ por nombre, p.ej. 'org.mpxj.reader'."""
    ensure_jvm()
    return importlib.import_module(name)
```

- [ ] **Step 4: Correr el test para verificar que pasa**

Run: `uv run pytest tests/test_jvm.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/projectlibre_mcp/jvm.py tests/test_jvm.py
git commit -m "feat: arranque de JVM y acceso a paquetes MPXJ"
```

---

## Task 3: Fixture de muestra + IO cargar/guardar (`io.py`)

**Files:**
- Create: `tests/conftest.py`, `src/projectlibre_mcp/io.py`
- Test: `tests/test_io.py`

- [ ] **Step 1: Crear el fixture `sample_xml` (usa mpxj directo, independiente del paquete)**

```python
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
```

- [ ] **Step 2: Escribir el test que falla**

```python
# tests/test_io.py
import os

import pytest

from projectlibre_mcp import io


def test_load_project_reads_sample(sample_xml):
    p = io.load_project(sample_xml)
    names = sorted(str(t.getName()) for t in p.getTasks() if t.getName() is not None)
    assert names == ["Construccion", "Diseno", "Pruebas"]


def test_load_project_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        io.load_project("no_existe_12345.xml")


def test_save_xml_writes_file(sample_xml, tmp_path):
    p = io.load_project(sample_xml)
    out = str(tmp_path / "copia.xml")
    result = io.save_xml(p, out)
    assert result == out
    assert os.path.isfile(out) and os.path.getsize(out) > 0


def test_save_xml_rejects_pod_output(sample_xml, tmp_path):
    p = io.load_project(sample_xml)
    with pytest.raises(ValueError, match="pod"):
        io.save_xml(p, str(tmp_path / "x.pod"))
```

- [ ] **Step 3: Correr el test para verificar que falla**

Run: `uv run pytest tests/test_io.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'projectlibre_mcp.io'`

- [ ] **Step 4: Implementar `io.py`**

```python
# src/projectlibre_mcp/io.py
"""Cargar y guardar proyectos. Lee .pod/.xml; escribe MSPDI .xml."""
import os

from .jvm import ensure_jvm, pkg


def load_project(path):
    """Lee un archivo de proyecto (.pod, .xml, .mpp, .mpx) y devuelve un ProjectFile."""
    ensure_jvm()
    if not os.path.isfile(path):
        raise FileNotFoundError(f"No existe el archivo: {path}")
    reader = pkg("org.mpxj.reader").UniversalProjectReader()
    try:
        project = reader.read(path)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            f"No se pudo leer '{path}'. Si es un .pod y falla, expórtalo a XML "
            f"desde ProjectLibre (File → Save As → MS Project XML). Detalle: {exc}"
        ) from exc
    if project is None:
        raise ValueError(f"Formato no reconocido o archivo vacío: {path}")
    return project


def save_xml(project, out_path):
    """Escribe el proyecto como MSPDI XML. Rechaza salidas .pod."""
    ensure_jvm()
    low = out_path.lower()
    if low.endswith(".pod"):
        raise ValueError(
            "No se puede escribir .pod (formato propietario). Usa una salida .xml "
            "y ábrela en ProjectLibre (File → Open)."
        )
    if not low.endswith(".xml"):
        raise ValueError("La salida debe terminar en .xml (MSPDI).")
    w = pkg("org.mpxj.writer")
    w.UniversalProjectWriter(w.FileFormat.MSPDI).write(project, out_path)
    return out_path
```

- [ ] **Step 5: Correr el test para verificar que pasa**

Run: `uv run pytest tests/test_io.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add tests/conftest.py tests/test_io.py src/projectlibre_mcp/io.py
git commit -m "feat: cargar/guardar proyectos + fixture de muestra"
```

---

## Task 4: Conversión Java→dict (`model.py`)

**Files:**
- Create: `src/projectlibre_mcp/model.py`
- Test: `tests/test_model.py`

- [ ] **Step 1: Escribir el test que falla**

```python
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
    assert set(rd) == {"predecessor_id", "type", "lag"}
    assert rd["type"] == "FS"
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `uv run pytest tests/test_model.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'projectlibre_mcp.model'`

- [ ] **Step 3: Implementar `model.py`**

```python
# src/projectlibre_mcp/model.py
"""Conversión de objetos Java de MPXJ a dicts serializables."""


def jstr(v):
    return None if v is None else str(v)


def jfloat(v):
    return None if v is None else float(v)


def jbool(v):
    return None if v is None else bool(v)


def relation_dict(rel):
    return {
        "predecessor_id": int(rel.getPredecessorTask().getUniqueID()),
        "type": jstr(rel.getType()),   # "FS", "SS", "FF", "SF"
        "lag": jstr(rel.getLag()),     # p.ej. "0.0d"
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
```

- [ ] **Step 4: Correr el test para verificar que pasa**

Run: `uv run pytest tests/test_model.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/projectlibre_mcp/model.py tests/test_model.py
git commit -m "feat: conversión Java→dict de tareas y relaciones"
```

---

## Task 5: Lectura — summarize / list_tasks / get_task (`reader.py`)

**Files:**
- Create: `src/projectlibre_mcp/reader.py`
- Test: `tests/test_reader.py`

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_reader.py
import pytest

from projectlibre_mcp import reader


def test_summarize_project(sample_xml):
    s = reader.summarize_project(sample_xml)
    assert s["name"] == "Demo"
    assert s["task_count"] == 3
    assert s["resource_count"] == 1


def test_list_tasks_returns_all(sample_xml):
    tasks = reader.list_tasks(sample_xml)
    names = sorted(t["name"] for t in tasks)
    assert names == ["Construccion", "Diseno", "Pruebas"]


def test_get_task_by_id(sample_xml):
    tasks = reader.list_tasks(sample_xml)
    first = tasks[0]
    detail = reader.get_task(sample_xml, first["id"])
    assert detail["id"] == first["id"]
    assert detail["name"] == first["name"]


def test_get_task_missing_raises(sample_xml):
    with pytest.raises(ValueError, match="no encontrada"):
        reader.get_task(sample_xml, 99999)
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `uv run pytest tests/test_reader.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'projectlibre_mcp.reader'`

- [ ] **Step 3: Implementar `reader.py` (parte 1)**

```python
# src/projectlibre_mcp/reader.py
"""Lógica de lectura y análisis de proyectos."""
import jpype

from .io import load_project
from .model import jfloat, jstr, task_to_dict


def _named_tasks(project):
    return [t for t in project.getTasks() if t.getName() is not None]


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
```

- [ ] **Step 4: Correr el test para verificar que pasa**

Run: `uv run pytest tests/test_reader.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/projectlibre_mcp/reader.py tests/test_reader.py
git commit -m "feat: summarize_project, list_tasks, get_task"
```

---

## Task 6: Lectura — list_resources / critical_path (`reader.py`)

**Files:**
- Modify: `src/projectlibre_mcp/reader.py`
- Test: `tests/test_reader.py` (agregar tests)

- [ ] **Step 1: Agregar tests que fallan**

```python
# tests/test_reader.py (agregar al final)
def test_list_resources(sample_xml):
    from projectlibre_mcp import reader
    res = reader.list_resources(sample_xml)
    assert len(res) == 1
    imanol = res[0]
    assert imanol["name"] == "Imanol"
    # tiene 1 asignación: a "Construccion"
    assert len(imanol["assignments"]) == 1
    assert imanol["assignments"][0]["task_name"] == "Construccion"


def test_critical_path_shape(sample_xml):
    from projectlibre_mcp import reader
    cp = reader.critical_path(sample_xml)
    assert set(cp) == {"critical_task_ids", "tasks"}
    assert len(cp["tasks"]) == 3
    for t in cp["tasks"]:
        assert set(t) >= {"id", "name", "is_critical", "total_slack", "free_slack"}
```

- [ ] **Step 2: Correr para verificar que fallan**

Run: `uv run pytest tests/test_reader.py -v -k "resources or critical"`
Expected: FAIL con `AttributeError: module 'projectlibre_mcp.reader' has no attribute 'list_resources'`

- [ ] **Step 3: Agregar a `reader.py`**

```python
# src/projectlibre_mcp/reader.py (agregar al final)
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
        })
    return {"critical_task_ids": crit_ids, "tasks": rows}
```

- [ ] **Step 4: Correr para verificar que pasan**

Run: `uv run pytest tests/test_reader.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/projectlibre_mcp/reader.py tests/test_reader.py
git commit -m "feat: list_resources y critical_path"
```

---

## Task 7: Escritura — create_project (`writer.py`)

**Files:**
- Create: `src/projectlibre_mcp/writer.py`
- Test: `tests/test_writer.py`

- [ ] **Step 1: Escribir el test que falla**

```python
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
    # "Escribir" depende de "Investigar"
    assert len(tasks["Escribir"]["predecessors"]) == 1
    # "Defender" es hito y depende de "Escribir"
    assert tasks["Defender"]["is_milestone"] is True
    assert len(tasks["Defender"]["predecessors"]) == 1


def test_create_project_rejects_pod_output(tmp_path):
    import pytest
    with pytest.raises(ValueError, match="pod"):
        writer.create_project("X", "2026-01-01", [{"name": "a", "duration_days": 1}],
                              out=str(tmp_path / "x.pod"))
```

- [ ] **Step 2: Correr para verificar que falla**

Run: `uv run pytest tests/test_writer.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'projectlibre_mcp.writer'`

- [ ] **Step 3: Implementar `writer.py` (parte 1)**

```python
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
    c = core()  # noqa: F841  (asegura JVM)
    res = None
    for r in project.getResources():
        if r.getName() is not None and str(r.getName()) == resource_name:
            res = r
            break
    if res is None:
        res = project.addResource()
        res.setName(resource_name)
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
                raise ValueError("predecessor inválido (bool)")
            if isinstance(pre, int):
                pred_task = created[pre - 1]
            else:
                pred_task = name_to_task[str(pre)]
            builder = c.Relation.Builder().predecessorTask(pred_task).type(_reltype("FS"))
            created[i].addPredecessor(builder)
        if spec.get("resource"):
            _assign(p, created[i], spec["resource"], 100)

    save_xml(p, out)
    return {"out": out, "task_count": len(created)}
```

- [ ] **Step 4: Correr para verificar que pasa**

Run: `uv run pytest tests/test_writer.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/projectlibre_mcp/writer.py tests/test_writer.py
git commit -m "feat: create_project (crear proyecto desde cero → MSPDI XML)"
```

---

## Task 8: Edición — add_task / update_task / remove_task (`writer.py`)

**Files:**
- Modify: `src/projectlibre_mcp/writer.py`
- Test: `tests/test_writer.py` (agregar tests)

- [ ] **Step 1: Agregar tests que fallan**

```python
# tests/test_writer.py (agregar al final)
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
```

- [ ] **Step 2: Correr para verificar que fallan**

Run: `uv run pytest tests/test_writer.py -v -k "add_task or update or remove"`
Expected: FAIL con `AttributeError: module 'projectlibre_mcp.writer' has no attribute 'add_task'`

- [ ] **Step 3: Agregar a `writer.py`**

```python
# src/projectlibre_mcp/writer.py (agregar al final)
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
    t = _make_task(p, name, duration_days)
    new_id = int(t.getUniqueID())
    for pid in (predecessors or []):
        _link(p, pid, new_id, "FS", 0)
    if resource:
        _assign(p, t, resource, 100)
    out = _resolve_out(file, out)
    save_xml(p, out)
    return {"out": out, "task_id": new_id}


def update_task(file, task_id, fields, out=None):
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
```

- [ ] **Step 4: Correr para verificar que pasan**

Run: `uv run pytest tests/test_writer.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/projectlibre_mcp/writer.py tests/test_writer.py
git commit -m "feat: add_task, update_task, remove_task"
```

---

## Task 9: Edición — set_dependency / assign_resource (`writer.py`)

**Files:**
- Modify: `src/projectlibre_mcp/writer.py`
- Test: `tests/test_writer.py` (agregar tests)

- [ ] **Step 1: Agregar tests que fallan**

```python
# tests/test_writer.py (agregar al final)
def test_set_dependency(sample_xml, tmp_path):
    from projectlibre_mcp import reader, writer
    tasks = {t["name"]: t for t in reader.list_tasks(sample_xml)}
    # crear dependencia Diseno -> Pruebas (que aún no existe directamente)
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
```

- [ ] **Step 2: Correr para verificar que fallan**

Run: `uv run pytest tests/test_writer.py -v -k "dependency or assign"`
Expected: FAIL con `AttributeError: module 'projectlibre_mcp.writer' has no attribute 'set_dependency'`

- [ ] **Step 3: Agregar a `writer.py`**

```python
# src/projectlibre_mcp/writer.py (agregar al final)
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
```

- [ ] **Step 4: Correr para verificar que pasan**

Run: `uv run pytest tests/test_writer.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add src/projectlibre_mcp/writer.py tests/test_writer.py
git commit -m "feat: set_dependency y assign_resource"
```

---

## Task 10: Servidor MCP (`server.py`) + smoke test

**Files:**
- Create: `src/projectlibre_mcp/server.py`
- Test: `tests/test_server_smoke.py`

- [ ] **Step 1: Escribir el smoke test que falla**

```python
# tests/test_server_smoke.py
import asyncio


def test_tools_registered_with_correct_schema():
    from projectlibre_mcp.server import mcp

    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    expected = {
        "summarize_project", "list_tasks", "get_task", "list_resources", "critical_path",
        "create_project", "add_task", "update_task", "remove_task",
        "set_dependency", "assign_resource",
    }
    assert expected <= names, f"faltan tools: {expected - names}"

    by = {t.name: t for t in tools}
    # el schema NO debe colapsar a {kwargs} (lección osu-mcp): verificar properties reales
    sd = by["set_dependency"].inputSchema.get("properties", {})
    assert "predecessor_id" in sd and "successor_id" in sd, sd
    cp = by["create_project"].inputSchema.get("properties", {})
    assert "name" in cp and "tasks" in cp and "out" in cp, cp
    st = by["summarize_project"].inputSchema.get("properties", {})
    assert "file" in st, st
```

- [ ] **Step 2: Correr para verificar que falla**

Run: `uv run pytest tests/test_server_smoke.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'projectlibre_mcp.server'`

- [ ] **Step 3: Implementar `server.py`**

```python
# src/projectlibre_mcp/server.py
"""MCP server `projectlibre`: expone lectura/escritura de proyectos ProjectLibre."""
from mcp.server.fastmcp import FastMCP

from . import reader, writer

mcp = FastMCP("projectlibre")


# ---------- Lectura / análisis (aceptan .pod o .xml) ----------

@mcp.tool()
def summarize_project(file: str) -> dict:
    """Resumen del proyecto: nombre, fechas, # tareas/recursos e hitos."""
    return reader.summarize_project(file)


@mcp.tool()
def list_tasks(file: str, only_critical: bool = False) -> list:
    """Lista las tareas con id, nombre, fechas, duración, %, predecesoras y recursos."""
    return reader.list_tasks(file, only_critical=only_critical)


@mcp.tool()
def get_task(file: str, task_id: int) -> dict:
    """Detalle de una tarea por su id (uniqueID)."""
    return reader.get_task(file, task_id)


@mcp.tool()
def list_resources(file: str) -> list:
    """Lista los recursos y sus asignaciones (tarea, unidades, trabajo)."""
    return reader.list_resources(file)


@mcp.tool()
def critical_path(file: str) -> dict:
    """Ruta crítica y holgura (slack) por tarea. Requiere un archivo ya calendarizado."""
    return reader.critical_path(file)


# ---------- Creación / edición (escriben .xml MSPDI para importar) ----------

@mcp.tool()
def create_project(name: str, start_date: str, tasks: list, out: str) -> dict:
    """Crea un proyecto desde cero y escribe un .xml que se abre en ProjectLibre.

    start_date en formato YYYY-MM-DD. tasks: lista de objetos con
    name, duration_days y opcionales predecessors (índices 1-based o nombres),
    resource, percent_complete, is_milestone. out debe terminar en .xml.
    """
    return writer.create_project(name, start_date, tasks, out)


@mcp.tool()
def add_task(file: str, name: str, duration_days: float,
             predecessors: list | None = None, resource: str | None = None,
             out: str | None = None) -> dict:
    """Agrega una tarea a un proyecto y guarda el resultado en .xml (out o el .xml de entrada)."""
    return writer.add_task(file, name, duration_days, predecessors=predecessors,
                           resource=resource, out=out)


@mcp.tool()
def update_task(file: str, task_id: int, fields: dict, out: str | None = None) -> dict:
    """Modifica campos de una tarea (name, duration_days, percent_complete, is_milestone, start)."""
    return writer.update_task(file, task_id, fields, out=out)


@mcp.tool()
def remove_task(file: str, task_id: int, out: str | None = None) -> dict:
    """Elimina una tarea por id y guarda el resultado en .xml."""
    return writer.remove_task(file, task_id, out=out)


@mcp.tool()
def set_dependency(file: str, predecessor_id: int, successor_id: int,
                   type: str = "FS", lag_days: float = 0, out: str | None = None) -> dict:
    """Crea una dependencia entre tareas. type ∈ {FS, SS, FF, SF}."""
    return writer.set_dependency(file, predecessor_id, successor_id, type=type,
                                 lag_days=lag_days, out=out)


@mcp.tool()
def assign_resource(file: str, task_id: int, resource_name: str,
                    units: float = 100, out: str | None = None) -> dict:
    """Asigna un recurso a una tarea (lo crea si no existe) y guarda en .xml."""
    return writer.assign_resource(file, task_id, resource_name, units=units, out=out)


def main():
    """Entry point del console script. Arranca el server por stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Correr para verificar que pasa**

Run: `uv run pytest tests/test_server_smoke.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Correr TODA la suite**

Run: `uv run pytest -v`
Expected: PASS (todos: jvm 3, io 4, model 2, reader 6, writer 8, smoke 1 = 24)

- [ ] **Step 6: Commit**

```bash
git add src/projectlibre_mcp/server.py tests/test_server_smoke.py
git commit -m "feat: servidor MCP FastMCP con 11 tools + smoke test"
```

---

## Task 11: README, registro en Claude y verificación end-to-end

**Files:**
- Create: `README.md`

- [ ] **Step 1: Escribir `README.md`**

```markdown
# projectlibre-mcp

MCP server para leer, analizar, crear y editar proyectos de **ProjectLibre** desde Claude, vía la librería [MPXJ](https://www.mpxj.org/).

## Cómo funciona
- **Lee** `.pod` (nativo de ProjectLibre) y `.xml` (MS Project / MSPDI) directamente.
- **Escribe** `.xml` (MSPDI). Para ver los cambios en ProjectLibre: `File → Open` el `.xml` generado (y, si quieres, `Save As` → `.pod`).
- No se puede escribir `.pod` directamente (formato propietario); por eso la escritura produce `.xml`.

## Requisitos
- Java (JDK 21 recomendado; `JAVA_HOME` configurado).
- [uv](https://docs.astral.sh/uv/).

## Instalación
```
uv sync
```

## Registrar en Claude Code
```
claude mcp add -s user projectlibre -- uv run --directory "<RUTA_AL_REPO>" projectlibre-mcp
```

## Herramientas
Lectura: `summarize_project`, `list_tasks`, `get_task`, `list_resources`, `critical_path`.
Edición: `create_project`, `add_task`, `update_task`, `remove_task`, `set_dependency`, `assign_resource`.

## Limitaciones (v1)
- La escritura genera `.xml` (requiere abrirlo en ProjectLibre para persistir como `.pod`).
- `critical_path` lee valores de holgura/crítica ya calendarizados (archivos reales de ProjectLibre).
- Detección automática de sobreasignación de recursos: trabajo futuro.
```

- [ ] **Step 2: Commit del README**

```bash
git add README.md
git commit -m "docs: README con uso, instalación y limitaciones"
```

- [ ] **Step 3: Registrar el MCP en Claude Code**

Run (reemplazar la ruta real):
`claude mcp add -s user projectlibre -- uv run --directory "C:\Users\osyanne\Documents\Claude\Projects\projectlibre-mcp" projectlibre-mcp`
Expected: confirma que el server fue agregado.

- [ ] **Step 4: Verificar el server arranca y lista tools**

Run: `claude mcp list`
Expected: `projectlibre` aparece como conectado (✓).

- [ ] **Step 5: Verificación end-to-end manual (crear → abrir en ProjectLibre)**

1. Pedirle a Claude (o correr un script) que use `create_project` para generar `~/Desktop/prueba_pl.xml` con 3 tareas encadenadas.
2. Abrir ProjectLibre → `File → Open` → seleccionar `prueba_pl.xml`.
3. Confirmar que se ven las 3 tareas con sus dependencias en el Gantt.
4. (Opcional) `Save As` → `prueba_pl.pod`, luego usar `summarize_project` sobre ese `.pod` para cerrar el círculo `.pod`→lectura.

Expected: ProjectLibre abre el `.xml` sin errores y muestra el cronograma. `summarize_project` sobre el `.pod` devuelve las 3 tareas (confirmación final de lectura de `.pod`).

---

## Self-Review (completado al escribir el plan)

- **Cobertura del spec:** las 11 tools del spec ↔ Tasks 5,6 (lectura) y 7,8,9 (escritura); arquitectura Python+MPXJ ↔ Tasks 1,2; round-trip ↔ Task 3 + Task 11 Step 5; manejo de errores ↔ `io.load_project`/`save_xml` + guardas `_get_task_or_raise`/`_resolve_out`; pruebas ↔ tests por tarea + smoke; empaquetado ↔ Task 1 + Task 11.
- **Ajustes vs spec (por hallazgos del spike):** (1) `JPype1` se instala explícito; (2) `list_resources` sin flag automático de sobreasignación (diferido); (3) namespace `org.mpxj` y fechas `java.time`. Documentados arriba.
- **Consistencia de tipos:** `id` = `getUniqueID()` en todo el código; lookups con `jpype.JInt`; salidas siempre `.xml` vía `save_xml`/`_resolve_out`; nombres de funciones consistentes entre `reader`/`writer`/`server`.
- **Sin placeholders:** todo paso de código trae el código real y verificado contra mpxj 16.3.0.
