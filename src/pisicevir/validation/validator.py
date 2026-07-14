from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from pisicevir.linter.linter import RecipeLinter


class ArtifactValidator:
    """Run validation checks for generated Pisicevir/PISI recipe artifacts."""

    SUPPORTED_STAGES = {"recipe"}

    def __init__(self, path: str, stage: str | None = None):
        self.path = Path(path)
        self.stage = stage or "recipe"

    def validate(self) -> Dict[str, Any]:
        if self.stage not in self.SUPPORTED_STAGES:
            supported = ", ".join(sorted(self.SUPPORTED_STAGES))
            raise ValueError(
                f"Unsupported validation stage: {self.stage} (supported: {supported})"
            )
        return self._validate_recipe()

    def _validate_recipe(self) -> Dict[str, Any]:
        findings: List[Dict[str, Any]] = RecipeLinter(str(self.path)).lint()
        errors = sum(1 for finding in findings if finding["severity"] == "ERROR")
        warnings = sum(1 for finding in findings if finding["severity"] == "WARN")
        return {
            "path": str(self.path),
            "stage": "recipe",
            "valid": errors == 0,
            "summary": {
                "errors": errors,
                "warnings": warnings,
                "findings": len(findings),
            },
            "findings": findings,
        }

    @staticmethod
    def render_text(result: Dict[str, Any]) -> str:
        lines = [
            f"Validation stage: {result['stage']}",
            f"Path: {result['path']}",
            "Result: " + ("valid" if result["valid"] else "invalid"),
            (
                "Findings: "
                f"{result['summary']['errors']} error(s), "
                f"{result['summary']['warnings']} warning(s)"
            ),
        ]
        for finding in result["findings"]:
            lines.append(
                f"[{finding['severity']}] {finding['code']}: {finding['message']}"
            )
        return "\n".join(lines) + "\n"

    @staticmethod
    def render_json(result: Dict[str, Any]) -> str:
        return json.dumps(result, indent=2, sort_keys=True) + "\n"
