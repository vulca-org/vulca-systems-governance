from pathlib import Path

import pytest

from vulca_governance.commands import CommandResult, GitObjectReader
from vulca_governance.errors import GovernanceError


class RecordingRunner:
    def __init__(self, result: CommandResult) -> None:
        self.result = result
        self.calls: list[tuple[list[str], int]] = []

    def run(self, args: list[str], timeout: int) -> CommandResult:
        self.calls.append((args, timeout))
        return self.result


def test_git_reader_uses_fixed_list_command_and_timeout(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    runner = RecordingRunner(CommandResult(0, "a" * 40 + "\n"))
    reader = GitObjectReader(runner)
    assert reader.head(root) == "a" * 40
    assert runner.calls == [(["git", "-C", str(root), "rev-parse", "HEAD"], 10)]


@pytest.mark.parametrize("path", ["README.md", "../pyproject.toml", "/tmp/file"])
def test_git_reader_rejects_unapproved_paths_before_execution(
    tmp_path: Path, path: str
) -> None:
    runner = RecordingRunner(CommandResult(0, "unused"))
    with pytest.raises(GovernanceError, match="not approved"):
        GitObjectReader(runner).read(tmp_path.resolve(), path)
    assert runner.calls == []


def test_git_reader_bounds_command_failure(tmp_path: Path) -> None:
    runner = RecordingRunner(CommandResult(1, "secret output", "command-failed"))
    with pytest.raises(GovernanceError) as exc_info:
        GitObjectReader(runner).head(tmp_path.resolve())
    assert "secret output" not in str(exc_info.value)


def test_git_reader_requires_explicit_absolute_root(tmp_path: Path) -> None:
    runner = RecordingRunner(CommandResult(0, "unused"))
    with pytest.raises(GovernanceError, match="absolute"):
        GitObjectReader(runner).head(Path("relative"))
    assert runner.calls == []
