from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List

import yaml

from pisicevir.models.pisi import (
    PisiArchive,
    PisiDependency,
    PisiFilePath,
    PisiHistoryEntry,
    PisiPackage,
    PisiPackager,
    PisiRecipe,
    PisiSource,
)
from pisicevir.renderers.actions import ActionsRenderer
from pisicevir.renderers.pspec import PspecRenderer


class RecipeGenerator:
    def __init__(
        self,
        source_path: str,
        inspection: Dict[str, Any],
        plan: Dict[str, Any],
        output_dir: str,
    ):
        self.source_path = Path(source_path)
        self.inspection = inspection
        self.plan = plan
        self.output_dir = Path(output_dir)

    def generate(self) -> str:
        self._validate_inputs()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        source_dir = self.output_dir / "files"
        metadata_dir = self.output_dir / "metadata"
        source_dir.mkdir(exist_ok=True)
        metadata_dir.mkdir(exist_ok=True)

        copied_source = source_dir / self.source_path.name
        shutil.copyfile(self.source_path, copied_source)
        copied_source.chmod(0o644)
        epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))
        os.utime(copied_source, (epoch, epoch))

        recipe = self._create_recipe_model(copied_source)
        self._write_text(self.output_dir / "pspec.xml", PspecRenderer(recipe).render())
        self._write_text(
            self.output_dir / "actions.py", ActionsRenderer(self.plan).render(), mode=0o755
        )

        self._write_text(
            metadata_dir / "inspection.json",
            json.dumps(self.inspection, indent=2, sort_keys=True) + "\n",
        )
        self._write_text(
            metadata_dir / "transformation-plan.yaml",
            yaml.safe_dump(self.plan, sort_keys=True),
        )
        provenance = {
            "source_file": self.source_path.name,
            "source_sha1": self._hash_file(self.source_path, "sha1"),
            "source_sha256": self.inspection["sha256"],
            "policy_family": self.plan["policy_family"],
            "conversion_class": self.plan["conversion_class"],
        }
        self._write_text(
            metadata_dir / "provenance.json",
            json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        )
        return os.fspath(self.output_dir)

    def _validate_inputs(self) -> None:
        if not self.source_path.is_file():
            raise FileNotFoundError(f"Source package not found: {self.source_path}")
        if self.plan.get("approved") is not True:
            raise ValueError(
                "Transformation plan must be reviewed and set approved: true before generation"
            )
        if self.plan.get("source_type") != "deb":
            raise ValueError("Only Debian source plans are currently supported")
        if self.plan.get("source_sha256") != self.inspection.get("sha256"):
            raise ValueError("Transformation plan does not match the inspected source package")

        packager = self.plan.get("packager", {})
        if not packager.get("name") or not packager.get("email"):
            raise ValueError("Plan must define packager name and email")
        if not self.plan.get("homepage"):
            raise ValueError("Plan must define a homepage")
        licenses = self.plan.get("licenses", [])
        if not licenses or any(value in {"UNKNOWN", "NOASSERTION"} for value in licenses):
            raise ValueError("Plan must define reviewed package licensing")

        payload = {entry["path"]: entry for entry in self.inspection["payload"]}
        install = self.plan.get("install", {})
        operations = [
            *install.get("preserve", []),
            *install.get("relocate", []),
        ]
        omitted = install.get("omit", [])
        if not operations and not omitted:
            raise ValueError("Transformation plan contains no payload decisions")

        decided_sources: set[str] = set()
        targets: set[str] = set()
        for operation in operations:
            source = operation.get("source")
            target = operation.get("target")
            if not isinstance(source, str) or not source.startswith("payload/"):
                raise ValueError("Every install operation source must start with payload/")
            relative_source = source.removeprefix("payload/")
            entry = payload.get(relative_source)
            if entry is None:
                raise ValueError(f"Install source is not present in the package: {source}")
            if source in decided_sources:
                raise ValueError(f"Payload source has multiple decisions: {source}")
            if not isinstance(target, str) or not target.startswith("/"):
                raise ValueError("Every install operation requires an absolute target")
            if target in targets:
                raise ValueError(f"Multiple payload entries target the same path: {target}")
            if operation.get("kind") != entry["kind"]:
                raise ValueError(f"Payload kind was changed for {source}")
            if entry.get("link_target") != operation.get("link_target"):
                raise ValueError(f"Payload link target was changed for {source}")
            decided_sources.add(source)
            targets.add(target)

        for raw_omission in omitted:
            source = (
                raw_omission.get("source")
                if isinstance(raw_omission, dict)
                else raw_omission
            )
            if not isinstance(source, str) or not source.startswith("payload/"):
                raise ValueError("Every omission must identify a payload/ source")
            relative_source = source.removeprefix("payload/")
            if relative_source not in payload:
                raise ValueError(f"Omitted source is not present in the package: {source}")
            if source in decided_sources:
                raise ValueError(f"Payload source has multiple decisions: {source}")
            decided_sources.add(source)

        expected_sources = {f"payload/{path}" for path in payload}
        undecided = sorted(expected_sources - decided_sources)
        if undecided:
            raise ValueError(
                "Transformation plan does not cover every payload entry: "
                + ", ".join(undecided[:10])
            )

    def _create_recipe_model(self, copied_source: Path) -> PisiRecipe:
        metadata = self.inspection["metadata"]
        package_name = metadata["Package"]
        description = metadata["Description"]
        summary = description.splitlines()[0]
        source_version = self._upstream_version(metadata["Version"])
        packager_data = self.plan["packager"]
        packager = PisiPackager(
            name=packager_data["name"], email=packager_data["email"]
        )

        runtime_dependencies = sorted(
            {
                mapped
                for mapped in self.plan.get("dependencies", {}).get("map", {}).values()
                if mapped
            }
        )
        file_paths = self._target_paths()
        source_sha1 = self._hash_file(self.source_path, "sha1")

        source = PisiSource(
            name=package_name,
            homepage=self.plan["homepage"],
            packager=packager,
            licenses=list(self.plan["licenses"]),
            summary=summary,
            description=description,
            archive=PisiArchive(
                uri=f"files/{copied_source.name}",
                archive_type="binary",
                sha1sum=source_sha1,
            ),
            build_dependencies=[PisiDependency(name="python3-zstandard")],
        )
        package = PisiPackage(
            name=package_name,
            summary=summary,
            description=description,
            runtime_dependencies=[
                PisiDependency(name=name) for name in runtime_dependencies
            ],
            files=file_paths,
        )
        history = PisiHistoryEntry(
            version=source_version,
            release=str(self.plan.get("release", "1")),
            date=self._release_date(),
            name=packager.name,
            email=packager.email,
            comment=f"Generated from reviewed Debian package {metadata['Version']}",
        )
        return PisiRecipe(source=source, packages=[package], history=[history])

    def _target_paths(self) -> List[PisiFilePath]:
        paths: Dict[str, PisiFilePath] = {}
        install = self.plan.get("install", {})
        for operation in (*install.get("preserve", []), *install.get("relocate", [])):
            target = operation["target"]
            paths[target] = PisiFilePath(
                path=target, file_type=self._file_type(target)
            )
        return [paths[path] for path in sorted(paths)]

    @staticmethod
    def _file_type(path: str) -> str:
        pure = PurePosixPath(path)
        if path.startswith(("/usr/bin/", "/usr/sbin/", "/bin/", "/sbin/")):
            return "executable"
        if path.startswith(("/usr/lib/", "/lib/")):
            return "library"
        if path.startswith("/etc/"):
            return "config"
        if "/man/" in path:
            return "man"
        if path.startswith("/usr/share/doc/"):
            return "doc"
        if pure.suffix in {".h", ".hpp"}:
            return "header"
        return "data"

    @staticmethod
    def _upstream_version(version: str) -> str:
        without_epoch = version.split(":", 1)[-1]
        return without_epoch.rsplit("-", 1)[0]

    @staticmethod
    def _release_date() -> str:
        epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))
        moment = datetime.fromtimestamp(epoch, tz=timezone.utc)
        return moment.date().isoformat()

    @staticmethod
    def _hash_file(path: Path, algorithm: str) -> str:
        digest = hashlib.new(algorithm)
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _write_text(path: Path, content: str, mode: int = 0o644) -> None:
        path.write_text(content, encoding="utf-8", newline="\n")
        path.chmod(mode)
