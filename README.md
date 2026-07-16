# Vulca Systems Governance

Central, evidence-governed repository authority and migration validation for
Vulca Systems. This repository validates public registry, policy, source-bound
evidence, and migration state. It is not a product runtime dependency and does
not authorize or perform GitHub mutations.

The source-controlled security posture is a verified snapshot, not a live
GitHub credential or mutation mechanism. It records whether all required public
organization repositories meet the approved minimum controls and zero-open-
finding thresholds at the declared verification date.

Refresh the posture after adding a public repository or changing default-branch
security controls, then run `vulca-governance security check` and
`vulca-governance audit`. Existing controls may be stronger than the minimum;
the validator rejects weaker controls, missing repositories, and excess open
findings.

## Initial command surface

```text
vulca-governance registry check|render
vulca-governance evidence collect|verify
vulca-governance naming check
vulca-governance migration check
vulca-governance security check
vulca-governance audit
vulca-governance snapshot
```

Product observation requires an explicit source root. Private seeds and
snapshots remain outside this repository.
