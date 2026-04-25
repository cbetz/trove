"""Composed analytical queries over HCRIS, Form 990 Schedule H, and the crosswalk."""

from analytics.community_benefit import community_benefit_gap

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "community_benefit_gap",
]
