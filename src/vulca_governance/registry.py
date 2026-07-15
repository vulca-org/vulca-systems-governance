"""Stable public repository authority validation and rendering."""

from collections.abc import Mapping
import json
from pathlib import Path
import re

from vulca_governance.errors import GovernanceError
from vulca_governance.policies import PolicySet, validate_repository_name
from vulca_governance.safety import validate_public_object
from vulca_governance.schemas import load_yaml_object, require_exact_fields


TOP_LEVEL_FIELDS = {"schema_version", "verified_on", "policy", "repositories"}
RECORD_FIELDS = {
    "id",
    "current_owner",
    "current_name",
    "target_name",
    "visibility",
    "lane",
    "lifecycle",
    "disposition",
    "canonical_for",
    "sync_direction",
    "version_source",
    "release_channels",
    "release_boundary",
    "public_url",
    "notes",
}
NULL_TARGET_DISPOSITIONS = {"blocked", "archive", "excluded"}


def load_registry(path: Path) -> dict[str, object]:
    """Load a public registry mapping without observing any repository."""
    return load_yaml_object(path)


def validate_registry(
    data: dict[str, object],
    policies: PolicySet,
    private_denylist: set[str] | None = None,
) -> None:
    """Validate stable public authority against organization policies."""
    validate_public_object(data, private_denylist)
    require_exact_fields(data, TOP_LEVEL_FIELDS, context="registry")
    if data.get("schema_version") != 1:
        raise GovernanceError("registry schema_version must be 1")
    for field in ("verified_on", "policy"):
        _require_string(data, field, "registry")
    repositories = data.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise GovernanceError("registry repositories must be a non-empty list")

    approved_lanes = set(policies.lanes["lanes"])
    approved_lifecycles = set(policies.lifecycle["states"])
    approved_dispositions = set(policies.admission["dispositions"])
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    seen_authorities: set[str] = set()
    for index, record in enumerate(repositories):
        if not isinstance(record, dict):
            raise GovernanceError(f"registry record {index} must be a mapping")
        require_exact_fields(record, RECORD_FIELDS, context=f"registry record {index}")
        record_id = _require_string(record, "id", f"registry record {index}")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", record_id):
            raise GovernanceError("registry ID must use lowercase kebab-case")
        if record_id in seen_ids:
            raise GovernanceError("duplicate registry ID")
        seen_ids.add(record_id)

        for field in (
            "current_owner",
            "current_name",
            "sync_direction",
            "version_source",
            "release_boundary",
            "public_url",
            "notes",
        ):
            _require_string(record, field, f"registry record {record_id}")
        if record.get("visibility") != "public":
            raise GovernanceError("registry visibility must be public")
        if record.get("lane") not in approved_lanes:
            raise GovernanceError("registry record must belong to one approved lane")
        if record.get("lifecycle") not in approved_lifecycles:
            raise GovernanceError("registry lifecycle is not approved")
        disposition = record.get("disposition")
        if disposition not in approved_dispositions:
            raise GovernanceError("registry disposition is not approved")

        target_name = record.get("target_name")
        if target_name is None:
            if disposition not in NULL_TARGET_DISPOSITIONS:
                raise GovernanceError("null target name requires an unresolved disposition")
        elif isinstance(target_name, str):
            validate_repository_name(target_name, policies)
        else:
            raise GovernanceError("target_name must be a string or null")

        canonical_for = _string_list(record.get("canonical_for"), "canonical responsibility")
        for responsibility in canonical_for:
            normalized = responsibility.casefold()
            if normalized in seen_authorities:
                raise GovernanceError("duplicate canonical responsibility")
            seen_authorities.add(normalized)
        _string_list(record.get("release_channels"), "release channels", allow_empty=True)

        public_url = str(record["public_url"])
        if not re.fullmatch(r"https://github\.com/[^/\s]+/[^/\s]+", public_url):
            raise GovernanceError("public_url must be a GitHub repository URL")
        normalized_url = public_url.casefold().rstrip("/")
        expected_url = f"https://github.com/{record['current_owner']}/{record['current_name']}".casefold()
        if normalized_url != expected_url:
            raise GovernanceError("public_url must match the current owner and name")
        if normalized_url in seen_urls:
            raise GovernanceError("duplicate registry public URL")
        seen_urls.add(normalized_url)


def render_registry(data: dict[str, object], evidence: Mapping[str, object]) -> str:
    """Render a deterministic public Markdown view from stable and injected facts."""
    repositories = data.get("repositories")
    if not isinstance(repositories, list):
        raise GovernanceError("registry repositories must be a list")
    lines = [
        "# Vulca Systems Repository Registry",
        "",
        f"Verified on: {data.get('verified_on', '')}",
        "",
        str(data.get("policy", "")),
        "",
    ]
    for record in sorted(repositories, key=lambda item: str(item.get("id", ""))):
        if not isinstance(record, Mapping):
            raise GovernanceError("registry record must be a mapping")
        record_id = str(record["id"])
        target = record.get("target_name") or "unresolved"
        lines.extend(
            [
                f"## {record_id}",
                "",
                f"- Current: [{record['current_owner']}/{record['current_name']}]({record['public_url']})",
                f"- Target: {target}",
                f"- Lane: {record['lane']}",
                f"- Lifecycle: {record['lifecycle']}",
                f"- Disposition: {record['disposition']}",
                f"- Canonical for: {', '.join(record['canonical_for'])}",
                f"- Version source: {record['version_source']}",
                f"- Release channels: {', '.join(record['release_channels']) or 'none'}",
                f"- Release boundary: {record['release_boundary']}",
                f"- Synchronization: {record['sync_direction']}",
                f"- Notes: {record['notes']}",
            ]
        )
        pack = evidence.get(record_id)
        if isinstance(pack, Mapping):
            derived = pack.get("derived")
            if isinstance(derived, Mapping) and derived:
                lines.append("- Evidence-derived facts:")
                for key in sorted(derived):
                    lines.append(f"  - {key}: {derived[key]}")
        lines.append("")
    rendered = "\n".join(lines).rstrip() + "\n"
    validate_public_object(rendered)
    return rendered


def check_registry(
    source: Path,
    output: Path,
    evidence_root: Path,
    policies: PolicySet,
) -> None:
    """Validate the registry and reject a stale deterministic Markdown view."""
    data = load_registry(source)
    validate_registry(data, policies)
    expected = render_registry(data, load_evidence_directory(evidence_root))
    try:
        actual = output.read_text(encoding="utf-8")
    except OSError as exc:
        raise GovernanceError(f"registry output is unavailable: {output.name}") from exc
    if actual != expected:
        raise GovernanceError("registry Markdown drift detected")


def load_evidence_directory(root: Path) -> dict[str, object]:
    """Load public JSON evidence packs keyed by repository ID."""
    evidence: dict[str, object] = {}
    if not root.exists():
        return evidence
    for path in sorted(root.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise GovernanceError(f"invalid evidence file: {path.name}") from exc
        if not isinstance(payload, dict):
            raise GovernanceError(f"evidence file must contain an object: {path.name}")
        repository_id = payload.get("repository_id")
        if isinstance(repository_id, str):
            evidence[repository_id] = payload
    return evidence


def _require_string(record: Mapping[str, object], field: str, context: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise GovernanceError(f"{context}: {field} must be a non-empty string")
    return value


def _string_list(value: object, context: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise GovernanceError(f"{context} must be a list of non-empty strings")
    if not value and not allow_empty:
        raise GovernanceError(f"{context} must not be empty")
    return value
