"""Explicit, local-only repository observation and private rendering."""

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from vulca_governance.commands import CommandResult, CommandRunner
from vulca_governance.errors import GovernanceError
from vulca_governance.schemas import load_yaml_object, require_exact_fields


SEED_FIELDS = {
    "id",
    "full_name",
    "visibility",
    "lifecycle",
    "local_roots",
    "expected_remote",
    "sensitivity",
    "release_boundary",
    "sync_relationship",
}
ALLOWED_GIT_OPERATIONS = {
    ("rev-parse", "--is-inside-work-tree"),
    ("rev-parse", "HEAD"),
    ("branch", "--show-current"),
    ("remote", "get-url", "origin"),
    ("status", "--porcelain=v1"),
    ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"),
    ("rev-list", "--left-right", "--count", "@{upstream}...HEAD"),
    ("worktree", "list", "--porcelain"),
}
_URL_USERINFO = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s/?#]*@")
_CREDENTIAL = re.compile(r"(?:github_pat_|gh[pousr]_[A-Za-z0-9]|sk-[A-Za-z0-9])", re.I)


def load_private_seeds(path: Path) -> dict[str, object]:
    data = load_yaml_object(path)
    _validate_private_seeds(data)
    return data


def private_seed_denylist(data: dict[str, object]) -> set[str]:
    _validate_private_seeds(data)
    denied: set[str] = set()
    for record in data["repositories"]:  # type: ignore[index]
        if record["visibility"] == "public":
            continue
        for field in ("id", "full_name", "expected_remote"):
            value = record[field]
            if isinstance(value, str):
                denied.add(value)
        if isinstance(record["full_name"], str):
            denied.add(record["full_name"].rsplit("/", 1)[-1])
        for root in record["local_roots"]:
            denied.update((root, Path(root).name))
    return denied


def classify_status(porcelain: str) -> str:
    lines = [line for line in porcelain.splitlines() if line]
    if not lines:
        return "clean"
    untracked = any(line.startswith("??") for line in lines)
    tracked = any(not line.startswith("??") for line in lines)
    if untracked and tracked:
        return "mixed"
    return "untracked" if untracked else "modified"


def parse_worktree_porcelain(text: str) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    current: dict[str, object] = {}

    def finish() -> None:
        if not current:
            return
        if "local_path" not in current:
            raise GovernanceError("worktree record is missing a path")
        current.setdefault("head", None)
        current.setdefault("current_branch", "detached")
        current.setdefault("locked", False)
        current.setdefault("prunable", False)
        records.append(dict(current))
        current.clear()

    for line in text.splitlines():
        if not line:
            finish()
            continue
        key, separator, value = line.partition(" ")
        if key == "worktree" and separator:
            if current:
                finish()
            current["local_path"] = value
        elif key == "HEAD" and separator:
            current["head"] = value
        elif key == "branch" and separator:
            current["current_branch"] = value.removeprefix("refs/heads/")
        elif key == "detached":
            current["current_branch"] = "detached"
        elif key == "locked":
            current["locked"] = True
        elif key == "prunable":
            current["prunable"] = True
    finish()
    return records


def build_private_snapshot(
    data: dict[str, object],
    runner: CommandRunner,
    observed_at: datetime | None = None,
    refresh_github: bool = False,
) -> dict[str, object]:
    _validate_private_seeds(data)
    timestamp = _timestamp(observed_at)
    records: list[dict[str, object]] = []
    seen: set[str] = set()
    for seed in data["repositories"]:  # type: ignore[index]
        github = None
        if refresh_github and isinstance(seed["full_name"], str):
            github = _github_metadata(seed["full_name"], runner)
        for root_value in seed["local_roots"]:
            root = Path(root_value)
            key = str(root.resolve(strict=False))
            if key in seen:
                continue
            observed = _scan_checkout(root, seed["expected_remote"], runner)
            candidates = [(root, observed)]
            if observed["availability"] == "available":
                worktrees = _git(runner, root, "worktree", "list", "--porcelain")
                if worktrees.returncode == 0:
                    for parsed in parse_worktree_porcelain(worktrees.stdout):
                        candidate = Path(str(parsed["local_path"]))
                        if str(candidate.resolve(strict=False)) != key:
                            candidates.append((candidate, None))
            for candidate, prescanned in candidates:
                candidate_key = str(candidate.resolve(strict=False))
                if candidate_key in seen:
                    continue
                seen.add(candidate_key)
                item = dict(prescanned) if prescanned is not None else _scan_checkout(
                    candidate, seed["expected_remote"], runner
                )
                record = {
                    "seed_id": seed["id"],
                    "full_name": seed["full_name"],
                    "visibility": seed["visibility"],
                    "lifecycle": seed["lifecycle"],
                    "expected_remote": seed["expected_remote"],
                    "sensitivity": seed["sensitivity"],
                    "release_boundary": seed["release_boundary"],
                    "sync_relationship": seed["sync_relationship"],
                    **item,
                }
                if github is not None:
                    record["github"] = github
                records.append(record)
    snapshot = {
        "schema_version": 1,
        "observed_at": timestamp,
        "github_refreshed": refresh_github,
        "records": sorted(records, key=lambda row: (str(row["seed_id"]), str(row["local_path"]))),
    }
    _validate_snapshot(snapshot)
    return snapshot


def render_private_json(snapshot: dict[str, object]) -> str:
    _validate_snapshot(snapshot)
    return json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render_private_markdown(snapshot: dict[str, object]) -> str:
    _validate_snapshot(snapshot)
    lines = [
        "# Vulca Private Repository Snapshot",
        "",
        f"- Observed at: `{snapshot['observed_at']}`",
        f"- GitHub refreshed: `{'yes' if snapshot['github_refreshed'] else 'no'}`",
        "",
        "| Seed | Local path | Availability | Branch | HEAD | Ahead | Behind | State | Action |",
        "| --- | --- | --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for record in snapshot["records"]:  # type: ignore[index]
        fields = (
            "seed_id",
            "local_path",
            "availability",
            "current_branch",
            "head",
            "ahead",
            "behind",
            "worktree_state",
            "recommended_action",
        )
        lines.append("| " + " | ".join(_cell(record.get(field)) for field in fields) + " |")
    lines.extend(
        [
            "",
            "This snapshot is observational. Recommended actions require human review and are never executed here.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _scan_checkout(root: Path, expected_remote: object, runner: CommandRunner) -> dict[str, object]:
    if not root.exists() or not root.is_dir():
        return _unavailable(root, "missing" if not root.exists() else "not-a-repository")
    inside = _git(runner, root, "rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return _unavailable(root, "not-a-repository", inside.error_category)
    head = _git(runner, root, "rev-parse", "HEAD")
    branch = _git(runner, root, "branch", "--show-current")
    remote = _git(runner, root, "remote", "get-url", "origin")
    status = _git(runner, root, "status", "--porcelain=v1")
    upstream = _git(runner, root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    remote_value = remote.stdout.strip() if remote.returncode == 0 else None
    if remote_value:
        _validate_private_values({"remote": remote_value})
    comparison = upstream.stdout.strip() if upstream.returncode == 0 else None
    ahead: int | str = "unknown"
    behind: int | str = "unknown"
    if comparison:
        divergence = _git(runner, root, "rev-list", "--left-right", "--count", "@{upstream}...HEAD")
        if divergence.returncode == 0:
            parts = divergence.stdout.split()
            if len(parts) == 2 and all(part.isdigit() for part in parts):
                behind, ahead = int(parts[0]), int(parts[1])
    record: dict[str, object] = {
        "availability": "available",
        "local_path": str(root),
        "remote_url": remote_value,
        "current_branch": branch.stdout.strip() if branch.returncode == 0 else None,
        "head": head.stdout.strip() if head.returncode == 0 else None,
        "comparison_ref": comparison,
        "ahead": ahead,
        "behind": behind,
        "worktree_state": classify_status(status.stdout) if status.returncode == 0 else "unknown",
        "prunable": False,
        "remote_mismatch": _normalize_remote(remote_value) != _normalize_remote(
            expected_remote if isinstance(expected_remote, str) else None
        ),
    }
    record["recommended_action"] = _recommend(record)
    return record


def _git(runner: CommandRunner, root: Path, *operation: str) -> CommandResult:
    if tuple(operation) not in ALLOWED_GIT_OPERATIONS:
        raise GovernanceError("Git operation is not allowlisted")
    return runner.run(["git", "-C", str(root), *operation], 10)


def _recommend(record: Mapping[str, object]) -> str:
    if record.get("prunable") is True:
        return "review-prunable-record"
    if record.get("availability") != "available":
        return "review-unavailable-checkout"
    if record.get("remote_mismatch") is True:
        return "inspect-remote-mismatch"
    if record.get("worktree_state") in {"modified", "untracked", "mixed"}:
        return "review-dirty-worktree"
    if any(isinstance(record.get(field), int) and record[field] > 0 for field in ("ahead", "behind")):
        return "review-divergence"
    return "none"


def _unavailable(root: Path, availability: str, error: str | None = None) -> dict[str, object]:
    record: dict[str, object] = {
        "availability": availability,
        "local_path": str(root),
        "remote_url": None,
        "current_branch": None,
        "head": None,
        "comparison_ref": None,
        "ahead": "unknown",
        "behind": "unknown",
        "worktree_state": "unknown",
        "prunable": False,
        "remote_mismatch": False,
    }
    if error:
        record["error_category"] = error
    record["recommended_action"] = _recommend(record)
    return record


def _normalize_remote(remote: str | None) -> str | None:
    if remote is None:
        return None
    value = remote.strip().rstrip("/").removesuffix(".git")
    if value.startswith("git@") and ":" in value:
        host, path = value[4:].split(":", 1)
        return f"{host.casefold()}/{path.casefold()}"
    match = re.match(r"https?://([^/]+)/(.+)", value, re.I)
    return f"{match.group(1).casefold()}/{match.group(2).casefold()}" if match else value


def _validate_private_seeds(data: dict[str, object]) -> None:
    _validate_private_values(data)
    require_exact_fields(data, {"schema_version", "repositories"}, context="private seeds")
    if data.get("schema_version") != 1:
        raise GovernanceError("private seed schema_version must be 1")
    repositories = data.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise GovernanceError("private repositories must be a non-empty list")
    seen: set[str] = set()
    for index, record in enumerate(repositories):
        if not isinstance(record, dict):
            raise GovernanceError(f"private seed {index} must be a mapping")
        require_exact_fields(record, SEED_FIELDS, context=f"private seed {index}")
        seed_id = record.get("id")
        if not isinstance(seed_id, str) or not seed_id:
            raise GovernanceError("private seed ID must be a non-empty string")
        if seed_id in seen:
            raise GovernanceError("duplicate private seed ID")
        seen.add(seed_id)
        roots = record.get("local_roots")
        if not isinstance(roots, list) or not roots or any(
            not isinstance(root, str) or not Path(root).is_absolute() for root in roots
        ):
            raise GovernanceError("private local_roots must contain absolute paths")
        if record.get("visibility") not in {"public", "private", "local-only"}:
            raise GovernanceError("private seed visibility is invalid")
        if record.get("sensitivity") not in {"public", "internal", "restricted"}:
            raise GovernanceError("private seed sensitivity is invalid")
        for field in ("lifecycle", "release_boundary", "sync_relationship"):
            if not isinstance(record.get(field), str) or not record[field]:
                raise GovernanceError(f"private seed {field} must be a non-empty string")


def _validate_private_values(value: object) -> None:
    if isinstance(value, Mapping):
        for child in value.values():
            _validate_private_values(child)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for child in value:
            _validate_private_values(child)
    elif isinstance(value, str):
        if _URL_USERINFO.search(value) or _CREDENTIAL.search(value):
            raise GovernanceError("private input contains credential-like material")


def _timestamp(value: datetime | None) -> str:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise GovernanceError("snapshot observed_at must include a timezone")
    return current.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_snapshot(snapshot: dict[str, object]) -> None:
    require_exact_fields(
        snapshot,
        {"schema_version", "observed_at", "github_refreshed", "records"},
        context="private snapshot",
    )
    if snapshot.get("schema_version") != 1 or not isinstance(snapshot.get("records"), list):
        raise GovernanceError("private snapshot schema is invalid")


def _github_metadata(full_name: str, runner: CommandRunner) -> dict[str, object]:
    if not re.fullmatch(r"[^/\s]+/[^/\s]+", full_name):
        raise GovernanceError("GitHub identity must be owner/repository")
    result = runner.run(
        ["gh", "repo", "view", full_name, "--json", "visibility,isArchived,defaultBranchRef"],
        30,
    )
    if result.returncode != 0:
        return {"availability": "unavailable", "error_category": result.error_category or "command-failed"}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"availability": "unavailable", "error_category": "invalid-response"}
    return payload if isinstance(payload, dict) else {"availability": "unavailable", "error_category": "invalid-response"}


def _cell(value: object) -> str:
    return ("unknown" if value is None else str(value)).replace("|", "\\|").replace("\n", " ")
