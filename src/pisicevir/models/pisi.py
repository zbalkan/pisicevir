from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field, validator


class PisiPackager(BaseModel):
    name: str
    email: str


class PisiArchive(BaseModel):
    uri: str
    archive_type: str = "binary"
    sha1sum: str


class PisiDependency(BaseModel):
    name: str
    version: str | None = None
    release: str | None = None


class PisiFilePath(BaseModel):
    path: str
    file_type: str

    @validator("path")
    def path_must_be_absolute(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("PISI package paths must be absolute")
        return value


class PisiSource(BaseModel):
    name: str
    homepage: str
    packager: PisiPackager
    licenses: List[str] = Field(default_factory=list)
    summary: str
    description: str
    archive: PisiArchive
    build_dependencies: List[PisiDependency] = Field(default_factory=list)


class PisiHistoryEntry(BaseModel):
    version: str
    release: str
    date: str
    name: str
    email: str
    comment: str


class PisiPackage(BaseModel):
    name: str
    summary: str | None = None
    description: str | None = None
    runtime_dependencies: List[PisiDependency] = Field(default_factory=list)
    files: List[PisiFilePath] = Field(default_factory=list)


class PisiRecipe(BaseModel):
    source: PisiSource
    packages: List[PisiPackage]
    history: List[PisiHistoryEntry]

    @validator("packages", "history")
    def list_must_not_be_empty(cls, value: List[BaseModel]) -> List[BaseModel]:
        if not value:
            raise ValueError("PISI recipes require at least one package and history entry")
        return value
