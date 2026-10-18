from __future__ import annotations

import pytest
from pydantic import ValidationError

from pisicevir.models.debian import DebianDependencyGroup
from pisicevir.models.pisi import PisiFilePath, PisiRecipe
from pisicevir.models.source import DebInspection, PayloadEntry


def test_payload_scalar_defaults() -> None:
    entry = PayloadEntry(path="usr/share/example", kind="file", mode=0o644)
    assert entry.size == 0
    assert entry.model_dump()["kind"] == "file"


def test_inspection_mutable_defaults_are_independent() -> None:
    first = DebInspection(path="/tmp/first.deb", sha256="a" * 64)
    second = DebInspection(path="/tmp/second.deb", sha256="b" * 64)
    first.conffiles.append("/etc/example")
    first.metadata["Package"] = "example"
    assert second.conffiles == []
    assert second.metadata == {}


@pytest.mark.parametrize("size", [-1, -10])
def test_negative_payload_size_is_rejected(size: int) -> None:
    with pytest.raises(ValidationError):
        PayloadEntry(path="usr/share/example", kind="file", mode=0o644, size=size)


def test_extra_inspection_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        DebInspection.model_validate(
            {"path": "/tmp/a.deb", "sha256": "a" * 64, "unexpected": True}
        )


def test_nested_dependency_groups_are_validated() -> None:
    inspection = DebInspection.model_validate(
        {
            "path": "/tmp/a.deb",
            "sha256": "a" * 64,
            "dependencies": {
                "Depends": [
                    {"raw": "python3", "alternatives": [{"raw": "python3", "package": "python3"}]}
                ]
            },
        }
    )
    assert isinstance(inspection.dependencies["Depends"][0], DebianDependencyGroup)
    assert inspection.model_dump()["dependencies"]["Depends"][0]["raw"] == "python3"


def test_empty_recipe_collections_are_rejected() -> None:
    valid_source = {
        "name": "example",
        "homepage": "https://example.test",
        "packager": {"name": "Example Maintainer", "email": "maintainer@example.test"},
        "summary": "Example",
        "description": "Example description",
        "archive": {"uri": "files/example.deb", "sha1sum": "a" * 40},
    }
    with pytest.raises(ValidationError) as error:
        PisiRecipe.model_validate(
            {"source": valid_source, "packages": [], "history": []}
        )
    assert {tuple(item["loc"]) for item in error.value.errors()} == {
        ("packages",),
        ("history",),
    }


def test_non_absolute_pisi_file_path_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PisiFilePath(path="usr/bin/example", file_type="executable")
