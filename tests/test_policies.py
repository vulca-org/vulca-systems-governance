from pathlib import Path

import pytest

from vulca_governance.errors import GovernanceError
from vulca_governance.policies import load_policy_set, validate_repository_name


def test_approved_names_pass() -> None:
    policies = load_policy_set()
    for name in (
        ".github",
        "vulca-systems-governance",
        "vulca-visual-control-sdk",
        "vulca-academic-writing-control",
        "vulca-gemini-agent-coprocessor",
        "vulca-cultural-visual-benchmark",
    ):
        validate_repository_name(name, policies)


def test_ambiguous_names_fail() -> None:
    policies = load_policy_set()
    for name in ("platform", "vulca-platform", "agent-toolkit", "vulca-agent"):
        with pytest.raises(GovernanceError):
            validate_repository_name(name, policies)


def test_policy_set_has_six_unique_lanes() -> None:
    policies = load_policy_set()
    lanes = policies.lanes["lanes"]
    assert isinstance(lanes, list)
    assert len(lanes) == 6
    assert len(set(lanes)) == 6


def test_policy_set_has_ordered_lifecycle_and_five_dispositions() -> None:
    policies = load_policy_set()
    assert policies.lifecycle["states"] == [
        "incubating",
        "active",
        "maintained",
        "deprecated",
        "archived",
    ]
    assert policies.admission["dispositions"] == [
        "adopt",
        "consolidate",
        "archive",
        "blocked",
        "excluded",
    ]


def test_policy_rules_are_non_empty() -> None:
    policies = load_policy_set()
    assert policies.admission["required_checks"]
    assert policies.release_boundaries["required_fields"]


def test_missing_policy_document_fails_without_exposing_values(tmp_path: Path) -> None:
    with pytest.raises(GovernanceError, match="naming.yaml"):
        load_policy_set(tmp_path)
