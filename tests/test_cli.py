from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

from pisicevir import __version__
from tests.test_deb_adapter import create_dummy_deb


def run_cli(
    *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pisicevir.cli", *args],
        capture_output=True,
        text=True,
        env=env,
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
        Path(tmpdir, "actions.py").write_text(
            "def install():\n    pass\n", encoding="utf-8"
        )
        result = run_cli("lint", tmpdir)
    assert result.returncode == 9
    assert "PSPEC003" in result.stdout


def test_unimplemented_command_returns_nonzero() -> None:
    result = run_cli("build", "recipe")
    assert result.returncode == 5
    assert "not implemented" in result.stderr


def test_validate_reports_recipe_status_as_json() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "pspec.xml").write_text("<PISI></PISI>", encoding="utf-8")
        Path(tmpdir, "actions.py").write_text(
            "def install():\n    pass\n", encoding="utf-8"
        )
        result = run_cli("validate", tmpdir, "--format", "json")
    assert result.returncode == 9
    document = json.loads(result.stdout)
    assert document["stage"] == "recipe"
    assert document["valid"] is False
    assert document["summary"]["errors"] >= 1


def test_generate_unresolved_dependencies_prompts_for_install_or_mapping() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        package = os.path.join(tmpdir, "test.deb")
        plan_path = Path(tmpdir, "plan.yaml")
        create_dummy_deb(package, depends="python3-yaml, binutils")

        plan_result = run_cli(
            "plan",
            package,
            "--homepage",
            "https://example.test/test-pkg",
            "--license",
            "GPL-3.0-or-later",
            "--packager-name",
            "Test Packager",
            "--packager-email",
            "test@example.test",
            "--output",
            os.fspath(plan_path),
        )
        assert plan_result.returncode == 0, plan_result.stderr
        plan = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
        plan["approved"] = True
        plan_path.write_text(yaml.safe_dump(plan, sort_keys=False), encoding="utf-8")

        result = run_cli(
            "generate",
            package,
            "--plan",
            os.fspath(plan_path),
            "--output",
            os.path.join(tmpdir, "recipe"),
        )

    assert result.returncode == 8
    assert "Install or map these dependencies" in result.stderr
    assert "  - binutils" in result.stderr
    assert "  - python3-yaml" in result.stderr
    assert "dependencies.map" in result.stderr
    assert "dependencies.ignore" in result.stderr


def test_validate_accepts_complete_recipe() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        package = os.path.join(tmpdir, "test.deb")
        plan_path = Path(tmpdir, "plan.yaml")
        recipe_dir = Path(tmpdir, "recipe")
        create_dummy_deb(package)

        plan_result = run_cli(
            "plan",
            package,
            "--homepage",
            "https://example.test/test-pkg",
            "--license",
            "GPL-3.0-or-later",
            "--packager-name",
            "Test Packager",
            "--packager-email",
            "test@example.test",
            "--output",
            os.fspath(plan_path),
        )
        assert plan_result.returncode == 0, plan_result.stderr
        plan = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
        plan["approved"] = True
        plan_path.write_text(yaml.safe_dump(plan, sort_keys=False), encoding="utf-8")

        environment = dict(os.environ)
        environment["SOURCE_DATE_EPOCH"] = "1672531200"
        generate = run_cli(
            "generate",
            package,
            "--plan",
            os.fspath(plan_path),
            "--output",
            os.fspath(recipe_dir),
            env=environment,
        )
        assert generate.returncode == 0, generate.stderr

        result = run_cli("validate", os.fspath(recipe_dir))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Result: valid" in result.stdout
