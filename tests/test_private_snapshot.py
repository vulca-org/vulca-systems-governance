from pathlib import Path

from vulca_governance.commands import CommandResult
from vulca_governance.private_snapshot import (
    build_private_snapshot,
    classify_status,
    parse_worktree_porcelain,
    private_seed_denylist,
    render_private_json,
    render_private_markdown,
)


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def run(self, args: list[str], timeout: int) -> CommandResult:
        self.calls.append(args)
        operation = args[3:]
        responses = {
            ("rev-parse", "--is-inside-work-tree"): "true\n",
            ("rev-parse", "HEAD"): "a" * 40 + "\n",
            ("branch", "--show-current"): "main\n",
            ("remote", "get-url", "origin"): "git@example.com:public/repo.git\n",
            ("status", "--porcelain=v1"): " M README.md\n?? notes\n",
            ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"): "origin/main\n",
            ("rev-list", "--left-right", "--count", "@{upstream}...HEAD"): "2\t3\n",
            ("worktree", "list", "--porcelain"): "",
        }
        return CommandResult(0, responses[tuple(operation)])


def _seeds(root: Path) -> dict[str, object]:
    return {
        "schema_version": 1,
        "repositories": [
            {
                "id": "example-private",
                "full_name": "example/private-repository",
                "visibility": "private",
                "lifecycle": "active",
                "local_roots": [str(root)],
                "expected_remote": "https://example.com/expected/repo.git",
                "sensitivity": "internal",
                "release_boundary": "Private development source.",
                "sync_relationship": "Exports selected public-safe artifacts.",
            }
        ],
    }


def test_status_and_worktree_parsing() -> None:
    assert classify_status("") == "clean"
    assert classify_status("?? one\n") == "untracked"
    assert classify_status(" M one\n") == "modified"
    assert classify_status(" M one\n?? two\n") == "mixed"
    parsed = parse_worktree_porcelain(
        "worktree /tmp/path with spaces\nHEAD " + "a" * 40 + "\nbranch refs/heads/main\n\n"
    )
    assert parsed[0]["local_path"] == "/tmp/path with spaces"
    assert parsed[0]["current_branch"] == "main"


def test_snapshot_is_read_only_no_network_by_default(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    runner = FakeRunner()
    snapshot = build_private_snapshot(_seeds(tmp_path), runner, refresh_github=False)
    record = snapshot["records"][0]
    assert record["remote_mismatch"] is True
    assert record["ahead"] == 3
    assert record["behind"] == 2
    assert record["worktree_state"] == "mixed"
    assert record["recommended_action"] == "inspect-remote-mismatch"
    assert all(call[0] == "git" for call in runner.calls)
    assert "gh" not in {call[0] for call in runner.calls}
    assert render_private_json(snapshot).endswith("\n")
    assert "Vulca Private Repository Snapshot" in render_private_markdown(snapshot)


def test_private_denylist_contains_identity_remote_and_root(tmp_path: Path) -> None:
    denied = private_seed_denylist(_seeds(tmp_path))
    assert "example/private-repository" in denied
    assert "private-repository" in denied
    assert str(tmp_path) in denied
