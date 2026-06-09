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
