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
claude mcp add -s user projectlibre -- uv run --directory "C:\Users\osyanne\Documents\Claude\Projects\projectlibre-mcp" projectlibre-mcp
```

## Herramientas

**Lectura / análisis** (aceptan `.pod` o `.xml`):
- `summarize_project(file)` — resumen: nombre, fechas, # tareas/recursos, hitos.
- `list_tasks(file, only_critical=False)` — tareas con id, nombre, fechas, duración, %, predecesoras, recursos.
- `get_task(file, task_id)` — detalle de una tarea.
- `list_resources(file)` — recursos y sus asignaciones (tarea, unidades, trabajo).
- `critical_path(file)` — ruta crítica y holgura por tarea (`total_slack`/`free_slack` como texto y `total_slack_days`/`free_slack_days` numéricos).

> En las tareas, `duration_days` y `lag_days` se convierten a días laborables según las horas/día del archivo. Si `duration_is_elapsed`/`lag_is_elapsed` es `true`, son días corridos (24 h). Un lag porcentual se calcula sobre la duración del predecesor. `summarize_project.duration_days` son días calendario entre inicio y fin.

**Creación / edición** (escriben `.xml` MSPDI para importar):
- `create_project(name, start_date, tasks, out)` — proyecto desde cero. `tasks` = lista de `{name, duration_days, predecessors?, resource?, percent_complete?, is_milestone?}`. `predecessors` admite índices 1-based o nombres.
- `add_task(file, name, duration_days, predecessors?, resource?, out?)`
- `update_task(file, task_id, fields, out?)` — `fields`: name, duration_days, percent_complete, is_milestone, start.
- `remove_task(file, task_id, out?)`
- `set_dependency(file, predecessor_id, successor_id, type="FS", lag_days=0, out?)` — type ∈ {FS, SS, FF, SF}.
- `assign_resource(file, task_id, resource_name, units=100, out?)`

> En las herramientas de edición, `out` es opcional si la entrada ya es `.xml` (se sobrescribe); si la entrada es `.pod`, `out` (`.xml`) es obligatorio. Las fechas usan formato `YYYY-MM-DD`; las duraciones, días laborables.
>
> Al sobrescribir un `.xml` existente, la versión anterior se conserva como `<archivo>.xml.bak` (un único respaldo, se reemplaza en cada guardado); la escritura es atómica, conserva los permisos del archivo y sigue symlinks (los hardlinks dejan de compartirse).

## Flujo típico
1. Exporta tu proyecto desde ProjectLibre o crea uno con `create_project`.
2. Pídele a Claude que lo lea/analice/edite — los cambios se guardan en un `.xml`.
3. `File → Open` ese `.xml` en ProjectLibre para ver/persistir el resultado.

## Limitaciones (v1)
- La escritura genera `.xml` (requiere abrirlo en ProjectLibre para persistir como `.pod`).
- `critical_path` lee valores de holgura/crítica ya calendarizados (archivos reales de ProjectLibre).
- Detección automática de sobreasignación de recursos: trabajo futuro.

## Desarrollo
```
uv run pytest -q     # suite completa
```

Stack: Python 3.12 · `mcp` (FastMCP) · `mpxj` (JPype sobre JDK 21) · pytest. Arquitectura en capas: `jvm` → `io` → `model` → `reader`/`writer` → `server`.
