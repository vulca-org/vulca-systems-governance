from pathlib import Path

import pytest

from vulca_governance.errors import GovernanceError
from vulca_governance.schemas import load_yaml_object, require_exact_fields


def test_load_yaml_object_requires_mapping(tmp_path: Path) -> None:
    path = tmp_path / "list.yaml"
    path.write_text("- one\n- two\n", encoding="utf-8")

    with pytest.raises(GovernanceError, match="top-level mapping"):
        load_yaml_object(path)


def test_load_yaml_object_bounds_parse_error(tmp_path: Path) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text("secret-value: [\n", encoding="utf-8")

    with pytest.raises(GovernanceError) as exc_info:
        load_yaml_object(path)

    message = str(exc_info.value)
    assert "invalid YAML" in message
    assert "secret-value" not in message


def test_require_exact_fields_reports_names_not_values() -> None:
    data = {"name": "private-value", "unexpected": "secret-value"}

    with pytest.raises(GovernanceError) as exc_info:
        require_exact_fields(data, {"name", "status"}, context="registry row")

    message = str(exc_info.value)
    assert "status" in message
    assert "unexpected" in message
    assert "private-value" not in message
    assert "secret-value" not in message
