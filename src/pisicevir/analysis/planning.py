from __future__ import annotations

from typing import Any, Dict, Iterable, Optional


_DEPENDENCY_FIELDS = ("Pre-Depends", "Depends")


def create_initial_plan(
    inspection: Dict[str, Any],
    classification: Dict[str, Any],
    *,
    homepage: str = "",
    licenses: Optional[Iterable[str]] = None,
    packager_name: str = "",
    packager_email: str = "",
) -> Dict[str, Any]:
    dependency_groups = [
        group["raw"]
        for field in _DEPENDENCY_FIELDS
        for group in inspection.get("dependencies", {}).get(field, [])
    ]
    preserve = [_payload_decision(entry) for entry in inspection["payload"]]
    return {
        "source_type": "deb",
        "source_sha256": inspection["sha256"],
        "conversion_class": classification["conversion_class"],
        "policy_family": classification["policy_family"],
        "approved": False,
        "homepage": homepage,
        "licenses": list(licenses or []),
        "packager": {"name": packager_name, "email": packager_email},
        "dependencies": {
            "required": dependency_groups,
            "map": {},
            "ignore": [],
        },
        "install": {
            "preserve": preserve,
            "relocate": [],
            "omit": [],
        },
        "analysis": {
            "confidence": classification["confidence"],
            "reasons": list(classification["reasons"]),
            "warnings": list(classification["warnings"]),
        },
    }


def _payload_decision(entry: Dict[str, Any]) -> Dict[str, Any]:
    item: Dict[str, Any] = {
        "source": f"payload/{entry['path']}",
        "target": f"/{entry['path']}",
        "kind": entry["kind"],
    }
    if entry.get("link_target") is not None:
        item["link_target"] = entry["link_target"]
    return item
