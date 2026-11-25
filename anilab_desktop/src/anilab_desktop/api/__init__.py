"""Catalog API clients (Jikan v4 primary + AniList GraphQL fallback)."""

from .anilist import ANILIST_URL, AniListCatalogClient
from .client import FallbackCatalogClient, create_catalog_client
from .jikan import JIKAN_BASE_URL, JikanCatalogClient

__all__ = [
    "ANILIST_URL",
    "AniListCatalogClient",
    "FallbackCatalogClient",
    "JIKAN_BASE_URL",
    "JikanCatalogClient",
    "create_catalog_client",
]
