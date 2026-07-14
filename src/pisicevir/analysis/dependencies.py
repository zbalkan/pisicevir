from __future__ import annotations

import re
from typing import Iterable, List

from pisicevir.models.debian import DebianDependencyAlternative, DebianDependencyGroup

_ALTERNATIVE_RE = re.compile(
    r"^\s*"
    r"(?P<package>[a-z0-9][a-z0-9+.-]*)"
    r"(?::(?P<qualifier>[a-z0-9-]+))?"
    r"(?:\s*\(\s*(?P<operator><<|<=|=|>=|>>)\s*(?P<version>[^)\s]+)\s*\))?"
    r"(?:\s*\[(?P<architectures>[^]]+)\])?"
    r"(?P<profiles>(?:\s*<[^>]+>)*)"
    r"\s*$"
)


class DebianDependencyError(ValueError):
    pass


def parse_dependency_fields(metadata: dict[str, str]) -> dict[str, List[DebianDependencyGroup]]:
    result: dict[str, List[DebianDependencyGroup]] = {}
    for field in ("Pre-Depends", "Depends"):
        value = metadata.get(field, "").strip()
        if value:
            result[field] = parse_dependency_expression(value)
    return result


def parse_dependency_expression(value: str) -> List[DebianDependencyGroup]:
    groups: List[DebianDependencyGroup] = []
    for raw_group in _split_top_level(value, ","):
        raw_group = raw_group.strip()
        if not raw_group:
            raise DebianDependencyError("Empty Debian dependency group")
        alternatives = [
            _parse_alternative(raw_alternative)
            for raw_alternative in _split_top_level(raw_group, "|")
        ]
        groups.append(
            DebianDependencyGroup(raw=raw_group, alternatives=alternatives)
        )
    return groups


def _parse_alternative(value: str) -> DebianDependencyAlternative:
    raw = value.strip()
    match = _ALTERNATIVE_RE.fullmatch(raw)
    if match is None:
        raise DebianDependencyError(f"Unsupported Debian dependency syntax: {raw}")

    architectures = (
        match.group("architectures").split()
        if match.group("architectures")
        else []
    )
    profiles = re.findall(r"<([^>]+)>", match.group("profiles") or "")
    return DebianDependencyAlternative(
        raw=raw,
        package=match.group("package"),
        architecture_qualifier=match.group("qualifier"),
        operator=match.group("operator"),
        version=match.group("version"),
        architecture_restrictions=architectures,
        build_profiles=profiles,
    )


def _split_top_level(value: str, delimiter: str) -> Iterable[str]:
    start = 0
    parentheses = 0
    brackets = 0
    angles = 0
    for index, character in enumerate(value):
        if character == "(":
            parentheses += 1
        elif character == ")":
            parentheses -= 1
        elif character == "[":
            brackets += 1
        elif character == "]":
            brackets -= 1
        elif character == "<" and parentheses == 0 and brackets == 0:
            angles += 1
        elif character == ">" and parentheses == 0 and brackets == 0:
            angles -= 1
        elif (
            character == delimiter
            and parentheses == 0
            and brackets == 0
            and angles == 0
        ):
            yield value[start:index]
            start = index + 1

        if parentheses < 0 or brackets < 0 or angles < 0:
            raise DebianDependencyError("Unbalanced Debian dependency expression")

    if parentheses or brackets or angles:
        raise DebianDependencyError("Unbalanced Debian dependency expression")
    yield value[start:]
