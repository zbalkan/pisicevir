# Building Debian packages locally

Pisicevir does not keep a static `debian/` directory. Packaging metadata is generated from release inputs so that version, changelog, homepage, maintainer identity, package split, and smoke tests do not drift independently.

## Prerequisites

On an Ubuntu or Debian-compatible build host, install:

```bash
sudo apt update
sudo apt install -y \
  binutils build-essential debhelper devscripts dh-python dpkg-dev fakeroot \
  libegl1 libgl1 libxkbcommon-x11-0 lintian pybuild-plugin-pyproject \
  python3-all python3-build python3-pydantic python3-pyqt5 python3-pytest \
  python3-pytestqt python3-setuptools python3-wheel python3-yaml \
  python3-zstandard
```

Install the locked Python test environment separately:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements/ci.lock
python -m pip install --no-deps --no-build-isolation -e .
python -m pytest -ra
```

## Generate release metadata

The software version comes from `src/pisicevir/__init__.py`. The normal release workflow generates metadata from Git tags. For a local test build, create a temporary changelog explicitly:

```bash
mkdir -p dist
cat > dist/debian-changelog <<'EOF'
pisicevir (0.1.0-1) noble; urgency=medium

  * Local test build.

 -- Zafer Balkan <zafer@zaferbalkan.com>  Thu, 01 Jan 1970 00:00:00 +0000
EOF
```

Generate the packaging directory:

```bash
python tools/generate_debian_packaging.py \
  --changelog dist/debian-changelog \
  --maintainer-name "Zafer Balkan" \
  --maintainer-email "zafer@zaferbalkan.com" \
  --homepage "https://github.com/zbalkan/pisicevir"
```

The generated `debian/` directory is ignored by Git.

## Build

The generated Debian rules file resets `PATH` to system directories so `pybuild` uses the distribution Python interpreter and modules. This avoids accidentally invoking a partially populated virtual environment (for example `.venv/bin/python3.12`) during package builds.

Set a stable build timestamp and build the binary packages:

```bash
export SOURCE_DATE_EPOCH="$(git show -s --format=%ct HEAD)"
export TZ=UTC
export LC_ALL=C.UTF-8
export PYTHONHASHSEED=0
export DEB_BUILD_OPTIONS='noautodbgsym reproducible=+fixfilepath'
export DEB_BUILD_MAINT_OPTIONS='hardening=+all reproducible=+fixfilepath'

dpkg-buildpackage --build=binary --unsigned-source --unsigned-changes
```

The packages are written to the parent directory.

## Validate

```bash
lintian --fail-on error ../pisicevir_*.changes
python tools/verify_debian_artifacts.py ../pisicevir_*.deb ../pisicevir-gui_*.deb
sudo apt install -y ../pisicevir_*.deb ../pisicevir-gui_*.deb
/usr/bin/pisicevir --version
QT_QPA_PLATFORM=offscreen /usr/bin/python3 -c \
  'from pisicevir.gui import PisicevirGUI; print(PisicevirGUI)'
sudo apt purge -y pisicevir-gui pisicevir
```

## Reproducibility check

A release is not accepted based on a single successful build. Build the same commit twice in isolated directories with the same `SOURCE_DATE_EPOCH`, then compare the package files directly:

```bash
cmp first/pisicevir_0.1.0-1_all.deb second/pisicevir_0.1.0-1_all.deb
cmp first/pisicevir-gui_0.1.0-1_all.deb second/pisicevir-gui_0.1.0-1_all.deb
```

The manual GitHub release workflow performs this check automatically before creating or pushing the version tag.
