"""F3: Python hooks must not conceal other maintainer-script commands."""
from pisicevir.analysis.classifier import Classifier


def test_py3compile_does_not_whitelist_unrelated_commands():
    scripts = {"postinst": "#!/bin/sh\nset -e\npy3compile -p example\ninstall -m 644 a /etc/example.conf\n"}
    result = Classifier({"Package": "example"}, [], scripts).classify()
    assert result["conversion_class"] == "E"


def test_known_python_helper_only_remains_eligible():
    scripts = {"postinst": "#!/bin/sh\nset -e\npy3compile -p example\nexit 0\n"}
    result = Classifier({"Package": "example"}, [], scripts).classify()
    assert result["conversion_class"] == "A"
