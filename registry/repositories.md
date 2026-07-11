# Vulca Systems Repository Registry

Verified on: 2026-07-10

Only public repositories appear as records. This registry describes stable authority, target naming, lifecycle, synchronization, and release boundaries; dynamic branch, commit, worktree, and local availability state remains outside the public artifact.

## claude-skills-vulca

- Current: [yha9806/claude-skills-vulca](https://github.com/yha9806/claude-skills-vulca)
- Target: unresolved
- Lane: integrations-internal-archive
- Lifecycle: archived
- Disposition: archive
- Canonical for: Historical Vulca skill distribution
- Version source: Repository revision
- Release channels: none
- Release boundary: Archived with no active release channel.
- Synchronization: none
- Notes: Archived historical surface; current skills ship through canonical repositories.

## comfyui-vulca

- Current: [vulca-org/comfyui-vulca](https://github.com/vulca-org/comfyui-vulca)
- Target: vulca-comfyui-visual-nodes
- Lane: integrations-internal-archive
- Lifecycle: active
- Disposition: adopt
- Canonical for: Vulca ComfyUI adapter
- Version source: Package manifest and Git tags
- Release channels: GitHub tags, GitHub Releases
- Release boundary: Maintainer-approved adapter releases through public Git channels.
- Synchronization: Adapter releases consume public Vulca SDK contracts; adapter-specific nodes remain authoritative in this repository.
- Notes: Canonical ComfyUI integration surface.

## emnlp2025-vulca

- Current: [yha9806/EMNLP2025-VULCA](https://github.com/yha9806/EMNLP2025-VULCA)
- Target: unresolved
- Lane: research-evaluation
- Lifecycle: deprecated
- Disposition: blocked
- Canonical for: Historical EMNLP 2025 research artifacts
- Version source: Repository revision
- Release channels: GitHub repository
- Release boundary: Historical research traceability only; no current product release authority.
- Synchronization: none
- Notes: Historical research surface; target naming remains unresolved.

## vulca-bench

- Current: [yha9806/VULCA-Bench](https://github.com/yha9806/VULCA-Bench)
- Target: vulca-cultural-visual-benchmark
- Lane: research-evaluation
- Lifecycle: maintained
- Disposition: adopt
- Canonical for: Public VULCA-Bench research artifacts
- Version source: Dataset and repository revisions
- Release channels: GitHub repository
- Release boundary: Research maintainers govern public dataset and repository revisions.
- Synchronization: none
- Notes: Supporting benchmark research; it is not the SDK release authority.

## vulca-emnlp2025-site

- Current: [yha9806/VULCA-EMNLP2025](https://github.com/yha9806/VULCA-EMNLP2025)
- Target: unresolved
- Lane: research-evaluation
- Lifecycle: deprecated
- Disposition: blocked
- Canonical for: Historical EMNLP 2025 project website
- Version source: Repository revision
- Release channels: GitHub Pages
- Release boundary: Historical website traceability only; no current product release authority.
- Synchronization: none
- Notes: Historical website surface; target naming remains unresolved.

## vulca-exhibition

- Current: [yha9806/vulca-exhibition](https://github.com/yha9806/vulca-exhibition)
- Target: unresolved
- Lane: integrations-internal-archive
- Lifecycle: deprecated
- Disposition: blocked
- Canonical for: Historical exhibition implementation
- Version source: Repository revision
- Release channels: none
- Release boundary: No active release channel; target naming remains unresolved.
- Synchronization: Superseded by current public product surfaces; no reverse synchronization is expected.
- Notes: Migrated historical implementation retained for traceability.

## vulca-framework

- Current: [yha9806/VULCA-Framework](https://github.com/yha9806/VULCA-Framework)
- Target: vulca-cultural-evaluation-framework
- Lane: research-evaluation
- Lifecycle: maintained
- Disposition: adopt
- Canonical for: Public VULCA framework research artifacts
- Version source: Repository revisions
- Release channels: GitHub repository
- Release boundary: Research maintainers govern public repository revisions.
- Synchronization: none
- Notes: Supporting research framework; it is not the SDK release authority.

## vulca-plugin

- Current: [vulca-org/vulca-plugin](https://github.com/vulca-org/vulca-plugin)
- Target: vulca-visual-agent-plugin
- Lane: visual-systems
- Lifecycle: active
- Disposition: adopt
- Canonical for: Vulca agent plugin distribution
- Version source: Plugin manifest
- Release channels: GitHub repository
- Release boundary: Maintainer-approved plugin packaging from the declared manifest.
- Synchronization: Selected public SDK skills synchronize from the SDK distribution into this plugin distribution repository.
- Notes: Canonical plugin packaging surface; it does not replace the SDK source.

## vulca-sdk

- Current: [vulca-org/vulca-visual-control-sdk](https://github.com/vulca-org/vulca-visual-control-sdk)
- Target: vulca-visual-control-sdk
- Lane: visual-systems
- Lifecycle: active
- Disposition: adopt
- Canonical for: Vulca Python SDK, Vulca CLI, Vulca MCP server, Public SDK documentation
- Version source: pyproject.toml
- Release channels: PyPI, GitHub tags, GitHub Releases
- Release boundary: Maintainer-approved public SDK releases from the declared version source.
- Synchronization: A non-public development source may export selected public-safe changes into this repository; this repository is the public distribution source.
- Notes: Canonical public product and developer surface.
- Evidence-derived facts:
  - mcp_tool_count: 23
  - version: 0.23.1
