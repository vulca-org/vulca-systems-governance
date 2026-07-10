import os
from pathlib import Path

import pytest

from vulca_governance.atomic_io import write_private_pair, write_public_atomic
from vulca_governance.errors import GovernanceError


def test_public_atomic_writes_only_when_changed(tmp_path: Path) -> None:
    target = tmp_path / "registry.md"
    assert write_public_atomic(target, "one\n") is True
    assert write_public_atomic(target, "one\n") is False
    assert target.read_text(encoding="utf-8") == "one\n"


def test_private_pair_rejects_resolved_path_collision(tmp_path: Path) -> None:
    target = tmp_path / "snapshot.json"
    alias = tmp_path / "." / "snapshot.json"
    with pytest.raises(GovernanceError, match="distinct"):
        write_private_pair(((target, "one"), (alias, "two")))


def test_private_pair_creates_mode_600_under_umask_022(tmp_path: Path) -> None:
    first = tmp_path / "one"
    second = tmp_path / "two"
    previous = os.umask(0o022)
    try:
        write_private_pair(((first, "one"), (second, "two")))
    finally:
        os.umask(previous)
    assert first.stat().st_mode & 0o777 == 0o600
    assert second.stat().st_mode & 0o777 == 0o600


def test_private_pair_bounds_second_replace_and_rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = tmp_path / "one"
    second = tmp_path / "two"
    first.write_text("old-one", encoding="utf-8")
    second.write_text("old-two", encoding="utf-8")
    real_replace = os.replace
    calls = 0

    def fail_second(source: str | Path, target: str | Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("raw secret error")
        real_replace(source, target)

    monkeypatch.setattr(os, "replace", fail_second)
    with pytest.raises(GovernanceError) as exc_info:
        write_private_pair(((first, "new-one"), (second, "new-two")))
    assert "raw secret error" not in str(exc_info.value)
    assert first.read_text(encoding="utf-8") == "old-one"
    assert second.read_text(encoding="utf-8") == "old-two"
    assert not list(tmp_path.glob(".vulca-private-*"))
