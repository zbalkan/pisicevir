import subprocess
import sys
import os

def test_cli_version():
    result = subprocess.run(
        [sys.executable, "-m", "pisicevir.cli", "--version"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "pisicevir 0.1.0" in result.stdout

def test_cli_help():
    result = subprocess.run(
        [sys.executable, "-m", "pisicevir.cli", "--help"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "usage: pisicevir" in result.stdout
