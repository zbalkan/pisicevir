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
