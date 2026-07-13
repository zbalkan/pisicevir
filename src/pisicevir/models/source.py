from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


PayloadKind = Literal["file", "directory", "symlink", "hardlink", "other"]


class PayloadEntry(BaseModel):
    path: str
    kind: PayloadKind
    mode: int
    size: int = 0
    uid: int = 0
    gid: int = 0
    link_target: Optional[str] = None
    sha256: Optional[str] = None
    is_elf: bool = False
    is_script: bool = False


class DebInspection(BaseModel):
    source_type: Literal["deb"] = "deb"
    path: str
    sha256: str
    architecture: Optional[str] = None
    metadata: Dict[str, str] = Field(default_factory=dict)
    payload: List[PayloadEntry] = Field(default_factory=list)
    maintainer_scripts: Dict[str, str] = Field(default_factory=dict)
    conffiles: List[str] = Field(default_factory=list)
    triggers: List[str] = Field(default_factory=list)
