from __future__ import annotations

from typing import Any, Dict, List


class ActionsRenderer:
    def __init__(self, plan: Dict[str, Any]):
        self.plan = plan

    def render(self) -> str:
        operations = self._operations()
        lines: List[str] = [
            "#!/usr/bin/python3",
            "",
            "from pisi.actionsapi import pisitools",
            "",
            "",
            "def install():",
        ]

        if not operations:
            lines.append("    pass")
        else:
            for operation, source, target in operations:
                lines.append(f"    # {operation.capitalize()} {source} to {target}")
                lines.append(
                    f"    pisitools.insinto({target!r}, {source!r})"
                )

        return "\n".join(lines) + "\n"

    def _operations(self) -> List[tuple[str, str, str]]:
        install = self.plan.get("install", {})
        operations: List[tuple[str, str, str]] = []
        for operation in ("preserve", "relocate"):
            for item in install.get(operation, []):
                source = item.get("source")
                target = item.get("target")
                if not isinstance(source, str) or not source:
                    raise ValueError(f"{operation} operation has no source")
                if not isinstance(target, str) or not target.startswith("/"):
                    raise ValueError(f"{operation} target must be an absolute path")
                operations.append((operation, source, target))
        return operations
