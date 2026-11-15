# tests/test_io.py
import os
import sys
from types import SimpleNamespace

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


def test_save_xml_rejects_missing_dir(sample_xml, tmp_path):
    p = io.load_project(sample_xml)
    with pytest.raises(ValueError, match="no existe"):
        io.save_xml(p, str(tmp_path / "missing" / "x.xml"))


def test_save_xml_leaves_no_temp_files(sample_xml, tmp_path):
    p = io.load_project(sample_xml)
    before = set(os.listdir(tmp_path))
    io.save_xml(p, str(tmp_path / "copia.xml"))
    assert set(os.listdir(tmp_path)) == before | {"copia.xml"}


def test_save_xml_first_save_creates_no_backup(sample_xml, tmp_path):
    p = io.load_project(sample_xml)
    out = tmp_path / "copia.xml"
    io.save_xml(p, str(out))
    assert not (tmp_path / "copia.xml.bak").exists()


def test_save_xml_overwrite_creates_backup_with_previous_content(sample_xml, tmp_path):
    p = io.load_project(sample_xml)
    out = tmp_path / "copia.xml"
    out.write_text("contenido anterior")
    io.save_xml(p, str(out))
    assert (tmp_path / "copia.xml.bak").read_text() == "contenido anterior"
    assert out.read_text() != "contenido anterior"


def test_save_xml_failure_keeps_original_and_cleans_temp(sample_xml, tmp_path, monkeypatch):
    p = io.load_project(sample_xml)
    out = tmp_path / "copia.xml"
    out.write_text("contenido anterior")
    before = set(os.listdir(tmp_path))

    def partial_write(project, path):
        with open(path, "w") as handle:
            handle.write("<Project>")
        raise RuntimeError("fallo simulado")

    failing_writer = SimpleNamespace(write=partial_write)
    fake_writer_package = SimpleNamespace(
        FileFormat=SimpleNamespace(MSPDI=None),
        UniversalProjectWriter=lambda file_format: failing_writer,
    )
    monkeypatch.setattr(io, "pkg", lambda _name: fake_writer_package)
    with pytest.raises(RuntimeError, match="fallo simulado"):
        io.save_xml(p, str(out))
    assert out.read_text() == "contenido anterior"
    assert set(os.listdir(tmp_path)) == before


@pytest.mark.skipif(sys.platform == "win32", reason="permisos POSIX")
def test_save_xml_overwrite_keeps_file_mode(sample_xml, tmp_path):
    p = io.load_project(sample_xml)
    out = tmp_path / "copia.xml"
    out.write_text("contenido anterior")
    os.chmod(out, 0o664)
    io.save_xml(p, str(out))
    assert os.stat(out).st_mode & 0o777 == 0o664


@pytest.mark.skipif(sys.platform == "win32", reason="permisos POSIX")
def test_save_xml_new_file_uses_umask_mode(sample_xml, tmp_path):
    p = io.load_project(sample_xml)
    out = tmp_path / "copia.xml"
    previous_umask = os.umask(0o022)
    try:
        io.save_xml(p, str(out))
    finally:
        os.umask(previous_umask)
    assert os.stat(out).st_mode & 0o777 == 0o644


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks POSIX")
def test_save_xml_follows_symlink(sample_xml, tmp_path):
    p = io.load_project(sample_xml)
    real_file = tmp_path / "real.xml"
    real_file.write_text("contenido anterior")
    link = tmp_path / "enlace.xml"
    link.symlink_to(real_file)
    io.save_xml(p, str(link))
    assert link.is_symlink()
    assert real_file.read_text() != "contenido anterior"
    assert (tmp_path / "real.xml.bak").read_text() == "contenido anterior"
