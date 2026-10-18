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
    groups are considered. :any and :native are suggestions only; the target\n    package name must still be reviewed before recipe generation.
    """

    if len(group.alternatives) != 1:
        return None
    alternative = group.alternatives[0]
    if alternative.architecture_restrictions or alternative.build_profiles:
        return None
    if alternative.architecture_qualifier not in (None, "native", "any"):
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
            if not package or not is_debian_package_installed(package):
                continue
            alternative = model.alternatives[0]
            if alternative.operator is not None:
                if not alternative.version:
                    continue
                architecture_result = subprocess.run(
                    ["dpkg", "--print-architecture"],
                    capture_output=True, text=True, check=False,
                )
                if architecture_result.returncode != 0:
                    continue
                native_arch = architecture_result.stdout.strip()
                version_result = subprocess.run(
                    ["dpkg-query", "-W",
                     "-f=${Architecture}\t${db:Status-Abbrev}\t${Version}\n", package],
                    capture_output=True, text=True, check=False,
                )
                if version_result.returncode != 0:
                    continue
                versions = [
                    parts[2] for line in version_result.stdout.splitlines()
                    if len(parts := line.split("\t")) == 3
                    and parts[0] == native_arch and parts[1].startswith("ii ")
                ]
                if len(versions) != 1 or not versions[0]:
                    continue
                comparison = subprocess.run(
                    ["dpkg", "--compare-versions", versions[0],
                     alternative.operator, alternative.version],
                    capture_output=True, text=True, check=False,
                )
                if comparison.returncode != 0:
                    continue
            mappings[model.raw] = package
    return mappings
