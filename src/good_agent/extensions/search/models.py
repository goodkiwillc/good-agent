from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from good_agent.core.models import GoodBase
from good_agent.core.types import URL


class OperationType(Enum):
    """Fundamental operation types for data sources."""

    SEARCH = "search"  # Discovery - finding unknown items
    RETRIEVE = "retrieve"  # Fetching specific known items
    ANALYZE = "analyze"  # Extracting insights from data
    GRAPH = "graph"  # Exploring relationships


class DataDomain(Enum):
    """High-level data domains that providers operate in."""

    WEB = "web"  # General web content
    SOCIAL_MEDIA = "social_media"  # Social platforms
    NEWS = "news"  # News articles
    PEOPLE = "people"  # Person entities
    COMPANIES = "companies"  # Organization entities
    DOMAINS = "domains"  # Website/domain analysis
    ADS = "ads"  # Advertising data
    MEDIA = "media"  # Images, videos, audio


class Platform(Enum):
    """Specific platforms/sources."""

    # Search engines
    GOOGLE = "google"
    BING = "bing"

    # Social media
    TWITTER = "twitter"
    REDDIT = "reddit"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    YOUTUBE = "youtube"
    THREADS = "threads"
    TRUTHSOCIAL = "truthsocial"

    # Data providers
    WIKIPEDIA = "wikipedia"
    WIKIDATA = "wikidata"
    BALLOTPEDIA = "ballotpedia"
    OPENCORPORATES = "opencorporates"
    LITTLESIS = "littlesis"

    # People/company data
    ZOOMINFO = "zoominfo"
    PEOPLEDATALABS = "peopledatalabs"


@dataclass
class MediaItem:
    """Media attachment in search results."""

    type: Literal["image", "video", "gif", "audio"]
    url: str
    thumbnail_url: str | None = None
    duration_seconds: int | None = None  # For video/audio
    width: int | None = None
    height: int | None = None
    alt_text: str | None = None


class SearchResult(GoodBase):
    """
    Standardized search result across all platforms.

    Provides common fields while preserving platform-specific data.
    """

    # Core fields (required)
    platform: str  # Platform identifier
    id: str  # Platform-specific ID
    url: URL  # Canonical URL to content
    content: str  # Main text content
    content_type: Literal["text", "image", "video", "mixed"]

    # Author information
    author_id: str | None = None
    author_name: str | None = None
    author_handle: str | None = None
    author_verified: bool = False
    author_url: URL | None = None

    # Temporal
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Engagement metrics (platform-specific keys)
    # Common keys: likes, shares, comments, views, bookmarks, retweets
    metrics: dict[str, int] = field(default_factory=dict)

    # Media and attachments
    media: list[MediaItem] = field(default_factory=list)

    # Relationships (for threaded content)
    reply_to_id: str | None = None
    quoted_id: str | None = None
    thread_id: str | None = None

    # Search-specific metadata
    relevance_score: float | None = None  # 0-1 score from search
    snippet: str | None = None  # Highlighted snippet from search

    # Platform-specific data preserved as-is
    platform_data: dict[str, Any] = field(default_factory=dict)

    def to_citation(self) -> dict:
        """Convert to citation format for CitationManager."""
        title = (
            f"{self.author_name}: {self.content[:100]}" if self.author_name else self.content[:100]
        )
        return {
            "url": self.url,
            "title": title,
            "platform": self.platform,
            "date": self.created_at,
        }


class UserResult(GoodBase):
    """
    Standardized user/profile result from entity search.

    Represents a person or organization profile on a platform.
    """

    # Core identity
    platform: str
    id: str
    username: str
    display_name: str
    profile_url: URL

    # Profile details
    bio: str | None = None
    location: str | None = None
    website: URL | None = None
    verified: bool = False

    # Statistics
    follower_count: int | None = None
    following_count: int | None = None
    post_count: int | None = None

    # Media
    avatar_url: URL | None = None
    banner_url: URL | None = None

    # Metadata
    created_at: datetime | None = None
    categories: list[str] = field(default_factory=list)

    # Platform-specific data
    platform_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderCapability:
    """
    Describes a specific capability of a search provider.

    Used for intelligent provider selection based on requirements.
    """

    # What this capability does
    operation: OperationType
    domain: DataDomain
    platform: Platform | None = None  # None for cross-platform
    method: str = ""  # Specific method name (e.g., "web_search", "news_search")

    # Quality metrics
    data_freshness: int = 0  # Minutes delay from real-time (0 = real-time)
    data_completeness: float = 1.0  # 0-1 score of result completeness
    rate_limit: int = 100  # Requests per minute

    # Cost metrics
    cost_per_request: float = 0.0  # In USD
    cost_model: Literal["per_request", "per_result", "subscription"] = "per_request"

    # Constraints
    requires_auth: bool = False
    geo_restricted: list[str] | None = None  # Country codes

    # Additional metadata
    unique_features: list[str] = field(default_factory=list)  # Platform-specific features
    supported_filters: list[str] = field(default_factory=list)  # Available filter options


@dataclass
class SearchQuery:
    """
    Unified query representation for cross-platform search.

    Providers transform this into platform-specific queries.
    """

    # Core search
    text: str | None = None

    # Common filters
    content_type: Literal["all", "text", "image", "video"] = "all"
    since: datetime | None = None
    until: datetime | None = None

    # Author filters
    from_users: list[str] = field(default_factory=list)
    to_users: list[str] = field(default_factory=list)

    # Engagement thresholds
    min_engagement: int | None = None  # Platform-specific interpretation

    # Location
    location: str | None = None
    radius_km: int | None = None

    # Language and region
    language: str | None = None  # ISO 639-1 code
    country: str | None = None  # ISO 3166-1 alpha-2

    # Advanced
    has_media: bool | None = None
    is_verified: bool | None = None
    hashtags: list[str] = field(default_factory=list)
    exclude_terms: list[str] = field(default_factory=list)

    # Pagination
    limit: int = 10
    offset: int = 0

    # Sorting
    sort_by: Literal["relevance", "recent", "popular"] = "relevance"


@dataclass
class SearchConstraints:
    """Constraints for provider selection and search execution."""

    # Cost constraints
    max_cost_per_request: float | None = None
    max_total_cost: float | None = None

    # Quality requirements
    min_data_freshness: int | None = None  # Max minutes old
    min_completeness: float | None = None  # 0-1 score

    # Performance
    max_response_time: int | None = None  # Milliseconds

    # Features
    required_features: list[str] = field(default_factory=list)

    # Optimization preference
    optimize_for: Literal["cost", "quality", "speed", "balanced"] = "balanced"
