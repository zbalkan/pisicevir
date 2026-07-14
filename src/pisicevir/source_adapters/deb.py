from __future__ import annotations

import hashlib
import io
import os
import subprocess
import tarfile
from email.parser import Parser
from email.policy import compat32
from pathlib import Path, PurePosixPath
from typing import IO, Any, BinaryIO, Dict, Iterable, List

import zstandard

from pisicevir.analysis.dependencies import parse_dependency_fields
from pisicevir.models.source import DebInspection, PayloadEntry


class DebFormatError(ValueError):
    """Raised when an input is not a structurally valid Debian binary package."""


class DebAdapter:
    CONTROL_PREFIX = "control.tar"
    DATA_PREFIX = "data.tar"
    MAINTAINER_SCRIPTS = ("preinst", "postinst", "prerm", "postrm")
    MAX_DECOMPRESSED_MEMBER_SIZE = 2 * 1024 * 1024 * 1024

    def __init__(self, path: str):
        self.path = Path(path)

    def inspect(self) -> Dict[str, Any]:
        if not self.path.is_file():
            raise FileNotFoundError(f"Package not found: {self.path}")

        members = self._ar_members()
        self._validate_ar_members(members)

        debian_binary = self._ar_read("debian-binary")
        if debian_binary != b"2.0\n":
            raise DebFormatError(
                "Unsupported Debian binary package format; debian-binary must contain '2.0\\n'"
            )

        control_name = self._single_member(members, self.CONTROL_PREFIX)
        data_name = self._single_member(members, self.DATA_PREFIX)

        metadata, scripts, conffiles, triggers = self._inspect_control_archive(
            control_name, self._ar_read(control_name)
        )
        payload = self._inspect_data_archive(data_name, self._ar_read(data_name))

        inspection = DebInspection(
            path=str(self.path.resolve()),
            sha256=self._sha256_file(self.path),
            architecture=metadata.get("Architecture"),
            metadata=metadata,
            dependencies=parse_dependency_fields(metadata),
            payload=payload,
            maintainer_scripts=scripts,
            conffiles=conffiles,
            triggers=triggers,
        )
        return inspection.dict()

    def _ar_members(self) -> List[str]:
        result = subprocess.run(
            ["ar", "t", os.fspath(self.path.resolve())],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        members = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if len(members) != len(set(members)):
            raise DebFormatError("Debian archive contains duplicate outer members")
        return members

    def _ar_read(self, member: str) -> bytes:
        result = subprocess.run(
            ["ar", "p", os.fspath(self.path.resolve()), member],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.stdout

    @classmethod
    def _validate_ar_members(cls, members: List[str]) -> None:
        if "debian-binary" not in members:
            raise DebFormatError("Debian archive is missing debian-binary")
        cls._single_member(members, cls.CONTROL_PREFIX)
        cls._single_member(members, cls.DATA_PREFIX)

    @staticmethod
    def _single_member(members: Iterable[str], prefix: str) -> str:
        matches = [member for member in members if member.startswith(prefix)]
        if len(matches) != 1:
            raise DebFormatError(
                f"Expected exactly one {prefix} member, found {len(matches)}"
            )
        return matches[0]

    def _inspect_control_archive(
        self, archive_name: str, archive_bytes: bytes
    ) -> tuple[Dict[str, str], Dict[str, str], List[str], List[str]]:
        with self._open_tar(archive_name, archive_bytes) as archive:
            members = self._validated_members(archive)
            by_path = {self._normalise_member_path(member.name): member for member in members}

            control_member = by_path.get("control")
            if control_member is None or not control_member.isfile():
                raise DebFormatError("control archive does not contain a regular control file")

            control_bytes = self._read_member(archive, control_member)
            try:
                control_text = control_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise DebFormatError("Debian control metadata is not valid UTF-8") from exc

            metadata = self._parse_control(control_text)
            for required in ("Package", "Version", "Architecture", "Description"):
                if not metadata.get(required):
                    raise DebFormatError(f"Debian control metadata is missing {required}")

            scripts: Dict[str, str] = {}
            for script_name in self.MAINTAINER_SCRIPTS:
                member = by_path.get(script_name)
                if member is not None:
                    if not member.isfile():
                        raise DebFormatError(f"Maintainer script {script_name} is not a file")
                    scripts[script_name] = self._read_member(archive, member).decode(
                        "utf-8", errors="replace"
                    )

            conffiles = self._read_lines(archive, by_path.get("conffiles"))
            triggers = self._read_lines(archive, by_path.get("triggers"))
            return metadata, scripts, conffiles, triggers

    def _inspect_data_archive(
        self, archive_name: str, archive_bytes: bytes
    ) -> List[PayloadEntry]:
        payload: List[PayloadEntry] = []
        with self._open_tar(archive_name, archive_bytes) as archive:
            for member in self._validated_members(archive):
                path = self._normalise_member_path(member.name)
                if not path:
                    continue

                kind = "other"
                link_target: str | None = None
                sha256: str | None = None
                is_elf = False
                is_script = False

                if member.isfile():
                    kind = "file"
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise DebFormatError(f"Unable to read payload member: {path}")
                    digest = hashlib.sha256()
                    first_bytes = b""
                    while True:
                        chunk = stream.read(1024 * 1024)
                        if not chunk:
                            break
                        if len(first_bytes) < 4:
                            first_bytes += chunk[: 4 - len(first_bytes)]
                        digest.update(chunk)
                    sha256 = digest.hexdigest()
                    is_elf = first_bytes == b"\x7fELF"
                    is_script = first_bytes.startswith(b"#!")
                elif member.isdir():
                    kind = "directory"
                elif member.issym():
                    kind = "symlink"
                    link_target = self._validate_link_target(path, member.linkname)
                elif member.islnk():
                    kind = "hardlink"
                    link_target = self._validate_link_target(path, member.linkname)

                payload.append(
                    PayloadEntry(
                        path=path,
                        kind=kind,
                        mode=member.mode,
                        size=member.size,
                        uid=member.uid,
                        gid=member.gid,
                        link_target=link_target,
                        sha256=sha256,
                        is_elf=is_elf,
                        is_script=is_script,
                    )
                )

        payload.sort(key=lambda entry: entry.path)
        return payload

    def _open_tar(self, name: str, data: bytes) -> tarfile.TarFile:
        if name.endswith(".zst"):
            try:
                with zstandard.ZstdDecompressor().stream_reader(io.BytesIO(data)) as reader:
                    data = self._read_limited(reader, self.MAX_DECOMPRESSED_MEMBER_SIZE)
            except zstandard.ZstdError as exc:
                raise DebFormatError(f"Unable to decompress {name}") from exc
            return tarfile.open(fileobj=io.BytesIO(data), mode="r:")
        try:
            return tarfile.open(fileobj=io.BytesIO(data), mode="r:*")
        except tarfile.TarError as exc:
            raise DebFormatError(f"Unable to open {name}") from exc

    def _validated_members(self, archive: tarfile.TarFile) -> List[tarfile.TarInfo]:
        seen: set[str] = set()
        members: List[tarfile.TarInfo] = []
        for member in archive.getmembers():
            path = self._normalise_member_path(member.name)
            if not path:
                continue
            if path in seen:
                raise DebFormatError(f"Archive contains duplicate path: {path}")
            seen.add(path)
            if member.ischr() or member.isblk() or member.isfifo():
                raise DebFormatError(f"Unsupported special payload entry: {path}")
            if member.issym() or member.islnk():
                self._validate_link_target(path, member.linkname)
            members.append(member)
        return members

    @staticmethod
    def _normalise_member_path(raw_path: str) -> str:
        raw_path = raw_path.replace("\\", "/")
        while raw_path.startswith("./"):
            raw_path = raw_path[2:]
        if raw_path in ("", "."):
            return ""
        path = PurePosixPath(raw_path)
        if path.is_absolute() or ".." in path.parts:
            raise DebFormatError(f"Unsafe archive path: {raw_path}")
        normalised = path.as_posix()
        if normalised.startswith("/"):
            raise DebFormatError(f"Unsafe archive path: {raw_path}")
        return normalised

    @classmethod
    def _validate_link_target(cls, member_path: str, raw_target: str) -> str:
        raw_target = raw_target.replace("\\", "/")
        target = PurePosixPath(raw_target)
        if target.is_absolute():
            raise DebFormatError(
                f"Archive link {member_path} has an absolute target: {raw_target}"
            )

        stack = list(PurePosixPath(member_path).parent.parts)
        for part in target.parts:
            if part in ("", "."):
                continue
            if part == "..":
                if not stack:
                    raise DebFormatError(
                        f"Archive link {member_path} escapes the package root: {raw_target}"
                    )
                stack.pop()
            else:
                stack.append(part)
        return raw_target

    @staticmethod
    def _read_member(archive: tarfile.TarFile, member: tarfile.TarInfo) -> bytes:
        stream: IO[bytes] | None = archive.extractfile(member)
        if stream is None:
            raise DebFormatError(f"Unable to read archive member: {member.name}")
        return stream.read()

    def _read_lines(
        self, archive: tarfile.TarFile, member: tarfile.TarInfo | None
    ) -> List[str]:
        if member is None:
            return []
        if not member.isfile():
            raise DebFormatError(f"Control member {member.name} is not a regular file")
        text = self._read_member(archive, member).decode("utf-8", errors="strict")
        return [line.strip() for line in text.splitlines() if line.strip()]

    @staticmethod
    def _parse_control(content: str) -> Dict[str, str]:
        message = Parser(policy=compat32).parsestr(content, headersonly=True)
        metadata: Dict[str, str] = {}
        for key in message.keys():
            values = message.get_all(key, failobj=[])
            if len(values) != 1:
                raise DebFormatError(f"Duplicate Debian control field: {key}")
            metadata[key] = str(values[0]).strip()
        return metadata

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _read_limited(stream: BinaryIO, limit: int) -> bytes:
        chunks: List[bytes] = []
        total = 0
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                raise DebFormatError("Compressed Debian member exceeds safety limit")
            chunks.append(chunk)
        return b"".join(chunks)
