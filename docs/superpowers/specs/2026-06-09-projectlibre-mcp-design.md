# Diseño: `projectlibre-mcp`

- **Fecha:** 2026-06-09
- **Estado:** Aprobado (diseño) — pendiente revisión del spec por el usuario
- **Autor:** Imanol + Claude

## 1. Objetivo

Construir un **MCP server** llamado `projectlibre` que permita a Claude (en Claude Code y Claude Desktop) **leer, analizar, crear y modificar** proyectos de **ProjectLibre 1.9.8** de forma reutilizable. Una vez instalado, ProjectLibre queda expuesto como herramientas nativas (`mcp__projectlibre__*`) en cualquier sesión.

Esto materializa el pedido original ("conéctate a ProjectLibre") como una conexión **permanente vía archivos**, ya que ProjectLibre de escritorio no tiene API en vivo.

## 2. Contexto técnico

### 2.1 ProjectLibre
- App de escritorio **Java (Swing)**, v1.9.8, instalada en `C:\Program Files\ProjectLibre\`.
- **Sin API REST ni servidor local** (eso solo lo tiene *ProjectLibre Cloud*, producto de pago aparte).
- Formato nativo: **`.pod`** (serialización propietaria de objetos Java — no escribible desde fuera).
- Importa/exporta **MS Project XML (MSPDI)** — formato abierto y documentado.

### 2.2 Matriz de formatos (lo que define la arquitectura)

| Formato | Lectura | Escritura |
|---|---|---|
| `.pod` nativo | ✅ MPXJ lo lee directo | ❌ Nadie lo escribe (propietario) |
| MS Project XML (MSPDI) | ✅ | ✅ MPXJ lo escribe correcto |

**Consecuencia:** la lectura del `.pod` es transparente; la escritura/modificación produce un **`.xml` (MSPDI)** que el usuario abre en ProjectLibre (`File → Open`, lo lee nativo) y opcionalmente guarda como `.pod`. Ese paso manual de import es la **única fricción**, inevitable porque el `.pod` no se puede escribir sin reimplementar la serialización interna de ProjectLibre.

### 2.3 Entorno verificado (2026-06-09)
- **JDK 21** (Microsoft OpenJDK) en `C:\Program Files\Microsoft\jdk-21.0.10.7-hotspot\`, con `JAVA_HOME` ya seteado. → habilita MPXJ.
- **uv** en `~\.local\bin\uv.exe`. → gestiona el Python real (el `python.exe` del PATH es el stub de la Windows Store, inservible).
- **git** 2.53, **node** disponibles.

## 3. Arquitectura

**MCP server en Python (FastMCP) + librería MPXJ, corrido con uv sobre el JDK 21.**

```
Claude  ──MCP──>  projectlibre-mcp (Python/FastMCP)
                        │
                        ├── mpxj (PyPI, JPype → MPXJ .jar)  ──>  JDK 21
                        │
                  lee .pod / .xml   ·   escribe .xml (MSPDI)
```

- **FastMCP**: framework del server (mismo patrón que `osu-mcp`).
- **`mpxj`** (PyPI): puente JPype a la librería Java MPXJ. Maneja el modelo de objetos (Task, Resource, Relation, ProjectCalendar), el cálculo de cronograma y la (de)serialización XML correcta.
- **uv**: entorno y ejecución (`uv run`).
- Estado: **sin estado de sesión** — cada herramienta recibe una ruta de archivo, carga, opera y (si escribe) produce un `.xml`. Robusto y predecible.

### Por qué MPXJ y no XML a mano
MSPDI tiene cientos de campos (UIDs, calendarios, asignaciones, holguras). MPXJ los maneja correctamente y calcula ruta crítica/holgura. Hacerlo a mano con lxml sería frágil y reimplementaría scheduling. (Enfoques B = lxml puro y C = MCP en Java nativo se descartaron por fricción/boilerplate.)

## 4. Superficie de herramientas (v1)

### 4.1 Lectura / análisis — aceptan `.pod` **o** `.xml`
- **`summarize_project(file)`** → `{name, start, finish, duration_days, task_count, resource_count, percent_complete, milestones[]}`
- **`list_tasks(file, only_critical=False)`** → lista de `{id, name, start, finish, duration_days, percent_complete, predecessors:[{id, type, lag_days}], resources[], is_milestone, is_critical}`
- **`get_task(file, task_id)`** → detalle completo de una tarea (incluye notas, restricciones, trabajo)
- **`list_resources(file)`** → `[{id, name, type, max_units, assignments:[{task_id, units, work}], overallocated}]`
- **`critical_path(file)`** → `{critical_task_ids[], tasks:[{id, name, total_slack_days, free_slack_days, is_critical}]}`

### 4.2 Creación / edición — producen `.xml` (MSPDI)
Regla de salida: si el input es `.xml`, `out` por defecto sobrescribe el input; si el input es `.pod` (o en `create_project`), `out` es **obligatorio** y debe terminar en `.xml` (no se escribe `.pod`).

- **`create_project(name, start_date, tasks[], out)`** — desde cero. `tasks` = `[{name, duration_days, predecessors?, resource?, percent_complete?, is_milestone?}]`. Auto-asigna IDs; enlaza predecesoras por índice o nombre.
- **`add_task(file, name, duration_days, after_task_id?, predecessors?, resource?, out?)`**
- **`update_task(file, task_id, fields{name?, duration_days?, start?, percent_complete?, ...}, out?)`**
- **`remove_task(file, task_id, out?)`**
- **`set_dependency(file, predecessor_id, successor_id, type='FS', lag_days=0, out?)`** — type ∈ {FS, SS, FF, SF}
- **`assign_resource(file, task_id, resource_name, units=100, out?)`**

Convenciones: fechas ISO `YYYY-MM-DD`; duración en **días laborables** del calendario del proyecto; v1 usa el **calendario estándar** por defecto.

## 5. Flujo de datos y round-trip

```
.pod / .xml  ──MPXJ lee──>  modelo de objetos  ──(Claude modifica)──>  MPXJ escribe .xml
                                                                              │
                                            usuario: ProjectLibre File→Open <.xml>  →  (opcional) Save As .pod
```

- **Leer**: apuntar a `.pod` o `.xml` directamente.
- **Editar/crear**: se genera/actualiza un `.xml`; el usuario lo abre en ProjectLibre para verlo y, si quiere, lo persiste como `.pod`.

## 6. Manejo de errores
- Archivo inexistente / extensión no soportada → mensaje claro.
- **`.pod` ilegible** (si MPXJ fallara con esa versión) → respuesta que instruye: *"exporta tu proyecto a XML desde ProjectLibre (File → Save As → MS Project XML) y vuelve a intentar"*. (Fallback garantizado.)
- Validación de fechas, `task_id` inexistente, dependencias circulares → errores explícitos, sin escribir archivos corruptos.
- Escritura: nunca sobrescribir un `.pod` (rechazar `out` con extensión `.pod`).

## 7. Pruebas
- **pytest round-trip**: `create_project` → `.xml` → `list_tasks`/`summarize_project` → aseverar que tareas, duraciones y dependencias sobreviven.
- **Edición**: `add_task`/`set_dependency`/`update_task` → releer → verificar el cambio.
- **Smoke test de tools**: verificar que cada tool carga y que su `inputSchema.properties` contiene los campos esperados — **no** solo `type == "object"` (lección de `osu-mcp` v0.1.0, donde un wrapper `**kwargs` colapsó el schema y rompió el paquete).
- Fixture: un proyecto de muestra pequeño (3–5 tareas con dependencias y 1 recurso).

## 8. Empaquetado e instalación
- Proyecto **uv** + **git**, repo `projectlibre-mcp` en `~\Documents\Claude\Projects\`.
- `pyproject.toml` con deps `mcp`/`fastmcp`, `mpxj`, `pytest` (dev).
- Registro: `claude mcp add -s user projectlibre -- uv run --directory <repo> projectlibre-mcp` (o equivalente). `JAVA_HOME` ya está seteado, así que JPype encuentra el JDK 21.
- Publicar a **PyPI**: opcional, posterior (como `osu-mcp`).

## 9. Supuestos a verificar y riesgos
- **[VERIFICAR PRIMERO]** Que MPXJ lea el `.pod` de ProjectLibre 1.9.8 (smoke test con un `.pod` real). Confianza ~90%. Si falla → camino XML como respaldo garantizado (degradación elegante, no bloquea el proyecto).
- JPype + JDK 21 en Windows: arranque de la JVM puede tardar ~1–2 s la primera vez (aceptable para uso conversacional).
- Diferencias de campos MSPDI ↔ lo que ProjectLibre muestra: validar el round-trip abriendo un `.xml` generado en ProjectLibre durante la implementación.

## 10. Fuera de alcance (v1) — YAGNI
- Escritura directa de `.pod` (no factible sin reventar ProjectLibre).
- Integración con ProjectLibre Cloud.
- Automatización de la GUI de ProjectLibre (headless/Swing).
- Costos avanzados de recursos, calendarios personalizados múltiples, líneas base, sub-proyectos.
- Generación de imágenes de Gantt (se puede evaluar después).

## 11. Criterios de éxito
1. Instalado como MCP, los tools aparecen como `mcp__projectlibre__*`.
2. `summarize_project` + `list_tasks` leen un `.pod`/`.xml` real y devuelven datos correctos.
3. `create_project` genera un `.xml` que **abre sin errores en ProjectLibre** y muestra las tareas/dependencias esperadas.
4. `add_task`/`set_dependency`/`assign_resource` modifican y el cambio se ve al reabrir.
5. `critical_path` devuelve la ruta crítica de un proyecto de prueba conocido.
6. Suite de tests (round-trip + smoke) en verde.
