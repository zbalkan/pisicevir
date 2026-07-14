from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class DebianDependencyAlternative(BaseModel):
    raw: str
    package: str
    architecture_qualifier: str | None = None
    operator: str | None = None
    version: str | None = None
    architecture_restrictions: List[str] = Field(default_factory=list)
    build_profiles: List[str] = Field(default_factory=list)


class DebianDependencyGroup(BaseModel):
    raw: str
    alternatives: List[DebianDependencyAlternative]
