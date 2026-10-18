"""F2/F4/F5: generated plans must preserve filesystem graph semantics."""
import pytest

from pisicevir.renderers.actions import ActionsRenderer
from pisicevir.renderers.generator import RecipeGenerator


def test_hardlink_install_uses_link_operation():
    plan = {"install": {"preserve": [
        {"source": "payload/usr/lib/first", "target": "/usr/lib/first", "kind": "file"},
        {"source": "payload/usr/lib/second", "target": "/usr/lib/second", "kind": "hardlink", "link_target": "usr/lib/first"},
    ]}}
    content = ActionsRenderer(plan).render()
    assert "os.link(" in content or "dohardlink(" in content


def test_reject_symlink_with_descendant_target(tmp_path):
    payload = [
        {"path": "usr/share/link", "kind": "symlink", "link_target": "real"},
        {"path": "usr/share/data", "kind": "file"},
    ]
    plan = {"install": {"preserve": [
        {"source": "payload/usr/share/link", "target": "/opt/app", "kind": "symlink", "link_target": "real"},
        {"source": "payload/usr/share/data", "target": "/opt/app/data", "kind": "file"},
    ], "relocate": [], "omit": []}}
    generator = RecipeGenerator("test.deb", {"payload": payload}, plan, str(tmp_path))
    with pytest.raises(ValueError, match="ancestor|descendant|parent|hierarchy|conflict"):
        generator._validate_payload_decisions()


def test_relocated_relative_symlink_target_is_rebased():
    plan = {"install": {"relocate": [
        {"source": "payload/usr/bin/tool", "target": "/opt/bin/tool", "kind": "symlink", "link_target": "../lib/tool"},
        {"source": "payload/usr/lib/tool", "target": "/opt/lib/tool", "kind": "file"},
    ]}}
    content = ActionsRenderer(plan).render()
    assert "pisitools.dosym('../lib/tool', '/opt/bin/tool')" in content
