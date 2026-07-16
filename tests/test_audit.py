import json

from vulca_governance.audit import build_audit, render_audit_json, render_audit_markdown
from vulca_governance.policies import load_policy_set


def test_audit_reports_are_deterministic_and_public() -> None:
    registry = {
        "repositories": [
            {"id": "b", "target_name": None},
            {"id": "vulca-sdk", "target_name": "vulca-visual-control-sdk"},
        ]
    }
    evidence = {"vulca-sdk": {"payload_sha256": "a" * 64}}
    migrations = {"records": [{"id": "vulca-sdk"}, {"id": "b"}]}
    security_posture = {"repositories": [{"name": ".github"}]}
    report = build_audit(
        registry,
        evidence,
        migrations,
        load_policy_set(),
        security_posture=security_posture,
    )
    assert report["repository_ids"] == ["b", "vulca-sdk"]
    assert report["categories"]["evidence"] == {"status": "pass", "repository_ids": ["vulca-sdk"]}
    assert report["categories"]["security"] == {
        "status": "pass",
        "repository_names": [".github"],
    }
    assert render_audit_json(report) == render_audit_json(report)
    assert json.loads(render_audit_json(report)) == report
    assert "Governance Audit" in render_audit_markdown(report)
    assert "observed_at" not in report
