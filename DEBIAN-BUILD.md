# Building the Debian package on Devuan

Install the build dependencies:

```bash
sudo apt update
sudo apt install \
  build-essential devscripts debhelper dh-python \
  pybuild-plugin-pyproject python3-all python3-setuptools \
  python3-pytest python3-yaml python3-pydantic python3-pyqt5 \
  binutils lintian
```

Build binary packages locally:

```bash
dpkg-buildpackage -us -uc -b
```

The resulting packages are written to the parent directory:

```text
../pisicevir_0.1.0-1_all.deb
../pisicevir-gui_0.1.0-1_all.deb
```

Install the CLI package:

```bash
sudo apt install ../pisicevir_0.1.0-1_all.deb
```

Install the optional GUI:

```bash
sudo apt install ../pisicevir-gui_0.1.0-1_all.deb
```

Run package checks:

```bash
lintian ../pisicevir_0.1.0-1_*.changes
```

Dogfood the converter:

```bash
pisicevir inspect ../pisicevir_0.1.0-1_all.deb --format json
pisicevir classify ../pisicevir_0.1.0-1_all.deb
pisicevir plan ../pisicevir_0.1.0-1_all.deb --output pisicevir.plan.yaml
pisicevir generate ../pisicevir_0.1.0-1_all.deb \
  --plan pisicevir.plan.yaml \
  --output generated/pisicevir
```
