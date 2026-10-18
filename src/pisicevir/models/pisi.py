from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

NonEmptyText = Annotated[str, StringConstraints(min_length=1)]
Sha1Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-fA-F]{40}$")]


class RecipeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PisiPackager(RecipeModel):
    name: NonEmptyText
    email: NonEmptyText


class PisiArchive(RecipeModel):
    uri: NonEmptyText
    archive_type: str = "binary"
    sha1sum: Sha1Hex


class PisiDependency(RecipeModel):
    name: NonEmptyText
    version: str | None = None
    release: str | None = None


class PisiFilePath(RecipeModel):
    path: str
    file_type: str

    @field_validator("path")
    @classmethod
    def path_must_be_absolute(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("PISI package paths must be absolute")
        return value


class PisiSource(RecipeModel):
    name: NonEmptyText
    homepage: str
    packager: PisiPackager
    licenses: list[str] = Field(default_factory=list)
    summary: str
    description: str
    archive: PisiArchive
    build_dependencies: list[PisiDependency] = Field(default_factory=list)


class PisiHistoryEntry(RecipeModel):
    version: NonEmptyText
    release: NonEmptyText
    date: str
    name: str
    email: str
    comment: str


class PisiPackage(RecipeModel):
    name: NonEmptyText
    summary: str | None = None
    description: str | None = None
    runtime_dependencies: list[PisiDependency] = Field(default_factory=list)
    files: list[PisiFilePath] = Field(default_factory=list)


class PisiRecipe(RecipeModel):
    source: PisiSource
    packages: list[PisiPackage] = Field(min_length=1)
    history: list[PisiHistoryEntry] = Field(min_length=1)
