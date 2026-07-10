"""Command-line dispatch for the local governance control plane."""

import argparse
import json
from pathlib import Path
import sys

from vulca_governance.adapters.vulca_sdk import collect_vulca_sdk_evidence
from vulca_governance.atomic_io import write_private_pair, write_public_atomic
from vulca_governance.audit import build_audit, render_audit_markdown
from vulca_governance.commands import GitObjectReader, SubprocessRunner
from vulca_governance.errors import GovernanceError
from vulca_governance.evidence import verify_evidence
from vulca_governance.migrations import load_migrations, validate_migrations
from vulca_governance.policies import load_policy_set, validate_repository_name
from vulca_governance.private_snapshot import (
    build_private_snapshot,
    load_private_seeds,
    render_private_json,
    render_private_markdown,
)
from vulca_governance.registry import (
    check_registry,
    load_evidence_directory,
    load_registry,
    render_registry,
    validate_registry,
)


REGISTRY_SOURCE = Path("registry/repositories.yaml")
REGISTRY_OUTPUT = Path("registry/repositories.md")
EVIDENCE_ROOT = Path("evidence/public")
MIGRATIONS_SOURCE = Path("migrations/public.yaml")


class UsageError(ValueError):
    pass


class BoundedParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise UsageError(message)


def _parser() -> argparse.ArgumentParser:
    parser = BoundedParser(prog="vulca-governance")
    commands = parser.add_subparsers(dest="command", required=True)

    registry = commands.add_parser("registry")
    registry_actions = registry.add_subparsers(dest="action", required=True)
    registry_actions.add_parser("check")
    registry_actions.add_parser("render")

    evidence = commands.add_parser("evidence")
    evidence_actions = evidence.add_subparsers(dest="action", required=True)
    collect = evidence_actions.add_parser("collect")
    collect.add_argument("--repository", required=True, choices=["vulca-sdk"])
    collect.add_argument("--source-root", type=Path, required=True)
    evidence_actions.add_parser("verify")

    naming = commands.add_parser("naming")
    naming.add_subparsers(dest="action", required=True).add_parser("check")
    migration = commands.add_parser("migration")
    migration.add_subparsers(dest="action", required=True).add_parser("check")
    commands.add_parser("audit")

    snapshot = commands.add_parser("snapshot")
    snapshot.add_argument("--seeds", type=Path, required=True)
    snapshot.add_argument("--json", dest="json_path", type=Path, required=True)
    snapshot.add_argument("--markdown", type=Path, required=True)
    snapshot.add_argument("--refresh-github", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        return _dispatch(args)
    except UsageError:
        return 2
    except SystemExit as exc:
        return int(exc.code or 0)
    except GovernanceError as exc:
        message = str(exc).casefold()
        if any(term in message for term in ("unsafe", "credential", "forbidden", "explicit absolute", "distinct")):
            return 2
        if any(term in message for term in ("git object read failed", "git head read failed", "observation")):
            return 3
        return 1


def _dispatch(args: argparse.Namespace) -> int:
    policies = load_policy_set()
    if args.command == "registry":
        if args.action == "check":
            check_registry(REGISTRY_SOURCE, REGISTRY_OUTPUT, EVIDENCE_ROOT, policies)
        else:
            data = load_registry(REGISTRY_SOURCE)
            validate_registry(data, policies)
            write_public_atomic(
                REGISTRY_OUTPUT, render_registry(data, load_evidence_directory(EVIDENCE_ROOT))
            )
        return 0
    if args.command == "evidence":
        if args.action == "collect":
            if not args.source_root.is_absolute():
                raise GovernanceError("source root must be an explicit absolute path")
            pack = collect_vulca_sdk_evidence(
                args.source_root, GitObjectReader(SubprocessRunner())
            )
            write_public_atomic(
                EVIDENCE_ROOT / "vulca-sdk.json",
                json.dumps(pack, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            )
        else:
            packs = load_evidence_directory(EVIDENCE_ROOT)
            if "vulca-sdk" not in packs:
                raise GovernanceError("required SDK evidence is missing")
            for pack in packs.values():
                if not isinstance(pack, dict):
                    raise GovernanceError("evidence pack must be an object")
                verify_evidence(pack)
        return 0
    if args.command == "naming":
        registry = load_registry(REGISTRY_SOURCE)
        validate_registry(registry, policies)
        for record in registry["repositories"]:  # type: ignore[index]
            target = record["target_name"]
            if isinstance(target, str):
                validate_repository_name(target, policies)
        return 0
    if args.command == "migration":
        validate_migrations(
            load_migrations(MIGRATIONS_SOURCE), load_registry(REGISTRY_SOURCE)
        )
        return 0
    if args.command == "audit":
        registry = load_registry(REGISTRY_SOURCE)
        validate_registry(registry, policies)
        migrations = load_migrations(MIGRATIONS_SOURCE)
        validate_migrations(migrations, registry)
        evidence = load_evidence_directory(EVIDENCE_ROOT)
        for pack in evidence.values():
            if isinstance(pack, dict):
                verify_evidence(pack)
        report = build_audit(registry, evidence, migrations, policies)
        if report["status"] != "pass":
            raise GovernanceError("combined governance audit failed")
        sys.stdout.write(render_audit_markdown(report))
        return 0
    if args.command == "snapshot":
        paths = [args.seeds, args.json_path, args.markdown]
        if len({path.resolve(strict=False) for path in paths}) != len(paths):
            raise GovernanceError("snapshot paths must be distinct")
        snapshot = build_private_snapshot(
            load_private_seeds(args.seeds),
            SubprocessRunner(),
            refresh_github=args.refresh_github,
        )
        write_private_pair(
            (
                (args.json_path, render_private_json(snapshot)),
                (args.markdown, render_private_markdown(snapshot)),
            )
        )
        return 0
    raise UsageError("unknown command")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
