"""Build legal, reproducible scientific-document campaigns."""

from sci_rag.campaigns.discovery import (
    CandidateWork,
    DiscoveryReport,
    discover_by_dois,
    discover_by_topic,
    normalize_doi,
)
from sci_rag.campaigns.state import CampaignRecord, CampaignState

__all__ = [
    "CampaignRecord",
    "CampaignState",
    "CandidateWork",
    "DiscoveryReport",
    "discover_by_dois",
    "discover_by_topic",
    "normalize_doi",
]
