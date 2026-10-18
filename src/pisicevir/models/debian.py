from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DebianDependencyAlternative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw: str
    package: str
    architecture_qualifier: str | None = None
    operator: str | None = None
    version: str | None = None
    architecture_restrictions: list[str] = Field(default_factory=list)
    build_profiles: list[str] = Field(default_factory=list)


class DebianDependencyGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw: str
    alternatives: list[DebianDependencyAlternative] = Field(min_length=1)
