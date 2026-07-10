"""Canonical source-evidence identity and verification."""

import hashlib
import json

from vulca_governance.errors import GovernanceError


def canonical_payload_bytes(payload: dict[str, object]) -> bytes:
    canonical = dict(payload)
    canonical.pop("payload_sha256", None)
    return json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")


def payload_sha256(payload: dict[str, object]) -> str:
    return hashlib.sha256(canonical_payload_bytes(payload)).hexdigest()


def finalize_evidence(payload: dict[str, object]) -> dict[str, object]:
    finalized = dict(payload)
    finalized["payload_sha256"] = payload_sha256(finalized)
    return finalized


def verify_evidence(pack: dict[str, object]) -> None:
    expected = pack.get("payload_sha256")
    if not isinstance(expected, str) or expected != payload_sha256(pack):
        raise GovernanceError("evidence payload hash mismatch")
