from __future__ import annotations

import tempfile
from pathlib import Path

from pisicevir.linter.linter import RecipeLinter
from pisicevir.models.pisi import (
    PisiArchive,
    PisiFilePath,
    PisiHistoryEntry,
    PisiPackage,
    PisiPackager,
    PisiRecipe,
    PisiSource,
)
from pisicevir.renderers.actions import ActionsRenderer
from pisicevir.renderers.pspec import PspecRenderer


def complete_recipe() -> PisiRecipe:
    return PisiRecipe(
        source=PisiSource(
            name="test-pkg",
            homepage="https://example.test/test-pkg",
            summary="Test summary",
            description="Test description",
            packager=PisiPackager(name="Test Packager", email="test@example.test"),
            licenses=["GPL-3.0-or-later"],
            archive=PisiArchive(
                uri="files/test.deb",
                archive_type="binary",
                sha1sum="a" * 40,
                sha256sum="b" * 64,
            ),
        ),
        packages=[
            PisiPackage(
                name="test-pkg",
                files=[PisiFilePath(path="/usr/share/test-pkg", file_type="data")],
            )
        ],
        history=[
            PisiHistoryEntry(
                version="1.0.0",
                release="1",
                date="2023-01-01",
                name="Test Packager",
                email="test@example.test",
                comment="Initial release",
            )
        ],
    )


def test_pspec_renderer_emits_required_metadata() -> None:
    xml_content = PspecRenderer(complete_recipe()).render()
    assert "<Archive" in xml_content
    assert 'sha256sum="' + "b" * 64 + '"' in xml_content
    assert '<Path fileType="data">/usr/share/test-pkg</Path>' in xml_content
    assert "<License>GPL-3.0-or-later</License>" in xml_content


def test_linter_rejects_empty_recipe() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "pspec.xml").write_text("<PISI></PISI>", encoding="utf-8")
        (root / "actions.py").write_text("def install():\n    pass\n", encoding="utf-8")
        findings = RecipeLinter(tmpdir).lint()
    codes = {finding["code"] for finding in findings}
    assert {"PSPEC003", "PSPEC004", "PSPEC005"}.issubset(codes)


def test_linter_accepts_complete_rendered_recipe() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "pspec.xml").write_text(
            PspecRenderer(complete_recipe()).render(), encoding="utf-8"
        )
        (root / "actions.py").write_text(
            "from pisi.actionsapi import pisitools\n\ndef install():\n    pass\n",
            encoding="utf-8",
        )
        findings = RecipeLinter(tmpdir).lint()
    assert not [finding for finding in findings if finding["severity"] == "ERROR"]


def test_actions_renderer_quotes_untrusted_paths() -> None:
    content = ActionsRenderer(
        {
            "install": {
                "preserve": [
                    {"source": "payload/a'b", "target": "/usr/share/a'b"}
                ]
            }
        }
    ).render()
    compile(content, "actions.py", "exec")
    assert '"' in content or "\\'" in content
