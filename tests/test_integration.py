import os
import subprocess
import sys
import tempfile
import yaml
from tests.test_deb_adapter import create_dummy_deb

def test_full_workflow():
    with tempfile.TemporaryDirectory() as tmpdir:
        deb_path = os.path.join(tmpdir, "test.deb")
        create_dummy_deb(deb_path)
        
        # 1. Inspect
        subprocess.run([sys.executable, "-m", "pisicevir.cli", "inspect", deb_path], check=True)
        
        # 2. Classify
        subprocess.run([sys.executable, "-m", "pisicevir.cli", "classify", deb_path], check=True)
        
        # 3. Plan
        plan_path = os.path.join(tmpdir, "plan.yaml")
        subprocess.run([sys.executable, "-m", "pisicevir.cli", "plan", deb_path, "--output", plan_path], check=True)
        assert os.path.exists(plan_path)
        
        # 4. Generate
        recipe_dir = os.path.join(tmpdir, "recipe")
        subprocess.run([sys.executable, "-m", "pisicevir.cli", "generate", deb_path, "--plan", plan_path, "--output", recipe_dir], check=True)
        assert os.path.exists(os.path.join(recipe_dir, "pspec.xml"))
        assert os.path.exists(os.path.join(recipe_dir, "actions.py"))
        
        # 5. Lint
        subprocess.run([sys.executable, "-m", "pisicevir.cli", "lint", recipe_dir], check=True)
