from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from pisicevir import __version__
from tests.test_deb_adapter import create_dummy_deb


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pisicevir.cli", *args],
        capture_output=True,
        text=True,
    )


def test_cli_version_uses_package_version() -> None:
    result = run_cli("--version")
    assert result.returncode == 0
    assert f"pisicevir {__version__}" in result.stdout


def test_cli_help() -> None:
    result = run_cli("--help")
    assert result.returncode == 0
    assert "usage: pisicevir" in result.stdout


def test_inspect_json_and_output_file() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        package = os.path.join(tmpdir, "test.deb")
        output = os.path.join(tmpdir, "inspection.json")
        create_dummy_deb(package)
        result = run_cli("inspect", package, "--format", "json", "--output", output)
        assert result.returncode == 0, result.stderr
        document = json.loads(Path(output).read_text(encoding="utf-8"))
    assert document["metadata"]["Package"] == "test-pkg"
    assert document["payload"][0]["path"] == "usr/share/test-pkg/data.txt"


def test_lint_returns_nonzero_for_errors() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "pspec.xml").write_text("<PISI></PISI>", encoding="utf-8")
        Path(tmpdir, "actions.py").write_text("def install():\n    pass\n", encoding="utf-8")
        result = run_cli("lint", tmpdir)
    assert result.returncode == 9
    assert "PSPEC003" in result.stdout


def test_unimplemented_command_returns_nonzero() -> None:
    result = run_cli("build", "recipe")
    assert result.returncode == 5
    assert "not implemented" in result.stderr
