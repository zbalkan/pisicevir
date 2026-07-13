import os
import shutil
import tempfile
from pisicevir.models.pisi import PisiRecipe, PisiSource, PisiPackager, PisiPackage, PisiHistoryEntry
from pisicevir.renderers.pspec import PspecRenderer
from pisicevir.linter.linter import RecipeLinter

def test_pspec_renderer():
    recipe = PisiRecipe(
        source=PisiSource(
            name="test-pkg",
            summary="Test summary",
            description="Test description",
            packager=PisiPackager(name="John Doe", email="john@example.com")
        ),
        packages=[
            PisiPackage(name="test-pkg", files=["/usr/bin/test"])
        ],
        history=[
            PisiHistoryEntry(version="1.0", release="1", date="2023-01-01", name="John Doe", email="john@example.com", comment="Initial release")
        ]
    )
    renderer = PspecRenderer(recipe)
    xml_content = renderer.render()
    assert "<Name>test-pkg</Name>" in xml_content
    assert "<Summary>Test summary</Summary>" in xml_content

def test_linter():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Test missing files
        linter = RecipeLinter(tmpdir)
        findings = linter.lint()
        codes = [f["code"] for f in findings]
        assert "FILE001" in codes
        
        # Test valid files
        with open(os.path.join(tmpdir, "pspec.xml"), "w") as f:
            f.write("<PISI></PISI>")
        with open(os.path.join(tmpdir, "actions.py"), "w") as f:
            f.write("def setup(): pass\ndef build(): pass\ndef install(): pass\n")
            
        linter = RecipeLinter(tmpdir)
        findings = linter.lint()
        assert len(findings) == 0
