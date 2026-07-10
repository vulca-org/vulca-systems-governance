# Vulca Systems Governance

Central, evidence-governed repository authority and migration validation for
Vulca Systems. This repository validates public registry, policy, source-bound
evidence, and migration state. It is not a product runtime dependency and does
not authorize or perform GitHub mutations.

## Initial command surface

```text
vulca-governance registry check|render
vulca-governance evidence collect|verify
vulca-governance naming check
vulca-governance migration check
vulca-governance audit
vulca-governance snapshot
```

Product observation requires an explicit source root. Private seeds and
snapshots remain outside this repository.
