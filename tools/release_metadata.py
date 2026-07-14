#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

_SEMVER_RE = re.compile(
    r"^(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


@dataclass(frozen=True)
class SemVer:
    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] = ()
    build: tuple[str, ...] = ()

    @classmethod
    def parse(cls, value: str) -> "SemVer":
        match = _SEMVER_RE.fullmatch(value)
        if match is None:
            raise ValueError(f"Invalid semantic version: {value}")
        prerelease = tuple(match.group(4).split(".")) if match.group(4) else ()
        for identifier in prerelease:
            if identifier.isdigit() and len(identifier) > 1 and identifier.startswith("0"):
                raise ValueError(
                    f"Numeric prerelease identifier has a leading zero: {identifier}"
                )
        build = tuple(match.group(5).split(".")) if match.group(5) else ()
        return cls(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
            prerelease,
            build,
        )

    def precedence_key(self) -> tuple[object, ...]:
        if not self.prerelease:
            prerelease_key: tuple[object, ...] = (1,)
        else:
            identifiers: list[object] = [0]
            for value in self.prerelease:
                identifiers.append((0, int(value)) if value.isdigit() else (1, value))
            prerelease_key = tuple(identifiers)
        return self.major, self.minor, self.patch, prerelease_key

    def __lt__(self, other: "SemVer") -> bool:
        return self.precedence_key() < other.precedence_key()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return self.precedence_key() == other.precedence_key()

    def __str__(self) -> str:
        value = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            value += "-" + ".".join(self.prerelease)
        if self.build:
            value += "+" + ".".join(self.build)
        return value


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def read_source_version(path: Path = Path("src/pisicevir/__init__.py")) -> str:
    module = ast.parse(path.read_text(encoding="utf-8"), filename=os.fspath(path))
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if isinstance(value, str):
                SemVer.parse(value)
                return value
    raise ValueError(f"Unable to read __version__ from {path}")


def reachable_versions() -> list[tuple[SemVer, str]]:
    versions: list[tuple[SemVer, str]] = []
    for tag in git("tag", "--list", "v*").splitlines():
        try:
            version = SemVer.parse(tag[1:])
        except ValueError:
            print(f"Ignoring non-SemVer tag: {tag}")
            continue
        reachable = subprocess.run(
            ["git", "merge-base", "--is-ancestor", tag, "HEAD"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
        if reachable:
            versions.append((version, tag))
        else:
            print(f"Ignoring tag not reachable from HEAD: {tag}")
    return versions


def validate_release(output: Path | None) -> dict[str, str]:
    subprocess.run(["git", "fetch", "--tags", "--force"], check=True)
    current = SemVer.parse(read_source_version())
    versions = reachable_versions()
    latest_version: SemVer | None = None
    latest_tag = ""
    if versions:
        latest_version, latest_tag = max(versions, key=lambda item: item[0].precedence_key())
        if current == latest_version:
            raise ValueError(
                f"Source version {current} is already published as {latest_tag}"
            )
        if current < latest_version:
            raise ValueError(
                f"Source version {current} is lower than latest tag {latest_tag}"
            )

    tag = f"v{current}"
    if subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0:
        raise ValueError(f"Tag already exists: {tag}")

    values = {
        "version": str(current),
        "tag": tag,
        "latest_tag": latest_tag,
        "debian_version": f"{current}-1",
        "source_date_epoch": git("show", "-s", "--format=%ct", "HEAD"),
    }
    if output:
        with output.open("a", encoding="utf-8", newline="\n") as stream:
            for key, value in values.items():
                stream.write(f"{key}={value}\n")
    return values


def commits_between(previous_tag: str) -> list[tuple[str, str]]:
    revision = f"{previous_tag}..HEAD" if previous_tag else "HEAD"
    output = git(
        "log",
        revision,
        "--no-merges",
        "--reverse",
        "--format=%H%x1f%s",
    )
    commits: list[tuple[str, str]] = []
    for line in output.splitlines():
        if not line:
            continue
        sha, subject = line.split("\x1f", 1)
        commits.append((sha, subject.strip()))
    if not commits:
        raise ValueError("There are no commits to include in this release")
    return commits


def generate_metadata(
    *,
    version: str,
    tag: str,
    previous_tag: str,
    repository: str,
    release_notes: Path,
    changelog: Path,
    maintainer_name: str,
    maintainer_email: str,
    source_date_epoch: int,
) -> None:
    SemVer.parse(version)
    commits = commits_between(previous_tag)

    notes = [f"# Pisicevir {version}", ""]
    notes.append(
        f"Changes since `{previous_tag}`:" if previous_tag else "Initial release changes:"
    )
    notes.append("")
    for sha, subject in commits:
        notes.append(
            f"- {subject} ([`{sha[:7]}`](https://github.com/{repository}/commit/{sha}))"
        )
    if previous_tag:
        notes.extend(
            [
                "",
                f"**Full comparison:** https://github.com/{repository}/compare/{previous_tag}...{tag}",
            ]
        )
    release_notes.parent.mkdir(parents=True, exist_ok=True)
    release_notes.write_text("\n".join(notes) + "\n", encoding="utf-8", newline="\n")

    release_date = datetime.fromtimestamp(
        source_date_epoch, tz=timezone.utc
    ).strftime("%a, %d %b %Y %H:%M:%S +0000")
    changelog_lines = [
        f"pisicevir ({version}-1) noble; urgency=medium",
        "",
    ]
    changelog_lines.extend(f"  * {subject}" for _, subject in commits)
    changelog_lines.extend(
        [
            "",
            f" -- {maintainer_name} <{maintainer_email}>  {release_date}",
            "",
        ]
    )
    changelog.parent.mkdir(parents=True, exist_ok=True)
    changelog.write_text(
        "\n".join(changelog_lines), encoding="utf-8", newline="\n"
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    subcommands = root.add_subparsers(dest="command", required=True)

    validate = subcommands.add_parser("validate")
    validate.add_argument("--github-output", type=Path)

    generate = subcommands.add_parser("generate")
    generate.add_argument("--version", required=True)
    generate.add_argument("--tag", required=True)
    generate.add_argument("--previous-tag", default="")
    generate.add_argument("--repository", required=True)
    generate.add_argument("--release-notes", type=Path, required=True)
    generate.add_argument("--changelog", type=Path, required=True)
    generate.add_argument("--maintainer-name", required=True)
    generate.add_argument("--maintainer-email", required=True)
    generate.add_argument("--source-date-epoch", type=int, required=True)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "validate":
        values = validate_release(args.github_output)
        for key, value in values.items():
            print(f"{key}={value}")
        return 0
    generate_metadata(
        version=args.version,
        tag=args.tag,
        previous_tag=args.previous_tag,
        repository=args.repository,
        release_notes=args.release_notes,
        changelog=args.changelog,
        maintainer_name=args.maintainer_name,
        maintainer_email=args.maintainer_email,
        source_date_epoch=args.source_date_epoch,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
