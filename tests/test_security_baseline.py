from copy import deepcopy
from pathlib import Path

import pytest

from vulca_governance.errors import GovernanceError
from vulca_governance.policies import load_policy_set
from vulca_governance.security_baseline import (
    load_security_posture,
    validate_security_posture,
)


POSTURE_PATH = Path("evidence/public/organization-security-posture.yaml")


def test_checked_in_security_posture_satisfies_baseline() -> None:
    policies = load_policy_set()
    posture = load_security_posture(POSTURE_PATH)
    validate_security_posture(posture, policies.security_baseline)


def test_open_finding_fails_baseline() -> None:
    policies = load_policy_set()
    posture = deepcopy(load_security_posture(POSTURE_PATH))
    posture["repositories"][0]["open_code_scanning_alerts"] = 1
    with pytest.raises(GovernanceError, match="exceeds open_code_scanning_alerts"):
        validate_security_posture(posture, policies.security_baseline)


def test_missing_repository_fails_baseline() -> None:
    policies = load_policy_set()
    posture = deepcopy(load_security_posture(POSTURE_PATH))
    posture["repositories"].pop()
    with pytest.raises(GovernanceError, match="coverage does not match"):
        validate_security_posture(posture, policies.security_baseline)


def test_stronger_repository_controls_remain_valid() -> None:
    policies = load_policy_set()
    posture = deepcopy(load_security_posture(POSTURE_PATH))
    posture["repositories"][0]["required_approving_review_count"] = 1
    posture["repositories"][0]["code_scanning_required_check"] = "required"
    validate_security_posture(posture, policies.security_baseline)
