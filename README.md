# Pisicevir

Pisicevir is a policy-driven external package importer and native PISI recipe generator. The first source adapter inspects Debian binary packages without installing them or executing their maintainer scripts.

The repository is an early implementation. Generated transformation plans require explicit review and approval, and generated PISI recipes still require a real PISI build and installation test before use.

> Refer to [PISI Linux  Developer](https://developer.pisilinux.org/) page for more information.

## Safety model

Pisicevir treats every external package as untrusted input. Debian archives are read without extracting them into the host filesystem. The adapter validates the outer archive, rejects unsafe paths and escaping links, records payload ownership and modes, hashes regular files, and surfaces maintainer scripts for manual lifecycle review.

Recipe generation is blocked until the plan contains:

- `approved: true`;
- the exact source SHA-256;
- reviewed licensing;
- packager identity;
- a homepage;
- explicit install operations.

## Commands

```bash
pisicevir --help
pisicevir inspect package.deb --format json
pisicevir classify package.deb
pisicevir plan package.deb --output plan.yaml
```

Update the `plan.yaml` manually. See [Safety Model](#safety-model) section for the mandatory changes.

```bash
pisicevir generate package.deb --plan plan.yaml --output recipe/
pisicevir lint recipe/ --strict
pisicevir validate recipe/ --format json
```

The generated plan is deliberately unapproved. Review and edit it before setting `approved: true`.
When `pisicevir plan` runs on a Debian host, unambiguous dependencies that are
already installed according to `dpkg-query` are pre-filled in `dependencies.map`
using the Debian package name without architecture qualifiers (for example,
`python3:any` maps to `python3`). Review these mappings before generation,
especially when the target PISI distribution uses different package names.

## Development

Create a virtual environment and install the locked CI dependency set:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements/ci.lock
python -m pip install --no-deps --no-build-isolation -e .
python -m pytest -ra
```

The optional graphical workbench is included in the locked test environment and can be started with:

```bash
pisicevir-gui
```

## Debian releases

Debian packaging files are not stored in the repository. The manual GitHub release workflow generates them from the Python source version and commits since the previous SemVer tag.

Before a tag is pushed, the workflow:

1. validates that the source version is newer than the latest reachable tag;
2. generates release notes and the Debian changelog;
3. runs the locked Python tests;
4. creates two isolated source snapshots;
5. generates Debian packaging in both snapshots;
6. builds both package sets;
7. requires byte-identical `.deb` files;
8. runs Lintian and payload leak checks;
9. installs and smoke-tests both packages;
10. uploads release evidence, creates the tag, and publishes the GitHub Release.

See [DEBIAN-BUILD.md](DEBIAN-BUILD.md) for local packaging instructions.

## Versioning

The authoritative software version is:

```python
src/pisicevir/__init__.py::__version__
```

Git tags, Debian versions, artifact names, release notes, and the Debian changelog are derived from that value.

## License

Pisicevir is licensed under GPL-3.0-or-later. See [LICENSE](LICENSE).
