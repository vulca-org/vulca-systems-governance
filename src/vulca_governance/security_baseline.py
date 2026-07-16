"""Validation for the source-controlled Vulca Organization security posture."""

from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

from vulca_governance.errors import GovernanceError
from vulca_governance.schemas import load_yaml_object, require_exact_fields


POSTURE_FIELDS = {
    "schema_version",
    "organization",
    "verified_on",
    "scope",
    "observation_mode",
    "organization_defaults",
    "repositories",
}
REPOSITORY_FIELDS = {
    "name",
    "default_branch",
    "secret_scanning",
    "secret_scanning_push_protection",
    "dependabot_alerts",
    "dependabot_security_updates",
    "code_scanning_default_setup",
    "code_scanning_required_check",
    "initial_codeql_scan",
    "protection_mode",
    "required_status_checks",
    "strict_repository_ci",
    "pull_request_required",
    "required_approving_review_count",
    "required_conversation_resolution",
    "administrator_bypass",
    "force_pushes",
    "branch_deletions",
    "open_secret_scanning_alerts",
    "open_code_scanning_alerts",
    "open_dependabot_alerts",
}


def load_security_posture(path: Path) -> dict[str, Any]:
    """Load one public organization security posture snapshot."""
    return load_yaml_object(path)


def validate_security_posture(
    posture: Mapping[str, Any], baseline: Mapping[str, Any]
) -> None:
    """Require a complete posture snapshot that satisfies the approved baseline."""
    require_exact_fields(posture, POSTURE_FIELDS, context="security posture")
    if posture.get("schema_version") != 1:
        raise GovernanceError("security posture schema_version must be 1")
    if posture.get("organization") != "vulca-org":
        raise GovernanceError("security posture organization must be vulca-org")
    _require_iso_date(posture.get("verified_on"))
    for field in ("scope", "observation_mode"):
        if posture.get(field) != baseline.get(field):
            raise GovernanceError(f"security posture {field} does not match policy")
    if posture.get("organization_defaults") != baseline.get("organization_defaults"):
        raise GovernanceError("security posture organization defaults do not match policy")

    required = _unique_strings(
        baseline.get("required_repositories"), "security baseline repositories"
    )
    repositories = posture.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise GovernanceError("security posture repositories must be a non-empty list")

    controls = baseline.get("repository_controls")
    thresholds = baseline.get("finding_thresholds")
    if not isinstance(controls, Mapping) or not isinstance(thresholds, Mapping):
        raise GovernanceError("security baseline controls are invalid")

    observed_names: list[str] = []
    for index, repository in enumerate(repositories):
        if not isinstance(repository, Mapping):
            raise GovernanceError(f"security posture repository {index} must be a mapping")
        require_exact_fields(
            repository, REPOSITORY_FIELDS, context=f"security posture repository {index}"
        )
        name = _require_string(repository.get("name"), "repository name")
        observed_names.append(name)
        _validate_repository(repository, controls, thresholds)

    if len(observed_names) != len(set(observed_names)):
        raise GovernanceError("security posture repository names must be unique")
    if set(observed_names) != set(required):
        raise GovernanceError("security posture repository coverage does not match policy")


def _validate_repository(
    repository: Mapping[str, Any],
    controls: Mapping[str, Any],
    thresholds: Mapping[str, Any],
) -> None:
    _require_string(repository.get("default_branch"), "default branch")
    for field in (
        "strict_repository_ci",
        "pull_request_required",
        "required_conversation_resolution",
        "administrator_bypass",
    ):
        if not isinstance(repository.get(field), bool):
            raise GovernanceError(f"security posture {field} must be a boolean")
    approving_reviews = repository.get("required_approving_review_count")
    if not isinstance(approving_reviews, int) or isinstance(approving_reviews, bool):
        raise GovernanceError("required approving review count must be an integer")

    expected_features = {
        "secret_scanning": "enabled",
        "secret_scanning_push_protection": "enabled",
        "dependabot_alerts": "enabled",
        "dependabot_security_updates": "disabled",
        "code_scanning_default_setup": controls["code_scanning_default_setup"],
        "initial_codeql_scan": "success",
        "strict_repository_ci": controls["strict_repository_ci"],
        "pull_request_required": controls["pull_request_required"],
        "required_conversation_resolution": controls[
            "required_conversation_resolution"
        ],
        "force_pushes": controls["force_pushes"],
        "branch_deletions": controls["branch_deletions"],
    }
    for field, expected in expected_features.items():
        if repository.get(field) != expected:
            raise GovernanceError(f"security posture repository does not satisfy {field}")

    minimum_reviews = controls["required_approving_review_count"]
    if approving_reviews < minimum_reviews:
        raise GovernanceError("security posture repository has too few approving reviews")
    required_check = repository.get("code_scanning_required_check")
    approved_check_modes = {controls["code_scanning_required_check"], "required"}
    if required_check not in approved_check_modes:
        raise GovernanceError("security posture code-scanning check mode is invalid")

    if repository.get("protection_mode") not in {"branch-protection", "ruleset"}:
        raise GovernanceError("security posture protection mode is invalid")
    _unique_strings(repository.get("required_status_checks"), "required status checks")
    if controls.get("administrator_bypass") != "permitted" and repository.get(
        "administrator_bypass"
    ):
        raise GovernanceError("administrator bypass is not permitted")

    for field, maximum in thresholds.items():
        value = repository.get(field)
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or not isinstance(maximum, int)
            or value < 0
            or value > maximum
        ):
            raise GovernanceError(f"security posture repository exceeds {field}")


def _require_iso_date(value: object) -> None:
    if not isinstance(value, str):
        raise GovernanceError("security posture verified_on must be an ISO date")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise GovernanceError("security posture verified_on must be an ISO date") from exc


def _require_string(value: object, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise GovernanceError(f"{context} must be a non-empty string")
    return value


def _unique_strings(value: object, context: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item for item in value)
    ):
        raise GovernanceError(f"{context} must be a list of non-empty strings")
    if len(value) != len(set(value)):
        raise GovernanceError(f"{context} must contain unique values")
    return value
