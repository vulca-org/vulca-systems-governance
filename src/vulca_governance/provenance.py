"""Fresh-history provenance validation against the verified Wave 0A source."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from vulca_governance.errors import GovernanceError


DESIGN_COMMIT = "bc30259f3dd97ed7aedbc0858e7ce6b14500a22a"
WAVE0A_COMMIT = "d61139ef1d088e68d0fa23798f37ca04c00399bf"
SOURCE_PATHS = (
    "docs/product/repository-registry.yaml",
    "docs/product/repository-registry.md",
    "scripts/build_repository_registry.py",
    "tests/test_repository_registry.py",
)
FIELDS = {
    "schema_version",
    "design_commit",
    "wave0a_commit",
    "candidate_content_commit",
    "source_hashes",
    "extracted_symbols",
    "excluded_sdk_product_files",
}
BLOCK = re.compile(r"```json\n(?P<payload>\{.*\})\n```", re.DOTALL)
SHA40 = re.compile(r"[0-9a-f]{40}")
SHA64 = re.compile(r"[0-9a-f]{64}")


def parse_provenance(text: str) -> dict[str, object]:
    match = BLOCK.search(text)
    if not match:
        raise GovernanceError("missing provenance JSON block")
    try:
        payload = json.loads(match.group("payload"))
    except json.JSONDecodeError as exc:
        raise GovernanceError("invalid provenance JSON block") from exc
    if not isinstance(payload, dict):
        raise GovernanceError("provenance payload must be an object")
    return payload


def validate_provenance(payload: dict[str, object]) -> None:
    if set(payload) != FIELDS or payload.get("schema_version") != 1:
        raise GovernanceError("invalid provenance schema")
    for field in ("design_commit", "wave0a_commit", "candidate_content_commit"):
        value = payload.get(field)
        if not isinstance(value, str) or not SHA40.fullmatch(value):
            raise GovernanceError(f"invalid provenance commit field: {field}")
    if payload["design_commit"] != DESIGN_COMMIT or payload["wave0a_commit"] != WAVE0A_COMMIT:
        raise GovernanceError("provenance source commits do not match the approved design")

    hashes = payload.get("source_hashes")
    if not isinstance(hashes, dict) or not hashes:
        raise GovernanceError("provenance source hashes are incomplete")
    for source_path, digest in hashes.items():
        if not isinstance(source_path, str) or Path(source_path).is_absolute():
            raise GovernanceError("provenance source hashes require relative paths")
        if not isinstance(digest, str) or not SHA64.fullmatch(digest):
            raise GovernanceError("invalid provenance source hash")
    if set(hashes) != set(SOURCE_PATHS):
        raise GovernanceError("provenance source hashes are incomplete")

    symbols = payload.get("extracted_symbols")
    if not isinstance(symbols, dict) or not symbols:
        raise GovernanceError("provenance symbol map must be non-empty")
    for module, names in symbols.items():
        if not isinstance(module, str) or not module or not isinstance(names, list) or not names:
            raise GovernanceError("provenance symbol map is invalid")
        if any(not isinstance(name, str) or not name for name in names):
            raise GovernanceError("provenance symbol names must be non-empty strings")

    excluded = payload.get("excluded_sdk_product_files")
    if not isinstance(excluded, list) or not excluded:
        raise GovernanceError("excluded SDK product files must be non-empty")
    if any(not isinstance(item, str) or Path(item).is_absolute() for item in excluded):
        raise GovernanceError("excluded SDK product files require relative paths")


def check_source_hashes(payload: dict[str, object], source_root: Path) -> None:
    """Compare recorded hashes to fixed committed objects, never working-tree files."""
    if not source_root.is_absolute():
        raise GovernanceError("provenance source root must be absolute")
    hashes = payload["source_hashes"]
    assert isinstance(hashes, dict)
    for source_path in SOURCE_PATHS:
        content = _git_bytes(source_root, source_path)
        if hashes.get(source_path) != hashlib.sha256(content).hexdigest():
            raise GovernanceError("provenance source hash mismatch")


def _git_bytes(source_root: Path, source_path: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(source_root), "show", f"{WAVE0A_COMMIT}:{source_path}"],
            shell=False,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GovernanceError("provenance source read failed") from exc
    if result.returncode != 0:
        raise GovernanceError("provenance source read failed")
    return result.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--check", action="store_true", required=True)
    args = parser.parse_args(argv)
    try:
        payload = parse_provenance(Path("PROVENANCE.md").read_text(encoding="utf-8"))
        validate_provenance(payload)
        check_source_hashes(payload, args.source_root)
    except (OSError, GovernanceError):
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
