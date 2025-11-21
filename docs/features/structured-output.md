# Structured Output

Good Agent provides first-class support for extracting structured, typed data from LLM responses using Pydantic models and the Instructor library. This enables reliable data extraction with automatic validation, retry logic, and type safety.

## Overview

### Key Benefits

- **Type Safety** - Get fully typed Python objects from LLM responses
- **Automatic Validation** - Pydantic validates the extracted data
- **Retry Logic** - Built-in retry handling for malformed responses
- **Schema Generation** - Automatic JSON schema generation for LLMs
- **Instructor Integration** - Powered by the popular Instructor library. However unlike Instructor on its own, you can have follow-up messages and tool calls in the same conversation.
- **Event Hooks** - Full event system integration for monitoring and debugging

### How It Works

When you specify a `response_model` parameter in `agent.call()`, Good Agent:

1. Generates a JSON schema from your Pydantic model
2. Instructs the LLM to respond in that format
3. Validates and parses the response using Pydantic
4. Returns an `AssistantMessageStructuredOutput` with both text content and typed data
5. Automatically retries on validation failures

## Basic Usage

### Simple Data Extraction

Extract structured data from natural language:

```python
from pydantic import BaseModel
from good_agent import Agent

class Weather(BaseModel):
    temperature: float
    condition: str
    humidity: int
    wind_speed: float

async with Agent("You are a weather assistant.") as agent:
    response = await agent.call(
        "What's the weather like in Paris tomorrow?",
        response_model=Weather
    )

    # Access the structured data
    weather_data = response.output
    print(f"Temperature: {weather_data.temperature}°C")
    print(f"Condition: {weather_data.condition}")
    print(f"Humidity: {weather_data.humidity}%")

    # Still access the original text response
    print(f"Full response: {response.content}")
```

### Complex Nested Models

Handle complex data structures with nested models:

```python
from typing import List, Optional
from pydantic import BaseModel, Field

class Person(BaseModel):
    name: str
    age: int
    email: Optional[str] = None

class Company(BaseModel):
    name: str
    industry: str
    founded: int
    employees: List[Person]
    headquarters: str

class MarketAnalysis(BaseModel):
    company: Company
    market_cap: float = Field(description="Market capitalization in billions USD")
    growth_rate: float = Field(description="Annual growth rate as percentage")
    key_competitors: List[str]
    risk_factors: List[str]

async with Agent("You are a financial analyst.") as agent:
    analysis = await agent.call(
        "Analyze Tesla as an investment opportunity",
        response_model=MarketAnalysis
    )

    company = analysis.output.company
    print(f"Analyzing: {company.name}")
    print(f"Industry: {company.industry}")
    print(f"Employee count: {len(company.employees)}")
    print(f"Market cap: ${analysis.output.market_cap}B")
```

## Advanced Pydantic Features

### Field Validation and Descriptions

Use Pydantic's validation features for robust data extraction:

```python
from pydantic import BaseModel, Field, validator
from typing import Literal
from datetime import datetime

class TaskPriority(BaseModel):
    level: Literal["low", "medium", "high", "urgent"]
    score: int = Field(ge=1, le=10, description="Priority score from 1-10")

class Task(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    priority: TaskPriority
    due_date: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list, max_items=5)
    estimated_hours: float = Field(gt=0, le=1000)

    @validator('due_date')
    def due_date_not_in_past(cls, v):
        if v and v < datetime.now():
            raise ValueError('Due date cannot be in the past')
        return v

# Usage with validation
async with Agent("You are a project manager.") as agent:
    task = await agent.call(
        "Create a task for implementing user authentication with high priority, "
        "due next Friday, estimated 8 hours",
        response_model=Task
    )

    task_data = task.output
    print(f"Task: {task_data.title}")
    print(f"Priority: {task_data.priority.level} (score: {task_data.priority.score})")
    print(f"Estimated: {task_data.estimated_hours} hours")
```

### Enums and Constrained Types

Use Python enums and Pydantic constraints:

```python
from enum import Enum
from pydantic import BaseModel, Field, HttpUrl

class Status(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"

class Category(str, Enum):
    TECH = "technology"
    BUSINESS = "business"
    SCIENCE = "science"
    ENTERTAINMENT = "entertainment"

class Article(BaseModel):
    title: str = Field(min_length=10, max_length=200)
    slug: str = Field(regex=r'^[a-z0-9-]+$')
    category: Category
    status: Status
    tags: List[str] = Field(max_items=10)
    word_count: int = Field(ge=100, le=10000)
    source_url: Optional[HttpUrl] = None
    reading_time_minutes: int = Field(ge=1, description="Estimated reading time")

async with Agent("You are a content editor.") as agent:
    article = await agent.call(
        "Create metadata for an article about quantum computing breakthroughs, "
        "approximately 1500 words, from a tech blog",
        response_model=Article
    )

    article_data = article.output
    print(f"Title: {article_data.title}")
    print(f"Category: {article_data.category.value}")
    print(f"Status: {article_data.status.value}")
    print(f"Reading time: {article_data.reading_time_minutes} minutes")
```

## Message Types and Response Handling

### AssistantMessageStructuredOutput

Structured responses return a special message type:

```python
from good_agent.messages import AssistantMessageStructuredOutput

class UserProfile(BaseModel):
    name: str
    age: int
    interests: List[str]

async with Agent("Extract user information.") as agent:
    response = await agent.call(
        "John is 30 years old and likes coding, hiking, and cooking",
        response_model=UserProfile
    )

    # Check the message type
    assert isinstance(response, AssistantMessageStructuredOutput)

    # Access both text content and structured data
    print(f"LLM Response: {response.content}")
    print(f"Extracted Data: {response.output}")
    print(f"User Name: {response.output.name}")

    # The message appears in conversation history
    assert agent.messages[-1] == response
    assert agent.assistant[-1].output.name == "John"
```

### Continuing Conversations

Structured output works seamlessly in multi-turn conversations:

```python
class Sentiment(BaseModel):
    score: float = Field(ge=-1, le=1, description="Sentiment score from -1 to 1")
    label: Literal["positive", "negative", "neutral"]
    confidence: float = Field(ge=0, le=1)

async with Agent("You are a sentiment analysis expert.") as agent:
    # First turn: structured output
    sentiment = await agent.call(
        "Analyze the sentiment: 'I love this new feature!'",
        response_model=Sentiment
    )

    print(f"Sentiment: {sentiment.output.label} (score: {sentiment.output.score})")

    # Second turn: regular conversation
    follow_up = await agent.call(
        "What makes this sentiment particularly strong?"
    )

    print(f"Explanation: {follow_up.content}")

    # Third turn: another structured analysis
    comparison = await agent.call(
        "Now analyze: 'This is okay, I guess'",
        response_model=Sentiment
    )

    print(f"Comparison: {comparison.output.label} (score: {comparison.output.score})")
```

## Lists and Collections

### Extracting Multiple Items

Handle lists of structured data:

```python
class Contact(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    company: Optional[str] = None

class ContactList(BaseModel):
    contacts: List[Contact]
    total_count: int
    source: str

async with Agent("Extract contact information.") as agent:
    response = await agent.call(
        """
        Extract contacts from this text:
        - John Doe (john@example.com, 555-1234, Acme Corp)
        - Jane Smith (jane@smith.org)
        - Bob Johnson (bob@tech.com, TechCorp)
        """,
        response_model=ContactList
    )

    contacts = response.output
    print(f"Found {contacts.total_count} contacts from {contacts.source}")

    for contact in contacts.contacts:
        print(f"- {contact.name} ({contact.email})")
        if contact.company:
            print(f"  Company: {contact.company}")
```

### Dynamic Lists with Union Types

Handle variable content types:

```python
from typing import Union
from pydantic import BaseModel, Field

class TextContent(BaseModel):
    type: Literal["text"] = "text"
    content: str

class ImageContent(BaseModel):
    type: Literal["image"] = "image"
    url: str
    alt_text: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None

class LinkContent(BaseModel):
    type: Literal["link"] = "link"
    url: str
    title: str
    description: Optional[str] = None

ContentItem = Union[TextContent, ImageContent, LinkContent]

class WebPage(BaseModel):
    title: str
    url: str
    content: List[ContentItem]

async with Agent("Extract web page structure.") as agent:
    page = await agent.call(
        "Analyze this webpage content and structure...",
        response_model=WebPage
    )

    for item in page.output.content:
        if item.type == "text":
            print(f"Text: {item.content[:100]}...")
        elif item.type == "image":
            print(f"Image: {item.url} (alt: {item.alt_text})")
        elif item.type == "link":
            print(f"Link: {item.title} -> {item.url}")
```

## Tool Integration

### Structured Tool Responses

Combine structured output with tool usage:

```python
from good_agent import tool

class DatabaseQuery(BaseModel):
    table: str
    columns: List[str]
    where_clause: Optional[str] = None
    limit: Optional[int] = None

class QueryResult(BaseModel):
    query: DatabaseQuery
    row_count: int
    execution_time_ms: float
    data: List[dict]

@tool
async def execute_query(query: DatabaseQuery) -> QueryResult:
    """Execute a database query and return structured results."""
    # Simulate database execution
    import time
    start = time.time()

    # Mock query execution
    mock_data = [
        {"id": 1, "name": "Alice", "age": 30},
        {"id": 2, "name": "Bob", "age": 25},
    ]

    end = time.time()

    return QueryResult(
        query=query,
        row_count=len(mock_data),
        execution_time_ms=(end - start) * 1000,
        data=mock_data
    )

async with Agent("You are a database assistant.", tools=[execute_query]) as agent:
    # Agent can generate structured data AND use tools
    result = await agent.call(
        "Find all users over 25 years old from the users table",
        response_model=QueryResult
    )

    query_result = result.output
    print(f"Query: SELECT {', '.join(query_result.query.columns)} FROM {query_result.query.table}")
    print(f"Execution time: {query_result.execution_time_ms:.2f}ms")
    print(f"Results: {query_result.row_count} rows")
```

## Error Handling and Validation

### Handling Validation Errors

Good Agent automatically retries on validation failures, but you can also handle errors:

```python
from pydantic import ValidationError
from good_agent.exceptions import ExtractionError

class StrictData(BaseModel):
    number: int = Field(ge=1, le=100)
    email: str = Field(regex=r'^[^@]+@[^@]+\.[^@]+$')

async with Agent("Be precise with data formats.") as agent:
    try:
        response = await agent.call(
            "Generate a number between 1-100 and a valid email",
            response_model=StrictData
        )
        print(f"Valid data: {response.output}")

    except ExtractionError as e:
        print(f"Failed to extract valid data: {e}")
        # The LLM failed to generate valid data after retries

    except ValidationError as e:
        print(f"Validation failed: {e}")
        # This is less likely since Good Agent handles retries
```

### Custom Validation Logic

Add complex validation rules:

```python
from datetime import datetime, date
from pydantic import BaseModel, validator, root_validator

class Event(BaseModel):
    name: str
    start_date: date
    end_date: date
    max_attendees: int
    current_attendees: int = 0

    @validator('end_date')
    def end_after_start(cls, v, values):
        if 'start_date' in values and v <= values['start_date']:
            raise ValueError('End date must be after start date')
        return v

    @root_validator
    def validate_attendees(cls, values):
        current = values.get('current_attendees', 0)
        max_val = values.get('max_attendees', 0)
        if current > max_val:
            raise ValueError('Current attendees cannot exceed maximum')
        return values

async with Agent("You are an event planner.") as agent:
    event = await agent.call(
        "Plan a 3-day conference starting next Monday for up to 100 people",
        response_model=Event
    )

    event_data = event.output
    print(f"Event: {event_data.name}")
    print(f"Duration: {event_data.start_date} to {event_data.end_date}")
    print(f"Capacity: {event_data.current_attendees}/{event_data.max_attendees}")
```

## Event System Integration

### Monitoring Extraction

Use events to monitor structured output extraction:

```python
from good_agent.events import AgentEvents
from good_agent.core.event_router import EventContext

async with Agent("Extract structured data.") as agent:
    @agent.on(AgentEvents.LLM_EXTRACT_BEFORE)
    def before_extraction(ctx: EventContext):
        response_model = ctx.parameters['response_model']
        print(f"Starting extraction for model: {response_model.__name__}")

    @agent.on(AgentEvents.LLM_EXTRACT_AFTER)
    def after_extraction(ctx: EventContext):
        response = ctx.parameters['response']
        duration = ctx.parameters['duration']
        print(f"Extraction completed in {duration:.2f}s")
        print(f"Extracted: {type(response).__name__}")

    @agent.on(AgentEvents.LLM_EXTRACT_ERROR)
    def extraction_error(ctx: EventContext):
        error = ctx.parameters['error']
        response_model = ctx.parameters['response_model']
        print(f"Extraction failed for {response_model.__name__}: {error}")

    # Events will fire during extraction
    result = await agent.call(
        "Generate user data",
        response_model=UserProfile
    )
```

### Modifying Extraction Parameters

Use events to modify extraction behavior:

```python
@agent.on(AgentEvents.LLM_EXTRACT_BEFORE)
def modify_extraction_config(ctx: EventContext):
    config = ctx.parameters['config']

    # Increase temperature for more creative structured output
    config['temperature'] = 0.3

    # Add custom instructions for complex models
    response_model = ctx.parameters['response_model']
    if hasattr(response_model, '__name__') and 'Analysis' in response_model.__name__:
        # Modify messages to include analysis guidance
        messages = list(ctx.parameters['messages'])
        messages.append({
            "role": "system",
            "content": "Provide detailed, analytical responses with specific examples."
        })
        ctx.parameters['messages'] = messages
```

## Performance and Optimization

### Schema Optimization

Design efficient schemas for better extraction:

```python
# ❌ Overly complex nested structure
class BadStructure(BaseModel):
    data: Dict[str, Dict[str, List[Dict[str, Any]]]]  # Too nested
    everything: List[Union[str, int, float, bool]]    # Too permissive

# ✅ Clear, focused structure
class GoodStructure(BaseModel):
    """A well-designed model for reliable extraction."""

    # Clear field names and types
    user_id: int
    username: str
    status: Literal["active", "inactive", "pending"]

    # Optional fields with defaults
    last_login: Optional[datetime] = None
    preferences: Dict[str, str] = Field(default_factory=dict)

    # Reasonable constraints
    tags: List[str] = Field(max_items=10, default_factory=list)
```

### Caching and Reuse

Cache commonly used models:

```python
# Create reusable model classes
class StandardUser(BaseModel):
    id: int
    name: str
    email: str
    created_at: datetime

class StandardProduct(BaseModel):
    id: int
    name: str
    price: float
    category: str
    in_stock: bool

# Use consistently across calls
async with Agent("Data extraction assistant.") as agent:
    users = await agent.call("Extract user data...", response_model=StandardUser)
    products = await agent.call("Extract product data...", response_model=StandardProduct)
```

## Testing Structured Output

### Unit Testing Models

Test your Pydantic models independently:

```python
import pytest
from pydantic import ValidationError

def test_user_profile_validation():
    # Valid data
    valid_data = {
        "name": "Alice",
        "age": 30,
        "interests": ["coding", "hiking"]
    }
    user = UserProfile(**valid_data)
    assert user.name == "Alice"
    assert user.age == 30

    # Invalid data
    with pytest.raises(ValidationError):
        UserProfile(name="", age=-5, interests=[])

@pytest.mark.asyncio
async def test_structured_extraction():
    async with Agent("Test agent") as agent:
        response = await agent.call(
            "Create a profile for John, age 25, likes reading",
            response_model=UserProfile
        )

        assert isinstance(response, AssistantMessageStructuredOutput)
        assert response.output.name == "John"
        assert response.output.age == 25
        assert "reading" in response.output.interests
```

### Mock Testing

Mock structured responses for testing:

```python
from unittest.mock import Mock
from good_agent.mock import with_mock_llm

class TestData(BaseModel):
    value: int
    message: str

@pytest.mark.asyncio
async def test_with_mocked_extraction():
    mock_response = TestData(value=42, message="Test message")

    with with_mock_llm() as mock_llm:
        mock_llm.extract.return_value = mock_response

        async with Agent("Test agent") as agent:
            response = await agent.call(
                "Generate test data",
                response_model=TestData
            )

            assert response.output.value == 42
            assert response.output.message == "Test message"
```

## Best Practices

### Model Design Guidelines

- **Keep models focused** - Each model should represent a single concept
- **Use descriptive field names** - Make intent clear to the LLM
- **Add field descriptions** - Help the LLM understand requirements
- **Set reasonable constraints** - Use Pydantic validators appropriately
- **Avoid overly deep nesting** - Flatten complex structures when possible

### Error Handling Strategy

```python
from good_agent.exceptions import ExtractionError

async def robust_extraction(agent: Agent, prompt: str, model: type[BaseModel]):
    """Robust extraction with fallback handling."""
    try:
        # Primary extraction attempt
        response = await agent.call(prompt, response_model=model)
        return response.output

    except ExtractionError:
        # Fallback: try without structured output
        fallback = await agent.call(
            f"{prompt}\n\nPlease format your response clearly for manual parsing."
        )

        # Log the fallback for analysis
        print(f"Structured extraction failed, got fallback: {fallback.content}")
        return None
```

### Schema Evolution

Handle model changes gracefully:

```python
# Version 1
class UserV1(BaseModel):
    name: str
    email: str

# Version 2 - backward compatible
class UserV2(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None  # New optional field
    created_at: Optional[datetime] = None  # New optional field

# Version 3 - with migration
class UserV3(BaseModel):
    full_name: str = Field(alias='name')  # Renamed field with alias
    email: str
    phone: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        allow_population_by_field_name = True  # Allow old field names
```

## Complete Example

Here's a comprehensive example demonstrating advanced structured output usage:

```python
--8<-- "examples/structured/comprehensive_extraction.py"
```

## Common Patterns

### Data Transformation Pipeline

```python
class InputData(BaseModel):
    raw_text: str
    source: str

class ProcessedData(BaseModel):
    clean_text: str
    sentiment: float
    entities: List[str]
    summary: str

class OutputData(BaseModel):
    processed: ProcessedData
    metadata: Dict[str, Any]
    confidence: float

async with Agent("Data processing pipeline.") as agent:
    # Step 1: Extract input data
    input_data = await agent.call(
        "Parse this raw input...",
        response_model=InputData
    )

    # Step 2: Process the data
    processed = await agent.call(
        f"Process this data: {input_data.output.raw_text}",
        response_model=ProcessedData
    )

    # Step 3: Generate final output
    output = await agent.call(
        f"Finalize analysis with confidence score for: {processed.output.summary}",
        response_model=OutputData
    )
```

## Next Steps

- **[Agent Modes](./modes.md)** - Use structured output in different agent modes
- **[Tools](../core/tools.md)** - Combine structured output with tool usage
- **[Events](../core/events.md)** - Monitor and customize extraction with events
