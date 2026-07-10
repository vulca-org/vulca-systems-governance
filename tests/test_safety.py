import pytest

from vulca_governance.errors import GovernanceError
from vulca_governance.safety import validate_public_object


@pytest.mark.parametrize(
    "value",
    [
        "/private/absolute/path",
        "file:///private/path",
        "http://localhost:8000",
        "git@example.com:private/repo.git",
        "https://alice:arbitrary-secret@example.com/repo",
        "github_" + "pat_" + "examplevalue",
        {"local_path": "hidden"},
    ],
)
def test_public_objects_reject_private_or_credential_material(value: object) -> None:
    with pytest.raises(GovernanceError, match="unsafe public value"):
        validate_public_object(value)


def test_errors_do_not_echo_secret() -> None:
    secret = "https://alice:do-not-echo@example.com/repo"
    with pytest.raises(GovernanceError) as exc:
        validate_public_object({"notes": f"See {secret}"})
    assert "do-not-echo" not in str(exc.value)


def test_plain_scp_style_identity_is_allowed_when_not_a_public_url() -> None:
    validate_public_object({"example": "user@example.com:group/repo"})


def test_private_denylist_is_case_insensitive() -> None:
    with pytest.raises(GovernanceError, match="private denylist"):
        validate_public_object({"notes": "INTERNAL-REPOSITORY"}, {"internal-repository"})
