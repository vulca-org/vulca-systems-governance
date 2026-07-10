from pathlib import Path
import shutil
import subprocess

from vulca_governance.adapters.vulca_sdk import collect_vulca_sdk_evidence
from vulca_governance.commands import GitObjectReader, SubprocessRunner
from vulca_governance.evidence import verify_evidence


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_adapter_reads_committed_head_without_changing_status(tmp_path: Path) -> None:
    root = tmp_path / "sdk"
    shutil.copytree(Path("tests/fixtures/sdk"), root)
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "Test User")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "fixture")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "vulca"\nversion = "9.9.9"\n', encoding="utf-8"
    )
    before = _git(root, "status", "--porcelain")

    pack = collect_vulca_sdk_evidence(root.resolve(), GitObjectReader(SubprocessRunner()))

    assert pack["source_commit"] == _git(root, "rev-parse", "HEAD")
    assert len(pack["source_commit"]) == 40
    assert pack["input_paths"] == ["pyproject.toml", "src/vulca/mcp_server.py"]
    assert pack["derived"] == {"mcp_tool_count": 2, "version": "1.2.3"}
    assert "observed_at" not in pack
    verify_evidence(pack)
    assert _git(root, "status", "--porcelain") == before
