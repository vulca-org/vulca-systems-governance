from pathlib import Path

from vulca_governance.cli import main


def test_cli_exposes_policy_migration_and_security_checks() -> None:
    assert main(["naming", "check"]) == 0
    assert main(["migration", "check"]) == 0
    assert main(["security", "check"]) == 0


def test_cli_invalid_use_returns_two() -> None:
    assert main(["evidence", "collect"]) == 2
    assert main(["unknown"]) == 2


def test_snapshot_requires_explicit_distinct_paths(tmp_path: Path) -> None:
    same = tmp_path / "same"
    assert (
        main(
            [
                "snapshot",
                "--seeds",
                str(same),
                "--json",
                str(same),
                "--markdown",
                str(tmp_path / "other"),
            ]
        )
        == 2
    )


def test_public_check_does_not_create_private_outputs(tmp_path: Path) -> None:
    private_marker = tmp_path / "private-output"
    assert main(["naming", "check"]) == 0
    assert not private_marker.exists()
