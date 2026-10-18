"""F6: dependency alternatives cannot disappear during policy resolution."""
from pisicevir.analysis.apt_policy import _parse_apt_cache_depends


def test_alternative_dependencies_are_not_silently_dropped():
    lines = ["  Depends: example-core", " |Depends: systemd-helper"]
    assert "systemd-helper" in list(_parse_apt_cache_depends(lines))


def test_regular_dependencies_still_parse():
    assert list(_parse_apt_cache_depends(["  PreDepends: libc6", "  Depends: python3"])) == ["libc6", "python3"]
