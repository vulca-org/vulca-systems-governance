"""Atomic public and private artifact writes with bounded failures."""

import os
from pathlib import Path
from collections.abc import Sequence
import tempfile

from vulca_governance.errors import GovernanceError


def write_public_atomic(path: Path, content: str) -> bool:
    """Atomically replace a public UTF-8 file only when its content changed."""
    try:
        if path.is_file() and path.read_text(encoding="utf-8") == content:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, staged_name = tempfile.mkstemp(prefix=".vulca-public-", dir=path.parent)
        staged = Path(staged_name)
        try:
            mode = (path.stat().st_mode & 0o777) if path.exists() else _default_public_mode()
            os.fchmod(descriptor, mode)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                descriptor = -1
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(staged, path)
        except BaseException:
            if descriptor >= 0:
                os.close(descriptor)
            staged.unlink(missing_ok=True)
            raise
    except OSError as exc:
        raise GovernanceError("public atomic write failed") from exc
    return True


def write_private_pair(outputs: tuple[tuple[Path, str], tuple[Path, str]]) -> None:
    """Atomically replace two distinct mode-0600 private artifacts as one transaction."""
    resolved = [target.resolve(strict=False) for target, _ in outputs]
    if resolved[0] == resolved[1]:
        raise GovernanceError("private snapshot targets must be distinct")
    _write_private_outputs(outputs)


def _default_public_mode() -> int:
    current = os.umask(0)
    os.umask(current)
    return 0o666 & ~current


def _stage_private_file(target: Path, content: bytes) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor = -1
    staged: Path | None = None
    try:
        descriptor, name = tempfile.mkstemp(prefix=".vulca-private-", dir=target.parent)
        staged = Path(name)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        return staged
    except OSError:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if staged is not None:
            try:
                staged.unlink()
            except OSError:
                pass
        raise


def _stage_backup(target: Path) -> Path | None:
    try:
        content = target.read_bytes()
    except FileNotFoundError:
        return None
    return _stage_private_file(target, content)


def _cleanup(paths: Sequence[Path | None]) -> bool:
    clean = True
    for path in paths:
        if path is None:
            continue
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            clean = False
    return clean


def _write_private_outputs(outputs: Sequence[tuple[Path, str]]) -> None:
    staged: list[Path] = []
    backups: dict[Path, Path | None] = {}
    try:
        for target, content in outputs:
            staged.append(_stage_private_file(target, content.encode("utf-8")))
        for target, _ in outputs:
            backups[target] = _stage_backup(target)
    except OSError as exc:
        _cleanup([*staged, *backups.values()])
        raise GovernanceError("private snapshot staging failed") from exc

    replaced: list[Path] = []
    try:
        for (target, _), staged_path in zip(outputs, staged):
            os.replace(staged_path, target)
            replaced.append(target)
    except OSError as exc:
        rollback_failed = False
        for target in reversed(replaced):
            backup = backups[target]
            try:
                if backup is None:
                    target.unlink(missing_ok=True)
                else:
                    os.replace(backup, target)
                    backups[target] = None
            except OSError:
                rollback_failed = True
        cleanup_failed = not _cleanup([*staged, *backups.values()])
        category = (
            "private snapshot rollback failed"
            if rollback_failed or cleanup_failed
            else "private snapshot transaction failed"
        )
        raise GovernanceError(category) from exc
    if not _cleanup([*staged, *backups.values()]):
        raise GovernanceError("private snapshot cleanup failed")
