from __future__ import annotations

import ast
import datetime as dt
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List


class RecipeLinter:
    def __init__(self, recipe_dir: str):
        self.recipe_dir = Path(recipe_dir)
        self.findings: List[Dict[str, Any]] = []
        self.binary_archive = False

    def lint(self) -> List[Dict[str, Any]]:
        self.findings = []
        self.binary_archive = False
        self._check_files_exist()
        self._check_pspec_xml()
        self._check_actions_py()
        return list(self.findings)

    def _add_finding(self, code: str, severity: str, message: str) -> None:
        self.findings.append(
            {"code": code, "severity": severity, "message": message}
        )

    def _check_files_exist(self) -> None:
        if not self.recipe_dir.is_dir():
            self._add_finding("FILE000", "ERROR", "Recipe path is not a directory")
            return
        for filename in ("pspec.xml", "actions.py"):
            if not (self.recipe_dir / filename).is_file():
                self._add_finding(
                    "FILE001", "ERROR", f"Missing required file: {filename}"
                )

    def _check_pspec_xml(self) -> None:
        path = self.recipe_dir / "pspec.xml"
        if not path.is_file():
            return
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            self._add_finding("PSPEC001", "ERROR", f"Malformed XML: {exc}")
            return

        if root.tag != "PISI":
            self._add_finding("PSPEC002", "ERROR", "Root element must be <PISI>")
            return

        source = root.find("Source")
        packages = root.findall("Package")
        history = root.find("History")
        if source is None:
            self._add_finding("PSPEC003", "ERROR", "Missing <Source>")
        if not packages:
            self._add_finding("PSPEC004", "ERROR", "At least one <Package> is required")
        if history is None:
            self._add_finding("PSPEC005", "ERROR", "Missing <History>")

        if source is not None:
            for child in (
                "Name",
                "Homepage",
                "Packager",
                "License",
                "Summary",
                "Description",
                "Archive",
            ):
                if source.find(child) is None:
                    self._add_finding(
                        "PSPEC006", "ERROR", f"Source is missing <{child}>"
                    )
            archive = source.find("Archive")
            if archive is not None:
                sha1 = archive.get("sha1sum", "")
                if not re.fullmatch(r"[0-9a-fA-F]{40}", sha1):
                    self._add_finding("PSPEC007", "ERROR", "Archive has an invalid SHA-1")
                if not (archive.text or "").strip():
                    self._add_finding("PSPEC008", "ERROR", "Archive URI is empty")
                self.binary_archive = archive.get("type") == "binary"

        seen_paths: set[str] = set()
        for package in packages:
            if package.find("Name") is None:
                self._add_finding("PSPEC010", "ERROR", "Package is missing <Name>")
            files = package.find("Files")
            if files is None or not files.findall("Path"):
                self._add_finding("PSPEC011", "ERROR", "Package has no file paths")
                continue
            for path_element in files.findall("Path"):
                package_path = (path_element.text or "").strip()
                if not package_path.startswith("/"):
                    self._add_finding(
                        "PSPEC012", "ERROR", f"Package path is not absolute: {package_path}"
                    )
                if not path_element.get("fileType"):
                    self._add_finding(
                        "PSPEC013", "ERROR", f"Package path has no fileType: {package_path}"
                    )
                if package_path in seen_paths:
                    self._add_finding(
                        "PSPEC014", "ERROR", f"Duplicate package path: {package_path}"
                    )
                seen_paths.add(package_path)

        if history is not None:
            updates = history.findall("Update")
            if not updates:
                self._add_finding("PSPEC015", "ERROR", "History has no updates")
            releases: set[str] = set()
            today = dt.date.today()
            for update in updates:
                release = update.get("release", "")
                if not release or release in releases:
                    self._add_finding(
                        "PSPEC016", "ERROR", f"Invalid or duplicate history release: {release}"
                    )
                releases.add(release)
                date_text = update.findtext("Date", default="")
                try:
                    release_date = dt.date.fromisoformat(date_text)
                    if release_date > today:
                        self._add_finding(
                            "PSPEC017", "ERROR", f"History date is in the future: {date_text}"
                        )
                except ValueError:
                    self._add_finding(
                        "PSPEC018", "ERROR", f"Invalid history date: {date_text}"
                    )
                for child in ("Version", "Comment", "Name", "Email"):
                    if not update.findtext(child, default="").strip():
                        self._add_finding(
                            "PSPEC019", "ERROR", f"History update is missing <{child}>"
                        )

    def _check_actions_py(self) -> None:
        path = self.recipe_dir / "actions.py"
        if not path.is_file():
            return
        content = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(content, filename=os.fspath(path))
        except SyntaxError as exc:
            self._add_finding("ACT001", "ERROR", f"Syntax error: {exc}")
            return

        functions = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if "install" not in functions:
            self._add_finding("ACT002", "ERROR", "actions.py must define install()")
        if self.binary_archive and "setup" not in functions:
            self._add_finding(
                "ACT008", "ERROR", "Binary archive recipes must define setup()"
            )

        imported_modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_modules.add(node.module)

            if isinstance(node, ast.Call):
                name = self._call_name(node.func)
                if name in {
                    "os.system",
                    "subprocess.run",
                    "subprocess.call",
                    "subprocess.Popen",
                }:
                    self._add_finding(
                        "ACT003", "ERROR", f"Unsafe external command execution: {name}"
                    )

        if "sudo" in content:
            self._add_finding("ACT004", "ERROR", "actions.py contains sudo")
        if "IgnoreAutodep" in content:
            self._add_finding("ACT005", "WARN", "IgnoreAutodep requires explicit policy")
        if "NoStrip" in content and '"/"' in content:
            self._add_finding("ACT006", "ERROR", "Root-wide NoStrip is forbidden")
        if {"shelltools", "autotools"}.intersection(imported_modules):
            self._add_finding(
                "ACT007", "WARN", "Generated recipes should avoid broad shell/autotools helpers"
            )

    @staticmethod
    def _call_name(node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            prefix = RecipeLinter._call_name(node.value)
            return f"{prefix}.{node.attr}" if prefix else node.attr
        return ""
