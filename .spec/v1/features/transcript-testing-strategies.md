# Transcript Testing Strategies: Approaches and Concepts

## Executive Summary

This document explores different approaches to testing probabilistic agent systems deterministically. It addresses the fundamental tension between:

- **What we want**: Deterministic, reliable, maintainable tests
- **What we have**: Probabilistic LLM responses that vary naturally

The document proposes a **layered testing strategy** with multiple transcript types and replay modes, allowing developers to choose the right abstraction level for each test scenario.

## The Fundamental Problem

### The Core Tension

Testing agent systems involves testing **probabilistic systems deterministically**:

```
Recording Session:
  User: "What's the weather?"
  LLM:  "I'll check the weather for you in NYC"  [probabilistic output]
  Tool: weather(location="NYC") → {temp: 72}
  LLM:  "It's 72°F and sunny!"  [probabilistic output]

Replaying Test:
  User: "What is the weather?"  [slightly different wording]
  ???:  Should we return same response?
        What if system prompt changed?
        What if context changed?
        What if we're testing error handling?
```

### Key Challenges

1. **Response Variance**: LLMs naturally produce different responses to the same input
2. **Context Sensitivity**: Responses depend on system prompt, context, conversation history
3. **Branching Logic**: Conversations can branch in multiple directions
4. **Long Conversations**: Maintaining fixtures for multi-turn conversations is tedious
5. **Configuration Coupling**: Should fixtures dictate agent config or just responses?

### What Makes This Different from HTTP Mocking

| HTTP (VCR.py) | Agent Systems |
|---------------|---------------|
| Deterministic requests | Probabilistic responses |
| Request URL is unique key | Context + message = fuzzy key |
| Single request/response | Multi-turn stateful conversation |
| Config in code (URL, headers) | Config mixed (system prompt, context, tools) |
| Replay is exact match | Replay needs semantic matching |

## Proposed Approaches

### Approach 1: Record → Compile to Code

**Concept**: Record real sessions with actual LLM, compile recordings into editable Python test fixtures.

#### Recording Format

```yaml
# recordings/weather_session_2025_01_13.yaml
version: "1.0"
type: "recording"

metadata:
  recorded_at: "2025-01-13T10:30:00Z"
  model: "gpt-4"
  purpose: "Capture successful weather query flow"

session:
  - user: "What's the weather in NYC?"

  - assistant: "I'll check the weather for you"
    tool_calls:
      - name: weather
        arguments: {location: "NYC"}

  - tool: weather
    result: {temp: 72, condition: "sunny"}

  - assistant: "It's 72°F and sunny in NYC!"
```

#### Compilation

```bash
# Compile recording to Python fixture
$ good-agent compile recordings/weather_session_2025_01_13.yaml \
    --output tests/fixtures/test_weather_fixtures.py
```

#### Generated Code

```python
# tests/fixtures/test_weather_fixtures.py
# GENERATED from recordings/weather_session_2025_01_13.yaml
# Edit this file to customize behavior!

from good_agent.transcripts import Fixture

class WeatherNYCSunny(Fixture):
    """Weather query for NYC returning sunny conditions.

    Recorded: 2025-01-13T10:30:00Z
    Model: gpt-4
    """

    def setup(self, agent):
        """Configure agent and tool mocks."""
        # Mock weather tool for NYC
        agent.tools.mock("weather",
            when={"location": "NYC"},
            return_value={"temp": 72, "condition": "sunny"}
        )

    def responses(self):
        """Return LLM response sequence.

        You can edit these responses or add variations!
        """
        return [
            # Original recorded response
            "I'll check the weather for you",

            # Variations you can add:
            # "Let me look that up for you",
            # "I'll find out what the weather is like",
        ]

    def assertions(self, result):
        """Post-execution assertions."""
        assert self.agent.tools.was_called("weather")
        assert self.agent.tools.last_call("weather").args["location"] == "NYC"
        assert "72" in result.content or "sunny" in result.content
```

#### Usage

```python
# tests/test_weather.py
from fixtures.test_weather_fixtures import WeatherNYCSunny

def test_weather_nyc_sunny():
    agent = Agent("You are a helpful weather assistant")
    agent.tools.add(weather_tool)

    with WeatherNYCSunny().apply(agent):
        result = await agent.call("What's the weather in NYC?")
        # Assertions already in fixture, but can add more
        assert result.content
```

#### Benefits

- ✅ Start from real LLM behavior
- ✅ Human-editable code (no YAML editing)
- ✅ Version control friendly
- ✅ Type-safe
- ✅ Can add logic, variations, conditionals
- ✅ IDE support (autocomplete, refactoring)

#### Drawbacks

- ❌ Extra compilation step
- ❌ Code generation can be brittle
- ❌ Harder for non-programmers

---

### Approach 2: Semantic Branching Trees

**Concept**: Record multiple conversation paths, use semantic matching to choose the right branch at runtime.

#### Format

```yaml
# transcripts/weather_queries_branching.yaml
version: "1.0"
type: "branching_tree"

scenario: "Weather queries with multiple paths"

# Define decision points and branches
tree:
  root:
    branches:
      # Branch 1: Specific city mentioned
      - match:
          type: "semantic"
          user_intent: "weather_specific_city"
          entities: {city: "*"}  # Any city

        path:
          - assistant: "I'll check the weather for you in {city}"
            tool_calls: [{weather: {location: "{city}"}}]

          - tool: weather
            # Dynamic result based on entity
            result_template: true

          - assistant: "It's {temp}°F and {condition} in {city}!"

      # Branch 2: Use context for location
      - match:
          type: "semantic"
          user_intent: "weather_user_location"
          requires_context: ["user_city"]

        path:
          - assistant: "I'll check the weather in {user_city}"
            tool_calls: [{weather: {location: "{user_city}"}}]

          - tool: weather
            result: {temp: 65, condition: "cloudy"}

          - assistant: "It's 65°F and cloudy!"

      # Branch 3: Error handling
      - match:
          type: "semantic"
          user_intent: "weather_specific_city"
          entities: {city: "InvalidCity"}

        path:
          - assistant: "I'll check that location"
            tool_calls: [{weather: {location: "InvalidCity"}}]

          - tool: weather
            error: "City not found"

          - assistant: "I couldn't find that city. Could you check the spelling?"

# Configuration for branch selection
branching:
  mode: "semantic_match"  # Use embeddings/NLU to match
  model: "text-embedding-3-small"
  threshold: 0.85  # Similarity threshold

  fallback: "first"  # Use first branch if no match
```

#### Usage

```python
from good_agent.transcripts import BranchingReplayer

def test_weather_with_branches():
    agent = Agent("You are helpful")
    agent.tools.add(weather_tool)

    replayer = BranchingReplayer("weather_queries_branching.yaml")

    with replayer.mock_agent(agent):
        # Automatically selects branch 1 (specific city)
        r1 = await agent.call("What's the weather in NYC?")
        assert "NYC" in r1.content

        # Automatically selects branch 2 (user location)
        agent.context.update(user_city="LA")
        r2 = await agent.call("What's the weather?")
        assert "LA" in r2.content or "65" in r2.content

        # Automatically selects branch 3 (error)
        r3 = await agent.call("Weather in Asdfghjkl?")
        assert "couldn't find" in r3.content.lower()
```

#### Advanced: Multi-Level Branching

```yaml
tree:
  root:
    branches:
      - match: {intent: "weather_query"}

        subtree:
          branches:
            - match: {has_location: true}
              path: [...]

            - match: {has_location: false}

              subtree:
                branches:
                  - match: {context_has_location: true}
                    path: [...]

                  - match: {context_has_location: false}
                    path:
                      - assistant: "Which city would you like to know about?"
                      # ... ask for location
```

#### Benefits

- ✅ Single file for multiple scenarios
- ✅ Handles conversation branching naturally
- ✅ Semantic matching allows prompt variation
- ✅ Can test error paths alongside happy path

#### Drawbacks

- ❌ Requires embedding model for matching
- ❌ Non-deterministic (semantic matching)
- ❌ Complex YAML structure
- ❌ Harder to debug when wrong branch chosen

---

### Approach 3: Checkpoint/Fork Model

**Concept**: Save conversation state at decision points, test different branches independently.

#### Format

```yaml
# transcripts/conversation_checkpoints.yaml
version: "1.0"
type: "checkpoint_tree"

scenario: "Multi-step planning conversation"

# Linear conversation up to first decision point
prologue:
  - user: "I need help planning my day"

  - assistant: "I'd be happy to help! What information do you need?"

# Save state at this point
checkpoint_001:
  name: "After greeting, awaiting user request"

  state:
    context:
      planning_mode: true
      user_engaged: true

    messages: [msg_001, msg_002]

    visible_messages: [msg_001, msg_002]

  # Different possible paths from this checkpoint
  branches:
    weather_only:
      - user: "What's the weather?"

      - assistant: "I'll check the weather for you"
        tool_calls: [{weather: {location: "{user_city}"}}]

      - tool: weather
        result: {temp: 72, condition: "sunny"}

      - assistant: "It's 72°F and sunny today!"

      # Another checkpoint
      checkpoint_002:
        name: "After weather, can ask follow-up"
        branches:
          done:
            - user: "Thanks!"
            - assistant: "You're welcome!"

          more_info:
            - user: "Should I bring an umbrella?"
            - assistant: "No need! It's sunny with no rain expected."

    calendar_only:
      - user: "What's on my calendar?"

      - assistant: "Let me check your calendar"
        tool_calls: [{calendar: {date: "today"}}]

      - tool: calendar
        result: [{time: "2pm", event: "Team meeting"}]

      - assistant: "You have a team meeting at 2pm today."

    both:
      - user: "Weather and calendar please"

      - assistant: "I'll check both for you"
        tool_calls:
          - {weather: {location: "{user_city}"}}
          - {calendar: {date: "today"}}

      # Parallel tool execution
      - tool: weather
        result: {temp: 72, condition: "sunny"}

      - tool: calendar
        result: [{time: "2pm", event: "Team meeting"}]

      - assistant: "It's 72°F and sunny. You have a team meeting at 2pm."
```

#### Usage

```python
from good_agent.transcripts import CheckpointReplayer

def test_planning_branches():
    transcript = CheckpointReplayer.load("conversation_checkpoints.yaml")

    # Test each branch independently
    for branch_name in ["weather_only", "calendar_only", "both"]:
        # Create fresh agent
        agent = Agent("You are a helpful assistant")

        # Run prologue (shared setup)
        with transcript.run_prologue(agent):
            # Verify prologue executed
            assert len(agent.messages) == 2

        # Restore to checkpoint
        checkpoint = transcript.restore("checkpoint_001")

        # Replay specific branch
        with checkpoint.replay_branch(branch_name, agent):
            result = await agent.execute()

            # Branch-specific assertions
            if branch_name == "weather_only":
                assert agent.tools.was_called("weather")
                assert not agent.tools.was_called("calendar")

            elif branch_name == "calendar_only":
                assert agent.tools.was_called("calendar")
                assert not agent.tools.was_called("weather")

            elif branch_name == "both":
                assert agent.tools.was_called("weather")
                assert agent.tools.was_called("calendar")
```

#### Advanced: Nested Checkpoints

```python
def test_nested_conversation():
    transcript = CheckpointReplayer.load("conversation_checkpoints.yaml")
    agent = Agent("You are helpful")

    with transcript.run_prologue(agent):
        pass

    # Follow weather_only branch to checkpoint_002
    checkpoint = transcript.restore("checkpoint_001")
    with checkpoint.replay_branch("weather_only", agent):
        # Now at checkpoint_002

        # Test both sub-branches
        cp2 = transcript.restore("checkpoint_002")

        with cp2.replay_branch("done", agent):
            # Test the "done" path
            pass

        # Restore again for different path
        with cp2.replay_branch("more_info", agent):
            # Test the "more_info" path
            pass
```

#### Benefits

- ✅ Test branches independently
- ✅ Share common setup (prologue)
- ✅ Explicit conversation structure
- ✅ Can nest checkpoints deeply
- ✅ Easy to add new branches

#### Drawbacks

- ❌ Manual checkpoint management
- ❌ Verbose YAML for complex trees
- ❌ Need to track checkpoint names

---

### Approach 4: Property-Based Transcripts

**Concept**: Specify **what should happen**, not exact responses. Run with real LLM, assert properties.

#### Format

```yaml
# transcripts/weather_properties.yaml
version: "1.0"
type: "property_test"

scenario: "User asks about weather"

description: |
  Test that agent correctly handles weather queries by:
  1. Extracting location from user message or context
  2. Calling weather tool with correct parameters
  3. Reporting results in natural language
  4. Handling errors gracefully

# Don't specify exact responses - specify properties
properties:
  - step: 1
    name: "Agent calls weather tool with correct location"

    when:
      user_message:
        contains_any: ["weather", "temperature", "forecast"]

    then:
      assistant_must:
        - call_tool: "weather"
        - tool_parameters:
            location:
              # Extract from user message or context
              source: ["user_message", "context.user_city"]
              not_empty: true
              not_null: true

  - step: 2
    name: "Agent reports weather in natural language"

    when:
      tool: "weather"
      result_type: "success"
      result_contains: ["temp", "condition"]

    then:
      assistant_must:
        - mention_all: ["{result.temp}", "{result.condition}"]
        - format: "natural_language"
        - not_include: "raw_json"
        - not_include: "{\"temp\":"  # Don't output JSON
        - sentiment: "neutral_or_positive"

  - step: 3
    name: "Agent handles errors gracefully"

    when:
      tool: "weather"
      result_type: "error"

    then:
      assistant_must:
        - apologize: true
        - explain_error: true
        - offer_alternative: true
        - not_hallucinate: true  # Don't make up weather!
        - not_include: ["probably", "I think", "maybe"]

      assistant_must_not:
        - provide_fake_data: true
        - blame_user: true

# Optional: Provide examples for reference
examples:
  good_responses:
    - "It's 72°F and sunny in NYC!"
    - "The weather in New York is sunny with a high of 72°F"
    - "Currently 72 degrees and sunny"

  bad_responses:
    - "{temp: 72, condition: 'sunny'}"  # Raw JSON
    - "I think it's probably nice out"  # Hallucination
    - "The weather is {result.condition}"  # Template leak

# Assertions to run after execution
final_assertions:
  - no_errors: true
  - tool_called: "weather"
  - conversation_complete: true
  - user_satisfied: true  # Subjective, could use sentiment analysis
```

#### Usage

```python
from good_agent.transcripts import PropertyChecker

@pytest.mark.llm  # Mark as requiring real LLM
def test_weather_properties():
    agent = Agent("You are a helpful weather assistant")
    agent.tools.add(weather_tool)

    # Property checker runs assertions, not exact matching
    checker = PropertyChecker("weather_properties.yaml")

    # Run with REAL LLM (non-deterministic)
    with checker.verify(agent) as session:
        result = await agent.call("What's the weather in NYC?")

        # Checker automatically validates all properties
        # Raises assertion if any property violated

    # Can also check manually
    report = session.get_report()
    print(f"Properties passed: {report.passed}/{report.total}")

    if report.failed:
        print("Failed properties:")
        for failure in report.failures:
            print(f"  - {failure.property}: {failure.reason}")
```

#### Advanced: Custom Property Validators

```yaml
# Custom validators
validators:
  - name: "no_hallucination"
    type: "custom"
    implementation: "validators.check_no_hallucination"

  - name: "sentiment"
    type: "builtin"
    model: "sentiment-analysis"

  - name: "natural_language"
    type: "regex"
    pattern: "^[A-Z][^{]*[.!?]$"  # Starts with capital, no braces, ends with punctuation
```

```python
# validators.py
def check_no_hallucination(assistant_response, tool_result, context):
    """Verify response only contains information from tool result."""

    # Extract claims from response
    claims = extract_factual_claims(assistant_response)

    # Verify each claim is supported by tool result
    for claim in claims:
        if not is_supported_by(claim, tool_result):
            return False, f"Unsupported claim: {claim}"

    return True, "No hallucinations detected"
```

#### Benefits

- ✅ Tests behavior, not exact output
- ✅ Works with real LLM
- ✅ Allows natural variation
- ✅ Catches regressions in behavior
- ✅ More robust to prompt/model changes
- ✅ Can use for monitoring production

#### Drawbacks

- ❌ Slower (requires real LLM calls)
- ❌ More expensive (API costs)
- ❌ Non-deterministic (can flake)
- ❌ Harder to debug failures

---

### Approach 5: Differential/Golden Testing

**Concept**: Record a "golden" baseline execution, compare future runs against it with bounded variance.

#### Format

```yaml
# transcripts/weather_golden.yaml
version: "1.0"
type: "golden_test"

metadata:
  created: "2025-01-13T10:30:00Z"
  model: "gpt-4"
  purpose: "Baseline for weather query behavior"

# The "golden" execution to compare against
golden:
  - user: "What's the weather in NYC?"

  - assistant: "I'll check the weather for you"
    tool_calls:
      - name: weather
        arguments: {location: "NYC"}
    metadata:
      embedding: [0.123, -0.456, ...]  # Cached embedding

  - tool: weather
    result: {temp: 72, condition: "sunny"}

  - assistant: "It's 72°F and sunny in NYC!"
    metadata:
      embedding: [0.789, -0.234, ...]

# Define what variance is acceptable
variance_rules:
  assistant_messages:
    # Semantic similarity using embeddings
    min_semantic_similarity: 0.85

    # Required keywords must appear
    required_keywords:
      - weather: true
      - "72": true
      - sunny: true

    # Optional keywords (nice to have)
    optional_keywords:
      - NYC: 0.8  # Should appear 80% of the time
      - New York: 0.5

  tool_calls:
    # Tool calls must match exactly
    exact_match: true

    # Or allow some variance
    # parameters_can_vary: ["units"]  # Allow units to be different

  conversation_flow:
    # Overall structure
    max_turns_difference: 1  # Can be +/- 1 turn
    same_tools_called: true
    same_tool_order: false  # Order can change

  timing:
    # Performance variance
    max_latency_increase: 1.5  # 50% slower is acceptable
    max_tokens_increase: 1.2   # 20% more tokens is acceptable

# What must be identical (invariants)
invariants:
  - tool_called: "weather"
  - tool_parameters:
      location: "NYC"
  - final_answer_contains: "72"
  - no_errors: true
  - no_refusals: true

# What to do when variance exceeded
on_variance_exceeded:
  action: "flag"  # or "fail", "auto_update"
  notify: "slack"
  create_report: true
```

#### Usage

```python
from good_agent.transcripts import GoldenTest

def test_weather_vs_golden():
    agent = Agent("You are a helpful weather assistant")
    agent.tools.add(weather_tool)

    golden = GoldenTest("weather_golden.yaml")

    # Run with real LLM
    with golden.compare(agent) as diff:
        result = await agent.call("What's the weather in NYC?")

    # Check if within acceptable variance
    if diff.within_bounds():
        print("✓ Behavior matches golden test")
    else:
        print("✗ Behavior deviated from golden:")
        print(f"  Semantic similarity: {diff.semantic_similarity:.2f} (min: 0.85)")
        print(f"  Flow difference: {diff.flow_diff}")
        print(f"  Invariants broken: {diff.broken_invariants}")

        # Option to update golden
        if input("Update golden baseline? (y/n)") == "y":
            golden.update_from_current()
```

#### Advanced: Multiple Baselines

```yaml
# Can have multiple golden baselines for same scenario
baselines:
  gpt4:
    model: "gpt-4"
    execution: [...]

  gpt35:
    model: "gpt-3.5-turbo"
    execution: [...]

  claude:
    model: "claude-3-sonnet"
    execution: [...]

# Compare against appropriate baseline
compare_against:
  rule: "same_model"  # Use baseline with same model
  # or
  # rule: "any"  # Must match at least one baseline
```

#### Benefits

- ✅ Catch regressions automatically
- ✅ Allow bounded variance
- ✅ Works with real LLM
- ✅ Can update baseline when behavior improves
- ✅ Good for monitoring

#### Drawbacks

- ❌ Need to maintain baselines
- ❌ Requires embedding model
- ❌ Subjective variance thresholds
- ❌ Can drift over time

---

### Approach 6: Hybrid Record-Regenerate

**Concept**: Record examples from expensive model, regenerate responses with cheaper/faster model for testing.

#### Format

```yaml
# transcripts/weather_hybrid.yaml
version: "1.0"
type: "hybrid"

metadata:
  source_model: "gpt-4"  # Expensive model used for recording
  test_model: "gpt-3.5-turbo"  # Cheaper model for replay

# Recorded examples from GPT-4 (few-shot examples)
examples:
  - user: "What's the weather in NYC?"
    assistant: "I'll check the weather for you in New York City"
    tool_calls: [{weather: {location: "NYC"}}]

    metadata:
      quality_score: 0.95
      tone: "friendly"
      style: "concise"

  - user: "How about LA?"
    assistant: "Let me check Los Angeles for you"
    tool_calls: [{weather: {location: "LA"}}]

    metadata:
      quality_score: 0.93

  - user: "What's the temperature?"
    assistant: "I'll need to know which city. Could you specify the location?"

    metadata:
      quality_score: 0.90
      handling: "clarification_request"

# Template for regeneration
regeneration_template:
  system_prompt: |
    You are a helpful weather assistant.

    Respond to weather queries by:
    1. Calling the weather tool with the correct location
    2. Reporting results in a friendly, concise manner

    Here are examples of good responses:
    {examples}

  task: "Respond to the user's weather query"

  style:
    tone: "friendly"
    length: "concise"
    format: "natural_language"

  constraints:
    must_call_tool: true
    no_hallucination: true

# Replay strategy
replay_strategy:
  mode: "regenerate"  # Regenerate responses at test time

  model: "gpt-3.5-turbo"  # Cheaper model
  temperature: 0.0  # Deterministic

  # Use examples as few-shot
  few_shot_examples: 3  # Use 3 most similar examples
  similarity_metric: "embedding"

  # Quality checks
  min_quality_score: 0.80
  max_retries: 2

  # Fallback strategies
  fallback_on_failure: "use_example"  # Use closest example
  fallback_on_low_quality: "use_gpt4"  # Fall back to expensive model
```

#### Usage

```python
from good_agent.transcripts import HybridReplayer

def test_weather_hybrid():
    agent = Agent("You are helpful")
    agent.tools.add(weather_tool)

    # Replayer uses cheap model to regenerate responses
    replayer = HybridReplayer("weather_hybrid.yaml")

    with replayer.mock_agent(agent):
        # Behind the scenes:
        # 1. Finds most similar example(s)
        # 2. Uses them as few-shot for GPT-3.5
        # 3. Generates response at test time
        # 4. Falls back to recorded example if quality low

        result = await agent.call("What's the weather in NYC?")

        # Response is generated, not exact replay
        # But should be similar quality to examples
```

#### Advanced: Quality Scoring

```python
# Custom quality scorer
class WeatherResponseQualityScorer:
    def score(self, response, user_message, tool_result):
        score = 1.0

        # Deduct points for issues
        if "I think" in response or "probably" in response:
            score -= 0.2  # Hallucination indicators

        if "{" in response:
            score -= 0.3  # JSON leak

        if not any(word in response for word in ["weather", "temperature"]):
            score -= 0.1  # Missing topic

        # Bonus for good practices
        if tool_result and str(tool_result.get("temp")) in response:
            score += 0.1  # Correctly uses tool result

        return max(0.0, min(1.0, score))

# Use in replay
replayer = HybridReplayer(
    "weather_hybrid.yaml",
    quality_scorer=WeatherResponseQualityScorer()
)
```

#### Benefits

- ✅ Fast tests (cheap model)
- ✅ Based on real high-quality examples
- ✅ Can regenerate variations
- ✅ Deterministic (temperature=0)
- ✅ Cost-effective

#### Drawbacks

- ❌ Requires recording examples first
- ❌ Quality may vary from source
- ❌ Still makes LLM calls (slower than pure mocks)
- ❌ Complex fallback logic

---

### Approach 7: State Machine with Recorded Transitions

**Concept**: Model conversation as explicit state machine, record actual transitions taken.

#### Format

```yaml
# transcripts/weather_fsm.yaml
version: "1.0"
type: "state_machine"

scenario: "Weather query state machine"

# Define all possible states
states:
  initial:
    description: "Starting state"
    on_enter:
      - set_system_prompt: "You are a helpful weather assistant"

  awaiting_query:
    description: "Waiting for user to ask something"

    transitions:
      - trigger: {intent: "weather_query", has_location: true}
        next: checking_weather

      - trigger: {intent: "weather_query", has_location: false}
        next: requesting_location

      - trigger: {intent: "other"}
        next: general_response

  requesting_location:
    description: "Ask user for location"

    actions:
      - respond: "Which city would you like to know about?"

    transitions:
      - trigger: {provides_location: true}
        next: checking_weather

      - trigger: {provides_location: false}
        next: awaiting_query

  checking_weather:
    description: "Calling weather tool"

    actions:
      - extract_location: from_user_or_context
      - call_tool:
          name: weather
          parameters: {location: "{extracted_location}"}

    transitions:
      - trigger: {tool_success: true}
        next: reporting_weather

      - trigger: {tool_error: true}
        next: weather_error

  reporting_weather:
    description: "Report weather to user"

    actions:
      - respond: "It's {temp}°F and {condition}"

    transitions:
      - trigger: {user_satisfied: true}
        next: awaiting_query

      - trigger: {user_asks_followup: true}
        next: awaiting_query

  weather_error:
    description: "Handle weather tool error"

    actions:
      - apologize: true
      - explain: "I couldn't find weather for that location"

    transitions:
      - next: awaiting_query

# Record actual execution path
recorded_execution:
  - state: initial
    timestamp: "2025-01-13T10:30:00Z"

  - state: awaiting_query
    user_input: "What's the weather in NYC?"

    # State machine evaluates triggers
    triggers_matched:
      intent: "weather_query"
      has_location: true

    transition: checking_weather

  - state: checking_weather
    actions_executed:
      - extracted_location: "NYC"
      - tool_call: {weather: {location: "NYC"}}

    tool_result: {temp: 72, condition: "sunny"}

    triggers_matched:
      tool_success: true

    transition: reporting_weather

  - state: reporting_weather
    actions_executed:
      - response: "It's 72°F and sunny in NYC!"

    user_response: "Thanks!"

    triggers_matched:
      user_satisfied: true

    transition: awaiting_query

  - state: awaiting_query
    # Conversation ends here
```

#### Usage

```python
from good_agent.transcripts import StateMachineReplayer

def test_weather_state_machine():
    agent = Agent("You are helpful")
    agent.tools.add(weather_tool)

    fsm = StateMachineReplayer("weather_fsm.yaml")

    # Replay enforces state transitions
    with fsm.enforce_states(agent):
        result = await agent.call("What's the weather in NYC?")

        # Verify state machine path
        assert fsm.visited_states == [
            "initial",
            "awaiting_query",
            "checking_weather",
            "reporting_weather",
            "awaiting_query"
        ]

        # Verify we didn't enter error states
        assert "weather_error" not in fsm.visited_states
```

#### Advanced: State Machine Validation

```python
def test_all_states_reachable():
    """Verify state machine has no dead states."""
    fsm = StateMachineReplayer("weather_fsm.yaml")

    # Analyze state machine
    analysis = fsm.analyze()

    assert len(analysis.unreachable_states) == 0, \
        f"Unreachable states: {analysis.unreachable_states}"

    assert len(analysis.dead_end_states) == 0, \
        f"Dead end states: {analysis.dead_end_states}"

def test_error_handling_paths():
    """Test all error paths in state machine."""
    fsm = StateMachineReplayer("weather_fsm.yaml")

    # Force error state
    agent = Agent("You are helpful")
    agent.tools.add(weather_tool)
    agent.tools.mock("weather", raises=Exception("API down"))

    with fsm.enforce_states(agent):
        result = await agent.call("What's the weather?")

        # Should have entered error state
        assert "weather_error" in fsm.visited_states
```

#### Benefits

- ✅ Explicit conversation structure
- ✅ Easy to visualize
- ✅ Testable state machine
- ✅ Can verify all paths
- ✅ Good for complex logic

#### Drawbacks

- ❌ Verbose for simple flows
- ❌ Requires upfront design
- ❌ Rigid structure
- ❌ Hard to handle unexpected states

---

### Approach 8: Multi-Level Testing Strategy

**Concept**: Use different transcript types for different test levels (unit, integration, E2E).

#### Level 1: Unit Tests - Pure Fixtures (Fast)

```python
# tests/unit/test_weather_tool_calling.py
from good_agent import Agent
from good_agent.testing import mock_response

@pytest.mark.unit  # Fast, no LLM
def test_weather_tool_called_correctly():
    """Test that agent calls weather tool with correct parameters."""

    agent = Agent("You are helpful")
    agent.tools.add(weather_tool)

    # Simple inline mock - no transcript file
    with agent.mock_response(
        "I'll check the weather",
        tool_calls=[{"weather": {"location": "NYC"}}]
    ):
        result = await agent.call("What's the weather in NYC?")

        # Assert tool was called
        assert agent.tools.was_called("weather")
        assert agent.tools.last_call("weather").args["location"] == "NYC"
```

#### Level 2: Integration Tests - Recorded Responses (Medium)

```python
# tests/integration/test_weather_flow.py
from good_agent.transcripts import TranscriptReplayer

@pytest.mark.integration  # Medium speed, uses fixtures
def test_weather_conversation_flow():
    """Test full conversation flow with recorded LLM responses."""

    agent = Agent("You are a helpful weather assistant")
    agent.tools.add(weather_tool)

    # Load recorded transcript
    replayer = TranscriptReplayer("transcripts/weather_nyc_sunny.yaml")

    with replayer.mock_agent(agent):
        result = await agent.call("What's the weather in NYC?")

        # Assertions based on recorded flow
        assert "72" in result.content
        assert "sunny" in result.content
```

#### Level 3: E2E Tests - Real LLM with Properties (Slow)

```python
# tests/e2e/test_weather_end_to_end.py
from good_agent.transcripts import PropertyChecker

@pytest.mark.e2e  # Slow, expensive, uses real LLM
@pytest.mark.llm  # Requires API key
def test_weather_end_to_end():
    """Test with real LLM, validate behavior properties."""

    agent = Agent("You are a helpful weather assistant")
    agent.tools.add(weather_tool)

    # Property-based assertions
    checker = PropertyChecker("transcripts/weather_properties.yaml")

    with checker.verify(agent):
        # Real LLM call
        result = await agent.call("What's the weather in NYC?")

        # Properties automatically verified:
        # - Called weather tool
        # - Used correct location
        # - Response in natural language
        # - No hallucinations
```

#### Level 4: Regression Tests - Differential (Periodic)

```python
# tests/regression/test_weather_regression.py
from good_agent.transcripts import GoldenTest

@pytest.mark.regression  # Run less frequently
@pytest.mark.llm
def test_weather_vs_baseline():
    """Compare current behavior against baseline."""

    agent = Agent("You are a helpful weather assistant")
    agent.tools.add(weather_tool)

    golden = GoldenTest("transcripts/golden/weather_baseline.yaml")

    with golden.compare(agent) as diff:
        result = await agent.call("What's the weather in NYC?")

        # Allow some variance
        assert diff.semantic_similarity > 0.85
        assert diff.same_tools_called

        # Generate report if deviated significantly
        if diff.significant_change:
            diff.generate_report("reports/weather_regression.html")
```

#### Test Suite Configuration

```yaml
# pytest.ini
[pytest]
markers =
    unit: Fast unit tests with mocks (no LLM)
    integration: Integration tests with fixtures (no LLM)
    e2e: End-to-end tests with real LLM (slow, expensive)
    regression: Regression tests vs baseline (periodic)
    llm: Requires LLM API key

# Run different test levels
# $ pytest -m unit  # Fast, during development
# $ pytest -m "unit or integration"  # Pre-commit
# $ pytest -m e2e  # Before merging
# $ pytest -m regression  # Nightly/weekly
```

#### Benefits

- ✅ Right tool for each job
- ✅ Fast feedback loop (unit tests)
- ✅ Comprehensive coverage (E2E)
- ✅ Catch regressions (differential)
- ✅ Cost-effective (only use LLM when needed)

---

### Approach 9: Executable Specification (BDD-style)

**Concept**: Write specifications in natural language that compile to executable tests.

#### Format

```yaml
# specs/weather_query.spec.yaml
version: "1.0"
type: "executable_specification"

feature: Weather Query Handling

background: |
  Given a helpful agent with access to a weather tool
  And the weather tool returns accurate data

scenarios:
  - name: Successful weather query for specific city

    given:
      - agent_has_tool: weather
      - user_context:
          timezone: "America/New_York"

    when:
      - user_asks: "What's the weather in NYC?"

    then:
      - agent_should_call_tool:
          name: weather
          parameters:
            location: "NYC"

      - agent_should_respond_with:
          mentions: ["temperature", "condition"]
          format: natural_language
          tone: friendly

      - agent_should_not:
          - hallucinate_data
          - expose_raw_json
          - refuse_request

  - name: Weather query without location (use context)

    given:
      - agent_has_tool: weather
      - user_context:
          user_city: "Los Angeles"

    when:
      - user_asks: "What's the weather?"

    then:
      - agent_should_extract_location:
          from: context
          key: user_city

      - agent_should_call_tool:
          name: weather
          parameters:
            location: "{user_city}"

  - name: Weather tool returns error

    given:
      - agent_has_tool: weather
      - weather_tool_will_fail:
          error: "City not found"

    when:
      - user_asks: "What's the weather in Asdfghjkl?"

    then:
      - agent_should_handle_error_gracefully
      - agent_should_apologize
      - agent_should_explain_what_went_wrong
      - agent_should_not_hallucinate

# Execution modes
execution:
  mode: "property_based"  # Run with real LLM, check properties

  # Or use fixtures
  # mode: "fixture"
  # fixture_file: "weather_fixtures.yaml"
```

#### Compilation

```bash
# Compile spec to Python tests
$ good-agent compile-spec specs/weather_query.spec.yaml \
    --output tests/generated/test_weather_spec.py
```

#### Generated Tests

```python
# tests/generated/test_weather_spec.py
# GENERATED from specs/weather_query.spec.yaml

import pytest
from good_agent import Agent
from good_agent.testing import PropertyAsserter

class TestWeatherQueryHandling:
    """Feature: Weather Query Handling

    Given a helpful agent with access to a weather tool
    And the weather tool returns accurate data
    """

    @pytest.mark.e2e
    async def test_successful_weather_query_for_specific_city(self):
        """Scenario: Successful weather query for specific city"""

        # Given
        agent = Agent("You are a helpful assistant")
        agent.tools.add(weather_tool)
        agent.context.update(timezone="America/New_York")

        # When
        result = await agent.call("What's the weather in NYC?")

        # Then
        assert agent.tools.was_called("weather")
        assert agent.tools.last_call("weather").args["location"] == "NYC"

        asserter = PropertyAsserter(result)
        asserter.mentions(["temperature", "condition"])
        asserter.format_is("natural_language")
        asserter.tone_is("friendly")
        asserter.does_not_hallucinate()
        asserter.does_not_expose_raw_json()
        asserter.does_not_refuse()

    @pytest.mark.e2e
    async def test_weather_query_without_location_use_context(self):
        """Scenario: Weather query without location (use context)"""

        # Given
        agent = Agent("You are a helpful assistant")
        agent.tools.add(weather_tool)
        agent.context.update(user_city="Los Angeles")

        # When
        result = await agent.call("What's the weather?")

        # Then
        assert agent.tools.was_called("weather")
        assert agent.tools.last_call("weather").args["location"] == "Los Angeles"

    # ... more generated tests
```

#### Benefits

- ✅ Readable by non-programmers
- ✅ Executable documentation
- ✅ BDD-style (Given/When/Then)
- ✅ Auto-generated tests
- ✅ Spec = documentation = tests

#### Drawbacks

- ❌ Requires compilation step
- ❌ Limited expressiveness (compared to code)
- ❌ Generated code can be hard to debug

---

## Recommended Layered Strategy

After exploring all approaches, I recommend a **layered strategy** that uses different tools for different purposes:

### Layer 1: Development (Fast Iteration)

**Purpose**: Quick feedback during development

**Tools**:
- Inline mocks: `agent.mock_response("...")`
- Code-based fixtures: Python functions
- No files needed

**Example**:
```python
def test_quick_check():
    agent = Agent("You are helpful")
    with agent.mock_response("I'll help!"):
        result = await agent.call("Hello")
```

### Layer 2: Integration Testing (Recorded Sessions)

**Purpose**: Test conversation flows with realistic responses

**Tools**:
- Record real LLM sessions
- Compile to editable Python fixtures
- Version control fixtures

**Example**:
```python
# Record session
$ good-agent record --output recordings/weather_session.yaml

# Compile to fixture
$ good-agent compile recordings/weather_session.yaml

# Use in tests
from fixtures.weather_session import WeatherNYCSunny
with WeatherNYCSunny().apply(agent):
    result = await agent.call("What's the weather?")
```

### Layer 3: E2E Testing (Property-Based)

**Purpose**: Validate behavior with real LLM

**Tools**:
- Property specifications
- Real LLM calls
- Behavior assertions

**Example**:
```yaml
# weather_properties.yaml
properties:
  - agent_calls_tool: weather
  - response_is_natural_language
  - no_hallucination
```

### Layer 4: Regression Monitoring (Golden Tests)

**Purpose**: Catch behavioral regressions over time

**Tools**:
- Golden baselines
- Differential comparison
- Auto-update on approval

**Example**:
```python
golden = GoldenTest("baselines/weather.yaml")
with golden.compare() as diff:
    result = await agent.call("What's the weather?")
    if diff.significant: diff.report()
```

## Decision Matrix

| Use Case | Approach | Speed | Cost | Deterministic | Maintenance |
|----------|----------|-------|------|---------------|-------------|
| Unit testing | Inline mocks | ⚡⚡⚡ | $ | ✅ | Low |
| Integration testing | Compiled fixtures | ⚡⚡ | $ | ✅ | Medium |
| Complex branching | Checkpoint trees | ⚡⚡ | $ | ✅ | High |
| Behavior validation | Property tests | ⚡ | $$$ | ❌ | Low |
| Regression detection | Golden tests | ⚡ | $$$ | ❌ | Medium |
| Cost optimization | Hybrid regenerate | ⚡⚡ | $$ | ~✅ | Medium |

## Open Questions for Discussion

1. **Primary Use Case**: What's your most common testing scenario?
   - Quick unit tests during development?
   - Integration tests for complex flows?
   - E2E tests with real LLM?
   - All three?

2. **Determinism vs Realism**: Where on this spectrum?
   ```
   Pure mocks          Hybrid            Real LLM
   (100% deterministic) (regenerate)     (0% deterministic)
   Fast, cheap         Medium            Slow, expensive
   ```

3. **Fixture Format Preference**:
   - YAML files (human-readable)?
   - Python code (type-safe)?
   - Both (record YAML, compile to code)?

4. **Branching Complexity**: How complex are your conversation trees?
   - Simple linear flows?
   - Some branching (2-3 paths)?
   - Complex trees (many paths)?

5. **Maintenance Philosophy**:
   - Manually maintain fixtures?
   - Auto-generate from recordings?
   - Mix of both?

6. **Testing Speed Requirements**:
   - Sub-second unit tests?
   - Few seconds for integration?
   - Minutes acceptable for E2E?

7. **LLM Variance Tolerance**:
   - Zero tolerance (exact replay)?
   - Some variance (semantic similarity)?
   - High variance (property-based only)?

## Next Steps

Based on your answers to the questions above, I can:

1. **Refine the spec** to focus on your primary use cases
2. **Implement a prototype** of the most valuable approach
3. **Create example fixtures** demonstrating best practices
4. **Build tooling** for the workflow (record → compile → test)

What resonates most with your testing needs?
