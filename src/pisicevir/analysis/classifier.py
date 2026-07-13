from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

from pisicevir.models.source import PayloadEntry


_LIBRARY_RE = re.compile(r"(?:^|/)lib[^/]+\.so(?:\.[0-9]+)*$")
_SERVICE_PATHS = (
    "etc/init.d/",
    "usr/lib/systemd/",
    "lib/systemd/",
    "usr/share/dbus-1/system-services/",
    "usr/lib/tmpfiles.d/",
    "usr/lib/sysusers.d/",
)
_BOOT_PATHS = (
    "boot/",
    "lib/modules/",
    "usr/lib/modules/",
    "usr/share/initramfs-tools/",
    "etc/initramfs-tools/",
    "usr/lib/grub/",
)


class Classifier:
    def __init__(
        self,
        metadata: Dict[str, Any],
        payload: Iterable[Dict[str, Any] | PayloadEntry],
        maintainer_scripts: Optional[Dict[str, str]] = None,
    ):
        self.metadata = metadata
        self.payload = [
            item if isinstance(item, PayloadEntry) else PayloadEntry.parse_obj(item)
            for item in payload
        ]
        self.maintainer_scripts = maintainer_scripts or {}

    def classify(self) -> Dict[str, Any]:
        paths = [entry.path for entry in self.payload]
        reasons: List[str] = []
        warnings: List[str] = []

        if self.maintainer_scripts:
            warnings.append(
                "Package contains Debian maintainer scripts that require explicit lifecycle review"
            )
            return self._result(
                conversion_class="E",
                policy="native-review",
                confidence="high",
                reasons=["Foreign lifecycle scripts cannot be translated mechanically"],
                warnings=warnings,
            )

        if any(path.startswith(_BOOT_PATHS) for path in paths):
            return self._result(
                conversion_class="C",
                policy="kernel-or-boot",
                confidence="high",
                reasons=["Contains kernel, initramfs, bootloader, or boot payload"],
                warnings=warnings,
            )

        if any(path.startswith(_SERVICE_PATHS) for path in paths):
            return self._result(
                conversion_class="D",
                policy="service-sysvinit",
                confidence="high",
                reasons=["Contains service lifecycle or system integration files"],
                warnings=warnings,
            )

        has_desktop = any(
            path.startswith("usr/share/applications/") and path.endswith(".desktop")
            for path in paths
        )
        has_python_modules = any(
            "/python3" in f"/{path}" and ("dist-packages/" in path or "site-packages/" in path)
            for path in paths
        )
        has_executable = any(
            entry.kind == "file"
            and (
                entry.is_elf
                or entry.is_script
                or bool(entry.mode & 0o111)
                or entry.path.startswith(("usr/bin/", "usr/sbin/", "bin/", "sbin/"))
            )
            for entry in self.payload
        )
        has_library = any(
            entry.kind == "file" and entry.is_elf and _LIBRARY_RE.search(entry.path)
            for entry in self.payload
        )

        if has_desktop:
            reasons.append("Contains freedesktop application integration")
            if has_python_modules:
                reasons.append("Contains Python modules")
                policy = "deb-python-qt-application"
            else:
                policy = "deb-desktop-application"
            return self._result("B", policy, "medium", reasons, warnings)

        if has_python_modules and has_executable:
            return self._result(
                "B",
                "deb-python-application",
                "high",
                ["Contains Python modules and executable entry points"],
                warnings,
            )

        if has_library:
            return self._result(
                "B",
                "deb-library",
                "high",
                ["Contains ELF shared libraries"],
                warnings,
            )

        if has_executable:
            return self._result(
                "B",
                "deb-cli-application",
                "medium",
                ["Contains executable files or command entry points"],
                warnings,
            )

        return self._result(
            "A",
            "deb-data",
            "high",
            ["Payload contains no executable, service, kernel, or boot integration"],
            warnings,
        )

    def _result(
        self,
        conversion_class: str,
        policy: str,
        confidence: str,
        reasons: List[str],
        warnings: List[str],
    ) -> Dict[str, Any]:
        return {
            "package": self.metadata.get("Package", "unknown"),
            "source_type": "deb",
            "conversion_class": conversion_class,
            "policy_family": policy,
            "confidence": confidence,
            "reasons": reasons,
            "warnings": warnings,
        }
