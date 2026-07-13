# Pisicevir

Pisicevir is a policy-driven external package importer and native PISI recipe generator.

This repository currently contains an early implementation. The first supported source format is Debian binary packages. Generated recipes must be reviewed and validated before use.

## Commands

```bash
pisicevir --help
pisicevir inspect package.deb
pisicevir classify package.deb
pisicevir plan package.deb --output plan.yaml
pisicevir generate package.deb --plan plan.yaml --output recipe/
pisicevir lint recipe/
```

The graphical workbench is provided separately by the `pisicevir-gui` Debian package.
