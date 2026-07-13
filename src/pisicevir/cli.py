from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import yaml

from pisicevir import __version__
from pisicevir.analysis.classifier import Classifier
from pisicevir.linter.linter import RecipeLinter
from pisicevir.renderers.generator import RecipeGenerator
from pisicevir.source_adapters.deb import DebAdapter, DebFormatError


EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_USAGE = 2
EXIT_SOURCE = 4
EXIT_UNSUPPORTED = 5
EXIT_GENERATION = 8
EXIT_LINT = 9


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pisicevir", description="Pisicevir: PISI recipe generator"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", help="subcommands")

    inspect_parser = subparsers.add_parser("inspect", help="inspect a Debian package")
    inspect_parser.add_argument("package")
    inspect_parser.add_argument("--format", choices=["text", "json"], default="text")
    inspect_parser.add_argument("--output")

    classify_parser = subparsers.add_parser("classify", help="classify conversion risk")
    classify_parser.add_argument("package")
    classify_parser.add_argument("--override-class")
    classify_parser.add_argument("--override-policy")

    plan_parser = subparsers.add_parser("plan", help="create a reviewable plan")
    plan_parser.add_argument("package")
    plan_parser.add_argument("--policy")
    plan_parser.add_argument("--homepage", default="")
    plan_parser.add_argument("--license", action="append", dest="licenses")
    plan_parser.add_argument("--packager-name", default="")
    plan_parser.add_argument("--packager-email", default="")
    plan_parser.add_argument("--output")

    generate_parser = subparsers.add_parser("generate", help="generate a PISI recipe")
    generate_parser.add_argument("package")
    generate_parser.add_argument("--plan", required=True)
    generate_parser.add_argument("--output", required=True)

    lint_parser = subparsers.add_parser("lint", help="lint a PISI recipe")
    lint_parser.add_argument("path")
    lint_parser.add_argument("--strict", action="store_true")
    lint_parser.add_argument("--format", choices=["text", "json"], default="text")

    build_parser = subparsers.add_parser("build", help="build a PISI package")
    build_parser.add_argument("path")

    validate_parser = subparsers.add_parser("validate", help="validate a PISI package")
    validate_parser.add_argument("package")
    validate_parser.add_argument("--stage")

    publish_parser = subparsers.add_parser("publish", help="publish a PISI package")
    publish_parser.add_argument("package")
    publish_parser.add_argument("--repository")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return EXIT_OK

    try:
        if args.command == "inspect":
            return _inspect(args)
        if args.command == "classify":
            return _classify(args)
        if args.command == "plan":
            return _plan(args)
        if args.command == "generate":
            return _generate(args)
        if args.command == "lint":
            return _lint(args)
        print(f"Command '{args.command}' is not implemented.", file=sys.stderr)
        return EXIT_UNSUPPORTED
    except (FileNotFoundError, DebFormatError, ValueError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        if isinstance(exc, (FileNotFoundError, DebFormatError)):
            return EXIT_SOURCE
        return EXIT_GENERATION
    except Exception as exc:  # defensive CLI boundary
        print(f"internal error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


def _inspect(args: argparse.Namespace) -> int:
    result = DebAdapter(args.package).inspect()
    if args.format == "json":
        rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    else:
        metadata = result["metadata"]
        rendered = (
            f"Package: {metadata['Package']}\n"
            f"Version: {metadata['Version']}\n"
            f"Architecture: {metadata['Architecture']}\n"
            f"SHA-256: {result['sha256']}\n"
            f"Payload entries: {len(result['payload'])}\n"
            f"Maintainer scripts: {', '.join(sorted(result['maintainer_scripts'])) or 'none'}\n"
        )
    _emit(rendered, args.output)
    return EXIT_OK


def _classify(args: argparse.Namespace) -> int:
    inspection = DebAdapter(args.package).inspect()
    result = Classifier(
        inspection["metadata"],
        inspection["payload"],
        inspection["maintainer_scripts"],
    ).classify()
    if args.override_class:
        result["conversion_class"] = args.override_class
        result["warnings"].append("Conversion class was overridden by the user")
    if args.override_policy:
        result["policy_family"] = args.override_policy
        result["warnings"].append("Policy family was overridden by the user")
    print(json.dumps(result, indent=2, sort_keys=True))
    return EXIT_OK


def _plan(args: argparse.Namespace) -> int:
    inspection = DebAdapter(args.package).inspect()
    classification = Classifier(
        inspection["metadata"],
        inspection["payload"],
        inspection["maintainer_scripts"],
    ).classify()
    if args.policy:
        classification["policy_family"] = args.policy
        classification["warnings"].append("Policy family was overridden by the user")

    preserve = [_plan_entry(entry) for entry in inspection["payload"]]
    plan: Dict[str, Any] = {
        "source_type": "deb",
        "source_sha256": inspection["sha256"],
        "conversion_class": classification["conversion_class"],
        "policy_family": classification["policy_family"],
        "approved": False,
        "homepage": args.homepage,
        "licenses": args.licenses or [],
        "packager": {
            "name": args.packager_name,
            "email": args.packager_email,
        },
        "dependencies": {"map": {}},
        "install": {"preserve": preserve, "relocate": [], "omit": []},
        "analysis": {
            "confidence": classification["confidence"],
            "reasons": classification["reasons"],
            "warnings": classification["warnings"],
        },
    }
    rendered = yaml.safe_dump(plan, sort_keys=False)
    _emit(rendered, args.output)
    return EXIT_OK


def _plan_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    item: Dict[str, Any] = {
        "source": f"payload/{entry['path']}",
        "target": f"/{entry['path']}",
        "kind": entry["kind"],
    }
    if entry.get("link_target") is not None:
        item["link_target"] = entry["link_target"]
    return item


def _generate(args: argparse.Namespace) -> int:
    inspection = DebAdapter(args.package).inspect()
    plan = yaml.safe_load(Path(args.plan).read_text(encoding="utf-8"))
    if not isinstance(plan, dict):
        raise ValueError("Transformation plan must be a YAML mapping")
    generator = RecipeGenerator(args.package, inspection, plan, args.output)
    output = generator.generate()
    print(f"Recipe generated in {output}")
    return EXIT_OK


def _lint(args: argparse.Namespace) -> int:
    findings = RecipeLinter(args.path).lint()
    if args.format == "json":
        print(json.dumps(findings, indent=2, sort_keys=True))
    elif not findings:
        print("No implemented lint checks reported an issue.")
    else:
        for finding in findings:
            print(
                f"[{finding['severity']}] {finding['code']}: {finding['message']}"
            )

    severities = {finding["severity"] for finding in findings}
    if "ERROR" in severities or (args.strict and "WARN" in severities):
        return EXIT_LINT
    return EXIT_OK


def _emit(content: str, output: Optional[str]) -> None:
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    else:
        print(content, end="")


if __name__ == "__main__":
    raise SystemExit(main())
