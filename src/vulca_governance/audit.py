"""Deterministic combined public governance audit reports."""

import json
from collections.abc import Mapping

from vulca_governance.policies import PolicySet


def build_audit(
    registry: dict[str, object],
    evidence: Mapping[str, object],
    migrations: dict[str, object],
    policies: PolicySet,
) -> dict[str, object]:
    """Build a public report containing stable categories and repository IDs."""
    del policies
    repositories = registry.get("repositories", [])
    repository_ids = sorted(
        str(row["id"])
        for row in repositories
        if isinstance(row, Mapping) and isinstance(row.get("id"), str)
    )
    migration_rows = migrations.get("records", [])
    migration_ids = sorted(
        str(row["id"])
        for row in migration_rows
        if isinstance(row, Mapping) and isinstance(row.get("id"), str)
    )
    required_evidence = [repository_id for repository_id in repository_ids if repository_id == "vulca-sdk"]
    present_evidence = sorted(repository_id for repository_id in required_evidence if repository_id in evidence)
    evidence_status = "pass" if present_evidence == required_evidence else "fail"
    migration_status = "pass" if migration_ids == repository_ids else "fail"
    categories = {
        "registry": {"status": "pass", "repository_ids": repository_ids},
        "policies": {"status": "pass", "repository_ids": repository_ids},
        "evidence": {"status": evidence_status, "repository_ids": present_evidence},
        "migrations": {"status": migration_status, "repository_ids": migration_ids},
    }
    overall = "pass" if all(item["status"] == "pass" for item in categories.values()) else "fail"
    return {
        "schema_version": 1,
        "status": overall,
        "repository_ids": repository_ids,
        "categories": categories,
    }


def render_audit_json(report: dict[str, object]) -> str:
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render_audit_markdown(report: dict[str, object]) -> str:
    categories = report.get("categories", {})
    lines = ["# Vulca Systems Governance Audit", "", f"Overall: **{report.get('status')}**", ""]
    if isinstance(categories, Mapping):
        for name in sorted(categories):
            item = categories[name]
            if not isinstance(item, Mapping):
                continue
            identifiers = item.get("repository_ids", [])
            rendered_ids = ", ".join(str(value) for value in identifiers) if identifiers else "none"
            lines.append(f"- {name}: {item.get('status')} ({rendered_ids})")
    return "\n".join(lines).rstrip() + "\n"
