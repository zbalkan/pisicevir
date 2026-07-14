from __future__ import annotations

import shutil
import subprocess

from typing import Any

from pisicevir.models.debian import DebianDependencyGroup


def canonical_debian_package_name(group: DebianDependencyGroup) -> str | None:
    """Return the plain package name for dependency groups Pisicevir can resolve.

    PISI dependency names cannot express Debian alternatives, version operators,
    architecture qualifiers, or architecture/build-profile restrictions directly.
    For automatic host-installed resolution, only unambiguous single-package
    groups are considered and the Debian architecture qualifier is stripped.
    """

    if len(group.alternatives) != 1:
        return None
    alternative = group.alternatives[0]
    if alternative.architecture_restrictions or alternative.build_profiles:
        return None
    return alternative.package


def is_debian_package_installed(package: str) -> bool:
    """Return True when dpkg reports an installed Debian package."""

    if shutil.which("dpkg-query") is None:
        return False
    result = subprocess.run(
        ["dpkg-query", "-W", "-f=${db:Status-Abbrev}", package],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.startswith("ii ")


def installed_dependency_mappings(
    dependencies: dict[str, list[Any]],
) -> dict[str, str]:
    """Map resolvable Debian dependency groups to installed package names."""

    mappings: dict[str, str] = {}
    for field in ("Pre-Depends", "Depends"):
        for group in dependencies.get(field, []):
            model = (
                group
                if isinstance(group, DebianDependencyGroup)
                else DebianDependencyGroup(**group)
            )
            package = canonical_debian_package_name(model)
            if package and is_debian_package_installed(package):
                mappings[model.raw] = package
    return mappings
