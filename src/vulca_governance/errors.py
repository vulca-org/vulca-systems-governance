"""Bounded public errors raised by governance validation."""


class GovernanceError(ValueError):
    """A validation error safe to surface without source values."""
