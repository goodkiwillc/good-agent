# Innovative Workflow Interfaces: Beyond Explicit Graphs

**Key Insight**: Code already IS a graph. Control flow in Python naturally forms a DAG. Why force developers to explicitly construct what the language already expresses?

This document explores innovative interfaces for defining agent workflows using Python's language features: operator overloading, context managers, decorators, type hints, async generators, and more.

---

## The Problem with Explicit Graphs

**Current approach (LangGraph style)**:
```python
workflow = StateGraph(state_schema=AgentState)
workflow.add_node("research", research_node)
workflow.add_node("analyze", analyze_node)
workflow.add_node("synthesize", synthesize_node)
workflow.add_edge("research", "analyze")
workflow.add_conditional_edges(
    "analyze",
    should_continue,
    {"continue": "synthesize", "end": END}
)
graph = workflow.compile()
```

**Problems**:
- Verbose and repetitive
- Separates structure from behavior
- Doesn't leverage Python's control flow
- Error-prone (typos in node names)
- Obscures the actual workflow logic

**We can do better!**

---

## Approach 1: Just Write Python Code (Automatic DAG Inference)

**Core Idea**: Write normal Python. The framework infers the DAG from your code structure.

### Basic Example

```python
from good_agent import workflow

@workflow
async def research_workflow(ctx):
    """Just write normal async Python!"""

    # Sequential steps - naturally expressed
    query = ctx.input
    web_results = await search_web(query)
    academic_results = await search_arxiv(query)

    # Conditional branching - natural if/else
    if needs_more_depth(web_results):
        additional = await deep_dive(query)
        web_results = combine(web_results, additional)

    # The framework sees this as a DAG:
    # query -> [search_web, search_arxiv] (parallel) -> needs_more_depth? -> deep_dive? -> combine

    synthesis = await synthesize(web_results, academic_results)
    return synthesis

# Use it
result = await research_workflow.run(input="quantum computing")
```

**How it works**:
1. Framework analyzes the async function
2. Detects independent `await` calls (can run in parallel)
3. Detects control flow (if/else, loops) for branching
4. Builds execution plan automatically
5. Runs with maximum parallelism while respecting dependencies

### Parallel Execution with Context Managers

```python
@workflow
async def parallel_research(ctx):
    """Use context manager for explicit parallelism"""

    query = ctx.input

    # Explicit parallel execution
    async with ctx.parallel() as p:
        web = p.run(search_web(query))
        academic = p.run(search_arxiv(query))
        news = p.run(search_news(query))

    # All three searches run in parallel
    # Results available after context exit

    return synthesize(web.result, academic.result, news.result)
```

### Loop-Based Workflows

```python
@workflow
async def iterative_refinement(ctx):
    """Loops are just loops"""

    draft = await initial_draft(ctx.input)

    for iteration in range(3):
        critique = await critique_draft(draft)

        if critique.is_good_enough:
            break

        draft = await revise_draft(draft, critique)

    return draft
```

### Error Handling

```python
@workflow
async def robust_workflow(ctx):
    """Use normal try/except"""

    try:
        result = await risky_operation(ctx.input)
    except APIError:
        # Automatic fallback path
        result = await fallback_operation(ctx.input)

    return result
```

### Benefits

✅ **Natural**: Just write Python
✅ **Readable**: Control flow is obvious
✅ **Type-safe**: Use normal type hints
✅ **IDE support**: Autocomplete, navigation work perfectly
✅ **Automatic parallelism**: Framework detects independent operations
✅ **Checkpointing**: Framework can checkpoint between awaits
✅ **Retry logic**: Wrap any await in try/except

### Advanced: Dependency Injection via Type Hints

```python
@workflow
async def smart_workflow(
    ctx: WorkflowContext,
    llm: LanguageModel,  # Auto-injected
    vector_db: VectorStore,  # Auto-injected
):
    """Type hints declare dependencies"""

    # Dependencies automatically available
    docs = await vector_db.search(ctx.input)

    response = await llm.call(
        f"Answer based on: {docs}\nQuestion: {ctx.input}"
    )

    return response
```

---

## Approach 2: Operator Overloading (Fluent DAG Construction)

**Core Idea**: Use Python operators (`>>`, `|`, `&`) to build DAGs fluently when you need explicit control.

### Sequential with `>>`

```python
from good_agent import Step

# Define steps
research = Step(search_web)
analyze = Step(analyze_results)
synthesize = Step(create_summary)

# Chain with >> operator
workflow = research >> analyze >> synthesize

# Execute
result = await workflow(input="quantum computing")
```

### Parallel with `|`

```python
# Define parallel steps
web_search = Step(search_web)
academic_search = Step(search_arxiv)
news_search = Step(search_news)

# Parallel execution with | operator
parallel = web_search | academic_search | news_search

# Combine results
workflow = parallel >> Step(combine_results)

result = await workflow(input="AI safety")
```

### Conditional Branching with `&` (When)

```python
from good_agent import Step, When

research = Step(do_research)

# Conditional branching
deep_dive = Step(deep_analysis)
quick_summary = Step(quick_summary)

workflow = (
    research >>
    When(lambda r: r.needs_depth,
         then=deep_dive,
         otherwise=quick_summary)
)
```

### Complex Example

```python
# Multi-stage workflow with operators
workflow = (
    # Stage 1: Parallel research
    (web_search | academic_search | news_search) >>

    # Stage 2: Combine
    Step(combine_results) >>

    # Stage 3: Conditional analysis
    When(
        lambda r: r.confidence < 0.7,
        then=(
            # Low confidence: do more research
            Step(additional_research) >>
            Step(reanalyze)
        ),
        otherwise=Step(finalize)
    ) >>

    # Stage 4: Final synthesis
    Step(create_report)
)

result = await workflow(input="climate change")
```

### Custom Operators

```python
from good_agent import Step

class Step:
    def __rshift__(self, other):
        """Sequential: self >> other"""
        return SequentialStep([self, other])

    def __or__(self, other):
        """Parallel: self | other"""
        return ParallelStep([self, other])

    def __and__(self, other):
        """Both required: self & other"""
        return AllStep([self, other])

    def __mul__(self, n):
        """Repeat: step * 3"""
        return RepeatStep(self, n)

    def __pow__(self, condition):
        """Conditional: step ** condition"""
        return ConditionalStep(self, condition)

# Usage examples
workflow = (
    step1 >> step2 |  # step1 then (step2 in parallel with...)
    step3 >>          # step3 then
    step4 * 3         # repeat step4 three times
)

# Conditional execution
workflow = step1 >> (step2 ** lambda r: r.needs_validation)
```

---

## Approach 3: Builder Pattern with Context Managers

**Core Idea**: Use nested context managers to define scope and relationships.

### Parallel Execution Scope

```python
from good_agent import Workflow

workflow = Workflow()

with workflow.parallel() as parallel:
    result1 = parallel.add(search_web)
    result2 = parallel.add(search_arxiv)
    result3 = parallel.add(search_news)

# After context: all three have executed in parallel
combined = workflow.add(combine_results, inputs=[result1, result2, result3])
```

### Conditional Scope

```python
workflow = Workflow()

research_result = workflow.add(do_research)

with workflow.when(lambda r: r.needs_depth):
    # Only runs if condition is true
    deep_result = workflow.add(deep_dive)
    workflow.add(detailed_analysis)

with workflow.otherwise():
    # Runs if condition is false
    workflow.add(quick_summary)
```

### Loop Scope

```python
workflow = Workflow()

draft = workflow.add(initial_draft)

with workflow.loop(max_iterations=3) as loop:
    critique = loop.add(critique_draft, inputs=[draft])

    with loop.when(lambda c: c.is_good_enough):
        loop.break_loop()

    draft = loop.add(revise_draft, inputs=[draft, critique])

final = workflow.add(finalize, inputs=[draft])
```

### Nested Scopes

```python
workflow = Workflow()

with workflow.parallel() as p:
    # Parallel research
    web = p.add(search_web)
    academic = p.add(search_arxiv)

    with p.serial():  # Serial sub-workflow within parallel branch
        news = p.add(fetch_news)
        filtered = p.add(filter_news, inputs=[news])

# Combine all results
result = workflow.add(combine, inputs=[web, academic, filtered])
```

---

## Approach 4: Decorator-Based Dependency Declaration

**Core Idea**: Use decorators and function signatures to declare dependencies implicitly.

### Dependencies from Function Parameters

```python
from good_agent import workflow, step

@workflow
class ResearchWorkflow:
    @step
    async def search_web(self, query: str):
        return await web_search(query)

    @step
    async def search_arxiv(self, query: str):
        return await arxiv_search(query)

    @step
    async def analyze(
        self,
        query: str,
        web: search_web,  # Type hint = dependency!
        arxiv: search_arxiv  # Depends on search_arxiv step
    ):
        """Dependencies inferred from parameter types"""
        return await analyze_results(web, arxiv)

    @step
    async def synthesize(
        self,
        analysis: analyze  # Depends on analyze step
    ):
        return await create_summary(analysis)

# Framework builds DAG automatically:
# query -> [search_web, search_arxiv] (parallel) -> analyze -> synthesize

workflow = ResearchWorkflow()
result = await workflow.run(query="quantum computing")
```

### Explicit Dependency Declaration

```python
from good_agent import workflow, step, depends_on

@workflow
class Pipeline:
    @step
    async def step1(self):
        return "result1"

    @step
    async def step2(self):
        return "result2"

    @step
    @depends_on(step1, step2)
    async def step3(self, results):
        # results = [step1_result, step2_result]
        return combine(results)
```

### Conditional Dependencies

```python
@workflow
class ConditionalPipeline:
    @step
    async def analyze(self, input):
        return analysis_result

    @step
    @depends_on(analyze)
    @when(lambda analyze: analyze.needs_depth)
    async def deep_dive(self, analyze):
        """Only runs if condition is true"""
        return deep_analysis(analyze)

    @step
    @depends_on(analyze, deep_dive)
    @optional(deep_dive)  # deep_dive may not run
    async def finalize(self, analyze, deep_dive=None):
        if deep_dive:
            return combine(analyze, deep_dive)
        return analyze
```

---

## Approach 5: Async Generators as Workflows

**Core Idea**: Use `yield` to define execution points, framework orchestrates.

### Basic Generator Workflow

```python
from good_agent import generator_workflow

@generator_workflow
async def research_pipeline(query):
    """Yield steps, framework executes them"""

    # Yield operations - framework executes them
    web_results = yield search_web(query)
    academic_results = yield search_arxiv(query)

    # Generator controls flow
    if web_results.needs_more:
        additional = yield deep_dive(query)
        web_results = combine(web_results, additional)

    # Final yield returns result
    synthesis = yield synthesize(web_results, academic_results)
    return synthesis

result = await research_pipeline("quantum computing")
```

### Parallel Yields

```python
@generator_workflow
async def parallel_research(query):
    """Yield multiple for parallel execution"""

    # Yield tuple = parallel execution
    web, academic, news = yield (
        search_web(query),
        search_arxiv(query),
        search_news(query)
    )

    synthesis = yield combine(web, academic, news)
    return synthesis
```

### Generator with Events

```python
@generator_workflow
async def event_driven_workflow(query):
    """Generators can emit events"""

    results = yield search(query)

    # Emit event
    yield Event('search_complete', data=results)

    if results.count > 100:
        # Wait for event
        user_input = yield WaitForEvent('user_confirmation')

        if user_input.approved:
            analysis = yield analyze(results)
        else:
            return None

    return results
```

---

## Approach 6: Pattern Matching (Python 3.10+)

**Core Idea**: Use structural pattern matching for workflow routing.

### Match-Based Routing

```python
from good_agent import workflow

@workflow
async def smart_router(ctx):
    """Pattern matching for workflow selection"""

    query_type = await classify_query(ctx.input)

    match query_type:
        case QueryType.RESEARCH:
            return await research_workflow(ctx)

        case QueryType.ANALYSIS:
            return await analysis_workflow(ctx)

        case QueryType.CREATIVE:
            return await creative_workflow(ctx)

        case QueryType.FACTUAL if ctx.needs_verification:
            # Guard clauses work too
            verified = await verify_facts(ctx.input)
            return await factual_workflow(ctx, verified)

        case _:
            return await default_workflow(ctx)
```

### Pattern Matching on Results

```python
@workflow
async def adaptive_workflow(ctx):
    """Adapt based on result patterns"""

    result = await initial_analysis(ctx.input)

    match result:
        case {'confidence': conf, 'data': data} if conf > 0.9:
            # High confidence - proceed
            return await finalize(data)

        case {'confidence': conf, 'data': data} if conf > 0.5:
            # Medium confidence - get more data
            additional = await gather_more_data(data)
            return await finalize(combine(data, additional))

        case {'confidence': conf}:
            # Low confidence - different approach
            return await alternative_method(ctx.input)

        case {'error': error_msg}:
            # Error handling
            return await handle_error(error_msg)
```

---

## Approach 7: Dataflow with `>>` and Implicit Variables

**Core Idea**: Variables flow through operators implicitly.

### Implicit Data Flow

```python
from good_agent import Flow

# Define flow with implicit data passing
flow = (
    Flow(search_web) >>          # Returns web_results
    Flow(search_arxiv) >>         # Returns academic_results
    Flow(lambda w, a: combine(w, a)) >>  # Receives both
    Flow(synthesize)              # Receives combined
)

result = await flow("quantum computing")
```

### Named Flows

```python
from good_agent import flow

@flow
async def research(query):
    return await search_web(query)

@flow
async def analyze(research_results):
    """Parameter name matches previous flow!"""
    return await analyze(research_results)

@flow
async def synthesize(analyze_results):
    """Chained automatically by parameter names"""
    return await create_summary(analyze_results)

# Auto-assembled into pipeline
pipeline = research >> analyze >> synthesize
result = await pipeline("query")
```

---

## Approach 8: State Machine with Decorators

**Core Idea**: Each method is a state, decorators define transitions.

### State-Based Workflow

```python
from good_agent import StateMachine, state, transition

class ResearchStateMachine(StateMachine):
    @state(initial=True)
    async def start(self, ctx):
        """Initial state"""
        results = await quick_search(ctx.input)
        ctx.state['results'] = results

        # Transition based on results
        if results.count < 10:
            return self.deep_search
        else:
            return self.analyze

    @state
    async def deep_search(self, ctx):
        """Deep search state"""
        more = await comprehensive_search(ctx.input)
        ctx.state['results'].extend(more)
        return self.analyze

    @state
    async def analyze(self, ctx):
        """Analysis state"""
        analysis = await analyze(ctx.state['results'])
        ctx.state['analysis'] = analysis

        if analysis.needs_verification:
            return self.verify
        else:
            return self.finalize

    @state
    async def verify(self, ctx):
        """Verification state"""
        verified = await verify(ctx.state['analysis'])
        ctx.state['verified'] = verified
        return self.finalize

    @state(terminal=True)
    async def finalize(self, ctx):
        """Terminal state"""
        return create_report(ctx.state)

# Use it
machine = ResearchStateMachine()
result = await machine.run(input="quantum computing")
```

### Transition Decorators

```python
class Pipeline(StateMachine):
    @state(initial=True)
    @transition(to='analyze', when=lambda r: r.ready)
    @transition(to='error', when=lambda r: r.has_error)
    async def fetch(self, ctx):
        return await fetch_data()

    @state
    @transition(to='finalize')
    async def analyze(self, ctx):
        return await analyze_data()

    @state(terminal=True)
    async def finalize(self, ctx):
        return result
```

---

## Approach 9: Declarative with Dataclasses

**Core Idea**: Define workflow as data structure, not code.

### Dataclass Workflow

```python
from dataclasses import dataclass
from good_agent import Step, Workflow

@dataclass
class ResearchWorkflow:
    # Steps defined as fields
    web_search: Step = Step(search_web)
    arxiv_search: Step = Step(search_arxiv)
    combine: Step = Step(combine_results)
    analyze: Step = Step(analyze)
    synthesize: Step = Step(create_summary)

    def __workflow__(self):
        """Dunder method defines flow"""
        return (
            (self.web_search | self.arxiv_search) >>
            self.combine >>
            self.analyze >>
            self.synthesize
        )

workflow = ResearchWorkflow()
result = await workflow(input="quantum computing")
```

---

## Approach 10: Railway-Oriented Programming

**Core Idea**: Model success/failure paths explicitly.

### Railway Pattern

```python
from good_agent import railway, success, failure

@railway
async def risky_workflow(input):
    """Returns Result[Success, Failure]"""

    # Each step returns Result
    result = await search(input)

    if result.is_failure():
        return failure("Search failed")

    # Chain operations - stops on first failure
    return (
        success(result.value)
        >> (lambda r: analyze(r))
        >> (lambda a: synthesize(a))
        >> (lambda s: finalize(s))
    )

result = await risky_workflow("query")

match result:
    case Success(value):
        print(f"Success: {value}")
    case Failure(error):
        print(f"Failed: {error}")
```

---

## Comparison Matrix

| Approach | Readability | Flexibility | Python-ness | Explicit Control | Learning Curve |
|----------|-------------|-------------|-------------|------------------|----------------|
| **Just Write Python** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ (Easy) |
| **Operator Overloading** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ (Easy) |
| **Context Managers** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ (Easy) |
| **Decorator Dependencies** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ (Medium) |
| **Async Generators** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ (Easy) |
| **Pattern Matching** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ (Easy) |
| **Dataflow >>** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ (Medium) |
| **State Machine** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ (Hard) |
| **Dataclasses** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ (Medium) |
| **Railway** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ (Hard) |

---

## Recommended Hybrid Approach

Combine the best ideas:

```python
from good_agent import workflow, Step

# Approach 1: Default - Just write Python
@workflow
async def simple_workflow(ctx):
    """For most cases, just write Python"""
    result = await step1(ctx.input)

    if result.needs_more:
        result = await step2(result)

    return result

# Approach 2: Operators when you need explicit DAG
web = Step(search_web)
arxiv = Step(search_arxiv)
combine = Step(combine_results)

explicit_workflow = (web | arxiv) >> combine

# Approach 3: Context managers for parallelism
@workflow
async def hybrid_workflow(ctx):
    """Mix approaches as needed"""

    # Normal Python
    initial = await analyze(ctx.input)

    # Explicit parallel with context manager
    async with ctx.parallel() as p:
        web = p.run(search_web(initial))
        arxiv = p.run(search_arxiv(initial))

    # Pattern matching for routing
    match (web.result, arxiv.result):
        case (w, a) if w.confidence > 0.9 and a.confidence > 0.9:
            return await quick_synthesis(w, a)
        case _:
            return await careful_synthesis(web.result, arxiv.result)

# Approach 4: Use operators for complex static DAGs
complex = (
    (step1 | step2 | step3) >>
    combine >>
    When(lambda r: r.needs_validation,
         then=validate >> reprocess,
         otherwise=finalize)
)
```

---

## Implementation Sketch

### Core Workflow Decorator

```python
import ast
import inspect
from typing import Callable, Any

class WorkflowContext:
    def __init__(self):
        self.state = {}
        self.input = None

    def parallel(self):
        """Context manager for parallel execution"""
        return ParallelContext()

def workflow(func: Callable) -> 'Workflow':
    """
    Decorator that analyzes function and creates executable workflow.

    Analyzes:
    - await statements (execution points)
    - if/else (branching)
    - loops (iteration)
    - try/except (error paths)

    Builds execution plan that maximizes parallelism.
    """

    # Get function source
    source = inspect.getsource(func)
    tree = ast.parse(source)

    # Analyze AST
    analyzer = WorkflowAnalyzer()
    execution_plan = analyzer.visit(tree)

    return Workflow(func, execution_plan)

class WorkflowAnalyzer(ast.NodeVisitor):
    """Analyzes async function to build execution plan"""

    def visit_Await(self, node):
        """Each await is a step"""
        pass

    def visit_If(self, node):
        """If/else creates branches"""
        pass

    def visit_For(self, node):
        """Loops create cycles"""
        pass
```

### Operator Overloading

```python
class Step:
    def __init__(self, func):
        self.func = func

    def __rshift__(self, other):
        """Sequential: self >> other"""
        return SequentialStep([self, other])

    def __or__(self, other):
        """Parallel: self | other"""
        return ParallelStep([self, other])

    async def __call__(self, *args, **kwargs):
        """Execute the step"""
        return await self.func(*args, **kwargs)

class SequentialStep(Step):
    def __init__(self, steps):
        self.steps = steps

    async def __call__(self, input):
        result = input
        for step in self.steps:
            result = await step(result)
        return result

class ParallelStep(Step):
    def __init__(self, steps):
        self.steps = steps

    async def __call__(self, input):
        tasks = [step(input) for step in self.steps]
        return await asyncio.gather(*tasks)
```

---

## Conclusion

**Best approaches for good-agent**:

1. **Primary: Just Write Python** - Use `@workflow` decorator, write normal async code, framework infers DAG
2. **Secondary: Operator Overloading** - Use `>>` and `|` for explicit DAG when needed
3. **Tertiary: Context Managers** - Use `async with ctx.parallel()` for explicit parallelism
4. **Bonus: Pattern Matching** - Use Python 3.10+ match for routing

**Why these win**:
- ✅ **Pythonic**: Leverages language features developers already know
- ✅ **Readable**: Code clearly expresses intent
- ✅ **Gradual complexity**: Simple by default, powerful when needed
- ✅ **IDE-friendly**: Full autocomplete, type checking, navigation
- ✅ **Debuggable**: Standard Python debugging works
- ✅ **No magic**: Clear what's happening
- ✅ **Composable**: Mix and match approaches

**Avoid**:
- ❌ Explicit `add_node` / `add_edge` - too verbose
- ❌ String-based node names - error-prone
- ❌ Separate structure from behavior - hard to understand
- ❌ Custom DSLs - steep learning curve
