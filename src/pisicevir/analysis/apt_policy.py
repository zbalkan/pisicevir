from __future__ import annotations

import fnmatch
import re
import subprocess
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
    resolved: dict[str, tuple[str, ...] | None] = {}
    active: set[str] = set()

    def check(package: str) -> tuple[str, ...] | None:
        if is_systemd_related_package(package):
            return (package,)
        if package in resolved:
            return resolved[package]
        if package in active:
            return None
        active.add(package)
        try:
            for group in _apt_dependency_groups(package, runner=runner):
                failure_path = None
                for candidate in group:
                    failure = check(candidate)
                    if failure is None:
                        break
                    if failure_path is None:
                        failure_path = failure
                else:
                    if failure_path is not None:
                        result = (package, *failure_path)
                        resolved[package] = result
                        return result
            resolved[package] = None
            return None
        finally:
            active.remove(package)

    failure = check(requested_package)
    return BlockedDependency(requested_package, failure[-1], failure) if failure else None


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
        candidate = match.group(1)
        if line.lstrip().startswith("|"):
            if not alternatives and groups:
                alternatives = list(groups.pop())
            alternatives.append(candidate)
        else:
            if alternatives:
                groups.append(tuple(alternatives))
                alternatives = []
            groups.append((candidate,))
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
