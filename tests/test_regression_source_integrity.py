"""F7: reject source bytes that no longer match the inspected package."""
import hashlib

import pytest

from pisicevir.renderers.generator import RecipeGenerator


def test_generator_rejects_source_modified_after_inspection(tmp_path):
    source = tmp_path / "source.deb"
    source.write_bytes(b"original")
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    source.write_bytes(b"changed")
    inspection = {"sha256": original_hash, "payload": [{"path": "usr/share/data", "kind": "file"}], "metadata": {}}
    plan = {
        "approved": True,
        "homepage": "https://example.test",
        "licenses": ["MIT"],
        "packager": {"name": "Tester", "email": "test@example.test"},
        "source_type": "deb",
        "source_sha256": original_hash,
        "conversion_class": "A",
        "policy_family": "deb-data",
        "dependencies": {"required": [], "map": {}, "ignore": []},
        "install": {"preserve": [{"source": "payload/usr/share/data", "target": "/usr/share/data", "kind": "file"}], "relocate": [], "omit": []},
    }
    generator = RecipeGenerator(str(source), inspection, plan, str(tmp_path / "recipe"))
    with pytest.raises(ValueError, match="hash|digest|SHA|changed|integrity|match"):
        generator.generate()


def test_generated_hashes_match_copied_archive(tmp_path):
    import json
    import xml.etree.ElementTree as ET

    source = tmp_path / "source.deb"
    source.write_bytes(b"valid fixture bytes")
    sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    inspection = {
        "sha256": sha256,
        "payload": [{"path": "usr/share/data", "kind": "file"}],
        "metadata": {
            "Package": "fixture",
            "Version": "1.0-1",
            "Description": "Fixture package",
        },
        "dependencies": {},
    }
    plan = {
        "approved": True,
        "homepage": "https://example.test",
        "licenses": ["MIT"],
        "packager": {"name": "Tester", "email": "test@example.test"},
        "source_type": "deb",
        "source_sha256": sha256,
        "conversion_class": "A",
        "policy_family": "deb-data",
        "dependencies": {"required": [], "map": {}, "ignore": []},
        "install": {
            "preserve": [
                {"source": "payload/usr/share/data", "target": "/usr/share/data", "kind": "file"}
            ],
            "relocate": [],
            "omit": [],
        },
    }
    output = tmp_path / "recipe"
    RecipeGenerator(str(source), inspection, plan, str(output)).generate()
    copied = output / "files" / source.name
    expected = hashlib.sha1(copied.read_bytes()).hexdigest()
    tree = ET.parse(output / "pspec.xml")
    archives = tree.findall(".//Archive")
    assert len(archives) == 1
    assert archives[0].attrib["sha1sum"] == expected
    provenance = json.loads((output / "metadata" / "provenance.json").read_text())
    assert provenance["source_sha1"] == expected
