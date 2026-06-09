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
