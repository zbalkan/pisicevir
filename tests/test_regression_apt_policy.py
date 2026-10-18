"""Regression coverage for Debian APT dependency alternatives."""

from subprocess import CompletedProcess

from pisicevir.analysis.apt_policy import (
    _parse_apt_cache_depends,
    first_blocked_systemd_dependency,
)


def test_alternative_dependencies_are_not_silently_dropped():
    lines = ["  Depends: example-core", " |Depends: systemd-helper"]
    assert "systemd-helper" in list(_parse_apt_cache_depends(lines))


def test_regular_dependencies_still_parse():
    lines = ["  PreDepends: libc6", "  Depends: python3"]
    assert list(_parse_apt_cache_depends(lines)) == ["libc6", "python3"]


def test_non_systemd_alternative_is_permitted():
    responses = {
        "example": " |Depends: systemd-helper\n  Depends: safe-helper\n",
        "safe-helper": "",
    }

    def runner(args, **kwargs):
        return CompletedProcess(args, 0, responses[args[-1]], "")

    assert first_blocked_systemd_dependency("example", runner=runner) is None


def test_all_systemd_alternatives_are_blocked():
    def runner(args, **kwargs):
        return CompletedProcess(
            args, 0, " |Depends: systemd-a\n  Depends: systemd-b\n", ""
        )

    assert first_blocked_systemd_dependency("example", runner=runner) is not None


def test_alternative_group_is_independent_of_line_order():
    from pisicevir.analysis.apt_policy import _apt_dependency_groups
    responses = {
        "example": "  Depends: safe-helper\n |Depends: systemd-helper\n",
        "safe-helper": "",
        "systemd-helper": "",
    }
    def runner(args, **kwargs):
        return CompletedProcess(args, 0, responses[args[-1]], "")
    assert _apt_dependency_groups("example", runner=runner) == [
        ("safe-helper", "systemd-helper")
    ]
    assert first_blocked_systemd_dependency("example", runner=runner) is None


def test_required_dependency_after_or_group_cannot_be_skipped():
    from pisicevir.analysis.apt_policy import _apt_dependency_groups
    responses = {
        "example": "  Depends: safe-a\n |Depends: safe-b\n  Depends: systemd-required\n",
        "safe-a": "",
    }
    def runner(args, **kwargs):
        return CompletedProcess(args, 0, responses.get(args[-1], ""), "")
    assert _apt_dependency_groups("example", runner=runner) == [
        ("safe-a", "safe-b"), ("systemd-required",)
    ]
    result = first_blocked_systemd_dependency("example", runner=runner)
    assert result is not None
    assert result.blocking_dependency == "systemd-required"


def test_shared_dependencies_are_queried_once():
    calls = []
    responses = {
        "example": "  Depends: first\n  Depends: second\n",
        "first": "  Depends: shared\n",
        "second": "  Depends: shared\n",
        "shared": "",
    }
    def runner(args, **kwargs):
        calls.append(args[-1])
        return CompletedProcess(args, 0, responses[args[-1]], "")
    assert first_blocked_systemd_dependency("example", runner=runner) is None
    assert calls.count("shared") == 1
