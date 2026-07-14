#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import tarfile
from pathlib import PurePosixPath
from typing import Sequence

FORBIDDEN_PARTS = {
    ".git",
    ".github",
    "__pycache__",
    ".pytest_cache",
    "tests",
    "tools",
    "debian",
}
FORBIDDEN_SUFFIXES = {".pyc", ".pyo"}


def package_paths(package: str) -> list[str]:
    process = subprocess.Popen(
        ["dpkg-deb", "--fsys-tarfile", package],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.stdout is None or process.stderr is None:
        raise RuntimeError("Unable to capture dpkg-deb output")

    paths: list[str] = []
    with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
        for member in archive:
            path = member.name
            while path.startswith("./"):
                path = path[2:]
            if path and path != ".":
                paths.append(path)
    process.stdout.close()
    stderr = process.stderr.read()
    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(stderr.decode("utf-8", errors="replace"))
    return sorted(paths)


def verify(package: str) -> None:
    paths = package_paths(package)
    if not paths:
        raise ValueError(f"Package has no payload: {package}")

    for raw_path in paths:
        path = PurePosixPath(raw_path)
        if FORBIDDEN_PARTS.intersection(path.parts):
            raise ValueError(f"Forbidden build path in {package}: {raw_path}")
        if any(part.endswith(".egg-info") for part in path.parts):
            raise ValueError(f"Legacy egg metadata leaked into {package}: {raw_path}")
        if any(raw_path.endswith(suffix) for suffix in FORBIDDEN_SUFFIXES):
            raise ValueError(f"Forbidden generated file in {package}: {raw_path}")

    expected_command = (
        "usr/bin/pisicevir-gui" if "pisicevir-gui_" in package else "usr/bin/pisicevir"
    )
    if expected_command not in paths:
        raise ValueError(f"Expected command is missing from {package}: {expected_command}")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("packages", nargs="+")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    for package in args.packages:
        verify(package)
        print(f"Verified package payload: {package}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
