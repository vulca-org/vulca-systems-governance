"""Public-output safety validation ported from the Wave 0A control boundary."""

from collections.abc import Mapping, Sequence
import re

from vulca_governance.errors import GovernanceError


PRIVATE_FIELDS: frozenset[str] = frozenset(
    {
        "local_path",
        "local_roots",
        "remote_url",
        "expected_remote",
        "head",
        "current_branch",
        "comparison_ref",
        "ahead",
        "behind",
        "worktree_state",
        "prunable",
        "recommended_action",
        "sensitivity",
    }
)

_CREDENTIAL_FIELD_PATTERN = re.compile(
    r"(?:token|password|secret|api[-_]?key|credential)", re.IGNORECASE
)
_CREDENTIAL_VALUE_PATTERN = re.compile(
    r"(?:github_pat_|gh[pousr]_[A-Za-z0-9]|sk-[A-Za-z0-9]|AIza[0-9A-Za-z_-])",
    re.IGNORECASE,
)
_URL_USERINFO_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s/?#]*@", re.IGNORECASE)
_WINDOWS_ABSOLUTE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
_GIT_SCP_REMOTE = re.compile(r"^git@[^\s:]+:[^\s]+$")
_PRIVATE_FRAGMENTS = (".env", "private-evidence", "credential-file", "session-file")


def _unsafe(field_path: str, category: str) -> GovernanceError:
    return GovernanceError(f"unsafe public value at {field_path}: {category}")


def validate_public_object(
    value: object,
    private_denylist: set[str] | None = None,
    field_path: str = "root",
) -> None:
    """Raise GovernanceError without echoing values when public content is unsafe."""
    lowered_denylist = {
        item.casefold() for item in (private_denylist or set()) if item.strip()
    }

    if isinstance(value, Mapping):
        for key, child in value.items():
            key_name = str(key)
            child_path = f"{field_path}.{key_name}"
            lowered_key = key_name.casefold()
            if lowered_key in PRIVATE_FIELDS:
                raise _unsafe(child_path, "private-only field")
            if _CREDENTIAL_FIELD_PATTERN.search(key_name):
                raise _unsafe(child_path, "credential-like field")
            validate_public_object(child, lowered_denylist, child_path)
        return

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            validate_public_object(child, lowered_denylist, f"{field_path}[{index}]")
        return

    if not isinstance(value, str):
        return

    stripped = value.strip()
    lowered = stripped.casefold()
    if _URL_USERINFO_PATTERN.search(stripped):
        raise _unsafe(field_path, "credential-like URL userinfo")
    if stripped.startswith("/") or _WINDOWS_ABSOLUTE_PATH.match(stripped):
        raise _unsafe(field_path, "absolute path")
    if lowered.startswith(("file://", "ssh://")) or _GIT_SCP_REMOTE.match(stripped):
        raise _unsafe(field_path, "non-public URL")
    if "localhost" in lowered or "127.0.0.1" in lowered:
        raise _unsafe(field_path, "localhost reference")
    if any(fragment in lowered for fragment in _PRIVATE_FRAGMENTS):
        raise _unsafe(field_path, "private path fragment")
    if _CREDENTIAL_VALUE_PATTERN.search(stripped):
        raise _unsafe(field_path, "credential-like value")
    if any(denied in lowered for denied in lowered_denylist):
        raise _unsafe(field_path, "private denylist match")
