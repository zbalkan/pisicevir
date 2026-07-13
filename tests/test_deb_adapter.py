import os
import subprocess
import tempfile
from pisicevir.source_adapters.deb import DebAdapter

def create_dummy_deb(path: str):
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create control file
        control_dir = os.path.join(tmpdir, "control")
        os.makedirs(control_dir)
        with open(os.path.join(control_dir, "control"), "w") as f:
            f.write("Package: test-pkg\nVersion: 1.0\nDescription: A test package\n")
        
        # Create data files
        data_dir = os.path.join(tmpdir, "data")
        os.makedirs(data_dir)
        target_file = os.path.join(data_dir, "usr/bin/test-cmd")
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w") as f:
            f.write("echo hello")
            
        # Create archives
        # Debian expects these to be in the root of the ar archive, not subdirs
        subprocess.run(["tar", "czf", os.path.join(tmpdir, "control.tar.gz"), "."], cwd=control_dir)
        subprocess.run(["tar", "czf", os.path.join(tmpdir, "data.tar.gz"), "."], cwd=data_dir)
        
        with open(os.path.join(tmpdir, "debian-binary"), "w") as f:
            f.write("2.0\n")
            
        # Create .deb using ar
        # The order of files in a .deb matters: debian-binary, control, data
        # Use 'ar r' to create/replace
        subprocess.run(["ar", "rc", path, "debian-binary", "control.tar.gz", "data.tar.gz"], cwd=tmpdir, check=True)

def test_deb_adapter_inspect():
    # Use a real file path instead of a file object for ar to work correctly
    with tempfile.TemporaryDirectory() as tmp_dir:
        deb_path = os.path.join(tmp_dir, "test.deb")
        create_dummy_deb(deb_path)
        adapter = DebAdapter(deb_path)
        result = adapter.inspect()
        
        assert result["source_type"] == "deb"
        assert result["metadata"]["Package"] == "test-pkg"
        # Check if any file in payload contains 'test-cmd'
        assert any("test-cmd" in f for f in result["payload"])
