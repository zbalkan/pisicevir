"""F1: A package being installed is insufficient to satisfy a Debian constraint."""
from unittest.mock import patch

from pisicevir.analysis.dependencies import parse_dependency_expression
from pisicevir.analysis.dependency_resolution import installed_dependency_mappings


def test_installed_older_version_is_not_automatically_mapped():
    group = parse_dependency_expression("python3 (>= 3.12)")[0].model_dump()
    with patch("pisicevir.analysis.dependency_resolution.is_debian_package_installed", return_value=True):
        with patch("subprocess.run") as run:
            run.side_effect = [__import__("subprocess").CompletedProcess([], 0, "3.11.9", ""), __import__("subprocess").CompletedProcess([], 1, "", "")]
            result = installed_dependency_mappings({"Depends": [group]})
    assert result == {}


def test_installed_satisfying_version_is_mapped():
    group = parse_dependency_expression("python3 (>= 3.12)")[0].model_dump()
    with patch("pisicevir.analysis.dependency_resolution.is_debian_package_installed", return_value=True):
        with patch("subprocess.run") as run:
            run.side_effect = [__import__("subprocess").CompletedProcess([], 0, "3.12.1", ""), __import__("subprocess").CompletedProcess([], 0, "", "")]
            result = installed_dependency_mappings({"Depends": [group]})
    assert result == {"python3 (>= 3.12)": "python3"}
