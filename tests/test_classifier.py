from __future__ import annotations

from pisicevir.analysis.classifier import Classifier


def entry(path: str, *, mode: int = 0o644, script: bool = False, elf: bool = False) -> dict:
    return {
        "path": path,
        "kind": "file",
        "mode": mode,
        "size": 1,
        "uid": 0,
        "gid": 0,
        "link_target": None,
        "sha256": "a" * 64,
        "is_elf": elf,
        "is_script": script,
    }


def test_data_package_is_class_a() -> None:
    result = Classifier(
        {"Package": "data"}, [entry("usr/share/data/file.txt")]
    ).classify()
    assert result["conversion_class"] == "A"
    assert result["policy_family"] == "deb-data"


def test_python_package_with_bytecode_hooks_remains_class_b() -> None:
    result = Classifier(
        {"Package": "python-app"},
        [
            entry("usr/bin/python-app", mode=0o755, script=True),
            entry("usr/lib/python3/dist-packages/python_app/__init__.py"),
        ],
        {
            "postinst": "#!/bin/sh\nset -e\nif command -v py3compile >/dev/null; then py3compile -p python-app; fi\n",
            "prerm": "#!/bin/sh\nset -e\npy3clean -p python-app\n",
        },
    ).classify()
    assert result["conversion_class"] == "B"
    assert result["policy_family"] == "deb-python-application"
    assert any("bytecode" in warning for warning in result["warnings"])


def test_service_lifecycle_script_requires_native_review() -> None:
    result = Classifier(
        {"Package": "daemon"},
        [entry("usr/sbin/daemon", mode=0o755, elf=True)],
        {"postinst": "#!/bin/sh\nsystemctl enable daemon.service\n"},
    ).classify()
    assert result["conversion_class"] == "E"
    assert result["policy_family"] == "native-review"
