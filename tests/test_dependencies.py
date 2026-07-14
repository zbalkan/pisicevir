from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from pisicevir.analysis.apt_policy import (
    AptPolicyError,
    enforce_systemd_free_policy,
    first_blocked_systemd_dependency,
    is_systemd_related_package,
)
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
        generator = RecipeGenerator(
            package, inspection, plan, os.path.join(tmpdir, "recipe")
        )
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


def test_generator_reports_all_missing_review_fields() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        package = os.path.join(tmpdir, "test.deb")
        create_dummy_deb(package)
        inspection = DebAdapter(package).inspect()
        classification = {
            "conversion_class": "A",
            "policy_family": "deb-data",
            "confidence": "high",
            "reasons": [],
            "warnings": [],
        }
        plan = create_initial_plan(inspection, classification)
        generator = RecipeGenerator(
            package, inspection, plan, os.path.join(tmpdir, "recipe")
        )

        with pytest.raises(ValueError) as excinfo:
            generator.generate()

        message = str(excinfo.value)
        assert "Transformation plan still needs review updates" in message
        assert "approved" in message
        assert "homepage" in message
        assert "licenses" in message
        assert "packager.name" in message
        assert "packager.email" in message


def test_systemd_policy_matches_any_systemd_package_name() -> None:
    assert is_systemd_related_package("systemd")
    assert is_systemd_related_package("systemd-sysv")
    assert is_systemd_related_package("libsystemd0")
    assert is_systemd_related_package("libpam-systemd")
    assert is_systemd_related_package("libnss-systemd")
    assert not is_systemd_related_package("elogind")


def test_systemd_policy_resolves_dependency_closure_and_reports_path() -> None:
    outputs = {
        "foo": "foo\n  Depends: bar\n",
        "bar": "bar\n  Depends: libsystemd0\n",
    }

    def runner(command, **kwargs):
        class Result:
            returncode = 0
            stderr = ""
            stdout = outputs[command[-1]]

        return Result()

    blocked = first_blocked_systemd_dependency("foo", runner=runner)

    assert blocked is not None
    assert blocked.requested_package == "foo"
    assert blocked.blocking_dependency == "libsystemd0"
    assert blocked.dependency_path == ("foo", "bar", "libsystemd0")


def test_systemd_policy_error_message_matches_frontend_policy() -> None:
    outputs = {
        "foo": "foo\n  Depends: bar\n",
        "bar": "bar\n  Depends: libsystemd0\n",
    }

    def runner(command, **kwargs):
        class Result:
            returncode = 0
            stderr = ""
            stdout = outputs[command[-1]]

        return Result()

    with pytest.raises(AptPolicyError) as excinfo:
        enforce_systemd_free_policy("foo", runner=runner)

    message = str(excinfo.value)
    assert "Installation blocked." in message
    assert 'Package "foo" depends on a systemd-related package:' in message
    assert "foo -> bar -> libsystemd0" in message
    assert (
        "Find a systemd-free Debian rebuild or use an alternative package." in message
    )
