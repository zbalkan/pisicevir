from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

from tests.test_deb_adapter import create_dummy_deb


def run_cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pisicevir.cli", *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_reviewed_data_package_workflow() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        package = os.path.join(tmpdir, "test.deb")
        plan_path = Path(tmpdir, "plan.yaml")
        recipe_dir = Path(tmpdir, "recipe")
        create_dummy_deb(package)

        classify = run_cli("classify", package)
        assert classify.returncode == 0, classify.stderr
        assert '"conversion_class": "A"' in classify.stdout

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
        assert plan["approved"] is False
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

        lint = run_cli("lint", os.fspath(recipe_dir), "--strict")
        assert lint.returncode == 0, lint.stdout + lint.stderr
        assert (recipe_dir / "files/test.deb").is_file()
        assert (recipe_dir / "metadata/inspection.json").is_file()

        pspec = (recipe_dir / "pspec.xml").read_text(encoding="utf-8")
        actions = (recipe_dir / "actions.py").read_text(encoding="utf-8")
        provenance = json.loads(
            (recipe_dir / "metadata/provenance.json").read_text(encoding="utf-8")
        )
        assert "sha1sum=" in pspec
        assert "sha256sum=" not in pspec
        assert "def setup():" in actions
        assert "subprocess" not in actions
        assert len(provenance["source_sha256"]) == 64
