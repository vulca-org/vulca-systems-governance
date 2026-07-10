from copy import deepcopy
from pathlib import Path

import pytest

from vulca_governance.errors import GovernanceError
from vulca_governance.migrations import load_migrations, validate_migrations
from vulca_governance.registry import load_registry


def _registry() -> dict[str, object]:
    return load_registry(Path("registry/repositories.yaml"))


def _migration() -> dict[str, object]:
    registry = _registry()
    record = registry["repositories"][0]  # type: ignore[index]
    return {
        "schema_version": 1,
        "records": [
            {
                "id": record["id"],
                "target_name": record["target_name"],
                "disposition": record["disposition"],
                "previous_state": None,
                "state": "inventory",
                "intended_visibility": "public",
                "required_preflight": ["confirm-public-source"],
                "required_postflight": ["verify-public-url"],
                "blockers": [],
            }
        ],
    }


def test_valid_initial_migration_passes() -> None:
    validate_migrations(_migration(), _registry())


def test_migration_requires_exact_fields() -> None:
    data = _migration()
    data["records"][0]["approval_token"] = "value"  # type: ignore[index]
    with pytest.raises(GovernanceError):
        validate_migrations(data, _registry())


@pytest.mark.parametrize("field", ["required_preflight", "required_postflight"])
def test_required_checks_are_non_empty(field: str) -> None:
    data = _migration()
    data["records"][0][field] = []  # type: ignore[index]
    with pytest.raises(GovernanceError):
        validate_migrations(data, _registry())


def test_target_and_disposition_must_match_registry() -> None:
    data = _migration()
    data["records"][0]["target_name"] = "vulca-cultural-visual-benchmark"  # type: ignore[index]
    with pytest.raises(GovernanceError, match="target"):
        validate_migrations(data, _registry())


@pytest.mark.parametrize("visibility", ["internal", "local-only"])
def test_intended_visibility_is_bounded(visibility: str) -> None:
    data = _migration()
    data["records"][0]["intended_visibility"] = visibility  # type: ignore[index]
    with pytest.raises(GovernanceError):
        validate_migrations(data, _registry())


def test_only_adjacent_transition_is_allowed() -> None:
    valid = _migration()
    valid["records"][0]["previous_state"] = "inventory"  # type: ignore[index]
    valid["records"][0]["state"] = "frozen"  # type: ignore[index]
    validate_migrations(valid, _registry())

    invalid = deepcopy(valid)
    invalid["records"][0]["state"] = "transferred"  # type: ignore[index]
    with pytest.raises(GovernanceError, match="adjacent"):
        validate_migrations(invalid, _registry())


def test_committed_manifest_covers_every_registry_record() -> None:
    registry = _registry()
    migrations = load_migrations(Path("migrations/public.yaml"))
    validate_migrations(migrations, registry)
    assert {row["id"] for row in migrations["records"]} == {  # type: ignore[index]
        row["id"] for row in registry["repositories"]  # type: ignore[index]
    }
