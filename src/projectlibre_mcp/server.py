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
