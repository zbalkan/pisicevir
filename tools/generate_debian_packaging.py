#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Optional, Sequence


CONTROL_TEMPLATE = """Source: pisicevir
Section: devel
Priority: optional
Maintainer: {maintainer_name} <{maintainer_email}>
Build-Depends:
 debhelper-compat (= 13),
 dh-sequence-python3,
 pybuild-plugin-pyproject,
 python3-all,
 python3-build,
 python3-wheel,
 python3-setuptools,
 python3-pytest,
 python3-pytestqt,
 python3-yaml,
 python3-pydantic,
 python3-zstandard,
 python3-pyqt5,
 binutils
Rules-Requires-Root: no
Standards-Version: 4.6.2
Homepage: {homepage}

Package: pisicevir
Architecture: all
Depends:
 ${{misc:Depends}},
 ${{python3:Depends}},
 binutils,
 python3-yaml,
 python3-pydantic,
 python3-zstandard
Description: external package importer and PISI recipe generator
 Pisicevir inspects external package artifacts, classifies conversion risk,
 and generates reviewable native PISI packaging projects. Debian package
 inspection is the first supported source adapter.

Package: pisicevir-gui
Section: devel
Architecture: all
Depends:
 ${{misc:Depends}},
 pisicevir (= ${{binary:Version}}),
 python3-pyqt5
Description: graphical workbench for Pisicevir
 This package provides the optional Qt workbench for inspecting Debian
 packages and reviewing transformation plans and lint findings.
"""

RULES = """#!/usr/bin/make -f

export PYBUILD_TEST_ARGS=-ra -p no:cacheprovider --ignore=tests/test_release_tools.py
export QT_QPA_PLATFORM=offscreen
export PYTHONHASHSEED=0

%:
\tdh $@ --buildsystem=pybuild

override_dh_auto_install:
\tdh_auto_install --buildsystem=pybuild --destdir=$(CURDIR)/debian/tmp
"""

DESKTOP = """[Desktop Entry]
Type=Application
Name=Pisicevir
Comment=Inspect external packages and generate PISI recipes
Exec=pisicevir-gui
Icon=system-software-install
Terminal=false
Categories=Development;Utility;
Keywords=PISI;package;converter;Debian;
"""

COPYRIGHT_TEMPLATE = """Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: Pisicevir
Source: {homepage}

Files: *
Copyright: 2026 {maintainer_name}
License: GPL-3+
 This program is free software: you can redistribute it and/or modify it
 under the terms of the GNU General Public License as published by the Free
 Software Foundation, either version 3 of the License, or (at your option)
 any later version.
 .
 On Debian systems, the complete text of the GNU General Public License
 version 3 can be found in /usr/share/common-licenses/GPL-3.
"""

SMOKE = """#!/bin/sh
set -eu

pisicevir --version
pisicevir --help >/dev/null
python3 -c 'import pisicevir; print(pisicevir.__version__)'
python3 -c 'from pisicevir.source_adapters.deb import DebAdapter; print(DebAdapter)'
"""


def write(path: Path, content: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    path.chmod(mode)


def generate(
    output: Path,
    changelog: Path,
    maintainer_name: str,
    maintainer_email: str,
    homepage: str,
) -> None:
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    write(
        output / "control",
        CONTROL_TEMPLATE.format(
            maintainer_name=maintainer_name,
            maintainer_email=maintainer_email,
            homepage=homepage,
        ),
    )
    write(output / "rules", RULES, mode=0o755)
    write(output / "source/format", "3.0 (quilt)\n")
    write(
        output / "copyright",
        COPYRIGHT_TEMPLATE.format(
            maintainer_name=maintainer_name,
            homepage=homepage,
        ),
    )
    write(output / "org.caracal.Pisicevir.desktop", DESKTOP)
    write(
        output / "pisicevir.install",
        "usr/bin/pisicevir\n"
        "usr/lib/python3*/dist-packages/pisicevir\n"
        "usr/lib/python3*/dist-packages/pisicevir-*.dist-info\n",
    )
    write(
        output / "pisicevir-gui.install",
        "usr/bin/pisicevir-gui\n"
        "debian/org.caracal.Pisicevir.desktop usr/share/applications\n",
    )
    write(output / "pisicevir.docs", "README.md\n")
    write(output / "pisicevir-gui.docs", "README.md\n")
    write(output / "tests/control", "Tests: smoke\nDepends: pisicevir\nRestrictions: superficial\n")
    write(output / "tests/smoke", SMOKE, mode=0o755)
    write(output / "changelog", changelog.read_text(encoding="utf-8"))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--output", type=Path, default=Path("debian"))
    result.add_argument("--changelog", type=Path, required=True)
    result.add_argument("--maintainer-name", required=True)
    result.add_argument("--maintainer-email", required=True)
    result.add_argument("--homepage", required=True)
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parser().parse_args(argv)
    generate(
        args.output,
        args.changelog,
        args.maintainer_name,
        args.maintainer_email,
        args.homepage,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
