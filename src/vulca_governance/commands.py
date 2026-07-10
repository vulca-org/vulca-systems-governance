"""Bounded read-only command boundaries for source evidence collection."""

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
from typing import Protocol

from vulca_governance.errors import GovernanceError


APPROVED_SDK_PATHS = frozenset({"pyproject.toml", "src/vulca/mcp_server.py"})


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    error_category: str | None = None


class CommandRunner(Protocol):
    def run(self, args: list[str], timeout: int) -> CommandResult: ...


class SubprocessRunner:
    """Run an argument list without a shell and discard raw error output."""

    def run(self, args: list[str], timeout: int) -> CommandResult:
        if not args or any(not isinstance(arg, str) for arg in args):
            raise GovernanceError("command must be a non-empty string argument list")
        try:
            completed = subprocess.run(
                args,
                shell=False,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return CommandResult(124, error_category="timeout")
        except FileNotFoundError:
            return CommandResult(127, error_category="executable-not-found")
        except OSError:
            return CommandResult(126, error_category="execution-error")
        category = None if completed.returncode == 0 else "command-failed"
        return CommandResult(completed.returncode, completed.stdout, category)


@dataclass(frozen=True)
class GitObjectReader:
    """Read only the approved objects from an explicit repository root at HEAD."""

    runner: CommandRunner

    def head(self, root: Path) -> str:
        self._require_root(root)
        result = self.runner.run(["git", "-C", str(root), "rev-parse", "HEAD"], 10)
        if result.returncode != 0:
            raise GovernanceError(f"Git HEAD read failed: {result.error_category or 'unknown'}")
        head = result.stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{40}", head):
            raise GovernanceError("Git HEAD is not a forty-character commit")
        return head

    def read(self, root: Path, relative_path: str) -> bytes:
        self._require_root(root)
        if relative_path not in APPROVED_SDK_PATHS:
            raise GovernanceError("Git object path is not approved")
        result = self.runner.run(
            ["git", "-C", str(root), "show", f"HEAD:{relative_path}"], 10
        )
        if result.returncode != 0:
            raise GovernanceError(
                f"Git object read failed: {result.error_category or 'unknown'}"
            )
        return result.stdout.encode("utf-8")

    @staticmethod
    def _require_root(root: Path) -> None:
        if not root.is_absolute():
            raise GovernanceError("source root must be an explicit absolute path")
