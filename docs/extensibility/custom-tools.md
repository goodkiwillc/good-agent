# Custom Tools

Good Agent's tool system provides sophisticated capabilities for creating custom tools with advanced error handling, validation, dependency injection, and performance optimization. This guide covers patterns for building production-ready tools.

## Advanced Tool Patterns

### Parameter Validation and Type Safety

Create tools with comprehensive parameter validation using Pydantic models:

```python
from good_agent import tool
from pydantic import BaseModel, Field, ValidationError
from typing import Literal, Optional
from enum import Enum

class SearchFilters(BaseModel):
    """Search filter configuration."""
    
    category: Literal["web", "academic", "news"] = "web"
    date_range: Literal["day", "week", "month", "year"] = "week"
    max_results: int = Field(default=10, ge=1, le=100, description="Max results (1-100)")
    include_images: bool = Field(default=False, description="Include image results")

class SearchResult(BaseModel):
    """Individual search result."""
    
    title: str
    url: str
    snippet: str
    score: float = Field(ge=0.0, le=1.0)
    
class SearchResponse(BaseModel):
    """Complete search response."""
    
    query: str
    results: list[SearchResult]
    total_found: int
    filters_applied: SearchFilters

@tool
async def advanced_search(
    query: str = Field(description="Search query string"),
    filters: SearchFilters = Field(default_factory=SearchFilters),
    api_key: str = Field(description="API key for search service")
) -> SearchResponse:
    """
    Perform advanced search with comprehensive filtering and validation.
    
    Args:
        query: The search query
        filters: Search configuration and filters
        api_key: Authentication key for the search service
        
    Returns:
        Structured search results with metadata
        
    Raises:
        ValueError: If query is empty or invalid
        ConnectionError: If search service is unavailable
    """
    if not query.strip():
        raise ValueError("Search query cannot be empty")
    
    try:
        # Simulate API call with validation
        results = await _perform_search(query, filters, api_key)
        return SearchResponse(
            query=query,
            results=results,
            total_found=len(results),
            filters_applied=filters
        )
    except ValidationError as e:
        raise ValueError(f"Invalid search parameters: {e}")
    except Exception as e:
        raise ConnectionError(f"Search service error: {e}")

async def _perform_search(
    query: str, 
    filters: SearchFilters, 
    api_key: str
) -> list[SearchResult]:
    """Internal search implementation."""
    # Mock implementation
    return [
        SearchResult(
            title=f"Result for '{query}'",
            url="https://example.com",
            snippet="Mock search result snippet",
            score=0.95
        )
    ]
```

### Dependency Injection Patterns

Use dependency injection for clean, testable tool architecture:

--8<-- "src/good_agent/tools/tools.py:70:90"

```python
from good_agent import tool, Depends
from good_agent.tools import ToolContext
import httpx
from typing import Protocol

# Define service interfaces
class DatabaseService(Protocol):
    async def query(self, sql: str) -> list[dict]:
        ...

class CacheService(Protocol):
    async def get(self, key: str) -> Any:
        ...
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        ...

# Service implementations
class PostgreSQLService:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        # Connection setup...
    
    async def query(self, sql: str) -> list[dict]:
        """Execute SQL query and return results."""
        # Implementation details...
        return [{"id": 1, "name": "example"}]

class RedisCache:
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        # Redis connection setup...
    
    async def get(self, key: str) -> Any:
        # Redis get implementation...
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        # Redis set implementation...
        pass

# Dependency providers
def get_database() -> DatabaseService:
    """Provide database service instance."""
    return PostgreSQLService("postgresql://localhost/mydb")

def get_cache() -> CacheService:
    """Provide cache service instance."""
    return RedisCache("redis://localhost:6379")

def get_http_client() -> httpx.AsyncClient:
    """Provide HTTP client instance."""
    return httpx.AsyncClient(timeout=30.0)

# Tools with dependency injection
@tool
async def fetch_user_data(
    user_id: int,
    db: DatabaseService = Depends(get_database),
    cache: CacheService = Depends(get_cache),
    ctx: ToolContext = Depends()
) -> dict:
    """
    Fetch user data with caching and database fallback.
    
    This tool demonstrates:
    - Service dependency injection
    - Agent context access via ToolContext
    - Caching patterns
    - Error handling
    """
    cache_key = f"user:{user_id}"
    
    # Try cache first
    cached_data = await cache.get(cache_key)
    if cached_data:
        ctx.agent.logger.info(f"Cache hit for user {user_id}")
        return cached_data
    
    # Fallback to database
    try:
        result = await db.query(f"SELECT * FROM users WHERE id = {user_id}")
        if not result:
            return {"error": f"User {user_id} not found"}
        
        user_data = result[0]
        
        # Cache the result
        await cache.set(cache_key, user_data, ttl=3600)
        
        ctx.agent.logger.info(f"Database hit for user {user_id}")
        return user_data
        
    except Exception as e:
        ctx.agent.logger.error(f"Error fetching user {user_id}: {e}")
        return {"error": "Database error occurred"}

@tool
async def external_api_call(
    endpoint: str,
    method: Literal["GET", "POST", "PUT", "DELETE"] = "GET",
    payload: Optional[dict] = None,
    http_client: httpx.AsyncClient = Depends(get_http_client),
    ctx: ToolContext = Depends()
) -> dict:
    """
    Make external API calls with proper error handling and logging.
    
    Args:
        endpoint: API endpoint URL
        method: HTTP method
        payload: Request payload for POST/PUT requests
        http_client: Injected HTTP client
        ctx: Tool context for agent access
        
    Returns:
        API response data or error information
    """
    try:
        # Log the request
        ctx.agent.logger.info(f"Making {method} request to {endpoint}")
        
        # Make the request
        if method == "GET":
            response = await http_client.get(endpoint)
        elif method == "POST":
            response = await http_client.post(endpoint, json=payload)
        elif method == "PUT":
            response = await http_client.put(endpoint, json=payload)
        elif method == "DELETE":
            response = await http_client.delete(endpoint)
        
        response.raise_for_status()
        
        # Parse and return response
        data = response.json()
        ctx.agent.logger.info(f"API call successful: {response.status_code}")
        return data
        
    except httpx.TimeoutException:
        error_msg = f"Timeout calling {endpoint}"
        ctx.agent.logger.error(error_msg)
        return {"error": error_msg}
        
    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP {e.response.status_code} from {endpoint}"
        ctx.agent.logger.error(error_msg)
        return {"error": error_msg, "status_code": e.response.status_code}
        
    except Exception as e:
        error_msg = f"Unexpected error calling {endpoint}: {e}"
        ctx.agent.logger.error(error_msg)
        return {"error": error_msg}
```

### Tool Composition and Chaining

Build complex workflows by composing simpler tools:

```python
from typing import AsyncIterator
import asyncio

class WorkflowContext:
    """Context for tool workflows."""
    
    def __init__(self):
        self.steps: list[dict] = []
        self.intermediate_data: dict[str, Any] = {}
    
    def log_step(self, step_name: str, input_data: Any, output_data: Any):
        """Log a workflow step."""
        self.steps.append({
            "step": step_name,
            "input": input_data,
            "output": output_data,
            "timestamp": asyncio.get_event_loop().time()
        })

@tool
async def extract_entities(
    text: str,
    entity_types: list[str] = ["PERSON", "ORGANIZATION", "LOCATION"]
) -> dict:
    """Extract named entities from text."""
    # Mock NLP processing
    entities = {
        "PERSON": ["John Doe", "Jane Smith"],
        "ORGANIZATION": ["OpenAI", "Google"],
        "LOCATION": ["New York", "California"]
    }
    
    return {
        "entities": {etype: entities.get(etype, []) for etype in entity_types},
        "confidence": 0.85
    }

@tool
async def enrich_entities(
    entities: dict,
    enrichment_sources: list[str] = ["wikipedia", "wikidata"]
) -> dict:
    """Enrich entities with additional information."""
    enriched = {}
    
    for entity_type, entity_list in entities.get("entities", {}).items():
        enriched[entity_type] = []
        for entity in entity_list:
            # Mock enrichment
            enriched[entity_type].append({
                "name": entity,
                "description": f"Information about {entity}",
                "sources": enrichment_sources,
                "confidence": 0.9
            })
    
    return {"enriched_entities": enriched}

@tool
async def analyze_sentiment(text: str) -> dict:
    """Analyze sentiment of text."""
    # Mock sentiment analysis
    return {
        "sentiment": "positive",
        "confidence": 0.82,
        "scores": {"positive": 0.82, "negative": 0.15, "neutral": 0.03}
    }

@tool
async def process_document_workflow(
    text: str,
    include_entities: bool = True,
    include_sentiment: bool = True,
    enrich_data: bool = True,
    ctx: ToolContext = Depends()
) -> dict:
    """
    Complete document processing workflow combining multiple tools.
    
    Args:
        text: Document text to process
        include_entities: Whether to extract entities
        include_sentiment: Whether to analyze sentiment
        enrich_data: Whether to enrich extracted entities
        ctx: Tool context for accessing other tools
        
    Returns:
        Complete document analysis results
    """
    workflow_ctx = WorkflowContext()
    results = {"original_text": text, "processing_steps": []}
    
    try:
        # Step 1: Sentiment Analysis
        if include_sentiment:
            sentiment_result = await ctx.agent.tools["analyze_sentiment"](
                _agent=ctx.agent, text=text
            )
            if sentiment_result.success:
                results["sentiment"] = sentiment_result.response
                workflow_ctx.log_step("sentiment_analysis", text, sentiment_result.response)
            else:
                results["sentiment"] = {"error": sentiment_result.error}
        
        # Step 2: Entity Extraction
        entities_result = None
        if include_entities:
            entities_result = await ctx.agent.tools["extract_entities"](
                _agent=ctx.agent, text=text
            )
            if entities_result.success:
                results["entities"] = entities_result.response
                workflow_ctx.log_step("entity_extraction", text, entities_result.response)
            else:
                results["entities"] = {"error": entities_result.error}
        
        # Step 3: Entity Enrichment (if entities were extracted)
        if enrich_data and entities_result and entities_result.success:
            enrichment_result = await ctx.agent.tools["enrich_entities"](
                _agent=ctx.agent, entities=entities_result.response
            )
            if enrichment_result.success:
                results["enriched_entities"] = enrichment_result.response
                workflow_ctx.log_step("entity_enrichment", entities_result.response, enrichment_result.response)
            else:
                results["enriched_entities"] = {"error": enrichment_result.error}
        
        # Add workflow metadata
        results["workflow_metadata"] = {
            "steps_completed": len(workflow_ctx.steps),
            "processing_order": [step["step"] for step in workflow_ctx.steps],
            "total_processing_time": sum(
                workflow_ctx.steps[i+1]["timestamp"] - workflow_ctx.steps[i]["timestamp"]
                for i in range(len(workflow_ctx.steps) - 1)
            ) if len(workflow_ctx.steps) > 1 else 0
        }
        
        return results
        
    except Exception as e:
        ctx.agent.logger.error(f"Workflow error: {e}")
        return {
            "error": f"Workflow failed: {e}",
            "partial_results": results,
            "failed_at_step": len(workflow_ctx.steps)
        }
```

### Stream Processing Tools

Create tools that handle streaming data and real-time processing:

```python
from typing import AsyncIterator
import asyncio

@tool
async def stream_processor(
    data_source: str,
    batch_size: int = 10,
    processing_delay: float = 0.1,
    ctx: ToolContext = Depends()
) -> AsyncIterator[dict]:
    """
    Process streaming data in batches.
    
    This tool demonstrates:
    - Streaming/generator patterns
    - Batch processing
    - Real-time data handling
    - Progress reporting
    
    Args:
        data_source: Source identifier for data stream
        batch_size: Number of items to process per batch
        processing_delay: Delay between batches (seconds)
        ctx: Tool context
        
    Yields:
        Processing results for each batch
    """
    try:
        # Simulate data stream
        total_items = 100  # Mock total
        processed = 0
        
        while processed < total_items:
            # Simulate batch processing
            batch_end = min(processed + batch_size, total_items)
            batch_items = list(range(processed, batch_end))
            
            # Process batch
            batch_results = []
            for item in batch_items:
                # Mock processing
                result = {
                    "item_id": item,
                    "processed_at": asyncio.get_event_loop().time(),
                    "status": "success",
                    "data": f"processed_item_{item}"
                }
                batch_results.append(result)
            
            # Yield batch results
            yield {
                "batch_number": processed // batch_size + 1,
                "items_processed": len(batch_results),
                "results": batch_results,
                "progress": {
                    "completed": batch_end,
                    "total": total_items,
                    "percentage": (batch_end / total_items) * 100
                }
            }
            
            processed = batch_end
            
            # Simulate processing delay
            if processing_delay > 0:
                await asyncio.sleep(processing_delay)
        
        # Final summary
        yield {
            "status": "completed",
            "total_processed": processed,
            "summary": f"Successfully processed {processed} items from {data_source}"
        }
        
    except Exception as e:
        ctx.agent.logger.error(f"Stream processing error: {e}")
        yield {
            "status": "error",
            "error": str(e),
            "items_processed": processed
        }

@tool
async def real_time_monitor(
    metric_name: str,
    duration_seconds: int = 60,
    sample_interval: float = 1.0,
    ctx: ToolContext = Depends()
) -> AsyncIterator[dict]:
    """
    Monitor a metric in real-time for a specified duration.
    
    Args:
        metric_name: Name of the metric to monitor
        duration_seconds: How long to monitor (seconds)
        sample_interval: Time between samples (seconds)
        ctx: Tool context
        
    Yields:
        Real-time metric samples
    """
    start_time = asyncio.get_event_loop().time()
    end_time = start_time + duration_seconds
    sample_count = 0
    
    ctx.agent.logger.info(f"Starting real-time monitoring of {metric_name}")
    
    try:
        while asyncio.get_event_loop().time() < end_time:
            current_time = asyncio.get_event_loop().time()
            sample_count += 1
            
            # Mock metric collection
            import random
            metric_value = random.uniform(0, 100)
            trend = "stable"
            if sample_count > 1:
                trend = "increasing" if metric_value > 50 else "decreasing"
            
            sample = {
                "metric": metric_name,
                "value": metric_value,
                "timestamp": current_time,
                "sample_number": sample_count,
                "trend": trend,
                "elapsed_time": current_time - start_time
            }
            
            yield sample
            
            # Wait for next sample
            await asyncio.sleep(sample_interval)
        
        # Monitoring complete
        yield {
            "status": "monitoring_complete",
            "metric": metric_name,
            "total_samples": sample_count,
            "duration": duration_seconds
        }
        
    except Exception as e:
        ctx.agent.logger.error(f"Monitoring error: {e}")
        yield {
            "status": "monitoring_error",
            "error": str(e),
            "samples_collected": sample_count
        }
```

## Error Handling and Resilience

### Comprehensive Error Handling

Implement robust error handling with custom exceptions and recovery strategies:

```python
from typing import Optional, Type
from enum import Enum
import traceback

class ToolErrorType(Enum):
    """Categories of tool errors."""
    
    VALIDATION_ERROR = "validation_error"
    CONNECTION_ERROR = "connection_error"
    TIMEOUT_ERROR = "timeout_error"
    AUTHENTICATION_ERROR = "authentication_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    RESOURCE_NOT_FOUND = "resource_not_found"
    INTERNAL_ERROR = "internal_error"

class ToolError(Exception):
    """Base exception for tool errors."""
    
    def __init__(
        self, 
        message: str, 
        error_type: ToolErrorType,
        recoverable: bool = False,
        retry_after: Optional[int] = None,
        context: Optional[dict] = None
    ):
        super().__init__(message)
        self.error_type = error_type
        self.recoverable = recoverable
        self.retry_after = retry_after
        self.context = context or {}

class ValidationError(ToolError):
    """Error for invalid input parameters."""
    
    def __init__(self, message: str, field: Optional[str] = None, value: Any = None):
        super().__init__(
            message, 
            ToolErrorType.VALIDATION_ERROR,
            recoverable=True
        )
        self.field = field
        self.value = value

class RetryableError(ToolError):
    """Error that can be retried."""
    
    def __init__(self, message: str, error_type: ToolErrorType, retry_after: int = 1):
        super().__init__(
            message, 
            error_type, 
            recoverable=True, 
            retry_after=retry_after
        )

def handle_tool_errors(func):
    """Decorator for comprehensive tool error handling."""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ToolError:
            # Re-raise tool errors as-is
            raise
        except ValidationError as e:
            raise ValidationError(str(e))
        except ConnectionError as e:
            raise RetryableError(
                f"Connection failed: {e}",
                ToolErrorType.CONNECTION_ERROR,
                retry_after=5
            )
        except TimeoutError as e:
            raise RetryableError(
                f"Operation timed out: {e}",
                ToolErrorType.TIMEOUT_ERROR,
                retry_after=10
            )
        except Exception as e:
            # Catch-all for unexpected errors
            raise ToolError(
                f"Unexpected error: {e}",
                ToolErrorType.INTERNAL_ERROR,
                context={"traceback": traceback.format_exc()}
            )
    
    return wrapper

@tool
@handle_tool_errors
async def robust_api_tool(
    endpoint: str,
    api_key: str,
    timeout: int = 30,
    max_retries: int = 3,
    ctx: ToolContext = Depends()
) -> dict:
    """
    API tool with comprehensive error handling and retry logic.
    
    Args:
        endpoint: API endpoint URL
        api_key: Authentication key
        timeout: Request timeout in seconds
        max_retries: Maximum retry attempts
        ctx: Tool context
        
    Returns:
        API response data
        
    Raises:
        ValidationError: For invalid parameters
        RetryableError: For transient failures
        ToolError: For other errors
    """
    # Parameter validation
    if not endpoint.startswith(('http://', 'https://')):
        raise ValidationError(
            "Invalid endpoint URL", 
            field="endpoint", 
            value=endpoint
        )
    
    if not api_key or len(api_key) < 10:
        raise ValidationError(
            "API key must be at least 10 characters",
            field="api_key"
        )
    
    # Retry logic with exponential backoff
    for attempt in range(max_retries + 1):
        try:
            ctx.agent.logger.info(f"API call attempt {attempt + 1}/{max_retries + 1}")
            
            # Simulate API call
            import httpx
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    endpoint,
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                
                if response.status_code == 401:
                    raise ToolError(
                        "Authentication failed",
                        ToolErrorType.AUTHENTICATION_ERROR
                    )
                elif response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    raise RetryableError(
                        "Rate limit exceeded",
                        ToolErrorType.RATE_LIMIT_ERROR,
                        retry_after=retry_after
                    )
                elif response.status_code == 404:
                    raise ToolError(
                        f"Resource not found: {endpoint}",
                        ToolErrorType.RESOURCE_NOT_FOUND
                    )
                
                response.raise_for_status()
                return response.json()
                
        except RetryableError as e:
            if attempt < max_retries:
                wait_time = min(2 ** attempt, e.retry_after or 1)
                ctx.agent.logger.warning(
                    f"Retryable error on attempt {attempt + 1}: {e}. "
                    f"Retrying in {wait_time}s"
                )
                await asyncio.sleep(wait_time)
                continue
            else:
                ctx.agent.logger.error(f"Max retries exceeded: {e}")
                raise
        except ToolError:
            # Don't retry non-retryable errors
            raise
    
    # This should never be reached
    raise ToolError(
        "Unexpected retry loop exit",
        ToolErrorType.INTERNAL_ERROR
    )
```

### Circuit Breaker Pattern

Implement circuit breaker for failing external services:

```python
from typing import Callable, Any
import time
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Blocking requests
    HALF_OPEN = "half_open"  # Testing recovery

class CircuitBreaker:
    """Circuit breaker for external service calls."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                raise ToolError(
                    "Circuit breaker is OPEN - service unavailable",
                    ToolErrorType.CONNECTION_ERROR,
                    retry_after=self.recovery_timeout
                )
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        return (
            self.last_failure_time and
            time.time() - self.last_failure_time >= self.recovery_timeout
        )
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

# Global circuit breakers for different services
_circuit_breakers: dict[str, CircuitBreaker] = {}

def get_circuit_breaker(service_name: str) -> CircuitBreaker:
    """Get or create circuit breaker for a service."""
    if service_name not in _circuit_breakers:
        _circuit_breakers[service_name] = CircuitBreaker()
    return _circuit_breakers[service_name]

@tool
async def external_service_tool(
    service_url: str,
    service_name: str = "default",
    ctx: ToolContext = Depends()
) -> dict:
    """
    Tool with circuit breaker protection for external services.
    
    Args:
        service_url: External service URL
        service_name: Service identifier for circuit breaker
        ctx: Tool context
        
    Returns:
        Service response or error information
    """
    circuit_breaker = get_circuit_breaker(service_name)
    
    async def make_request():
        """Internal function to make the actual request."""
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(service_url)
            response.raise_for_status()
            return response.json()
    
    try:
        result = await circuit_breaker.call(make_request)
        ctx.agent.logger.info(f"Service call successful: {service_name}")
        return result
        
    except ToolError:
        # Circuit breaker errors - already formatted
        raise
    except Exception as e:
        ctx.agent.logger.error(f"Service call failed: {service_name} - {e}")
        raise ToolError(
            f"Service {service_name} unavailable",
            ToolErrorType.CONNECTION_ERROR,
            recoverable=True
        )
```

## Tool Adapters and Middleware

### Custom Tool Adapters

Create sophisticated tool adapters for transparent functionality enhancement:

--8<-- "src/good_agent/components/tool_adapter.py:37:70"

```python
from good_agent.components import ToolAdapter
import json
import hashlib

class CachingAdapter(ToolAdapter):
    """Adapter that adds caching to tools."""
    
    def __init__(self, component, cache_ttl: int = 3600):
        super().__init__(component)
        self.cache_ttl = cache_ttl
        self.cache = {}  # Simple in-memory cache
    
    def should_adapt(self, tool_name: str, agent: Agent) -> bool:
        """Cache tools that have 'cacheable' in their metadata."""
        tool = agent.tools.get(tool_name)
        return tool and getattr(tool, 'cacheable', False)
    
    def _generate_cache_key(self, tool_name: str, parameters: dict) -> str:
        """Generate cache key from tool name and parameters."""
        cache_data = {"tool": tool_name, "params": parameters}
        cache_json = json.dumps(cache_data, sort_keys=True)
        return hashlib.md5(cache_json.encode()).hexdigest()
    
    async def adapt_parameters(
        self, 
        tool_name: str, 
        parameters: dict, 
        agent: Agent
    ) -> dict:
        """Check cache before tool execution."""
        cache_key = self._generate_cache_key(tool_name, parameters)
        
        if cache_key in self.cache:
            cached_result, timestamp = self.cache[cache_key]
            
            # Check if cache is still valid
            if time.time() - timestamp < self.cache_ttl:
                agent.logger.info(f"Cache hit for {tool_name}")
                # Return special parameter to indicate cache hit
                return {**parameters, "_cached_result": cached_result}
        
        return parameters
    
    async def adapt_response(
        self, 
        tool_name: str, 
        response: ToolResponse, 
        agent: Agent
    ) -> ToolResponse:
        """Cache successful responses."""
        if response.success and not hasattr(response, '_cached_result'):
            # Generate cache key from original parameters
            original_params = response.tool_call.parameters if response.tool_call else {}
            cache_key = self._generate_cache_key(tool_name, original_params)
            
            # Cache the response
            self.cache[cache_key] = (response.response, time.time())
            agent.logger.info(f"Cached result for {tool_name}")
        
        return response

class AuthenticationAdapter(ToolAdapter):
    """Adapter that adds authentication to tools."""
    
    def __init__(self, component, auth_provider: Callable[[], str]):
        super().__init__(component)
        self.auth_provider = auth_provider
    
    def should_adapt(self, tool_name: str, agent: Agent) -> bool:
        """Adapt tools that require authentication."""
        tool = agent.tools.get(tool_name)
        return tool and getattr(tool, 'requires_auth', False)
    
    def adapt_signature(
        self, 
        tool: Tool, 
        signature: ToolSignature, 
        agent: Agent
    ) -> ToolSignature:
        """Add auth_token parameter to tool signature."""
        adapted = copy.deepcopy(signature)
        properties = adapted["function"]["parameters"]["properties"]
        
        # Add auth_token parameter (hidden from LLM)
        properties["auth_token"] = {
            "type": "string",
            "description": "Authentication token",
            "x-hidden": True  # Custom field to mark as hidden
        }
        
        return adapted
    
    async def adapt_parameters(
        self, 
        tool_name: str, 
        parameters: dict, 
        agent: Agent
    ) -> dict:
        """Inject authentication token."""
        try:
            auth_token = self.auth_provider()
            return {**parameters, "auth_token": auth_token}
        except Exception as e:
            agent.logger.error(f"Authentication failed: {e}")
            raise ToolError(
                "Authentication required but failed",
                ToolErrorType.AUTHENTICATION_ERROR
            )

class MetricsAdapter(ToolAdapter):
    """Adapter that collects metrics for tool usage."""
    
    def __init__(self, component):
        super().__init__(component)
        self.metrics = {
            "call_count": {},
            "success_count": {},
            "error_count": {},
            "execution_time": {}
        }
    
    def should_adapt(self, tool_name: str, agent: Agent) -> bool:
        """Collect metrics for all tools."""
        return True
    
    async def adapt_parameters(
        self, 
        tool_name: str, 
        parameters: dict, 
        agent: Agent
    ) -> dict:
        """Record call start time."""
        # Initialize metrics for this tool
        if tool_name not in self.metrics["call_count"]:
            for metric in self.metrics:
                self.metrics[metric][tool_name] = 0 if metric != "execution_time" else []
        
        # Increment call count
        self.metrics["call_count"][tool_name] += 1
        
        # Add start time for execution time calculation
        return {**parameters, "_start_time": time.time()}
    
    async def adapt_response(
        self, 
        tool_name: str, 
        response: ToolResponse, 
        agent: Agent
    ) -> ToolResponse:
        """Record response metrics."""
        # Calculate execution time
        start_time = getattr(response, '_start_time', None)
        if start_time:
            execution_time = time.time() - start_time
            self.metrics["execution_time"][tool_name].append(execution_time)
        
        # Record success/error
        if response.success:
            self.metrics["success_count"][tool_name] += 1
        else:
            self.metrics["error_count"][tool_name] += 1
        
        # Log metrics periodically
        if self.metrics["call_count"][tool_name] % 10 == 0:
            self._log_metrics(tool_name, agent)
        
        return response
    
    def _log_metrics(self, tool_name: str, agent: Agent):
        """Log current metrics for a tool."""
        calls = self.metrics["call_count"][tool_name]
        success = self.metrics["success_count"][tool_name]
        errors = self.metrics["error_count"][tool_name]
        exec_times = self.metrics["execution_time"][tool_name]
        
        avg_time = sum(exec_times) / len(exec_times) if exec_times else 0
        success_rate = (success / calls) * 100 if calls > 0 else 0
        
        agent.logger.info(
            f"Tool {tool_name} metrics: "
            f"calls={calls}, success_rate={success_rate:.1f}%, "
            f"avg_time={avg_time:.3f}s"
        )
    
    def get_metrics_summary(self) -> dict:
        """Get comprehensive metrics summary."""
        summary = {}
        
        for tool_name in self.metrics["call_count"]:
            calls = self.metrics["call_count"][tool_name]
            success = self.metrics["success_count"][tool_name]
            errors = self.metrics["error_count"][tool_name]
            exec_times = self.metrics["execution_time"][tool_name]
            
            summary[tool_name] = {
                "total_calls": calls,
                "successful_calls": success,
                "failed_calls": errors,
                "success_rate": (success / calls) * 100 if calls > 0 else 0,
                "average_execution_time": sum(exec_times) / len(exec_times) if exec_times else 0,
                "min_execution_time": min(exec_times) if exec_times else 0,
                "max_execution_time": max(exec_times) if exec_times else 0
            }
        
        return summary

# Usage example with adapters
class EnhancedToolComponent(AgentComponent):
    """Component with multiple tool adapters."""
    
    def __init__(self):
        super().__init__()
        
        # Register adapters
        self.register_tool_adapter(CachingAdapter(self))
        self.register_tool_adapter(AuthenticationAdapter(self, self._get_auth_token))
        self.register_tool_adapter(MetricsAdapter(self))
    
    def _get_auth_token(self) -> str:
        """Get authentication token."""
        return "mock_auth_token_12345"
    
    @tool(cacheable=True, requires_auth=True)
    async def enhanced_api_call(
        self, 
        endpoint: str,
        auth_token: str = "",  # Will be injected by adapter
    ) -> dict:
        """API call with caching and authentication."""
        # Tool implementation...
        return {"endpoint": endpoint, "authenticated": bool(auth_token)}
    
    def get_tool_metrics(self) -> dict:
        """Get metrics from the metrics adapter."""
        for adapter in self._tool_adapter_registry._adapters:
            if isinstance(adapter, MetricsAdapter):
                return adapter.get_metrics_summary()
        return {}
```

## Testing Custom Tools

### Unit Testing Tools

```python
import pytest
from unittest.mock import Mock, AsyncMock, patch
from good_agent import Agent
from good_agent.tools import ToolContext, ToolResponse

class TestCustomTools:
    """Comprehensive tool testing examples."""
    
    @pytest.mark.asyncio
    async def test_tool_with_validation(self):
        """Test tool parameter validation."""
        
        @tool
        async def validated_tool(
            value: int = Field(ge=1, le=100),
            name: str = Field(min_length=1)
        ) -> str:
            return f"Processed {name}: {value}"
        
        # Test valid parameters
        result = await validated_tool(_agent=Mock(), value=50, name="test")
        assert result.success
        assert "test: 50" in result.response
        
        # Test invalid parameters should raise validation error
        with pytest.raises(Exception):  # Pydantic will raise validation error
            await validated_tool(_agent=Mock(), value=150, name="test")
    
    @pytest.mark.asyncio
    async def test_tool_with_dependencies(self):
        """Test tool with dependency injection."""
        
        # Mock dependencies
        mock_db = Mock()
        mock_db.query = AsyncMock(return_value=[{"id": 1, "name": "test"}])
        
        mock_cache = Mock()
        mock_cache.get = AsyncMock(return_value=None)  # Cache miss
        mock_cache.set = AsyncMock()
        
        @tool
        async def db_tool(
            query: str,
            db: DatabaseService = Depends(lambda: mock_db),
            cache: CacheService = Depends(lambda: mock_cache)
        ) -> dict:
            """Tool with database and cache dependencies."""
            
            # Check cache first
            cached = await cache.get(f"query:{query}")
            if cached:
                return cached
            
            # Query database
            result = await db.query(query)
            
            # Cache result
            await cache.set(f"query:{query}", result)
            
            return {"results": result}
        
        # Test tool execution
        result = await db_tool(_agent=Mock(), query="SELECT * FROM users")
        
        assert result.success
        assert "results" in result.response
        
        # Verify dependencies were called
        mock_db.query.assert_called_once_with("SELECT * FROM users")
        mock_cache.get.assert_called_once()
        mock_cache.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_tool_error_handling(self):
        """Test comprehensive error handling."""
        
        @tool
        async def error_prone_tool(
            operation: Literal["success", "validation_error", "connection_error", "unknown_error"]
        ) -> str:
            """Tool that can produce different types of errors."""
            
            if operation == "success":
                return "Operation successful"
            elif operation == "validation_error":
                raise ValidationError("Invalid operation parameter")
            elif operation == "connection_error":
                raise RetryableError("Connection failed", ToolErrorType.CONNECTION_ERROR)
            elif operation == "unknown_error":
                raise Exception("Unexpected error occurred")
            
            return "Should not reach here"
        
        # Test successful operation
        result = await error_prone_tool(_agent=Mock(), operation="success")
        assert result.success
        assert result.response == "Operation successful"
        
        # Test validation error
        result = await error_prone_tool(_agent=Mock(), operation="validation_error")
        assert not result.success
        assert "Invalid operation parameter" in result.error
        
        # Test connection error
        result = await error_prone_tool(_agent=Mock(), operation="connection_error")
        assert not result.success
        assert "Connection failed" in result.error
        
        # Test unknown error
        result = await error_prone_tool(_agent=Mock(), operation="unknown_error")
        assert not result.success
        assert "Unexpected error" in result.error
    
    @pytest.mark.asyncio
    async def test_tool_with_agent_context(self):
        """Test tool that uses agent context."""
        
        @tool
        async def context_aware_tool(
            message: str,
            ctx: ToolContext = Depends()
        ) -> dict:
            """Tool that accesses agent context."""
            
            # Access agent properties
            agent_name = getattr(ctx.agent, 'name', 'unknown')
            message_count = len(ctx.agent.messages) if hasattr(ctx.agent, 'messages') else 0
            
            return {
                "message": message,
                "agent_name": agent_name,
                "message_count": message_count,
                "context_available": ctx.agent is not None
            }
        
        # Create mock agent with context
        mock_agent = Mock()
        mock_agent.name = "test_agent"
        mock_agent.messages = ["msg1", "msg2", "msg3"]
        
        result = await context_aware_tool(_agent=mock_agent, message="test")
        
        assert result.success
        response = result.response
        assert response["message"] == "test"
        assert response["agent_name"] == "test_agent"
        assert response["message_count"] == 3
        assert response["context_available"] is True
    
    @pytest.mark.asyncio
    async def test_tool_performance(self):
        """Test tool performance and timeout handling."""
        
        @tool
        async def slow_tool(delay: float = 1.0) -> str:
            """Tool that takes time to execute."""
            await asyncio.sleep(delay)
            return f"Completed after {delay}s"
        
        # Test normal execution
        start_time = time.time()
        result = await slow_tool(_agent=Mock(), delay=0.1)
        execution_time = time.time() - start_time
        
        assert result.success
        assert execution_time < 0.2  # Should complete quickly
        
        # Test timeout (if implemented in tool framework)
        # This would depend on your tool execution framework
    
    def test_tool_signature_generation(self):
        """Test that tool signatures are generated correctly."""
        
        @tool
        def signature_test_tool(
            required_param: str,
            optional_param: int = 42,
            hidden_param: str = Field(default="secret", description="Hidden parameter")
        ) -> str:
            """Tool for testing signature generation."""
            return f"{required_param}-{optional_param}-{hidden_param}"
        
        # Get tool signature
        signature = signature_test_tool.signature
        
        assert signature["type"] == "function"
        assert signature["function"]["name"] == "signature_test_tool"
        assert signature["function"]["description"] == "Tool for testing signature generation."
        
        properties = signature["function"]["parameters"]["properties"]
        assert "required_param" in properties
        assert "optional_param" in properties
        assert "hidden_param" in properties
        
        # Check parameter details
        assert properties["required_param"]["type"] == "string"
        assert properties["optional_param"]["type"] == "integer"
        assert properties["optional_param"]["default"] == 42

@pytest.mark.asyncio
async def test_tool_integration_with_agent():
    """Test tool integration within agent context."""
    
    @tool
    async def integration_test_tool(message: str) -> str:
        """Tool for integration testing."""
        return f"Processed: {message}"
    
    # Create agent with tool
    agent = Agent("Test agent", tools=[integration_test_tool])
    await agent.initialize()
    
    # Verify tool is registered
    assert "integration_test_tool" in agent.tools
    
    # Test tool execution through agent
    tool_instance = agent.tools["integration_test_tool"]
    result = await tool_instance(_agent=agent, message="test message")
    
    assert result.success
    assert result.response == "Processed: test message"
```

### Integration Testing

```python
import pytest
from good_agent import Agent
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_full_tool_workflow():
    """Test complete tool workflow with real agent."""
    
    # Create tools for workflow
    @tool
    async def step_one(input_data: str) -> dict:
        """First step in workflow."""
        return {"step": 1, "data": f"step1_{input_data}"}
    
    @tool
    async def step_two(previous_result: dict) -> dict:
        """Second step in workflow."""
        return {
            "step": 2, 
            "data": f"step2_{previous_result['data']}",
            "previous": previous_result
        }
    
    @tool
    async def workflow_coordinator(
        input_data: str,
        ctx: ToolContext = Depends()
    ) -> dict:
        """Coordinate multi-step workflow."""
        
        # Execute step one
        step1_result = await ctx.agent.tools["step_one"](_agent=ctx.agent, input_data=input_data)
        if not step1_result.success:
            return {"error": f"Step 1 failed: {step1_result.error}"}
        
        # Execute step two
        step2_result = await ctx.agent.tools["step_two"](_agent=ctx.agent, previous_result=step1_result.response)
        if not step2_result.success:
            return {"error": f"Step 2 failed: {step2_result.error}"}
        
        return {
            "workflow_complete": True,
            "final_result": step2_result.response,
            "steps_executed": 2
        }
    
    # Create agent with all tools
    agent = Agent(
        "Workflow agent",
        tools=[step_one, step_two, workflow_coordinator]
    )
    await agent.initialize()
    
    # Execute workflow
    result = await agent.tools["workflow_coordinator"](_agent=agent, input_data="test")
    
    assert result.success
    response = result.response
    assert response["workflow_complete"] is True
    assert response["steps_executed"] == 2
    assert "step1_test" in response["final_result"]["data"]
    assert "step2" in response["final_result"]["data"]

@pytest.mark.asyncio  
async def test_tool_adapter_integration():
    """Test tool adapters in integration scenario."""
    
    # Mock external service
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = AsyncMock()
        mock_response.json.return_value = {"api_data": "test_response"}
        mock_response.raise_for_status.return_value = None
        mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
        
        # Create component with adapters
        component = EnhancedToolComponent()
        
        # Create agent
        agent = Agent("Test agent", extensions=[component])
        await agent.initialize()
        
        # Execute enhanced tool
        result = await agent.tools["enhanced_api_call"](
            _agent=agent, 
            endpoint="https://api.example.com/test"
        )
        
        assert result.success
        response = result.response
        assert response["endpoint"] == "https://api.example.com/test"
        assert response["authenticated"] is True  # Should be injected by adapter
        
        # Check that metrics were collected
        metrics = component.get_tool_metrics()
        assert "enhanced_api_call" in metrics
        assert metrics["enhanced_api_call"]["total_calls"] >= 1
```

## Best Practices

### 1. Design for Reliability

```python
# Use type hints and validation
@tool
async def reliable_tool(
    data: str = Field(min_length=1, description="Input data"),
    timeout: int = Field(default=30, ge=1, le=300, description="Timeout in seconds")
) -> dict:
    """Well-designed tool with proper validation."""
    
    # Input validation
    if not data.strip():
        raise ValidationError("Data cannot be empty or whitespace only")
    
    # Use timeouts for external calls
    try:
        async with asyncio.timeout(timeout):
            # Tool logic here
            return {"result": f"processed_{data}"}
    except asyncio.TimeoutError:
        raise ToolError("Operation timed out", ToolErrorType.TIMEOUT_ERROR)
```

### 2. Implement Proper Logging

```python
import logging

@tool
async def well_logged_tool(
    operation: str,
    ctx: ToolContext = Depends()
) -> str:
    """Tool with comprehensive logging."""
    
    logger = logging.getLogger(f"{__name__}.{well_logged_tool.__name__}")
    
    logger.info(f"Starting operation: {operation}")
    
    try:
        # Simulate work
        result = f"completed_{operation}"
        logger.info(f"Operation {operation} completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Operation {operation} failed: {e}", exc_info=True)
        raise
```

### 3. Use Dependency Injection

```python
# Define interfaces
class StorageService(Protocol):
    async def save(self, key: str, data: Any) -> bool: ...
    async def load(self, key: str) -> Any: ...

# Create testable tools
@tool
async def data_processor(
    input_data: dict,
    storage: StorageService = Depends(get_storage_service)
) -> dict:
    """Tool with injected dependencies."""
    
    # Process data
    processed = {"processed": True, **input_data}
    
    # Save using injected service
    save_key = f"processed_{hash(str(input_data))}"
    await storage.save(save_key, processed)
    
    return {"saved_key": save_key, "data": processed}
```

### 4. Handle Errors Gracefully

```python
@tool
async def graceful_tool(operation: str) -> dict:
    """Tool with graceful error handling."""
    
    try:
        # Tool logic
        if operation == "fail":
            raise ConnectionError("Simulated failure")
        
        return {"result": f"success_{operation}"}
        
    except ConnectionError as e:
        # Return structured error instead of raising
        return {
            "success": False,
            "error": str(e),
            "error_type": "connection_error",
            "recoverable": True,
            "suggested_action": "Please try again in a few moments"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {e}",
            "error_type": "internal_error",
            "recoverable": False
        }
```

### 5. Document Thoroughly

```python
@tool
async def well_documented_tool(
    input_value: str = Field(description="The input value to process"),
    processing_mode: Literal["fast", "thorough"] = Field(
        default="fast",
        description="Processing mode: 'fast' for quick results, 'thorough' for detailed analysis"
    ),
    options: Optional[dict] = Field(
        default=None,
        description="Additional processing options as key-value pairs"
    )
) -> dict:
    """
    Process input value with configurable modes and options.
    
    This tool demonstrates comprehensive documentation including:
    - Clear parameter descriptions
    - Expected return value structure
    - Usage examples
    - Error conditions
    
    Args:
        input_value: The primary data to process (required)
        processing_mode: How to process the data:
            - "fast": Quick processing with basic results
            - "thorough": Detailed processing with comprehensive analysis
        options: Optional configuration dictionary that may include:
            - "timeout": Maximum processing time in seconds
            - "format": Output format preference
            - "debug": Enable debug information in response
    
    Returns:
        Dictionary containing:
        - "result": The processed output
        - "mode": The processing mode used
        - "metadata": Processing information
        - "debug_info": Debug details (if debug=True in options)
    
    Raises:
        ValidationError: If input_value is empty or invalid
        TimeoutError: If processing exceeds specified timeout
        
    Examples:
        Basic usage:
        >>> await well_documented_tool(input_value="hello world")
        {"result": "HELLO WORLD", "mode": "fast", "metadata": {...}}
        
        Thorough processing:
        >>> await well_documented_tool(
        ...     input_value="hello world",
        ...     processing_mode="thorough",
        ...     options={"debug": True}
        ... )
        {"result": "HELLO WORLD", "mode": "thorough", "metadata": {...}, "debug_info": {...}}
    """
    # Implementation...
    return {
        "result": input_value.upper(),
        "mode": processing_mode,
        "metadata": {"processed_at": time.time()},
        "debug_info": options.get("debug", False) and {"input_length": len(input_value)}
    }
```

Custom tools in Good Agent provide a powerful foundation for building sophisticated, production-ready agent capabilities. By following these patterns and best practices, you can create tools that are reliable, maintainable, and integrate seamlessly with the agent ecosystem.
