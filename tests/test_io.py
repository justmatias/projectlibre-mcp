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

    def failing_pkg(name):
        raise RuntimeError("fallo simulado")

    monkeypatch.setattr(io, "pkg", failing_pkg)
    with pytest.raises(RuntimeError, match="fallo simulado"):
        io.save_xml(p, str(out))
    assert out.read_text() == "contenido anterior"
    assert set(os.listdir(tmp_path)) == before
