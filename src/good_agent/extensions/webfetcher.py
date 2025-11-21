# """
# WebFetcher Component for Agent Framework

# Provides clean web fetching tools with optional summarization.
# Exposes two tools: fetch (single URL) and fetch_many (multiple URLs).
# """

# import asyncio
# import datetime
# import logging
# from collections.abc import Callable
# from dataclasses import dataclass

# # from datetime import timedelta
# from typing import TYPE_CHECKING, Any, Literal

# from good_common.utilities import map_as_completed
# try:  # optional dependency; allow import without good_agent_fetch
#     from good_agent_fetch.web import ExtractedContent, fetch
# except Exception:  # pragma: no cover - optional dependency
#     ExtractedContent = object  # type: ignore
#     def fetch(*args, **kwargs):  # type: ignore
#         raise ImportError("good_agent_fetch is required for WebFetcher; install it to enable fetching")

# from good_agent.components import AgentComponent
# from good_agent.core.models import Renderable
# from good_agent.tools import tool
# from good_agent.core.types import URL, NullableParsedDate

# if TYPE_CHECKING:
#     try:
#         from good_agent_fetch.web import Response
#     except Exception:  # pragma: no cover
#         from typing import Any as Response

# logger = logging.getLogger(__name__)


# @dataclass
# class FetchStats:
#     """Statistics from a bulk fetch operation."""

#     total: int
#     success: int
#     failed: int
#     success_rate: float


# @dataclass
# class BulkFetchResult:
#     """Result from bulk_fetch_with_progress method."""

#     urls: list[str]
#     successful: list[str]
#     failed: list[str]
#     content: dict[
#         str, Any
#     ]  # URL -> fetched content (WebFetchSummary or ExtractedContent)
#     stats: FetchStats


# @dataclass
# class SearchFetchResult:
#     """Result from fetch_from_search_results method."""

#     urls: list[str]
#     successful: list[str]
#     failed: list[str]
#     content: dict[
#         str, Any
#     ]  # URL -> fetched content (WebFetchSummary or ExtractedContent)
#     stats: FetchStats


# class WebFetchSummary(Renderable):
#     """Renderable summary of web content for display with citation-ready XML wrapper."""

#     __template__ = """<content url="{{ url }}">
# {% if title or author or published_date -%}
# {% if title %}title: {{ title }}
# {% endif -%}
# {% if author %}author: {{ author }}
# {% endif -%}
# {% if published_date %}published: {{ published_date }}
# {% endif -%}

# ---

# {% endif -%}
# {{ summary }}
# </content>"""

#     title: str | None = None
#     url: URL | None = None
#     author: str | None = None
#     published_date: NullableParsedDate = None
#     summary: str


# class WebFetcher(AgentComponent):
#     """
#     WebFetcher component providing clean fetch tools.

#     Features:
#     - Two tools: fetch (single) and fetch_many (multiple URLs)
#     - Format parameter: 'full' (default) or 'summary'
#     - TTL-based caching via fetch API
#     - Configurable content validation and summarization
#     """

#     def __init__(
#         self,
#         default_ttl: int | datetime.timedelta = 3600,
#         default_format: Literal["full", "summary"] = "full",
#         validate_content: bool = True,
#         summarization_strategy: Literal[
#             "chain_of_density", "bullets", "tldr", "basic"
#         ] = "chain_of_density",
#         word_limit: int = 120,
#         enable_summarization: bool = True,
#         summarization_model: str = "gpt-4.1-mini",
#         **kwargs,
#     ):
#         """
#         Initialize WebFetcher component.

#         Args:
#             default_ttl: Default cache TTL (seconds or timedelta)
#             validate_content: Check for paywalls/errors
#             summarization_strategy: Default summarization strategy
#             word_limit: Default target word count for summaries
#             enable_summarization: Whether to enable summarization
#             summarization_model: Model to use for summarization
#         """
#         super().__init__(**kwargs)

#         self.default_ttl = (
#             default_ttl
#             if isinstance(default_ttl, datetime.timedelta)
#             else datetime.timedelta(seconds=default_ttl)
#         )
#         self.validate_content = validate_content
#         self.summarization_strategy = summarization_strategy
#         self.word_limit = word_limit
#         self.enable_summarization = enable_summarization
#         self.summarization_model = summarization_model
#         self.default_format = default_format

#     async def _fetch_urls(
#         self,
#         urls: list[URL],
#         ttl: int | datetime.timedelta | None = None,
#         validate_content: bool | None = None,
#         summarize: bool = False,
#         strategy: Literal["chain_of_density", "bullets", "tldr", "basic"] | None = None,
#         word_limit: int | None = None,
#         summarization_prompt: str | None = None,
#     ) -> list["Response"]:
#         """
#         Internal method to fetch URLs with caching and optional summarization.

#         Args:
#             urls: List of URLs to fetch
#             ttl: Cache TTL (uses default if None)
#             validate_content: Check for paywalls (uses default if None)
#             summarize: Whether to summarize content
#             strategy: Summarization strategy (uses default if None)
#             word_limit: Target word count (uses default if None)
#             summarization_prompt: Optional prompt to guide the summarization focus

#         Returns:
#             List of Response objects
#         """
#         # Use defaults if not specified
#         ttl = ttl or self.default_ttl
#         validate_content = (
#             validate_content if validate_content is not None else self.validate_content
#         )
#         strategy = strategy or self.summarization_strategy  # type: ignore
#         word_limit = word_limit or self.word_limit

#         responses = []

#         # Use fetch API with TTL for automatic caching
#         async for response in fetch(
#             urls=urls, ttl=ttl, log_progress=True, canonical=True
#         ):
#             try:
#                 # Check if this was from cache
#                 from_cache = response.metadata.get("from_cache", False)

#                 # Track cache status
#                 response.metadata["from_cache"] = from_cache

#                 # Process response based on status
#                 if response.status_code == 200:
#                     # Get content - prefer extracted main, fall back to full text
#                     content = (
#                         response.main
#                         or response.full
#                         or (
#                             response.text()
#                             if callable(response.text)
#                             else response.text
#                         )
#                     )

#                     # Detect paywalls if validation enabled
#                     if (
#                         validate_content
#                         and content
#                         and self._is_paywall(content, response)
#                     ):
#                         response.metadata["error"] = "Paywall detected"
#                         response.metadata["paywall"] = True
#                         content = None

#                     # Summarize if requested and content available
#                     if summarize and content and self.enable_summarization:
#                         # Check if we already have a cached summary
#                         summary_key = f"summary_{strategy}_{word_limit}"

#                         if summary_key not in response.metadata:
#                             logger.debug(
#                                 f"WebFetcher: No cached summary found for {response.url}, "
#                                 f"generating new {strategy} summary "
#                                 f"({word_limit} words)"
#                             )

#                             # Generate summary
#                             summary = await self._summarize_content(
#                                 content,
#                                 strategy=strategy or self.summarization_strategy,
#                                 word_limit=word_limit,
#                                 title=response.title,
#                                 url=str(response.url),
#                                 summarization_prompt=summarization_prompt,
#                             )
#                             response.metadata[summary_key] = summary
#                             response.metadata["summarized"] = True
#                             response.metadata["summarization_strategy"] = strategy
#                             logger.debug(
#                                 f"WebFetcher: Generated summary for {response.url}, "
#                                 f"length: {len(summary)} chars"
#                             )
#                         else:
#                             logger.debug(
#                                 f"WebFetcher: Using cached summary for {response.url} "
#                                 f"(key: {summary_key})"
#                             )

#                         # Store current summary in metadata for easy access
#                         response.metadata["summary"] = response.metadata[summary_key]
#                 else:
#                     response.metadata["error"] = f"HTTP {response.status_code}"

#                 responses.append(response)

#             except Exception as e:
#                 logger.error(f"Error processing response for {response.url}: {e}")
#                 response.metadata["error"] = str(e)
#                 responses.append(response)

#         return responses

#     def _is_paywall(self, content: str, response: "Response") -> bool:
#         """
#         Detect if content is behind a paywall.

#         Args:
#             content: Extracted content text
#             response: Response object

#         Returns:
#             True if paywall detected
#         """
#         if not content:
#             return False

#         # Common paywall indicators
#         paywall_indicators = [
#             "subscribe to continue reading",
#             "this content is for subscribers",
#             "become a member to read",
#             "sign up to read more",
#             "you've reached your free article limit",
#             "exclusive content for members",
#             "premium content",
#             "subscription required",
#         ]

#         content_lower = content.lower()

#         # Check for indicators
#         for indicator in paywall_indicators:
#             if indicator in content_lower:
#                 return True

#         # Check for very short content that might be truncated
#         if len(content) < 200 and "read more" in content_lower:
#             return True

#         return False

#     async def _summarize_content(
#         self,
#         content: str,
#         strategy: str = "chain_of_density",
#         word_limit: int = 120,
#         title: str | None = None,
#         url: str | None = None,
#         summarization_prompt: str | None = None,
#     ) -> str:
#         """
#         Summarize content using specified strategy with timeout.

#         Args:
#             content: Content to summarize
#             strategy: Summarization strategy
#             word_limit: Target word count
#             title: Optional article title
#             url: Optional source URL
#             summarization_prompt: Optional prompt to guide the summarization focus

#         Returns:
#             Summary text
#         """
#         # Add timeout to prevent hanging - increase for chain_of_density
#         timeout_seconds = 120 if strategy == "chain_of_density" else 60

#         try:
#             logger.debug(
#                 f"WebFetcher: Starting {strategy} summarization with {timeout_seconds}s timeout"
#             )

#             if strategy == "chain_of_density":
#                 summary_coro = self._chain_of_density_summary(
#                     content, word_limit, title, summarization_prompt
#                 )
#             elif strategy == "bullets":
#                 summary_coro = self._bullet_summary(
#                     content, word_limit, summarization_prompt
#                 )
#             elif strategy == "tldr":
#                 summary_coro = self._tldr_summary(
#                     content, word_limit, summarization_prompt
#                 )
#             else:  # basic
#                 summary_coro = self._basic_summary(
#                     content, word_limit, summarization_prompt
#                 )

#             # Apply timeout
#             summary = await asyncio.wait_for(summary_coro, timeout=timeout_seconds)
#             logger.debug(f"WebFetcher: {strategy} summarization completed successfully")
#             return summary

#         except TimeoutError:
#             logger.error(
#                 f"WebFetcher: {strategy} summarization timed out after {timeout_seconds}s, "
#                 f"falling back to truncation"
#             )
#             # Fallback to simple truncation
#             words = content.split()[:word_limit]
#             return " ".join(words) + "..."
#         except Exception as e:
#             logger.error(f"WebFetcher: Error in {strategy} summarization: {e}")
#             # Fallback to simple truncation
#             words = content.split()[:word_limit]
#             return " ".join(words) + "..."

#     async def _chain_of_density_summary(
#         self,
#         content: str,
#         word_limit: int,
#         title: str | None = None,
#         summarization_prompt: str | None = None,
#     ) -> str:
#         """
#         Create chain of density summary using agent library.

#         This reimplements the chain of density approach natively.
#         """
#         logger.debug(
#             f"WebFetcher: Starting chain_of_density summary "
#             f"(word_limit={word_limit}, title={title})"
#         )

#         # Lazy import to avoid circular dependency
#         from good_agent import Agent

#         # Use async context manager for proper initialization
#         system_prompt = """You are an expert summarizer. Create concise, information-dense summaries.
#         {% if summarization_prompt %}
#         User guidance: {{summarization_prompt}}
#         {% endif %}
#         {% if word_limit %}
#         Always respond with exactly {{word_limit}} words.
#         {% endif %}"""

#         async with Agent(
#             system_prompt,
#             model=self.summarization_model,
#             context={
#                 "word_limit": word_limit,
#                 "summarization_prompt": summarization_prompt,
#             },
#         ) as agent:
#             # Iteratively create denser summaries
#             current_summary = ""

#             # Limit iterations for speed - 2 is enough for good density
#             max_iterations = 2  # Reduced further for speed

#             for iteration in range(max_iterations):
#                 logger.debug(
#                     f"WebFetcher: Chain of density iteration {iteration + 1}/{max_iterations}"
#                 )
#                 if iteration == 0:
#                     try:
#                         logger.debug("WebFetcher: Generating initial summary...")
#                         initial_prompt = """Create a {{word_limit}}-word summary of this content{% if title %} titled "{{title}}"'{% endif %}.
#                         {% if summarization_prompt %}
#                         Focus on: {{summarization_prompt}}
#                         {% endif %}

#                         Content: {{content |truncate(3000, killwords=False)}}

#                         Create an initial summary focusing on the main points in exactly {{word_limit}} words.
#                         {% if summarization_prompt %}
#                         Ensure you address the user's focus area: {{summarization_prompt}}
#                         {% endif %}
#                         Respond with ONLY the summary text, no JSON format needed for this initial summary. Do not include any preamble, explanation, follow-up questions or any other text. The summary should be self-contained and not refer to the original content. It should not appear like a message from an AI assistant (e.g. follow up questions, "If you like I could...")."""

#                         response = await agent.call(
#                             initial_prompt,
#                             context={
#                                 "word_limit": word_limit,
#                                 "title": title,
#                                 "content": content,
#                                 "summarization_prompt": summarization_prompt,
#                             },
#                         )
#                         current_summary = response.content.strip()
#                         logger.debug(
#                             f"WebFetcher: Initial summary generated, "
#                             f"word count: {len(current_summary.split())}"
#                         )
#                     except Exception as e:
#                         logger.error(f"WebFetcher: Error in initial summary: {e}")
#                         # Simple fallback
#                         fallback = f"Summary of content: {content[: word_limit * 6][: word_limit * 7]}"
#                         logger.debug("WebFetcher: Using fallback summary")
#                         return fallback
#                 else:
#                     try:
#                         logger.debug(
#                             f"WebFetcher: Requesting density iteration {iteration}..."
#                         )
#                         iterate_prompt = """Previous summary: {{current_summary}}

#                         Make this summary more information-dense by adding 1-2 important missing details.
#                         {% if summarization_prompt %}
#                         Continue to focus on: {{summarization_prompt}}
#                         {% endif %}
#                         Rewrite in exactly {{word_limit}} words. Be more specific and include key entities.

#                         New summary:"""

#                         response = await agent.call(
#                             iterate_prompt,
#                             context={
#                                 "current_summary": current_summary,
#                                 "word_limit": word_limit,
#                                 "summarization_prompt": summarization_prompt,
#                             },
#                         )
#                         response_text = response.content.strip()
#                         logger.debug(
#                             f"WebFetcher: Got response for iteration {iteration}, "
#                             f"length: {len(response_text)} chars"
#                         )

#                         # Simply use the response as the new summary
#                         word_count = len(response_text.split())
#                         if word_count <= word_limit * 1.3:  # Allow 30% margin
#                             current_summary = response_text
#                             logger.debug(
#                                 f"WebFetcher: Updated summary, word count: {word_count}"
#                             )
#                         else:
#                             logger.debug(
#                                 f"WebFetcher: Response too long ({word_count} words), "
#                                 f"keeping previous summary"
#                             )
#                     except Exception as e:
#                         logger.error(
#                             f"WebFetcher: Error in chain of density iteration {iteration}: {e}"
#                         )
#                         # Continue with current summary
#                         logger.debug(
#                             "WebFetcher: Continuing with current summary after error"
#                         )
#                         pass

#             logger.debug(
#                 f"WebFetcher: Chain of density complete, "
#                 f"final word count: {len(current_summary.split())}"
#             )
#             return current_summary

#     async def _bullet_summary(
#         self, content: str, word_limit: int, summarization_prompt: str | None = None
#     ) -> str:
#         """Create bullet point summary."""
#         from good_agent import Agent

#         async with Agent(
#             "You are an expert at creating concise bullet point summaries.",
#             model=self.summarization_model,
#         ) as agent:
#             prompt = """Create a bullet point summary of this content in approximately {{word_limit}} words total.
#                 {% if summarization_prompt %}
#                 Focus on: {{summarization_prompt}}
#                 {% endif %}
#                 Content: {{content | truncate(3000, killwords=False)}}

#                 Format:
#                 • Key point 1
#                 • Key point 2
#                 • Key point 3
#                 (etc.)"""
#             response = await agent.call(
#                 prompt,
#                 context={
#                     "word_limit": word_limit,
#                     "content": content,
#                     "summarization_prompt": summarization_prompt,
#                 },
#             )
#             return response.content

#     async def _tldr_summary(
#         self, content: str, word_limit: int, summarization_prompt: str | None = None
#     ) -> str:
#         """Create TL;DR summary."""
#         from good_agent import Agent

#         async with Agent(
#             "You are an expert at creating TL;DR summaries.",
#             model=self.summarization_model,
#         ) as agent:
#             #             prompt = f"""Create a TL;DR summary of this content in exactly {word_limit} words.

#             # Content: {content[:3000]}

#             # Start with 'TL;DR:' and provide the essence of the content."""

#             prompt = """Create a TL;DR summary of this content in exactly {{word_limit}} words.
#                 {% if summarization_prompt %}
#                 Focus on: {{summarization_prompt}}
#                 {% endif %}
#                 Content: {{content | truncate(3000, killwords=False)}}
#                 Start with 'TL;DR:' and provide the essence of the content."""
#             response = await agent.call(
#                 prompt,
#                 context={
#                     "word_limit": word_limit,
#                     "content": content,
#                     "summarization_prompt": summarization_prompt,
#                 },
#             )
#             return response.content

#     async def _basic_summary(
#         self, content: str, word_limit: int, summarization_prompt: str | None = None
#     ) -> str:
#         """Create basic summary."""
#         from good_agent import Agent

#         async with Agent(
#             "You are an expert summarizer.", model=self.summarization_model
#         ) as agent:
#             prompt = """Summarize this content in approximately {{word_limit}} words.
#                 {% if summarization_prompt %}
#                 Focus on: {{summarization_prompt}}
#                 {% endif %}
#                 Content: {{content | truncate(3000, killwords=False)}}"""
#             response = await agent.call(
#                 prompt,
#                 context={
#                     "word_limit": word_limit,
#                     "content": content,
#                     "summarization_prompt": summarization_prompt,
#                 },
#             )
#             return str(response)

#     # Component-bound tools

#     @tool(name="fetch")
#     async def fetch(
#         self,
#         url: URL,
#         format: Literal["full", "summary"] | None = None,
#         ttl: int | None = None,
#         validate_content: bool | None = None,
#         strategy: Literal["chain_of_density", "bullets", "tldr", "basic"] | None = None,
#         word_limit: int | None = None,
#         summarization_prompt: str | None = None,
#     ) -> ExtractedContent | WebFetchSummary:
#         """
#         Fetch content from a single URL.

#         Args:
#             url: URL to fetch
#             format: Response format - 'full' (ExtractedContent) or 'summary' (WebFetchSummary)
#             ttl: Cache TTL in seconds (uses component default if None)
#             validate_content: Check for paywalls/errors (uses component default if None)
#             strategy: Summarization strategy (uses component default if None)
#             word_limit: Target word count for summaries (uses component default if None)
#             summarization_prompt: Optional prompt to guide summarization focus (e.g., "focus on financial data", "extract key dates and events")

#         Returns:
#             ExtractedContent for full format, WebFetchSummary for summary format
#         """

#         format = format or self.default_format

#         logger.info(f"WebFetcher: Fetching URL: {url} with format: {format}")

#         responses = await self._fetch_urls(
#             [url],
#             ttl=ttl,
#             validate_content=validate_content,
#             summarize=(format == "summary"),
#             strategy=strategy,
#             word_limit=word_limit,
#             summarization_prompt=summarization_prompt,
#         )

#         if not responses:
#             raise ValueError("No content fetched")

#         response = responses[0]

#         if format == "summary":
#             summary_text = (
#                 response.metadata.get("summary")
#                 or response.main
#                 or "No content available"
#             )
#             return WebFetchSummary(
#                 title=response.title,
#                 url=response.url,
#                 author=response.author,
#                 published_date=response.published_date
#                 if response.published_date
#                 else None,
#                 summary=summary_text,
#             )
#         else:
#             # Return ExtractedContent
#             return response.to(ExtractedContent)

#     @tool(name="fetch_many")
#     async def fetch_many(
#         self,
#         urls: list[URL],
#         format: Literal["full", "summary"] | None = None,
#         ttl: int | None = None,
#         validate_content: bool | None = None,
#         strategy: Literal["chain_of_density", "bullets", "tldr", "basic"] | None = None,
#         word_limit: int | None = None,
#         summarization_prompt: str | None = None,
#     ) -> list[ExtractedContent | WebFetchSummary]:
#         """
#         Fetch content from multiple URLs.

#         Args:
#             urls: List of URLs to fetch
#             format: Response format - 'full' (ExtractedContent) or 'summary' (WebFetchSummary)
#             ttl: Cache TTL in seconds (uses component default if None)
#             validate_content: Check for paywalls/errors (uses component default if None)
#             strategy: Summarization strategy (uses component default if None)
#             word_limit: Target word count for summaries (uses component default if None)
#             summarization_prompt: Optional prompt to guide summarization focus (e.g., "focus on financial data", "extract key dates and events")

#         Returns:
#             List of ExtractedContent for full format, WebFetchSummary for summary format
#         """
#         format = format or self.default_format
#         logger.info(f"WebFetcher: Fetching URL: {urls} with format: {format}")

#         responses = await self._fetch_urls(
#             urls,
#             ttl=ttl,
#             validate_content=validate_content,
#             summarize=(format == "summary"),
#             strategy=strategy,
#             word_limit=word_limit,
#             summarization_prompt=summarization_prompt,
#         )

#         results = []
#         for response in responses:
#             if format == "summary":
#                 summary_text = (
#                     response.metadata.get("summary")
#                     or response.main
#                     or "No content available"
#                 )
#                 results.append(
#                     WebFetchSummary(
#                         title=response.title,
#                         url=response.request.url,
#                         author=response.author,
#                         published_date=response.published_date
#                         if response.published_date
#                         else None,
#                         summary=summary_text,
#                     )
#                 )
#             else:
#                 results.append(response.to(ExtractedContent))

#         return results

#     @tool(name="batch_fetch")
#     async def batch_fetch(
#         self,
#         urls: list[URL],
#         format: Literal["full", "summary"] = "summary",
#         ttl: int | None = None,
#         validate_content: bool | None = None,
#         strategy: Literal["chain_of_density", "bullets", "tldr", "basic"] | None = None,
#         word_limit: int | None = None,
#         summarization_prompt: str | None = None,
#         batch_size: int = 50,
#         progress_interval: int = 25,
#     ) -> str:
#         """
#         Fetch content from multiple URLs and return as concatenated text.

#         This tool solves the 128 tool call limit by returning all fetched content
#         as a single concatenated string with XML citation tags. Perfect for large
#         URL sets from search results.

#         Args:
#             urls: List of URLs to fetch
#             format: Response format - 'full' or 'summary'
#             ttl: Cache TTL in seconds (uses component default if None)
#             validate_content: Check for paywalls/errors (uses component default if None)
#             strategy: Summarization strategy (uses component default if None)
#             word_limit: Target word count for summaries (uses component default if None)
#             summarization_prompt: Optional prompt to guide summarization focus
#             batch_size: Number of URLs to process concurrently
#             progress_interval: How often to log progress updates

#         Returns:
#             Single string with all fetched content, each wrapped in XML citation tags
#         """
#         format = format or self.default_format

#         if not urls:
#             return "No URLs provided for batch fetching."

#         logger.info(
#             f"WebFetcher: Batch fetching {len(urls)} URLs with format: {format}"
#         )

#         responses = await self._fetch_urls(
#             urls,
#             ttl=ttl,
#             validate_content=validate_content,
#             summarize=(format == "summary"),
#             strategy=strategy,
#             word_limit=word_limit,
#             summarization_prompt=summarization_prompt,
#         )

#         # Build concatenated result with XML citations
#         result_parts = []
#         successful_count = 0

#         for response in responses:
#             if format == "summary":
#                 summary_text = (
#                     response.metadata.get("summary")
#                     or response.main
#                     or "No content available"
#                 )

#                 if summary_text and summary_text != "No content available":
#                     summary_obj = WebFetchSummary(
#                         title=response.title,
#                         url=response.url,
#                         author=response.author,
#                         published_date=response.published_date
#                         if response.published_date
#                         else None,
#                         summary=summary_text,
#                     )
#                     result_parts.append(str(summary_obj))
#                     successful_count += 1
#                 else:
#                     # Include failed fetches with error info
#                     error_msg = response.metadata.get("error", "Content unavailable")
#                     result_parts.append(
#                         f'<content url="{response.url}">Error: {error_msg}</content>'
#                     )
#             else:
#                 # Full format - convert to string representation
#                 content = response.to(ExtractedContent)
#                 if content.main:
#                     result_parts.append(
#                         f'<content url="{response.url}">\n{content.main}\n</content>'
#                     )
#                     successful_count += 1
#                 else:
#                     error_msg = response.metadata.get("error", "Content unavailable")
#                     result_parts.append(
#                         f'<content url="{response.url}">Error: {error_msg}</content>'
#                     )

#         # Add summary header
#         total_urls = len(urls)
#         success_rate = (successful_count / total_urls * 100) if total_urls > 0 else 0

#         header = (
#             f"Batch fetch completed: {successful_count}/{total_urls} URLs "
#             f"({success_rate:.1f}% success rate)\n\n"
#         )

#         # Wrap the XML content in markdown code blocks for proper formatting
#         xml_content = "\n\n".join(result_parts)
#         return f"{header}```xml\n{xml_content}\n```"

#     # Utility methods for search-and-fetch workflows

#     def _extract_urls_from_results(self, search_results: list[Any]) -> list[URL]:
#         """
#         Extract unique URLs from various search result formats.

#         Handles:
#         - Objects with .links dict property
#         - Objects with .response.links
#         - Objects with .urls list
#         - Direct URL lists

#         Args:
#             search_results: List of search result objects

#         Returns:
#             List of unique URLs found
#         """
#         all_urls = set()

#         for result in search_results:
#             if result is None:
#                 continue

#             # Try different common patterns
#             urls = None

#             # Pattern 1: .links property (dict of URLs)
#             if hasattr(result, "links") and result.links:
#                 if isinstance(result.links, dict):
#                     urls = list(result.links.values())
#                 elif isinstance(result.links, list):
#                     urls = result.links

#             # Pattern 2: .response.links
#             elif hasattr(result, "response") and result.response:
#                 if hasattr(result.response, "links") and result.response.links:
#                     if isinstance(result.response.links, dict):
#                         urls = list(result.response.links.values())
#                     elif isinstance(result.response.links, list):
#                         urls = result.response.links

#             # Pattern 3: .urls property
#             elif hasattr(result, "urls") and result.urls:
#                 urls = result.urls if isinstance(result.urls, list) else [result.urls]

#             # Pattern 4: Direct URL list
#             elif isinstance(result, (list, tuple)):
#                 urls = result

#             # Add found URLs to set
#             if urls:
#                 for url in urls:
#                     if url:  # Skip None/empty
#                         all_urls.add(URL(url) if not isinstance(url, URL) else url)

#         return list(all_urls)

#     async def fetch_from_search_results(
#         self,
#         search_results: list[Any],
#         format: Literal["full", "summary"] = "summary",
#         strategy: Literal["chain_of_density", "bullets", "tldr", "basic"] = "tldr",
#         word_limit: int = 200,
#         ttl: int | datetime.timedelta = 3600 * 24,
#         concurrency: int = 50,
#         progress_interval: int = 25,
#         use_agent_invoke: bool = False,
#     ) -> SearchFetchResult:
#         """
#         Extract URLs from search results and fetch them concurrently.

#         This utility method simplifies the common pattern of:
#         1. Performing searches that return results with links
#         2. Extracting unique URLs from all search results
#         3. Fetching and summarizing each URL concurrently
#         4. Tracking progress and handling failures

#         Args:
#             search_results: List of objects with .links property or .response.links
#             format: Whether to return full content or summaries
#             strategy: Summarization strategy if format="summary"
#             word_limit: Word limit for summaries
#             ttl: Cache TTL for fetched content
#             concurrency: Maximum concurrent fetch operations
#             progress_interval: Report progress every N successful fetches
#             use_agent_invoke: If True, uses agent.invoke to make tool calls visible in conversation

#         Returns:
#             SearchFetchResult with:
#                 - urls: List of all unique URLs found
#                 - successful: List of successfully fetched URLs
#                 - failed: List of failed URLs
#                 - content: Dict mapping URLs to fetch results
#                 - stats: Statistics about the operation
#         """
#         # Extract unique URLs from search results
#         all_urls = self._extract_urls_from_results(search_results)

#         if not all_urls:
#             return SearchFetchResult(
#                 urls=[],
#                 successful=[],
#                 failed=[],
#                 content={},
#                 stats=FetchStats(total=0, success=0, failed=0, success_rate=0.0),
#             )

#         logger.info(f"Found {len(all_urls)} unique URLs to fetch from search results")

#         # Fetch URLs with progress tracking
#         bulk_results = await self.bulk_fetch_with_progress(
#             urls=all_urls,
#             format=format,
#             strategy=strategy,
#             word_limit=word_limit,
#             ttl=ttl,
#             concurrency=concurrency,
#             progress_interval=progress_interval,
#             use_agent_invoke=use_agent_invoke,
#         )

#         # Convert BulkFetchResult to SearchFetchResult (same structure, different type)
#         return SearchFetchResult(
#             urls=bulk_results.urls,
#             successful=bulk_results.successful,
#             failed=bulk_results.failed,
#             content=bulk_results.content,
#             stats=bulk_results.stats,
#         )

#     async def bulk_fetch_with_progress(
#         self,
#         urls: list[URL],
#         format: Literal["full", "summary"] = "full",
#         strategy: Literal["chain_of_density", "bullets", "tldr", "basic"] = "tldr",
#         word_limit: int = 200,
#         ttl: int | datetime.timedelta = 3600,
#         concurrency: int = 50,
#         progress_interval: int = 25,
#         on_progress: Callable[[int, int, int], None] | None = None,
#         use_agent_invoke: bool = False,
#     ) -> BulkFetchResult:
#         """
#         Fetch multiple URLs concurrently with progress tracking.

#         Uses map_as_completed for streaming results and progress updates.

#         Args:
#             urls: List of URLs to fetch
#             format: Return format (full or summary)
#             strategy: Summarization strategy
#             word_limit: Word limit for summaries
#             ttl: Cache TTL
#             concurrency: Maximum concurrent requests
#             progress_interval: Report progress every N successes
#             on_progress: Optional callback(successful_count, processed_count, total_count)
#             use_agent_invoke: If True, uses agent.invoke to make tool calls visible in conversation

#         Returns:
#             BulkFetchResult with results and statistics
#         """
#         if not urls:
#             return BulkFetchResult(
#                 urls=[],
#                 successful=[],
#                 failed=[],
#                 content={},
#                 stats=FetchStats(total=0, success=0, failed=0, success_rate=0.0),
#             )

#         # Get fetch tool reference - tools are registered as methods on the component
#         fetch_tool = self.fetch
#         if not fetch_tool:
#             raise ValueError("Fetch tool not available")

#         # Track results
#         successful_urls = []
#         failed_urls = []
#         content_map = {}
#         processed_count = 0
#         successful_count = 0

#         if use_agent_invoke and self.agent:
#             # Use batch_fetch tool for large URL sets to avoid 128 tool call limit
#             logger.info(
#                 f"Starting concurrent fetch of {len(urls)} URLs using agent.invoke..."
#             )

#             # Use single batch_fetch tool call instead of multiple individual calls
#             try:
#                 batch_result = await self.agent.tool_calls.invoke(
#                     self.batch_fetch,
#                     urls=urls,
#                     format=format,
#                     strategy=strategy,
#                     word_limit=word_limit,
#                     ttl=ttl,
#                     batch_size=concurrency,
#                     progress_interval=progress_interval,
#                 )

#                 # Parse the batch result to extract statistics and content
#                 batch_content = (
#                     batch_result.response
#                     if hasattr(batch_result, "response")
#                     else str(batch_result)
#                 )

#                 # Extract XML content from markdown code blocks if present
#                 import re

#                 xml_match = re.search(r"```xml\n(.*?)\n```", batch_content, re.DOTALL)
#                 xml_content = xml_match.group(1) if xml_match else batch_content

#                 # Extract statistics from the header
#                 successful_count = 0
#                 processed_count = len(urls)

#                 # Count successful fetches by counting non-error content blocks
#                 content_blocks = re.findall(
#                     r'<content url="[^"]+">.*?</content>', xml_content, re.DOTALL
#                 )
#                 error_blocks = re.findall(r'<content url="[^"]+">Error:', xml_content)
#                 successful_count = len(content_blocks) - len(error_blocks)

#                 # Build results compatible with existing interface
#                 successful_urls = []
#                 failed_urls = []
#                 content_map = {}

#                 # Parse individual content blocks to populate result structure
#                 for url in urls:
#                     url_str = str(url)
#                     # Check if this URL appears in a successful content block
#                     url_pattern = (
#                         rf'<content url="{re.escape(url_str)}">(.*?)</content>'
#                     )
#                     match = re.search(url_pattern, xml_content, re.DOTALL)

#                     if match and not match.group(1).strip().startswith("Error:"):
#                         successful_urls.append(url_str)
#                         content_map[url_str] = match.group(
#                             0
#                         )  # Store the full XML block
#                     else:
#                         failed_urls.append(url_str)

#                 # Store the full batch result in a special key for agent visibility
#                 content_map["__batch_result__"] = batch_content

#             except Exception as e:
#                 logger.error(f"Error in agent batch fetch: {e}")
#                 # Fall back to direct mode
#                 use_agent_invoke = False

#         if not use_agent_invoke:
#             # Original implementation - direct calls without agent visibility
#             # Create wrapper for tool invocation
#             async def fetch_with_metadata(url, **kwargs):
#                 """Wrapper to include URL in result."""
#                 try:
#                     # Call the fetch method directly
#                     result = await fetch_tool(url=url, **kwargs)
#                     return {"url": url, "result": result, "success": True}
#                 except Exception as e:
#                     logger.debug(f"Failed to fetch {url}: {e}")
#                     return {"url": url, "error": str(e), "success": False}

#             # Prepare fetch parameters
#             fetch_kwargs = [
#                 {
#                     "url": url,
#                     "format": format,
#                     "strategy": strategy,
#                     "word_limit": word_limit,
#                     "ttl": ttl,
#                 }
#                 for url in urls
#             ]

#             # Execute concurrent fetches
#             logger.info(f"Starting concurrent fetch of {len(urls)} URLs...")

#             results = await map_as_completed(
#                 fetch_with_metadata,
#                 *fetch_kwargs,
#                 concurrency=concurrency,
#                 return_exceptions=True,
#             )

#             # Process streaming results for direct mode
#             for item in results:
#                 processed_count += 1

#                 if isinstance(item, Exception):
#                     # Handle exceptions
#                     failed_urls.append(None)  # URL unknown from exception
#                     logger.debug(f"Exception during fetch: {item}")
#                     continue

#                 url = item["url"]

#                 if item["success"] and item.get("result"):
#                     result = item["result"]

#                     # Check for valid content based on format
#                     if format == "summary":
#                         # For summary format, result is WebFetchSummary
#                         if hasattr(result, "summary") and result.summary:
#                             summary_text = result.summary
#                             if (
#                                 summary_text
#                                 and "CONTENT UNAVAILABLE" not in summary_text
#                             ):
#                                 successful_count += 1
#                                 successful_urls.append(url)
#                                 # Store the full rendered XML format for citation management
#                                 content_map[str(url)] = str(result)

#                                 # Progress reporting
#                                 if successful_count % progress_interval == 0:
#                                     logger.info(
#                                         f"Progress: {successful_count}/{processed_count}/{len(urls)} "
#                                         f"(successful/processed/total)"
#                                     )
#                                     if on_progress:
#                                         await on_progress(
#                                             successful_count, processed_count, len(urls)
#                                         )
#                             else:
#                                 failed_urls.append(url)
#                                 logger.debug(f"Content unavailable for: {url}")
#                         else:
#                             failed_urls.append(url)
#                             logger.debug(f"No summary available for: {url}")
#                     else:
#                         # For full format, result is ExtractedContent
#                         if hasattr(result, "main") or hasattr(result, "content"):
#                             successful_count += 1
#                             successful_urls.append(url)
#                             content_map[str(url)] = result

#                             # Progress reporting
#                             if successful_count % progress_interval == 0:
#                                 logger.info(
#                                     f"Progress: {successful_count}/{processed_count}/{len(urls)} "
#                                     f"(successful/processed/total)"
#                                 )
#                                 if on_progress:
#                                     await on_progress(
#                                         successful_count, processed_count, len(urls)
#                                     )
#                         else:
#                             failed_urls.append(url)
#                             logger.debug(f"No content available for: {url}")
#                 else:
#                     failed_urls.append(url)
#                     logger.debug(f"Failed to fetch: {url} - {item.get('error')}")

#         # Final statistics
#         success_rate = successful_count / len(urls) if urls else 0.0
#         stats = FetchStats(
#             total=len(urls),
#             success=successful_count,
#             failed=len(failed_urls),
#             success_rate=success_rate,
#         )

#         logger.info(
#             f"Fetch completed: {stats.success}/{stats.total} successful "
#             f"({stats.success_rate:.1%} success rate)"
#         )

#         return BulkFetchResult(
#             urls=[str(url) for url in urls],
#             successful=[str(url) for url in successful_urls],
#             failed=[str(url) for url in failed_urls if url],
#             content=content_map,
#             stats=stats,
#         )

#     async def fetch_and_cache_urls(
#         self,
#         urls: list[URL],
#         ttl: int | datetime.timedelta = 3600 * 24,
#         force_refresh: bool = False,
#     ) -> dict[str, bool]:
#         """
#         Pre-fetch and cache URLs for later use.

#         This is useful for warming the cache before processing.

#         Args:
#             urls: URLs to cache
#             ttl: Cache TTL
#             force_refresh: Force re-fetch even if cached

#         Returns:
#             Dict mapping URLs to success status
#         """
#         cache_status = {}

#         for url in urls:
#             try:
#                 # Use fetch with TTL to populate cache
#                 await self._fetch_urls(
#                     [url],
#                     ttl=ttl,
#                     validate_content=False,  # Just cache, don't validate
#                     summarize=False,
#                 )
#                 cache_status[str(url)] = True
#             except Exception as e:
#                 logger.debug(f"Failed to cache {url}: {e}")
#                 cache_status[str(url)] = False

#         return cache_status
