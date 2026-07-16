"""Organization policy loading and repository-name validation."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from vulca_governance.errors import GovernanceError
from vulca_governance.schemas import load_yaml_object, require_exact_fields


@dataclass(frozen=True)
class PolicySet:
    """The six versioned organization policy documents."""

    naming: Mapping[str, Any]
    lanes: Mapping[str, Any]
    lifecycle: Mapping[str, Any]
    admission: Mapping[str, Any]
    release_boundaries: Mapping[str, Any]
    security_baseline: Mapping[str, Any]


def load_policy_set(root: Path = Path("policies")) -> PolicySet:
    """Load and validate all organization policies from one directory."""
    policies = PolicySet(
        naming=load_yaml_object(root / "naming.yaml"),
        lanes=load_yaml_object(root / "lanes.yaml"),
        lifecycle=load_yaml_object(root / "lifecycle.yaml"),
        admission=load_yaml_object(root / "admission.yaml"),
        release_boundaries=load_yaml_object(root / "release-boundaries.yaml"),
        security_baseline=load_yaml_object(root / "security-baseline.yaml"),
    )
    validate_policy_set(policies)
    return policies


def validate_policy_set(policies: PolicySet) -> None:
    """Validate the explicit version-one organization policy contracts."""
    require_exact_fields(
        policies.naming,
        {
            "schema_version",
            "prefix",
            "exceptions",
            "word_count",
            "approved_surfaces",
            "ambiguous_standalone",
        },
        context="naming policy",
    )
    require_exact_fields(
        policies.lanes, {"schema_version", "lanes"}, context="lanes policy"
    )
    require_exact_fields(
        policies.lifecycle,
        {"schema_version", "states", "transitions"},
        context="lifecycle policy",
    )
    require_exact_fields(
        policies.admission,
        {"schema_version", "required_checks", "dispositions"},
        context="admission policy",
    )
    require_exact_fields(
        policies.release_boundaries,
        {"schema_version", "required_fields", "archived_release_channels"},
        context="release-boundaries policy",
    )
    require_exact_fields(
        policies.security_baseline,
        {
            "schema_version",
            "scope",
            "observation_mode",
            "required_repositories",
            "organization_defaults",
            "repository_controls",
            "finding_thresholds",
            "exceptions",
        },
        context="security-baseline policy",
    )

    documents = (
        policies.naming,
        policies.lanes,
        policies.lifecycle,
        policies.admission,
        policies.release_boundaries,
        policies.security_baseline,
    )
    if any(document.get("schema_version") != 1 for document in documents):
        raise GovernanceError("policy schema_version must be 1")

    lanes = _unique_string_list(policies.lanes.get("lanes"), "lanes")
    if len(lanes) != 6:
        raise GovernanceError("lanes policy must define six unique lane IDs")

    states = _unique_string_list(policies.lifecycle.get("states"), "lifecycle states")
    if states != ["incubating", "active", "maintained", "deprecated", "archived"]:
        raise GovernanceError("lifecycle states must use the approved order")
    transitions = policies.lifecycle.get("transitions")
    if not isinstance(transitions, Mapping) or set(transitions) != set(states):
        raise GovernanceError("lifecycle transitions must cover every state")
    for state, targets in transitions.items():
        target_list = _string_list(targets, f"lifecycle transition {state}", allow_empty=True)
        if any(target not in states for target in target_list):
            raise GovernanceError("lifecycle transition references an unknown state")

    dispositions = _unique_string_list(
        policies.admission.get("dispositions"), "admission dispositions"
    )
    if dispositions != ["adopt", "consolidate", "archive", "blocked", "excluded"]:
        raise GovernanceError("admission policy must define five approved dispositions")
    _string_list(policies.admission.get("required_checks"), "admission checks")
    _string_list(
        policies.release_boundaries.get("required_fields"), "release-boundary fields"
    )

    word_count = policies.naming.get("word_count")
    if not isinstance(word_count, Mapping) or word_count != {"minimum": 3, "maximum": 5}:
        raise GovernanceError("naming word_count must define the approved range")
    prefix = policies.naming.get("prefix")
    if not isinstance(prefix, str) or not prefix:
        raise GovernanceError("naming prefix must be a non-empty string")
    _unique_string_list(policies.naming.get("exceptions"), "naming exceptions")
    _unique_string_list(policies.naming.get("approved_surfaces"), "approved surfaces")
    _unique_string_list(policies.naming.get("ambiguous_standalone"), "ambiguous names")

    _validate_security_baseline(policies.security_baseline)


def _validate_security_baseline(policy: Mapping[str, Any]) -> None:
    for field in ("scope", "observation_mode"):
        value = policy.get(field)
        if not isinstance(value, str) or not value:
            raise GovernanceError(f"security baseline {field} must be a non-empty string")
    _unique_string_list(policy.get("required_repositories"), "required repositories")
    _unique_string_list(policy.get("exceptions"), "security baseline exceptions")

    organization_defaults = policy.get("organization_defaults")
    expected_defaults = {
        "dependency_graph": "enabled",
        "dependabot_alerts": "enabled",
        "dependabot_security_updates": "disabled",
        "secret_scanning": "enabled",
        "secret_scanning_push_protection": "enabled",
    }
    if organization_defaults != expected_defaults:
        raise GovernanceError("security baseline organization defaults are not approved")

    repository_controls = policy.get("repository_controls")
    expected_controls = {
        "code_scanning_default_setup": "configured",
        "code_scanning_required_check": "observe-first",
        "pull_request_required": True,
        "required_approving_review_count": 0,
        "required_conversation_resolution": True,
        "strict_repository_ci": True,
        "administrator_bypass": "permitted",
        "force_pushes": "blocked",
        "branch_deletions": "blocked",
    }
    if repository_controls != expected_controls:
        raise GovernanceError("security baseline repository controls are not approved")

    thresholds = policy.get("finding_thresholds")
    expected_thresholds = {
        "open_secret_scanning_alerts": 0,
        "open_code_scanning_alerts": 0,
        "open_dependabot_alerts": 0,
    }
    if thresholds != expected_thresholds:
        raise GovernanceError("security baseline finding thresholds are not approved")


def validate_repository_name(name: str, policies: PolicySet) -> None:
    """Validate one public target name against the approved naming grammar."""
    if not isinstance(name, str) or not name:
        raise GovernanceError("repository name must be a non-empty string")
    exceptions = set(_string_list(policies.naming["exceptions"], "naming exceptions"))
    if name in exceptions:
        return
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise GovernanceError("repository name must use lowercase kebab-case")
    words = name.split("-")
    prefix = str(policies.naming["prefix"])
    if words[0] != prefix:
        raise GovernanceError("repository name must use the Vulca prefix")
    limits = policies.naming["word_count"]
    assert isinstance(limits, Mapping)
    minimum = int(limits["minimum"])
    maximum = int(limits["maximum"])
    if not minimum <= len(words) <= maximum:
        raise GovernanceError("repository name must use the approved descriptive word count")
    ambiguous = set(_string_list(policies.naming["ambiguous_standalone"], "ambiguous names"))
    if len(words) == 2 and words[-1] in ambiguous:
        raise GovernanceError("repository name cannot use an ambiguous standalone surface")


def _string_list(value: object, context: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise GovernanceError(f"{context} must be a list of non-empty strings")
    if not value and not allow_empty:
        raise GovernanceError(f"{context} must not be empty")
    return value


def _unique_string_list(value: object, context: str) -> list[str]:
    items = _string_list(value, context)
    if len(items) != len(set(items)):
        raise GovernanceError(f"{context} must contain unique values")
    return items
