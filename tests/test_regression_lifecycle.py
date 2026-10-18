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


def test_guarded_py3clean_is_accepted():
    scripts = {"postrm": "#!/bin/sh\nset -e\nif command -v py3clean >/dev/null; then py3clean -p example; fi\n"}
    assert Classifier({"Package": "example"}, [], scripts).classify()["conversion_class"] == "A"


def test_multiline_python_helper_guard_is_accepted():
    scripts = {"postinst": "#!/bin/sh\nset -e\nif command -v py3compile >/dev/null; then\npy3compile -p example\nfi\n"}
    assert Classifier({"Package": "example"}, [], scripts).classify()["conversion_class"] == "A"


def test_multiline_guard_with_unrelated_command_is_rejected():
    scripts = {"postinst": "#!/bin/sh\nif command -v py3clean >/dev/null; then\npy3clean -p example\ninstall a /etc/a\nfi\n"}
    assert Classifier({"Package": "example"}, [], scripts).classify()["conversion_class"] == "E"
