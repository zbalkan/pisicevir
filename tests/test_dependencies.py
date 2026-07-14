from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from pisicevir.analysis.dependencies import parse_dependency_expression
from pisicevir.analysis import planning
from pisicevir.analysis.planning import create_initial_plan
from pisicevir.renderers.generator import RecipeGenerator
from pisicevir.source_adapters.deb import DebAdapter
from tests.test_deb_adapter import create_dummy_deb


def test_dependency_parser_handles_versions_alternatives_and_architecture() -> None:
    groups = parse_dependency_expression(
        "python3:any (>= 3.10~) | pypy3, libc6 (>= 2.36) [amd64 arm64]"
    )
    assert len(groups) == 2
    assert groups[0].alternatives[0].package == "python3"
    assert groups[0].alternatives[0].architecture_qualifier == "any"
    assert groups[0].alternatives[0].operator == ">="
    assert groups[0].alternatives[0].version == "3.10~"
    assert groups[0].alternatives[1].package == "pypy3"
    assert groups[1].alternatives[0].architecture_restrictions == ["amd64", "arm64"]


def test_plan_maps_installed_dependency_groups_when_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        package = os.path.join(tmpdir, "test.deb")
        create_dummy_deb(package, depends="python3:any, python3-yaml")
        inspection = DebAdapter(package).inspect()
        classification = {
            "conversion_class": "A",
            "policy_family": "deb-data",
            "confidence": "high",
            "reasons": [],
            "warnings": [],
        }
        monkeypatch.setattr(
            planning,
            "installed_dependency_mappings",
            lambda dependencies: {
                "python3:any": "python3",
                "python3-yaml": "python3-yaml",
            },
        )

        plan = create_initial_plan(
            inspection,
            classification,
            homepage="https://example.test/test-pkg",
            licenses=["GPL-3.0-or-later"],
            packager_name="Test Packager",
            packager_email="test@example.test",
            resolve_installed_dependencies=True,
        )

        assert plan["dependencies"]["map"] == {
            "python3:any": "python3",
            "python3-yaml": "python3-yaml",
        }


def test_generator_rejects_unresolved_dependency_groups() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        package = os.path.join(tmpdir, "test.deb")
        create_dummy_deb(package, depends="python3 (>= 3.10), python3-yaml")
        inspection = DebAdapter(package).inspect()
        classification = {
            "conversion_class": "A",
            "policy_family": "deb-data",
            "confidence": "high",
            "reasons": [],
            "warnings": [],
        }
        plan = create_initial_plan(
            inspection,
            classification,
            homepage="https://example.test/test-pkg",
            licenses=["GPL-3.0-or-later"],
            packager_name="Test Packager",
            packager_email="test@example.test",
        )
        plan["approved"] = True
        generator = RecipeGenerator(package, inspection, plan, os.path.join(tmpdir, "recipe"))
        with pytest.raises(ValueError, match="unresolved"):
            generator.generate()


def test_generator_accepts_mapped_and_justifiably_ignored_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        package = os.path.join(tmpdir, "test.deb")
        create_dummy_deb(package, depends="python3 (>= 3.10), python3-yaml")
        inspection = DebAdapter(package).inspect()
        classification = {
            "conversion_class": "A",
            "policy_family": "deb-data",
            "confidence": "high",
            "reasons": [],
            "warnings": [],
        }
        plan = create_initial_plan(
            inspection,
            classification,
            homepage="https://example.test/test-pkg",
            licenses=["GPL-3.0-or-later"],
            packager_name="Test Packager",
            packager_email="test@example.test",
        )
        plan["approved"] = True
        plan["dependencies"]["map"]["python3 (>= 3.10)"] = "python3"
        plan["dependencies"]["ignore"] = [
            {
                "source": "python3-yaml",
                "reason": "Provided by the target image baseline for this fixture",
            }
        ]
        monkeypatch.setenv("SOURCE_DATE_EPOCH", "1672531200")
        output = RecipeGenerator(
            package, inspection, plan, os.path.join(tmpdir, "recipe")
        ).generate()
        pspec = Path(output, "pspec.xml").read_text(encoding="utf-8")
        assert "<Dependency>python3</Dependency>" in pspec
