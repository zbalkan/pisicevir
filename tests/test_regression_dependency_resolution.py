"""Regression tests for installed Debian dependency version matching."""

import subprocess
from unittest.mock import patch

from pisicevir.analysis.dependencies import parse_dependency_expression
from pisicevir.analysis.dependency_resolution import (
    canonical_debian_package_name,
    installed_dependency_mappings,
)


def _run_version_case(expression, installed_version, compare_returncode):
    group = parse_dependency_expression(expression)[0].model_dump()
    with patch(
        "pisicevir.analysis.dependency_resolution.is_debian_package_installed",
        return_value=True,
    ), patch("subprocess.run") as run:
        run.side_effect = [
            subprocess.CompletedProcess([], 0, "amd64\n", ""),
            subprocess.CompletedProcess(
                [], 0, f"amd64\tii \t{installed_version}\n", ""
            ),
            subprocess.CompletedProcess([], compare_returncode, "", ""),
        ]
        result = installed_dependency_mappings({"Depends": [group]})
    return result, run


def test_installed_older_version_is_not_automatically_mapped():
    result, _ = _run_version_case("python3 (>= 3.12)", "3.11.9", 1)
    assert result == {}


def test_installed_satisfying_version_is_mapped():
    result, _ = _run_version_case("python3 (>= 3.12)", "3.12.1", 0)
    assert result == {"python3 (>= 3.12)": "python3"}


def test_unsatisfied_strict_version_constraint_is_not_mapped():
    result, run = _run_version_case("python3 (>> 3.12)", "3.12", 1)
    assert result == {}
    assert run.call_args_list[-1].args[0] == [
        "dpkg", "--compare-versions", "3.12", ">>", "3.12"
    ]


def test_multiarch_versions_are_not_concatenated():
    group = parse_dependency_expression("python3 (>= 3.13)")[0].model_dump()
    with patch(
        "pisicevir.analysis.dependency_resolution.is_debian_package_installed",
        return_value=True,
    ), patch("subprocess.run") as run:
        run.side_effect = [
            subprocess.CompletedProcess([], 0, "amd64\n", ""),
            subprocess.CompletedProcess(
                [], 0, "i386\tii \t9.99\namd64\tii \t3.12\n", ""
            ),
            subprocess.CompletedProcess([], 1, "", ""),
        ]
        assert installed_dependency_mappings({"Depends": [group]}) == {}
        assert run.call_args_list[-1].args[0][2] == "3.12"


def test_missing_version_does_not_call_dpkg():
    group = parse_dependency_expression("python3 (>= 3.12)")[0].model_dump()
    group["alternatives"][0]["version"] = None
    with patch(
        "pisicevir.analysis.dependency_resolution.is_debian_package_installed",
        return_value=True,
    ), patch("subprocess.run") as run:
        assert installed_dependency_mappings({"Depends": [group]}) == {}
        run.assert_not_called()


def test_any_qualifier_stays_a_reviewable_suggestion():
    group = parse_dependency_expression("python3:any")[0]
    assert canonical_debian_package_name(group) == "python3"


def test_alternatives_are_not_auto_mapped_without_a_selected_target():
    group = parse_dependency_expression("python3 | pypy3")[0]
    assert canonical_debian_package_name(group) is None
