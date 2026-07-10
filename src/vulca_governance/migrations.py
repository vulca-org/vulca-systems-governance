"""Public migration-manifest validation without mutation authority."""

from collections.abc import Mapping, Sequence
from pathlib import Path

from vulca_governance.errors import GovernanceError
from vulca_governance.safety import validate_public_object
from vulca_governance.schemas import load_yaml_object, require_exact_fields


STATES = [
    "inventory",
    "frozen",
    "preflight-passed",
    "transferred",
    "transfer-verified",
    "renamed",
    "rename-verified",
    "development-restored",
]
DISPOSITIONS = {"adopt", "consolidate", "archive", "blocked", "excluded"}
VISIBILITIES = {"public", "private"}
TOP_LEVEL_FIELDS = {"schema_version", "records"}
RECORD_FIELDS = {
    "id",
    "target_name",
    "disposition",
    "previous_state",
    "state",
    "intended_visibility",
    "required_preflight",
    "required_postflight",
    "blockers",
}
FORBIDDEN_FIELD_FRAGMENTS = {
    "approval",
    "token",
    "credential",
    "secret",
    "webhook",
    "deploy_key",
    "environment",
    "local_root",
    "mutation",
    "authority",
}


def load_migrations(path: Path) -> dict[str, object]:
    return load_yaml_object(path)


def validate_migrations(data: dict[str, object], registry: dict[str, object]) -> None:
    """Validate public planning state against stable registry authority."""
    validate_public_object(data)
    _reject_forbidden_fields(data)
    require_exact_fields(data, TOP_LEVEL_FIELDS, context="migration manifest")
    if data.get("schema_version") != 1:
        raise GovernanceError("migration schema_version must be 1")
    records = data.get("records")
    if not isinstance(records, list) or not records:
        raise GovernanceError("migration records must be a non-empty list")
    registry_records = registry.get("repositories")
    if not isinstance(registry_records, list):
        raise GovernanceError("registry repositories must be a list")
    registry_by_id = {
        row.get("id"): row for row in registry_records if isinstance(row, Mapping)
    }
    seen_ids: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise GovernanceError(f"migration record {index} must be a mapping")
        require_exact_fields(record, RECORD_FIELDS, context=f"migration record {index}")
        record_id = _non_empty_string(record.get("id"), "migration ID")
        if record_id in seen_ids:
            raise GovernanceError("duplicate migration ID")
        seen_ids.add(record_id)
        authority = registry_by_id.get(record_id)
        if not isinstance(authority, Mapping):
            raise GovernanceError("migration ID does not exist in registry")
        if record.get("target_name") != authority.get("target_name"):
            raise GovernanceError("migration target must match registry target")
        if record.get("disposition") != authority.get("disposition"):
            raise GovernanceError("migration disposition must match registry disposition")
        if record.get("disposition") not in DISPOSITIONS:
            raise GovernanceError("migration disposition is not approved")
        if record.get("intended_visibility") not in VISIBILITIES:
            raise GovernanceError("migration visibility must be public or private")
        _string_list(record.get("required_preflight"), "required preflight")
        _string_list(record.get("required_postflight"), "required postflight")
        _string_list(record.get("blockers"), "blockers", allow_empty=True)
        _validate_transition(record.get("previous_state"), record.get("state"))


def _validate_transition(previous: object, current: object) -> None:
    if current not in STATES:
        raise GovernanceError("migration state is not approved")
    if previous is None:
        if current != STATES[0]:
            raise GovernanceError("migration initial state must be inventory")
        return
    if previous not in STATES:
        raise GovernanceError("migration previous_state is not approved")
    if STATES.index(current) != STATES.index(previous) + 1:
        raise GovernanceError("migration transition must be adjacent")


def _reject_forbidden_fields(value: object) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).casefold().replace("-", "_")
            if any(fragment in normalized for fragment in FORBIDDEN_FIELD_FRAGMENTS):
                raise GovernanceError("migration manifest contains a forbidden control field")
            _reject_forbidden_fields(child)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for child in value:
            _reject_forbidden_fields(child)


def _non_empty_string(value: object, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise GovernanceError(f"{context} must be a non-empty string")
    return value


def _string_list(value: object, context: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise GovernanceError(f"{context} must be a list of non-empty strings")
    if not value and not allow_empty:
        raise GovernanceError(f"{context} must not be empty")
    return value
