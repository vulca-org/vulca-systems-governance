"""Schema-loading helpers with bounded, value-free diagnostics."""

from collections.abc import Mapping, Set
from pathlib import Path
from typing import Any

import yaml

from vulca_governance.errors import GovernanceError


def load_yaml_object(path: Path) -> dict[str, Any]:
    """Load a YAML file whose top-level value must be a mapping."""
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise GovernanceError(f"invalid YAML in {path.name}") from exc

    if not isinstance(loaded, Mapping):
        raise GovernanceError(f"{path.name} must contain a top-level mapping")
    return dict(loaded)


def require_exact_fields(
    data: Mapping[str, Any], expected: Set[str], *, context: str
) -> None:
    """Require an exact field set while reporting names, never field values."""
    actual = set(data)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        raise GovernanceError(
            f"{context} fields do not match schema; missing={missing}; extra={extra}"
        )
