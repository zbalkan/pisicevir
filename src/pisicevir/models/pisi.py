from typing import List, Optional, Dict
from pydantic import BaseModel, Field

class PisiLicense(BaseModel):
    name: str

class PisiPackager(BaseModel):
    name: str
    email: str

class PisiSource(BaseModel):
    name: str
    homepage: Optional[str] = None
    packager: PisiPackager
    licenses: List[str] = []
    summary: str
    description: str

class PisiDependency(BaseModel):
    name: str
    version: Optional[str] = None
    release: Optional[str] = None

class PisiHistoryEntry(BaseModel):
    version: str
    release: str
    date: str
    name: str
    email: str
    comment: str

class PisiPackage(BaseModel):
    name: str
    summary: Optional[str] = None
    description: Optional[str] = None
    runtime_dependencies: List[PisiDependency] = []
    files: List[str] = []

class PisiRecipe(BaseModel):
    source: PisiSource
    packages: List[PisiPackage]
    history: List[PisiHistoryEntry]
