# Pisicevir

Pisicevir helps convert Debian binary packages (`.deb`) into reviewed PISI package recipes. It is **not** a universal package converter; the current implementation focuses on Debian-to-PISI workflows.

The tool inspects a `.deb` file, builds a conversion plan, and generates a PISI recipe directory from the approved plan. It does not install the Debian package, run maintainer scripts, or produce a ready-to-publish PISI package without human review.

The name was chosen to carry forward the legacy of [the earlier tool](https://github.com/pars-linux/pisicevir) with the same name.

The repository is an early implementation. Generated conversion plans require explicit review and approval, and generated PISI recipes still require a real PISI build and installation test before use.

> See the [PISI Linux Developer](https://developer.pisilinux.org/) page for more information about PISI packaging.

![Pisicevir CLI](/assets/cli.png)

![Pisicevir GUI](/assets/gui.png)

## What it does

Pisicevir provides a review-first Debian-to-PISI recipe workflow:

1. inspect a Debian binary package;
2. classify package metadata and contents;
3. create an editable conversion plan;
4. generate a PISI recipe from the approved plan;
5. lint and validate the generated recipe.

The generated recipe is a starting point for PISI packaging, not a substitute for maintainer review.

## Safety model

Pisicevir treats every Debian package as untrusted input. Debian archives are read without being extracted into the host filesystem. The adapter validates the outer archive, rejects unsafe paths and escaping links, records payload ownership and modes, hashes regular files, and surfaces maintainer scripts for manual lifecycle review.

Recipe generation is blocked until the plan contains:

- `approved: true`;
- the exact source SHA-256;
- reviewed licensing;
- packager identity;
- a homepage;
- explicit install operations.

## Commands

Inspect and plan a Debian package conversion:

```bash
pisicevir --help
pisicevir inspect package.deb --format json
pisicevir classify package.deb
pisicevir plan package.deb --output plan.yaml
```

Update `plan.yaml` manually. See [Safety model](#safety-model) for the mandatory fields.

Generate and check the PISI recipe:

```bash
pisicevir generate package.deb --plan plan.yaml --output recipe/
pisicevir lint recipe/ --strict
pisicevir validate recipe/ --format json
```

The generated plan is deliberately unapproved. Review and edit it before setting `approved: true`. When `pisicevir plan` runs on a Debian host, unambiguous dependencies that are already installed according to `dpkg-query` are pre-filled in `dependencies.map` using the Debian package name without architecture qualifiers (for example, `python3:any` maps to `python3`). Review these mappings before generation, especially when the target PISI distribution uses different package names.

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

## Trademark & Logo Attribution

**pisicevir** is an independent, community-developed companion tool.

- **Trademarks:** **PISI** is a registered trademark of **PISI Linux Community**. This project is not affiliated with, endorsed by, or sponsored by the **PISI** project or its community.
- **Logo:** The **PISI** logo used in this repository is the property of **PISI Linux Community**. It is used here solely for informational and referential purposes to indicate compatibility with their software.
