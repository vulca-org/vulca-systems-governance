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


def test_preflight_or_later_state_requires_no_blockers() -> None:
    data = _migration()
    data["records"][0]["previous_state"] = "frozen"  # type: ignore[index]
    data["records"][0]["state"] = "preflight-passed"  # type: ignore[index]
    data["records"][0]["blockers"] = ["unresolved-check"]  # type: ignore[index]

    with pytest.raises(GovernanceError, match="blockers"):
        validate_migrations(data, _registry())


def test_transferred_or_later_state_requires_vulca_org_ownership() -> None:
    data = _migration()
    data["records"][0]["previous_state"] = "preflight-passed"  # type: ignore[index]
    data["records"][0]["state"] = "transferred"  # type: ignore[index]
    registry = _registry()
    registry["repositories"][0]["current_owner"] = "legacy-owner"  # type: ignore[index]

    with pytest.raises(GovernanceError, match="owner"):
        validate_migrations(data, registry)


def test_renamed_or_later_state_requires_current_name_to_match_target() -> None:
    data = _migration()
    data["records"][0]["previous_state"] = "transferred"  # type: ignore[index]
    data["records"][0]["state"] = "transfer-verified"  # type: ignore[index]
    validate_migrations(data, _registry())

    data["records"][0]["previous_state"] = "transfer-verified"  # type: ignore[index]
    data["records"][0]["state"] = "renamed"  # type: ignore[index]
    registry = _registry()
    registry["repositories"][0]["current_name"] = "legacy-name"  # type: ignore[index]
    with pytest.raises(GovernanceError, match="current name"):
        validate_migrations(data, registry)


def test_committed_sdk_migration_is_reconciled_to_completed_state() -> None:
    registry = _registry()
    migrations = load_migrations(Path("migrations/public.yaml"))
    sdk_record = next(
        row for row in migrations["records"] if row["id"] == "vulca-sdk"  # type: ignore[index]
    )
    sdk_authority = next(
        row for row in registry["repositories"] if row["id"] == "vulca-sdk"  # type: ignore[index]
    )

    assert sdk_record["previous_state"] == "rename-verified"
    assert sdk_record["state"] == "development-restored"
    assert sdk_record["blockers"] == []
    assert sdk_authority["current_owner"] == "vulca-org"
    assert sdk_authority["current_name"] == sdk_record["target_name"]


def test_committed_bench_migration_is_reconciled_to_completed_state() -> None:
    registry = _registry()
    migrations = load_migrations(Path("migrations/public.yaml"))
    bench_record = next(
        row for row in migrations["records"] if row["id"] == "vulca-bench"  # type: ignore[index]
    )
    bench_authority = next(
        row for row in registry["repositories"] if row["id"] == "vulca-bench"  # type: ignore[index]
    )

    assert bench_record["previous_state"] == "rename-verified"
    assert bench_record["state"] == "development-restored"
    assert bench_record["blockers"] == []
    assert bench_authority["current_owner"] == "vulca-org"
    assert bench_authority["current_name"] == bench_record["target_name"]
    assert (
        bench_authority["public_url"]
        == "https://github.com/vulca-org/vulca-cultural-visual-benchmark"
    )


def test_committed_manifest_covers_every_registry_record() -> None:
    registry = _registry()
    migrations = load_migrations(Path("migrations/public.yaml"))
    validate_migrations(migrations, registry)
    assert {row["id"] for row in migrations["records"]} == {  # type: ignore[index]
        row["id"] for row in registry["repositories"]  # type: ignore[index]
    }
