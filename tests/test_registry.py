from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from vulca_governance.errors import GovernanceError
from vulca_governance.policies import load_policy_set
from vulca_governance.registry import (
    check_registry,
    load_registry,
    render_registry,
    validate_registry,
)


def _registry() -> dict[str, object]:
    return {
        "schema_version": 1,
        "verified_on": "2026-07-10",
        "policy": "Public authority only.",
        "repositories": [
            {
                "id": "example-sdk",
                "current_owner": "vulca-org",
                "current_name": "example",
                "target_name": "vulca-visual-control-sdk",
                "visibility": "public",
                "lane": "visual-systems",
                "lifecycle": "active",
                "disposition": "adopt",
                "canonical_for": ["Example public SDK"],
                "sync_direction": "Public distribution source.",
                "version_source": "pyproject.toml",
                "release_channels": ["PyPI"],
                "release_boundary": "Maintainer-approved public SDK releases.",
                "public_url": "https://github.com/vulca-org/example",
                "notes": "Public example.",
            }
        ],
    }


def test_registry_accepts_exact_public_authority() -> None:
    validate_registry(_registry(), load_policy_set())


@pytest.mark.parametrize("field", ["id", "canonical_for", "release_boundary"])
def test_registry_requires_exact_non_empty_fields(field: str) -> None:
    data = _registry()
    record = data["repositories"][0]  # type: ignore[index]
    assert isinstance(record, dict)
    record[field] = [] if field == "canonical_for" else ""
    with pytest.raises(GovernanceError):
        validate_registry(data, load_policy_set())


def test_registry_rejects_duplicate_ids_and_urls() -> None:
    data = _registry()
    data["repositories"].append(deepcopy(data["repositories"][0]))  # type: ignore[union-attr,index]
    with pytest.raises(GovernanceError, match="duplicate"):
        validate_registry(data, load_policy_set())


def test_registry_url_must_match_current_owner_and_name() -> None:
    data = _registry()
    data["repositories"][0]["public_url"] = "https://github.com/vulca-org/other"  # type: ignore[index]

    with pytest.raises(GovernanceError, match="current owner and name"):
        validate_registry(data, load_policy_set())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("visibility", "private"),
        ("lane", "unknown-lane"),
        ("target_name", "vulca-platform"),
        ("disposition", "move-now"),
    ],
)
def test_registry_enforces_public_policy(field: str, value: str) -> None:
    data = _registry()
    data["repositories"][0][field] = value  # type: ignore[index]
    with pytest.raises(GovernanceError):
        validate_registry(data, load_policy_set())


def test_null_target_requires_unresolved_disposition() -> None:
    data = _registry()
    data["repositories"][0]["target_name"] = None  # type: ignore[index]
    with pytest.raises(GovernanceError):
        validate_registry(data, load_policy_set())
    data["repositories"][0]["disposition"] = "blocked"  # type: ignore[index]
    validate_registry(data, load_policy_set())


def test_registry_rejects_private_denylist_without_echoing_value() -> None:
    data = _registry()
    data["repositories"][0]["notes"] = "INTERNAL-REPOSITORY"  # type: ignore[index]
    with pytest.raises(GovernanceError, match="private denylist"):
        validate_registry(data, load_policy_set(), {"internal-repository"})


def test_registry_rendering_is_deterministic_and_includes_evidence() -> None:
    evidence = {"example-sdk": {"derived": {"version": "0.1.0", "mcp_tool_count": 4}}}
    first = render_registry(_registry(), evidence)
    assert first == render_registry(_registry(), evidence)
    assert "Example public SDK" in first
    assert "mcp_tool_count: 4" in first


def test_registry_check_detects_committed_markdown_drift(tmp_path: Path) -> None:
    source = tmp_path / "repositories.yaml"
    output = tmp_path / "repositories.md"
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    source.write_text(yaml.safe_dump(_registry(), sort_keys=False), encoding="utf-8")
    output.write_text("stale\n", encoding="utf-8")

    with pytest.raises(GovernanceError, match="drift"):
        check_registry(source, output, evidence_root, load_policy_set())


def test_committed_registry_is_valid() -> None:
    validate_registry(load_registry(Path("registry/repositories.yaml")), load_policy_set())
