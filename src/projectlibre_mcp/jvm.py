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
    import java.lang  # noqa: PLC0415 -- only available after JVM starts
    if not java.lang.Thread.isAttached():
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
