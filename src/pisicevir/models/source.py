from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from pisicevir.models.debian import DebianDependencyGroup

PayloadKind = Literal["file", "directory", "symlink", "hardlink", "other"]
Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-fA-F]{64}$")]


class PayloadEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    kind: PayloadKind
    mode: int = Field(ge=0)
    size: int = Field(default=0, ge=0)
    uid: int = Field(default=0, ge=0)
    gid: int = Field(default=0, ge=0)
    link_target: str | None = None
    sha256: Sha256Hex | None = None
    is_elf: bool = False
    is_script: bool = False


class DebInspection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: Literal["deb"] = "deb"
    path: str
    sha256: Sha256Hex
    architecture: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    dependencies: dict[str, list[DebianDependencyGroup]] = Field(default_factory=dict)
    payload: list[PayloadEntry] = Field(default_factory=list)
    maintainer_scripts: dict[str, str] = Field(default_factory=dict)
    conffiles: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
