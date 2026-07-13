import os
import xml.etree.ElementTree as ET
from typing import List, Dict, Any

class RecipeLinter:
    def __init__(self, recipe_dir: str):
        self.recipe_dir = recipe_dir
        self.findings = []

    def lint(self) -> List[Dict[str, Any]]:
        self.findings = []
        self._check_files_exist()
        self._check_pspec_xml()
        self._check_actions_py()
        return self.findings

    def _add_finding(self, code: str, severity: str, message: str):
        self.findings.append({
            "code": code,
            "severity": severity,
            "message": message
        })

    def _check_files_exist(self):
        required_files = ["pspec.xml", "actions.py"]
        for f in required_files:
            if not os.path.exists(os.path.join(self.recipe_dir, f)):
                self._add_finding("FILE001", "ERROR", f"Missing required file: {f}")

    def _check_pspec_xml(self):
        pspec_path = os.path.join(self.recipe_dir, "pspec.xml")
        if not os.path.exists(pspec_path):
            return
        
        try:
            tree = ET.parse(pspec_path)
            root = tree.getroot()
            if root.tag != "PISI":
                self._add_finding("PSPEC001", "ERROR", "Root element is not <PISI>")
        except ET.ParseError as e:
            self._add_finding("PSPEC002", "ERROR", f"Malformed XML in pspec.xml: {e}")

    def _check_actions_py(self):
        actions_path = os.path.join(self.recipe_dir, "actions.py")
        if not os.path.exists(actions_path):
            return
            
        with open(actions_path, "r") as f:
            content = f.read()
            try:
                compile(content, actions_path, "exec")
            except SyntaxError as e:
                self._add_finding("ACT001", "ERROR", f"Syntax error in actions.py: {e}")
