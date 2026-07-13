from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pisicevir import __version__
from tools.generate_debian_packaging import generate
from tools.release_metadata import SemVer, read_source_version


def tree_snapshot(root: Path) -> dict[str, tuple[bytes, int]]:
    return {
        path.relative_to(root).as_posix(): (path.read_bytes(), path.stat().st_mode & 0o777)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_source_version_is_single_authoritative_value() -> None:
    assert read_source_version() == __version__


def test_semver_precedence() -> None:
    assert SemVer.parse("0.1.0") < SemVer.parse("0.2.0")
    assert SemVer.parse("1.0.0-alpha") < SemVer.parse("1.0.0")
    assert SemVer.parse("1.0.0+build.1") == SemVer.parse("1.0.0+build.2")
    with pytest.raises(ValueError):
        SemVer.parse("1.0")
    with pytest.raises(ValueError):
        SemVer.parse("1.0.0-01")


def test_debian_packaging_generation_is_deterministic() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        changelog = root / "changelog"
        changelog.write_text(
            "pisicevir (0.1.0-1) unstable; urgency=medium\n\n"
            "  * Test release\n\n"
            " -- Test Packager <test@example.test>  Thu, 01 Jan 1970 00:00:00 +0000\n",
            encoding="utf-8",
        )
        first = root / "first"
        second = root / "second"
        arguments = {
            "changelog": changelog,
            "maintainer_name": "Test Packager",
            "maintainer_email": "test@example.test",
            "homepage": "https://example.test/pisicevir",
        }
        generate(first, **arguments)
        generate(second, **arguments)

        assert tree_snapshot(first) == tree_snapshot(second)
        assert not (first / "install").exists()
        assert "org.caracal.Pisicevir.desktop" in (
            first / "pisicevir-gui.install"
        ).read_text(encoding="utf-8")
        assert "org.caracal.Pisicevir.desktop" not in (
            first / "pisicevir.install"
        ).read_text(encoding="utf-8")
