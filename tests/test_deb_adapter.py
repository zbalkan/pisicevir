from __future__ import annotations

import io
import os
import subprocess
import tarfile
import tempfile
from pathlib import Path

import pytest

from pisicevir.source_adapters.deb import DebAdapter, DebFormatError


def _add_bytes(
    archive: tarfile.TarFile,
    name: str,
    content: bytes,
    mode: int = 0o644,
) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(content)
    info.mode = mode
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    archive.addfile(info, io.BytesIO(content))


def create_dummy_deb(
    path: str,
    *,
    executable: bool = False,
    maintainer_script: bool = False,
    malicious_path: str | None = None,
    debian_binary: bytes = b"2.0\n",
) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        control_path = root / "control.tar.gz"
        data_path = root / "data.tar.gz"

        with tarfile.open(control_path, "w:gz") as archive:
            control = (
                b"Package: test-pkg\n"
                b"Version: 1.0.0-1\n"
                b"Architecture: all\n"
                b"Description: A test package\n"
            )
            _add_bytes(archive, "./control", control)
            if maintainer_script:
                _add_bytes(archive, "./postinst", b"#!/bin/sh\nset -e\n", 0o755)

        with tarfile.open(data_path, "w:gz") as archive:
            if malicious_path:
                _add_bytes(archive, malicious_path, b"escape")
            elif executable:
                _add_bytes(
                    archive,
                    "./usr/bin/test-cmd",
                    b"#!/bin/sh\necho hello\n",
                    0o755,
                )
            else:
                _add_bytes(
                    archive,
                    "./usr/share/test-pkg/data.txt",
                    b"hello\n",
                )

        (root / "debian-binary").write_bytes(debian_binary)
        subprocess.run(
            [
                "ar",
                "rc",
                path,
                "debian-binary",
                "control.tar.gz",
                "data.tar.gz",
            ],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )


def test_deb_adapter_returns_structured_payload() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        deb_path = os.path.join(tmpdir, "test.deb")
        create_dummy_deb(deb_path, executable=True)
        result = DebAdapter(deb_path).inspect()

    assert result["source_type"] == "deb"
    assert result["metadata"]["Package"] == "test-pkg"
    assert result["metadata"]["Architecture"] == "all"
    assert len(result["sha256"]) == 64
    entry = next(item for item in result["payload"] if item["path"] == "usr/bin/test-cmd")
    assert entry["kind"] == "file"
    assert entry["mode"] == 0o755
    assert entry["is_script"] is True
    assert len(entry["sha256"]) == 64


def test_deb_adapter_reports_maintainer_scripts() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        deb_path = os.path.join(tmpdir, "test.deb")
        create_dummy_deb(deb_path, maintainer_script=True)
        result = DebAdapter(deb_path).inspect()

    assert "postinst" in result["maintainer_scripts"]


def test_deb_adapter_rejects_path_traversal() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        deb_path = os.path.join(tmpdir, "test.deb")
        create_dummy_deb(deb_path, malicious_path="../escape")
        with pytest.raises(DebFormatError, match="Unsafe archive path"):
            DebAdapter(deb_path).inspect()


def test_deb_adapter_rejects_unknown_format_version() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        deb_path = os.path.join(tmpdir, "test.deb")
        create_dummy_deb(deb_path, debian_binary=b"1.0\n")
        with pytest.raises(DebFormatError, match="Unsupported Debian binary package format"):
            DebAdapter(deb_path).inspect()
