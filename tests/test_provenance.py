from pathlib import Path

import pytest

from vulca_governance.errors import GovernanceError
from vulca_governance.provenance import (
    DESIGN_COMMIT,
    SOURCE_PATHS,
    WAVE0A_COMMIT,
    parse_provenance,
    validate_provenance,
)


def _payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "design_commit": DESIGN_COMMIT,
        "wave0a_commit": WAVE0A_COMMIT,
        "candidate_content_commit": "c" * 40,
        "source_hashes": {path: "d" * 64 for path in SOURCE_PATHS},
        "extracted_symbols": {"safety": ["validate_public_object"]},
        "excluded_sdk_product_files": ["src/vulca/product.py"],
    }


def test_provenance_rejects_absolute_paths() -> None:
    payload = _payload()
    hashes = payload["source_hashes"]
    assert isinstance(hashes, dict)
    hashes["/private/source"] = hashes.pop(SOURCE_PATHS[0])
    with pytest.raises(GovernanceError, match="relative"):
        validate_provenance(payload)


def test_provenance_rejects_unknown_fields_and_invalid_hashes() -> None:
    payload = _payload()
    payload["unknown"] = True
    with pytest.raises(GovernanceError, match="schema"):
        validate_provenance(payload)
    payload = _payload()
    payload["source_hashes"][SOURCE_PATHS[0]] = "short"  # type: ignore[index]
    with pytest.raises(GovernanceError, match="hash"):
        validate_provenance(payload)


def test_provenance_requires_symbol_map() -> None:
    payload = _payload()
    payload["extracted_symbols"] = {}
    with pytest.raises(GovernanceError, match="symbol"):
        validate_provenance(payload)


def test_committed_provenance_is_valid() -> None:
    payload = parse_provenance(Path("PROVENANCE.md").read_text(encoding="utf-8"))
    validate_provenance(payload)
