from __future__ import annotations

import fnmatch
import re
import subprocess
from collections import deque
from dataclasses import dataclass
from typing import Iterable

_SYSTEMD_PATTERN = "*systemd*"
_DEPENDENCY_LINE_RE = re.compile(r"^\s*\|?\s*(?:Pre)?Depends:\s*(?:<)?([^\s>|(]+)")


@dataclass(frozen=True)
class BlockedDependency:
    requested_package: str
    blocking_dependency: str
    dependency_path: tuple[str, ...]

    def render(self) -> str:
        return (
            "Installation blocked.\n\n"
            f'Package "{self.requested_package}" depends on a systemd-related package:\n\n'
            f"{' -> '.join(self.dependency_path)}\n\n"
            "This distribution does not support systemd-related packages.\n"
            "Find a systemd-free Debian rebuild or use an alternative package."
        )


class AptPolicyError(RuntimeError):
    pass


def is_systemd_related_package(package: str) -> bool:
    """Return True when a package name matches the strict systemd deny rule."""
    return fnmatch.fnmatchcase(package, _SYSTEMD_PATTERN)


def first_blocked_systemd_dependency(
    requested_package: str,
    *,
    runner=subprocess.run,
) -> BlockedDependency | None:
    """Resolve Depends/Pre-Depends closure and return the first systemd match.

    The resolver intentionally checks dependency names before invoking any real
    installation command, so callers can show a policy-specific error instead of
    APT's generic dependency failure.
    """
    # Alternatives form OR-groups; only an unavoidable blocked choice fails.
    def check(package: str, path: tuple[str, ...]) -> tuple[str, ...] | None:
        if is_systemd_related_package(package):
            return path
        if package in path[:-1]:
            return None
        for group in _apt_dependency_groups(package, runner=runner):
            failures = [check(candidate, (*path, candidate)) for candidate in group]
            if failures and all(failure is not None for failure in failures):
                return failures[0]
        return None

    failure = check(requested_package, (requested_package,))
    return (
        BlockedDependency(requested_package, failure[-1], failure)
        if failure is not None else None
    )


def _apt_dependencies(package: str, *, runner=subprocess.run) -> list[str]:
    result = runner(
        ["apt-cache", "depends", "--no-recommends", "--no-suggests", package],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise AptPolicyError(f"Unable to resolve dependencies for {package}: {stderr}")
    return list(_parse_apt_cache_depends(result.stdout.splitlines()))


def _apt_dependency_groups(package: str, *, runner=subprocess.run) -> list[tuple[str, ...]]:
    result = runner(
        ["apt-cache", "depends", "--no-recommends", "--no-suggests", package],
        check=False, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise AptPolicyError(
            f"Unable to resolve dependencies for {package}: {(result.stderr or '').strip()}"
        )
    groups: list[tuple[str, ...]] = []
    alternatives: list[str] = []
    for line in result.stdout.splitlines():
        match = _DEPENDENCY_LINE_RE.match(line)
        if match is None:
            continue
        alternatives.append(match.group(1))
        if not line.lstrip().startswith("|"):
            groups.append(tuple(alternatives))
            alternatives = []
    if alternatives:
        groups.append(tuple(alternatives))
    return groups


def _parse_apt_cache_depends(lines: Iterable[str]) -> Iterable[str]:
    for line in lines:
        match = _DEPENDENCY_LINE_RE.match(line)
        if match is not None:
            yield match.group(1)


def enforce_systemd_free_policy(package: str, *, runner=subprocess.run) -> None:
    blocked = first_blocked_systemd_dependency(package, runner=runner)
    if blocked is not None:
        raise AptPolicyError(blocked.render())
