import json

import pytest

from vulca_governance.errors import GovernanceError
from vulca_governance.evidence import (
    canonical_payload_bytes,
    finalize_evidence,
    payload_sha256,
    verify_evidence,
)


def test_canonical_payload_is_sorted_compact_json() -> None:
    payload = {"z": 1, "a": {"b": 2}}
    assert canonical_payload_bytes(payload) == b'{"a":{"b":2},"z":1}'


def test_hash_excludes_payload_hash_field() -> None:
    payload = {"value": 1}
    digest = payload_sha256(payload)
    assert payload_sha256({**payload, "payload_sha256": "different"}) == digest


def test_finalize_and_verify_evidence() -> None:
    pack = finalize_evidence({"schema_version": 1, "value": "public"})
    verify_evidence(pack)
    assert json.loads(json.dumps(pack))["payload_sha256"] == pack["payload_sha256"]


def test_verify_rejects_hash_mismatch() -> None:
    with pytest.raises(GovernanceError, match="hash mismatch"):
        verify_evidence({"schema_version": 1, "payload_sha256": "0" * 64})
