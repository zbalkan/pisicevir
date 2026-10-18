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
    assert "_install_hardlink('/usr/lib/first', '/usr/lib/second')" in content


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
        {"source": "payload/usr/bin/tool", "target": "/opt/tools/bin/tool", "kind": "symlink", "link_target": "../lib/tool"},
        {"source": "payload/usr/lib/tool", "target": "/opt/lib/tool", "kind": "file"},
    ]}}
    content = ActionsRenderer(plan).render()
    assert "pisitools.dosym('../../lib/tool', '/opt/tools/bin/tool')" in content


def test_hardlink_target_is_archive_root_relative():
    plan = {"install": {"preserve": [
        {"source": "payload/usr/lib/first", "target": "/opt/first", "kind": "file"},
        {"source": "payload/usr/lib/second", "target": "/opt/second", "kind": "hardlink", "link_target": "./usr/lib/first"},
    ]}}
    rendered = ActionsRenderer(plan).render()
    assert "_install_hardlink('/opt/first', '/opt/second')" in rendered


def test_hardlink_target_escape_is_rejected():
    plan = {"install": {"preserve": [
        {"source": "payload/usr/lib/second", "target": "/opt/second", "kind": "hardlink", "link_target": "../../outside"},
    ]}}
    with pytest.raises(ValueError, match="Invalid hardlink target"):
        ActionsRenderer(plan).render()


def test_relocated_external_symlink_rebases_original_absolute_destination():
    plan = {"install": {"relocate": [
        {"source": "payload/usr/bin/example", "target": "/opt/example/bin/example",
         "kind": "symlink", "link_target": "../lib/example-runtime"},
    ]}}
    rendered = ActionsRenderer(plan).render()
    assert "pisitools.dosym('../../../usr/lib/example-runtime', '/opt/example/bin/example')" in rendered


def test_preserved_link_rebases_when_only_its_destination_moves():
    plan = {"install": {
        "preserve": [{"source": "payload/usr/bin/example", "target": "/usr/bin/example",
                      "kind": "symlink", "link_target": "../lib/example"}],
        "relocate": [{"source": "payload/usr/lib/example", "target": "/opt/example",
                      "kind": "file"}],
    }}
    rendered = ActionsRenderer(plan).render()
    assert "pisitools.dosym('../../opt/example', '/usr/bin/example')" in rendered


def test_omitted_target_requires_review_for_symlink():
    plan = {"install": {"preserve": [
        {"source": "payload/usr/bin/example", "target": "/usr/bin/example",
         "kind": "symlink", "link_target": "../lib/example"}]}}
    # An unresolved link can be deliberate, but should not be silently changed.
    rendered = ActionsRenderer(plan).render()
    assert "pisitools.dosym('../lib/example', '/usr/bin/example')" in rendered


def test_chained_hardlinks_install_in_dependency_order():
    plan = {"install": {"preserve": [
        {"source": "payload/usr/lib/z", "target": "/usr/lib/z", "kind": "file"},
        {"source": "payload/usr/lib/b", "target": "/usr/lib/b", "kind": "hardlink", "link_target": "usr/lib/z"},
        {"source": "payload/usr/lib/a", "target": "/usr/lib/a", "kind": "hardlink", "link_target": "usr/lib/b"},
    ]}}
    rendered = ActionsRenderer(plan).render()
    assert rendered.index("_install_hardlink('/usr/lib/z', '/usr/lib/b')") < rendered.index(
        "_install_hardlink('/usr/lib/b', '/usr/lib/a')"
    )


def test_double_slash_target_is_rejected(tmp_path):
    inspection = {"payload": [{"path": "usr/share/item", "kind": "file"}]}
    plan = {"install": {"preserve": [
        {"source": "payload/usr/share/item", "target": "//opt/item", "kind": "file"}
    ]}}
    generator = RecipeGenerator("source.deb", inspection, plan, str(tmp_path))
    with pytest.raises(ValueError, match="Invalid or non-normalized"):
        generator._validate_payload_decisions()


def test_hardlink_to_symlink_is_rejected_during_rendering():
    plan = {"install": {"preserve": [
        {"source": "payload/usr/lib/link", "target": "/usr/lib/link",
         "kind": "symlink", "link_target": "real"},
        {"source": "payload/usr/lib/alias", "target": "/usr/lib/alias",
         "kind": "hardlink", "link_target": "usr/lib/link"},
    ]}}
    with pytest.raises(ValueError, match="Hardlink to symlink inode is unsupported"):
        ActionsRenderer(plan).render()


def test_hardlink_normalization_agrees_with_generated_extractor():
    plan = {"install": {"preserve": [
        {"source": "payload/usr/share/foo", "target": "/usr/share/foo", "kind": "file"},
        {"source": "payload/usr/lib/alias", "target": "/usr/lib/alias",
         "kind": "hardlink", "link_target": "usr/lib/../share/foo"},
    ]}}
    output = ActionsRenderer(plan).render()
    assert "_install_hardlink('/usr/share/foo', '/usr/lib/alias')" in output
    assert 'target_path = _normalise_hardlink_target(member.linkname)' in output


def test_backslash_hardlink_target_matches_archive_root_path():
    plan = {"install": {"preserve": [
        {"source": "payload/usr/lib/first", "target": "/usr/lib/first", "kind": "file"},
        {"source": "payload/usr/lib/second", "target": "/usr/lib/second",
         "kind": "hardlink", "link_target": r"usr\lib\first"},
    ]}}
    output = ActionsRenderer(plan).render()
    assert "_install_hardlink('/usr/lib/first', '/usr/lib/second')" in output
    namespace = {"__name__": "generated_actions"}
    import ast
    import types
    # Execute the standalone generated normalization helper, without importing PISI.
    tree = ast.parse(output)
    helper = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_normalise_hardlink_target"
    )
    import posixpath
    exec(compile(ast.Module(body=[helper], type_ignores=[]), "<helper>", "exec"),
         {"posixpath": posixpath}, namespace)
    assert namespace["_normalise_hardlink_target"](r"usr\lib\first") == "usr/lib/first"
