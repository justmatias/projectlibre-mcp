# src/projectlibre_mcp/io.py
"""Cargar y guardar proyectos. Lee .pod/.xml; escribe MSPDI .xml."""
import os
import shutil
import tempfile

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
    target = os.path.realpath(out_path)  # seguir symlinks: actualizar el archivo real
    parent = os.path.dirname(target)
    if not os.path.isdir(parent):
        raise ValueError(f"El directorio de salida no existe: {parent}")
    descriptor, temp_path = tempfile.mkstemp(
        prefix="." + os.path.basename(target) + ".", suffix=".tmp", dir=parent
    )
    os.close(descriptor)
    try:
        w = pkg("org.mpxj.writer")
        w.UniversalProjectWriter(w.FileFormat.MSPDI).write(project, temp_path)
        if os.path.isfile(target):
            # mkstemp crea 0600: conservar los permisos del archivo existente.
            shutil.copymode(target, temp_path)
            shutil.copy2(target, target + ".bak")
        else:
            umask = os.umask(0)
            os.umask(umask)
            os.chmod(temp_path, 0o666 & ~umask)
        os.replace(temp_path, target)
    except BaseException:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise
    return out_path
