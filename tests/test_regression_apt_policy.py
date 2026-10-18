"""F6: dependency alternatives cannot disappear during policy resolution."""
from pisicevir.analysis.apt_policy import _parse_apt_cache_depends


def test_alternative_dependencies_are_not_silently_dropped():
    lines = ["  Depends: example-core", " |Depends: systemd-helper"]
    assert "systemd-helper" in list(_parse_apt_cache_depends(lines))


def test_regular_dependencies_still_parse():
    assert list(_parse_apt_cache_depends(["  PreDepends: libc6", "  Depends: python3"])) == ["libc6", "python3"]

def test_non_systemd_alternative_is_permitted():
    from subprocess import CompletedProcess
    from pisicevir.analysis.apt_policy import first_blocked_systemd_dependency
    responses = {
        "example": " |Depends: systemd-helper\n  Depends: safe-helper\n",
        "safe-helper": "",
    }
    def runner(args, **kwargs):
        return CompletedProcess(args, 0, responses[args[-1]], "")
    assert first_blocked_systemd_dependency("example", runner=runner) is None


def test_all_systemd_alternatives_are_blocked():
    from subprocess import CompletedProcess
    from pisicevir.analysis.apt_policy import first_blocked_systemd_dependency
    def runner(args, **kwargs):
        return CompletedProcess(args, 0, " |Depends: systemd-a\n  Depends: systemd-b\n", "")
    assert first_blocked_systemd_dependency("example", runner=runner) is not None
