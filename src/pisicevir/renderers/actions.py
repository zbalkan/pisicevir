from __future__ import annotations

from typing import Any, Dict, List
import posixpath

_TEMPLATE = r'''#!/usr/bin/python3

import os
import posixpath
import shutil
import tarfile
from pathlib import Path, PurePosixPath

import zstandard
from pisi.actionsapi import get, pisitools


_OPERATIONS = {operations!r}
_SELECTED = {{item["source"].removeprefix("payload/") for item in _OPERATIONS}}
_MAX_MEMBER_SIZE = 2 * 1024 * 1024 * 1024


def _normalise_path(raw_path):
    raw_path = raw_path.replace("\\", "/")
    while raw_path.startswith("./"):
        raw_path = raw_path[2:]
    if raw_path in ("", "."):
        return ""
    path = PurePosixPath(raw_path)
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError("Unsafe Debian payload path: %s" % raw_path)
    return path.as_posix()


def _validate_link_target(member_path, raw_target):
    target = PurePosixPath(raw_target.replace("\\", "/"))
    if target.is_absolute():
        raise RuntimeError(
            "Debian payload link %s has an absolute target: %s"
            % (member_path, raw_target)
        )
    stack = list(PurePosixPath(member_path).parent.parts)
    for part in target.parts:
        if part in ("", "."):
            continue
        if part == "..":
            if not stack:
                raise RuntimeError(
                    "Debian payload link %s escapes the package root: %s"
                    % (member_path, raw_target)
                )
            stack.pop()
        else:
            stack.append(part)


def _normalise_hardlink_target(raw_target):
    if raw_target.startswith("/") or "\\\\" in raw_target:
        raise RuntimeError("Invalid hardlink target: %s" % raw_target)
    normalized = posixpath.normpath(raw_target)
    if normalized in ("", ".", "..") or normalized.startswith("../"):
        raise RuntimeError("Invalid hardlink target: %s" % raw_target)
    return normalized


def _read_exact(stream, size, member_name):
    chunks = []
    remaining = size
    while remaining:
        chunk = stream.read(min(1024 * 1024, remaining))
        if not chunk:
            raise RuntimeError("Truncated ar member: %s" % member_name)
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _read_ar_data_member(package_path, destination_dir):
    members = {{}}
    with package_path.open("rb") as stream:
        if stream.read(8) != b"!<arch>\n":
            raise RuntimeError("Source is not an ar archive")
        while True:
            header = stream.read(60)
            if not header:
                break
            if len(header) != 60 or header[58:60] != b"`\n":
                raise RuntimeError("Malformed ar member header")
            name = header[0:16].decode("ascii", errors="strict").strip()
            if name.endswith("/"):
                name = name[:-1]
            if not name or name.startswith("/"):
                raise RuntimeError("Unsupported ar member name: %r" % name)
            try:
                size = int(header[48:58].decode("ascii").strip())
            except ValueError as error:
                raise RuntimeError("Invalid ar member size") from error
            if size < 0 or size > _MAX_MEMBER_SIZE:
                raise RuntimeError("ar member exceeds the configured safety limit")
            if name in members:
                raise RuntimeError("Duplicate ar member: %s" % name)

            if name == "debian-binary":
                members[name] = _read_exact(stream, size, name)
            elif name.startswith("data.tar"):
                output_path = destination_dir / name
                with output_path.open("wb") as output:
                    remaining = size
                    while remaining:
                        chunk = stream.read(min(1024 * 1024, remaining))
                        if not chunk:
                            raise RuntimeError("Truncated ar member: %s" % name)
                        output.write(chunk)
                        remaining -= len(chunk)
                members[name] = output_path
            elif name.startswith("control.tar"):
                stream.seek(size, os.SEEK_CUR)
                members[name] = None
            else:
                raise RuntimeError("Unexpected Debian archive member: %s" % name)

            if size % 2:
                if stream.read(1) != b"\n":
                    raise RuntimeError("Invalid ar member padding")

    if members.get("debian-binary") != b"2.0\n":
        raise RuntimeError("Unsupported or missing debian-binary member")
    control_members = [name for name in members if name.startswith("control.tar")]
    data_members = [name for name in members if name.startswith("data.tar")]
    if len(control_members) != 1:
        raise RuntimeError("Expected exactly one control.tar member")
    if len(data_members) != 1:
        raise RuntimeError("Expected exactly one data.tar member")
    return members[data_members[0]]


def _open_payload_archive(path):
    if path.name.endswith(".zst"):
        compressed = path.open("rb")
        reader = zstandard.ZstdDecompressor().stream_reader(compressed)
        archive = tarfile.open(fileobj=reader, mode="r|")
        return archive, reader, compressed
    archive = tarfile.open(path, mode="r|*")
    return archive, None, None


def _ensure_no_link_parent(relative_path, link_paths):
    parts = PurePosixPath(relative_path).parts
    for index in range(1, len(parts)):
        parent = PurePosixPath(*parts[:index]).as_posix()
        if parent in link_paths:
            raise RuntimeError(
                "Payload member is nested below a symbolic link: %s" % relative_path
            )


def _extract_selected(archive_path, payload_root):
    seen = set()
    link_paths = set()
    deferred_links = []
    archive, reader, compressed = _open_payload_archive(archive_path)
    try:
        for member in archive:
            relative_path = _normalise_path(member.name)
            if not relative_path:
                continue
            if relative_path in seen:
                raise RuntimeError("Duplicate Debian payload path: %s" % relative_path)
            seen.add(relative_path)
            if member.ischr() or member.isblk() or member.isfifo():
                raise RuntimeError("Unsupported special payload entry: %s" % relative_path)
            if member.issym() or member.islnk():
                if member.islnk():
                    _normalise_hardlink_target(member.linkname)
                else:
                    _validate_link_target(relative_path, member.linkname)
                link_paths.add(relative_path)
            if relative_path not in _SELECTED:
                continue

            _ensure_no_link_parent(relative_path, link_paths)
            destination = payload_root / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)

            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True)
                destination.chmod(member.mode & 0o7777)
            elif member.isfile():
                source = archive.extractfile(member)
                if source is None:
                    raise RuntimeError("Unable to read payload file: %s" % relative_path)
                with destination.open("wb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
                destination.chmod(member.mode & 0o7777)
                os.utime(destination, (member.mtime, member.mtime))
            elif member.issym() or member.islnk():
                deferred_links.append((member, destination, relative_path))
            else:
                raise RuntimeError("Unsupported payload entry: %s" % relative_path)
    finally:
        archive.close()
        if reader is not None:
            reader.close()
        if compressed is not None:
            compressed.close()

    # Tar ordering is arbitrary: reject descendants even when the link appears
    # after a selected child and was not yet known during extraction.
    for selected_path in _SELECTED:
        _ensure_no_link_parent(selected_path, link_paths)

    missing = sorted(_SELECTED - seen)
    if missing:
        raise RuntimeError("Selected payload paths are missing: %s" % ", ".join(missing))

    # Materialize symlinks first; resolve chained hardlinks irrespective of tar order.
    pending = []
    for member, destination, relative_path in deferred_links:
        if member.issym():
            destination.symlink_to(member.linkname)
        else:
            pending.append((member, destination, relative_path))
    while pending:
        next_pending = []
        progress = False
        for member, destination, relative_path in pending:
            target_path = _normalise_hardlink_target(member.linkname)
            target = payload_root / target_path
            if not target.is_file() or target.is_symlink():
                next_pending.append((member, destination, relative_path))
                continue
            os.link(target, destination)
            progress = True
        if not progress:
            raise RuntimeError("Missing or cyclic hardlink targets: %s" %
                               ", ".join(item[2] for item in next_pending))
        pending = next_pending


def setup():
    work_dir = Path(get.workDIR())
    packages = sorted(
        path for path in work_dir.rglob("*.deb") if "payload" not in path.parts
    )
    if len(packages) != 1:
        raise RuntimeError("Expected exactly one Debian package in the PISI work directory")

    payload_root = work_dir / "payload"
    if payload_root.exists():
        shutil.rmtree(payload_root)
    payload_root.mkdir(parents=True)

    archive_path = _read_ar_data_member(packages[0], work_dir)
    _extract_selected(archive_path, payload_root)


def _install_hardlink(existing, destination):
    root = Path(get.installDIR())
    source_path = root / existing.lstrip("/")
    target_path = root / destination.lstrip("/")
    if not source_path.is_file() or source_path.is_symlink():
        raise RuntimeError("Hardlink source not installed: %s" % existing)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    os.link(source_path, target_path)


def install():
    os.chdir(get.workDIR())
{install_lines}
'''


class ActionsRenderer:
    def __init__(self, plan: Dict[str, Any]):
        self.plan = plan

    def render(self) -> str:
        operations = self._operations()
        lines: List[str] = []
        source_targets = {
            op["source"].removeprefix("payload/"): op["target"]
            for op in operations
        }
        source_kinds = {
            op["source"].removeprefix("payload/"): op["kind"]
            for op in operations
        }
        for item in self._ordered_for_install(operations):
            source = item["source"]
            target = item["target"]
            kind = item["kind"]
            if kind == "directory":
                lines.append(f"    pisitools.dodir({target!r})")
            elif kind == "symlink":
                link_target = item.get("link_target")
                if not isinstance(link_target, str) or not link_target:
                    raise ValueError(f"Symlink operation has no link_target: {source}")
                source_path = source.removeprefix("payload/")
                resolved_source = posixpath.normpath(posixpath.join(
                    posixpath.dirname(source_path), link_target
                ))
                mapped_target = source_targets.get(resolved_source)
                if mapped_target is not None:
                    link_target = posixpath.relpath(mapped_target, posixpath.dirname(target))
                elif item["operation"] == "relocate":
                    # Preserve the original absolute destination for external or
                    # intentionally dangling targets when the link itself moves.
                    original_absolute = "/" + resolved_source.lstrip("/")
                    link_target = posixpath.relpath(
                        original_absolute, posixpath.dirname(target)
                    )
                lines.append(f"    pisitools.dosym({link_target!r}, {target!r})")
            elif kind == "file":
                parent, name = self._split_target(target)
                lines.append(f"    pisitools.insinto({parent!r}, {source!r}, {name!r})")
            elif kind == "hardlink":
                link_target = item.get("link_target")
                if not isinstance(link_target, str):
                    raise ValueError(f"Hardlink has no link target: {source}")
                # Debian tar hardlink names refer to archive-root paths.
                # They are not resolved relative to the link's parent.
                original = posixpath.normpath(link_target.removeprefix("./"))
                if original.startswith("../") or original in ("..", ".") or original.startswith("/"):
                    raise ValueError(f"Invalid hardlink target: {source}")
                resolved = source_targets.get(original)
                if source_kinds.get(original) == "symlink":
                    raise ValueError(f"Hardlink to symlink inode is unsupported: {source}")
                if not resolved:
                    raise ValueError(f"Hardlink target missing from plan: {source}")
                lines.append(f"    _install_hardlink({resolved!r}, {target!r})")
            else:
                raise ValueError(f"Unsupported payload kind: {kind}")

        if not lines:
            lines.append("    pass")
        return _TEMPLATE.format(
            operations=operations,
            install_lines="\n".join(lines),
        )

    def _operations(self) -> List[Dict[str, Any]]:
        install = self.plan.get("install", {})
        operations: List[Dict[str, Any]] = []
        for operation_name in ("preserve", "relocate"):
            for raw_item in install.get(operation_name, []):
                source = raw_item.get("source")
                target = raw_item.get("target")
                kind = raw_item.get("kind")
                if not isinstance(source, str) or not source.startswith("payload/"):
                    raise ValueError(
                        f"{operation_name} source must start with payload/: {source!r}"
                    )
                if not isinstance(target, str) or not target.startswith("/"):
                    raise ValueError(
                        f"{operation_name} target must be an absolute path"
                    )
                if not isinstance(kind, str):
                    raise ValueError(f"{operation_name} operation has no payload kind")
                item = {
                    "operation": operation_name,
                    "source": source,
                    "target": target,
                    "kind": kind,
                }
                if raw_item.get("link_target") is not None:
                    item["link_target"] = raw_item["link_target"]
                operations.append(item)
        return operations

    @staticmethod
    def _ordered_for_install(operations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        kind_order = {"directory": 0, "file": 1, "hardlink": 2, "symlink": 3}
        ordered = sorted(
            operations,
            key=lambda item: (
                kind_order.get(item["kind"], 99),
                item["target"].count("/"),
                item["target"],
            ),
        )
        by_source = {
            item["source"].removeprefix("payload/"): item
            for item in ordered
        }
        emitted: set[str] = set()
        visiting: set[str] = set()
        result: List[Dict[str, Any]] = []

        def visit(item: Dict[str, Any]) -> None:
            key = item["source"]
            if key in emitted:
                return
            if key in visiting:
                raise ValueError(f"Cyclic hardlink dependencies: {key}")
            visiting.add(key)
            if item["kind"] == "hardlink":
                target = item.get("link_target")
                if not isinstance(target, str):
                    raise ValueError(f"Hardlink missing target: {key}")
                normalized = posixpath.normpath(target.removeprefix("./"))
                if normalized.startswith("../") or normalized in ("..", ".") or normalized.startswith("/"):
                    raise ValueError(f"Invalid hardlink target: {key}")
                dependency = by_source.get(normalized)
                if dependency is None:
                    raise ValueError(f"Hardlink target missing from plan: {key}")
                visit(dependency)
            visiting.remove(key)
            emitted.add(key)
            result.append(item)

        for item in ordered:
            visit(item)
        return result

    @staticmethod
    def _split_target(target: str) -> tuple[str, str]:
        parent, _, name = target.rpartition("/")
        if not name:
            raise ValueError(f"File target must include a file name: {target}")
        return parent or "/", name
