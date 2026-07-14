from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class DebianDependencyAlternative(BaseModel):
    raw: str
    package: str
    architecture_qualifier: Optional[str] = None
    operator: Optional[str] = None
    version: Optional[str] = None
    architecture_restrictions: List[str] = Field(default_factory=list)
    build_profiles: List[str] = Field(default_factory=list)


class DebianDependencyGroup(BaseModel):
    raw: str
    alternatives: List[DebianDependencyAlternative]
