"""Evidence adapter for the committed Vulca SDK source surface."""

import hashlib
from pathlib import Path
import re

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib

from vulca_governance.commands import GitObjectReader
from vulca_governance.errors import GovernanceError
from vulca_governance.evidence import finalize_evidence


INPUT_PATHS = ["pyproject.toml", "src/vulca/mcp_server.py"]


def collect_vulca_sdk_evidence(root: Path, reader: GitObjectReader) -> dict[str, object]:
    """Derive public SDK facts from the two approved committed HEAD objects."""
    source_commit = reader.head(root)
    inputs = {path: reader.read(root, path) for path in INPUT_PATHS}
    try:
        project = tomllib.loads(inputs["pyproject.toml"].decode("utf-8"))
        version = project["project"]["version"]
    except (UnicodeError, tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        raise GovernanceError("SDK project version could not be derived") from exc
    if not isinstance(version, str) or not version:
        raise GovernanceError("SDK project version must be a non-empty string")
    try:
        server_source = inputs["src/vulca/mcp_server.py"].decode("utf-8")
    except UnicodeError as exc:
        raise GovernanceError("SDK MCP source is not UTF-8") from exc
    tool_count = len(re.findall(r"@mcp\.tool\(", server_source))

    payload: dict[str, object] = {
        "schema_version": 1,
        "repository_id": "vulca-sdk",
        "source_identity": "vulca-org/vulca",
        "source_commit": source_commit,
        "collector": {"name": "vulca-sdk", "schema_version": 1},
        "input_paths": list(INPUT_PATHS),
        "input_sha256": {
            path: hashlib.sha256(content).hexdigest() for path, content in inputs.items()
        },
        "derived": {"mcp_tool_count": tool_count, "version": version},
    }
    return finalize_evidence(payload)
