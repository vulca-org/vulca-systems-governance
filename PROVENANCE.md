# Provenance

This local-only candidate uses a fresh Git history. It ports bounded governance
algorithms from the verified Wave 0A source and does not copy SDK product code.

```json
{
  "candidate_content_commit": "68adeec836b0eafee5eb198348ca50866e4f0e35",
  "design_commit": "bc30259f3dd97ed7aedbc0858e7ce6b14500a22a",
  "excluded_sdk_product_files": [
    "pyproject.toml",
    "src/vulca/mcp_server.py",
    "src/vulca/pipeline/",
    "src/vulca/providers/"
  ],
  "extracted_symbols": {
    "atomic_io": [
      "private staging and rollback algorithms",
      "same-directory atomic replacement"
    ],
    "commands": [
      "bounded list-argument subprocess runner"
    ],
    "private_snapshot": [
      "build_private_snapshot",
      "classify_status",
      "parse_worktree_porcelain",
      "private_seed_denylist",
      "render_private_json",
      "render_private_markdown"
    ],
    "registry": [
      "deterministic public registry rendering",
      "stable public authority validation"
    ],
    "safety": [
      "recursive public value validation",
      "URL userinfo and credential detection"
    ]
  },
  "schema_version": 1,
  "source_hashes": {
    "docs/product/repository-registry.md": "c48531dc1561ab87ffb447f3d0a59c73a298a8a155c6487b5f5f617c04e98928",
    "docs/product/repository-registry.yaml": "f7de808b106ceff1e9873261aee490eed2e8193ab7efd09f7a9b4034e281745b",
    "scripts/build_repository_registry.py": "530799004c49391419b782a90df8e58ebcff3416bb33740c203f8c1bbf48641e",
    "tests/test_repository_registry.py": "b66681b2c4bd0d3cdcd65693b4ba99ab4e84d1a0aaff9a3155328230539f7faa"
  },
  "wave0a_commit": "d61139ef1d088e68d0fa23798f37ca04c00399bf"
}
```
