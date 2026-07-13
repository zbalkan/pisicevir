import os
import subprocess
import tarfile
import tempfile
import shutil
from typing import Dict, Any, List

class DebAdapter:
    def __init__(self, path: str):
        self.path = path

    def inspect(self) -> Dict[str, Any]:
        if not os.path.exists(self.path):
            raise FileNotFoundError(f"Package not found: {self.path}")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Extract .deb using ar
            subprocess.run(["ar", "x", os.path.abspath(self.path)], cwd=tmpdir, check=True)
            
            metadata = {}
            payload = []
            
            # Find control and data archives
            files = os.listdir(tmpdir)
            control_archive = next((f for f in files if f.startswith("control.tar")), None)
            data_archive = next((f for f in files if f.startswith("data.tar")), None)
            
            if control_archive:
                with tarfile.open(os.path.join(tmpdir, control_archive)) as tar:
                    control_file = tar.extractfile("./control")
                    if control_file:
                        content = control_file.read().decode("utf-8")
                        metadata = self._parse_control(content)
            
            if data_archive:
                with tarfile.open(os.path.join(tmpdir, data_archive)) as tar:
                    payload = [m.name for m in tar.getmembers() if m.isfile()]
                    
            return {
                "source_type": "deb",
                "path": self.path,
                "metadata": metadata,
                "payload": payload
            }

    def _parse_control(self, content: str) -> Dict[str, str]:
        metadata = {}
        current_key = None
        for line in content.splitlines():
            if not line:
                continue
            if line[0].isspace():
                if current_key:
                    metadata[current_key] += "\n" + line.strip()
            elif ":" in line:
                key, value = line.split(":", 1)
                current_key = key.strip()
                metadata[current_key] = value.strip()
        return metadata
