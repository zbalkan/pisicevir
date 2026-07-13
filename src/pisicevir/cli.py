import argparse
import sys
from pisicevir import __version__

def main():
    parser = argparse.ArgumentParser(prog="pisicevir", description="Pisicevir: PISI Recipe Generator")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")
    
    # inspect
    inspect_parser = subparsers.add_parser("inspect", help="Inspect a package")
    inspect_parser.add_argument("package", help="Path to the package file")
    inspect_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    inspect_parser.add_argument("--output", help="Output directory or file")
    
    # classify
    classify_parser = subparsers.add_parser("classify", help="Classify a package")
    classify_parser.add_argument("package", help="Path to the package file")
    classify_parser.add_argument("--override-class", help="Override conversion class")
    classify_parser.add_argument("--override-policy", help="Override policy family")
    
    # plan
    plan_parser = subparsers.add_parser("plan", help="Create a transformation plan")
    plan_parser.add_argument("package", help="Path to the package file")
    plan_parser.add_argument("--policy", help="Policy family to use")
    plan_parser.add_argument("--output", help="Output path for the plan")
    
    # generate
    generate_parser = subparsers.add_parser("generate", help="Generate a PISI recipe")
    generate_parser.add_argument("package", help="Path to the package file")
    generate_parser.add_argument("--plan", help="Path to the transformation plan")
    generate_parser.add_argument("--output", help="Output directory for the recipe")
    
    # lint
    lint_parser = subparsers.add_parser("lint", help="Lint a recipe")
    lint_parser.add_argument("path", help="Path to the recipe directory")
    lint_parser.add_argument("--strict", action="store_true", help="Strict mode")
    lint_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    
    # build
    build_parser = subparsers.add_parser("build", help="Build a PISI package")
    build_parser.add_argument("path", help="Path to the recipe directory")
    
    # validate
    validate_parser = subparsers.add_parser("validate", help="Validate a PISI package")
    validate_parser.add_argument("package", help="Path to the .pisi package")
    validate_parser.add_argument("--stage", help="Specific validation stage")
    
    # publish
    publish_parser = subparsers.add_parser("publish", help="Publish a PISI package")
    publish_parser.add_argument("package", help="Path to the .pisi package")
    publish_parser.add_argument("--repository", help="Target repository path")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
        
    if args.command == "inspect":
        from pisicevir.source_adapters.deb import DebAdapter
        adapter = DebAdapter(args.package)
        result = adapter.inspect()
        print(result)
    elif args.command == "classify":
        from pisicevir.source_adapters.deb import DebAdapter
        from pisicevir.analysis.classifier import Classifier
        adapter = DebAdapter(args.package)
        info = adapter.inspect()
        classifier = Classifier(info["metadata"], info["payload"])
        result = classifier.classify()
        import json
        print(json.dumps(result, indent=2))
    elif args.command == "lint":
        from pisicevir.linter.linter import RecipeLinter
        linter = RecipeLinter(args.path)
        findings = linter.lint()
        if not findings:
            print("No issues found.")
        for f in findings:
            print(f"[{f['severity']}] {f['code']}: {f['message']}")
    elif args.command == "plan":
        import yaml
        plan = {
            "source_type": "deb",
            "conversion_class": "A",
            "policy_family": args.policy or "deb-data",
            "install": {
                "preserve": [{"source": "usr/share/*", "target": "/usr/share/"}]
            }
        }
        if args.output:
            with open(args.output, "w") as f:
                yaml.dump(plan, f)
            print(f"Plan written to {args.output}")
        else:
            print(yaml.dump(plan))
    elif args.command == "generate":
        import yaml
        from pisicevir.source_adapters.deb import DebAdapter
        from pisicevir.renderers.generator import RecipeGenerator
        
        adapter = DebAdapter(args.package)
        info = adapter.inspect()
        
        with open(args.plan, "r") as f:
            plan = yaml.safe_load(f)
            
        generator = RecipeGenerator(info["metadata"], info["payload"], plan, args.output)
        generator.generate()
        print(f"Recipe generated in {args.output}")
    else:
        print(f"Command '{args.command}' is not yet fully implemented.", file=sys.stderr)
        sys.exit(0)

if __name__ == "__main__":
    main()
