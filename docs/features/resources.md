# Stateful Resources

!!! warning "⚠️ Under Active Development"
    This project is in early-stage development. APIs may change, break, or be completely rewritten without notice. Use at your own risk in production environments.

Stateful resources provide persistent, editable data containers that can be seamlessly integrated with agents. Good Agent offers specialized resources for YAML configuration files and MDXL (Markdown XML) documents, with extensible patterns for custom resource types.

## Core Concepts

### StatefulResource Base Class

All resources inherit from `StatefulResource`, which provides:

- **State Management**: Persistent state with initialization and persistence lifecycle
- **Tool Registration**: Automatic tool binding with metaclass-based collection
- **Agent Integration**: Context manager pattern for temporary agent binding
- **Isolated Contexts**: Thread-safe execution with message isolation

<!-- @TODO: Show the StatefulResource protocol/api here -->

```python
from good_agent.resources import StatefulResource
from good_agent import tool

class CustomResource(StatefulResource[dict]):
    def __init__(self, data: dict, name: str = "custom"):
        super().__init__(name=name)
        self._initial_data = data

    async def initialize(self) -> None:
        """Load initial state."""
        self.state = self._initial_data.copy()

    async def persist(self) -> None:
        """Save changes (implementation specific)."""
        print(f"Saving {self.name} with {len(self.state)} items")

    @tool
    async def get_item(self, key: str) -> str:
        """Get item by key."""
        return self.state.get(key, "Not found")

    @tool
    async def set_item(self, key: str, value: str) -> str:
        """Set item value."""
        self.state[key] = value
        return "OK"
```

### Resource Context Binding

Resources bind to agents using context managers, providing isolated execution environments:

```python
from good_agent import Agent

async with Agent("You are a data editor") as agent:
    resource = CustomResource({"name": "example"})

    # Bind resource to agent with isolated context
    async with resource(agent):
        # Agent now has only resource-specific tools
        # Original tools are temporarily replaced
        response = await agent.call("Set the name to 'updated'")
        # Resource tools handle the request
```

The binding process:

1. **Initialization**: Resource is initialized if not already done
2. **Context Isolation**: Creates thread context for message isolation
3. **Tool Replacement**: Temporarily replaces agent tools with resource tools
4. **System Message**: Adds resource-specific context to system prompt
5. **Restoration**: Original tools and context restored on exit

## EditableYAML

`EditableYAML` provides comprehensive YAML document editing with validation, atomic operations, and advanced merge strategies.

### Basic Operations

--8<-- "tests/unit/resources/test_editable_yaml.py:test_basic_get_set_delete_validate_v2"

### Merge Strategies

EditableYAML supports sophisticated merge operations for complex data updates:

--8<-- "tests/unit/resources/test_editable_yaml.py:test_merge_strategies_v2"

**Available Strategies:**

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `assign` | Replace value completely (default) | Simple value updates |
| `merge` | Shallow merge dictionaries | Adding new keys to objects |
| `deep_merge` | Deep merge nested structures | Complex nested updates |
| `merge_array` | Append unique array items | Adding to lists |
| `replace_array` | Replace entire array | Complete list replacement |

### Patch Operations

Batch operations using JSON Patch-style operations:

--8<-- "tests/unit/resources/test_editable_yaml.py:test_patch_ops_v2"

**Supported Operations:**

- `add`: Add new values with create_missing support
- `replace`: Update existing values
- `remove`: Delete paths
- `merge`: Shallow merge dictionaries
- `deep_merge`: Deep merge nested structures
- `merge_array`: Merge arrays with optional key-based deduplication
- `move`: Move values between paths
- `copy`: Copy values to new paths
- `test`: Assert path values for conditional operations

### Validation and Rollback

EditableYAML supports custom validators with automatic rollback on validation failure:

--8<-- "tests/unit/resources/test_editable_yaml.py:test_validation_and_rollback_v2"

**Validator Types:**

```python
# Dict-based validator
def dict_validator(doc: dict) -> tuple[bool, list[str]]:
    errors = []
    if "required_field" not in doc:
        errors.append("Missing required_field")
    return len(errors) == 0, errors

# String-based validator
def yaml_validator(yaml_text: str) -> dict:
    try:
        data = yaml.safe_load(yaml_text)
        return {"ok": True, "errors": []}
    except yaml.YAMLError as e:
        return {"ok": False, "errors": [str(e)]}
```

### Type Coercion

Automatic type coercion preserves existing data types when updating scalar values:

```python
# If existing value is integer
await editor.set("config.port", "8080", coerce_to_existing_type=True)
# Result: config.port = 8080 (int, not string)

# If existing value is boolean
await editor.set("config.debug", "true", coerce_to_existing_type=True)
# Result: config.debug = True (bool, not string)
```

## EditableMDXL

`EditableMDXL` provides XPath-based editing for MDXL (Markdown XML) documents with citation management and content filtering.

### Basic Document Operations

--8<-- "examples/resources/editable_mdxl.py"

### XPath Selectors

EditableMDXL uses XPath expressions for precise element targeting:

```python
# Basic descendant search
await editor.update("//person", text_content="Updated bio")

# Attribute filtering
await editor.update("//person[@name='John']", attributes={"role": "candidate"})

# Complex expressions
await editor.update("//timeline/day[@date='2024-01-20']/event[1]",
                   text_content="Updated event description")
```

**XPath Patterns:**

| Pattern | Description | Example |
|---------|-------------|---------|
| `//element` | Find element anywhere | `//person` |
| `//element[@attr='value']` | Filter by attribute | `//person[@name='John']` |
| `//*[@attr]` | Any element with attribute | `//*[@private]` |
| `//parent/child` | Direct parent-child | `//timeline/day` |
| `//element[1]` | First matching element | `//event[1]` |
| `//element[last()]` | Last matching element | `//person[last()]` |

### Structure Modification

**Adding Elements:**

```python
# Append child to existing parent
await editor.append_child(
    parent_xpath="//person[@name='John']",
    element_tag="details",
    text_content="Personal information",
    attributes={"type": "personal"}
)

# Insert sibling elements
await editor.insert(
    reference_xpath="//timeline/day[@date='2024-01-20']",
    element_tag="day",
    position="before",
    text_content="Pre-event activities",
    attributes={"date": "2024-01-19"}
)
```

**Updating Elements:**

```python
# Update text content
await editor.update("//summary", text_content="Updated summary")

# Update attributes
await editor.update("//person[@name='John']",
                   attributes={"role": "active", "status": "verified"})

# Update YAML data blocks
await editor.update("//config[@yaml]",
                   data={"database_url": "updated_connection"})

# Replace specific text
await editor.replace_text("//document",
                         old_text="draft", new_text="final",
                         all_occurrences=True)
```

**Removing Elements:**

```python
# Delete single element
await editor.delete("//person[@name='John']")

# Delete multiple elements
await editor.delete("//person[@role='former-candidate']", limit=-1)
```

### Citation Management

EditableMDXL automatically manages citations and references:

```python
# Citations in content are normalized to markdown format
await editor.update("//summary",
    text_content="Key findings [!CITE_1!] show trends [!CITE_2!]")
# Becomes: "Key findings [1] show trends [2]"
# With reference block: "[1]: https://source1.com\n[2]: https://source2.com"
```

**Citation Features:**

- **Global to Local**: Converts `[!CITE_X!]` to sequential `[N]` numbering
- **Reference Blocks**: Automatically appends `[N]: URL` definitions
- **Deduplication**: Removes duplicate reference blocks
- **Normalization**: Cleans up spacing and formatting

### Content Filtering

MDXL supports LLM-optimized content filtering:

```python
# Read filtered content (removes private elements and citations)
content = await editor.read()

# Access raw MDXL for full content
full_content = editor.state.outer_text
```

**Filter Operations:**

```python
# Remove private elements
filtered = mdxl.without("//*[@private]", ".//citations")

# LLM-optimized content
llm_content = mdxl.llm_outer_text  # Pre-filtered for LLM consumption
```

## MDXL Core

MDXL (Markdown XML) provides a structured document format combining XML's precision with Markdown's readability.

### Document Structure

```xml
<?mdxl version="2"?>
<root>
  <project name="Good Agent">
    <description>AI agent framework</description>
    <timeline>
      <event date="2024-01-01">Project started</event>
      <event date="2024-03-15">First release</event>
    </timeline>
  </project>

  <!-- YAML data blocks -->
  <config yaml>
database_url: postgres://localhost/db
debug: true
  </config>
</root>
```

### Navigation and Selection

```python
from good_agent.core.mdxl import MDXL

# Parse document
mdxl = MDXL(xml_content)

# XPath navigation
project = mdxl.select("//project")
events = mdxl.select_all("//event")

# Array-like access
first_event = mdxl.select("//timeline")[0]

# Attribute access
project_name = mdxl.select("//project").get("name")
```

### YAML Data Blocks

Elements with `yaml` attribute are treated as YAML data containers:

```python
# Access YAML data
config = mdxl.select("//config[@yaml]")
database_url = config.data.database_url

# Update YAML data
config.data.debug = False
config.data.new_setting = "value"

# Data is automatically serialized back to YAML text
```

### Document Operations

**Immutable Operations:**

```python
# Create filtered copy
public_doc = mdxl.without("//*[@private]", ".//internal")

# Deep copy
backup = mdxl.copy()
```

**Mutable Operations:**

```python
# Add elements
new_event = mdxl.append("event", text="New milestone", date="2024-06-01")

# Modify structure
mdxl.insert(0, "metadata", text="Document info")
mdxl.remove(2)  # Remove third child
mdxl.replace(1, "updated-element", text="Replacement")
```

### Serialization

```python
# Standard XML output
xml_string = mdxl.outer

# Pretty-printed with MDXL formatting
formatted = mdxl.to_string(pretty=True, mdxl_format=True)

# Include version header
versioned = mdxl.to_string(include_version=True)

# Filtered for LLM consumption
llm_safe = mdxl.llm_outer_text
```

## Advanced Patterns

### Custom Resource Types

Extend `StatefulResource` for domain-specific editing:

```python
from good_agent.resources import StatefulResource
from good_agent import tool
import json

class ConfigResource(StatefulResource[dict]):
    def __init__(self, config_path: str):
        super().__init__(name=f"config:{config_path}")
        self.config_path = config_path

    async def initialize(self) -> None:
        with open(self.config_path, 'r') as f:
            self.state = json.load(f)

    async def persist(self) -> None:
        with open(self.config_path, 'w') as f:
            json.dump(self.state, f, indent=2)

    @tool
    async def get_setting(self, key: str) -> str:
        """Get configuration setting."""
        return str(self.state.get(key, "Not found"))

    @tool
    async def update_setting(self, key: str, value: str) -> str:
        """Update configuration setting."""
        self.state[key] = value
        return f"Updated {key}"

    @tool
    async def list_settings(self) -> str:
        """List all configuration keys."""
        return "\n".join(f"- {key}: {value}" for key, value in self.state.items())
```

### Multi-Resource Workflows

Chain multiple resources for complex editing workflows:

```python
async def update_project_config(agent: Agent):
    # Load YAML configuration
    yaml_content = "database:\n  host: localhost\n  port: 5432"
    yaml_editor = EditableYAML(yaml_content, name="config")

    # Load MDXL documentation
    doc_content = "<project><name>My App</name></project>"
    mdxl_editor = EditableMDXL(MDXL(doc_content), name="docs")

    # Update configuration
    async with yaml_editor(agent):
        await agent.call("Update the database port to 3306")

    # Update documentation
    async with mdxl_editor(agent):
        await agent.call("Add a description: 'Web application with MySQL'")

    # Access final states
    updated_config = yaml_editor.state
    updated_docs = mdxl_editor.state.outer_text
```

### Validation Workflows

Implement complex validation chains:

```python
def validate_config(config_dict: dict) -> tuple[bool, list[str]]:
    errors = []

    # Required fields
    required = ["database", "api_key", "debug"]
    for field in required:
        if field not in config_dict:
            errors.append(f"Missing required field: {field}")

    # Type validation
    if "port" in config_dict:
        try:
            port = int(config_dict["port"])
            if not (1 <= port <= 65535):
                errors.append("Port must be between 1 and 65535")
        except (ValueError, TypeError):
            errors.append("Port must be a valid integer")

    return len(errors) == 0, errors

# Use with EditableYAML
editor = EditableYAML(yaml_content, validator=validate_config)
```

### Performance Optimization

**Batch Operations:**

```python
# Use patch operations for multiple changes
ops = [
    {"op": "add", "path": "new_section", "value": {"enabled": True}},
    {"op": "merge", "path": "existing", "value": {"updated": "2024-01-01"}},
    {"op": "remove", "path": "deprecated"}
]

result = await editor.patch(ops, validate=True)
if result["ok"]:
    print(f"Applied {len(result['applied'])} operations")
```

**Selective Reading:**

```python
# Read specific sections only
config_section = await editor.get("database.config")

# Read with line limits for large files
first_100_lines = await editor.read(start_line=1, num_lines=100)
```

### Error Handling

Resources provide comprehensive error reporting:

```python
# Validation failures include details
result = await editor.set("invalid.path", {"data": "value"}, validate=True)
if result.startswith("ERROR:"):
    print(f"Validation failed: {result}")
    # State automatically rolled back

# XPath errors provide guidance
update_result = await mdxl_editor.update("//nonexistent", text_content="test")
# Returns: "No elements found for XPath: //nonexistent. Element must exist..."
```

## Integration Examples

### Agent Component Integration

```python
from good_agent import Agent, AgentComponent
from good_agent.resources import EditableYAML

class ConfigurationComponent(AgentComponent):
    def __init__(self, config_path: str):
        super().__init__()
        self.config_path = config_path
        self.editor = None

    async def install(self, agent: Agent):
        await super().install(agent)

        # Load configuration resource
        with open(self.config_path, 'r') as f:
            yaml_content = f.read()

        self.editor = EditableYAML(yaml_content, name="app-config")

        # Add configuration management context
        agent.context["config_editor"] = self.editor

    @property
    def config_resource(self) -> EditableYAML:
        return self.editor

# Usage
async with Agent("Configuration manager") as agent:
    config_component = ConfigurationComponent("app.yaml")
    await config_component.install(agent)

    # Access configuration resource
    async with agent.context["config_editor"](agent):
        response = await agent.call("Update the API timeout to 30 seconds")
```

### Streaming Integration

Resources work seamlessly with streaming execution:

```python
from good_agent import Agent
from good_agent.resources import EditableMDXL
from good_agent.core.mdxl import MDXL

async def stream_document_updates():
    doc = MDXL("<document><title>Draft</title></document>")
    editor = EditableMDXL(doc, name="article")

    async with Agent("Technical writer") as agent:
        async with editor(agent):
            agent.append("Expand this document with technical details")

            async for message in agent.execute():
                if hasattr(message, 'tool_name') and message.tool_name:
                    print(f"🛠️ {message.tool_name}: {message.content[:100]}...")
                elif hasattr(message, 'content'):
                    print(f"📝 {message.content[:100]}...")

    # Document updated through resource tools
    final_doc = editor.state.outer_text
    print(f"Final document: {len(final_doc)} characters")
```

## Testing Resources

### Unit Testing

```python
import pytest
from good_agent.resources import EditableYAML

@pytest.mark.asyncio
async def test_yaml_validation():
    def validator(doc: dict) -> tuple[bool, list[str]]:
        if "required_field" not in doc:
            return False, ["Missing required_field"]
        return True, []

    editor = EditableYAML("optional: value", validator=validator)
    await editor.initialize()

    # Should fail validation
    result = await editor.set("new_field", "value", validate=True)
    assert result.startswith("ERROR:")

    # Should pass after adding required field
    await editor.set("required_field", "present", validate=False)
    result = await editor.set("new_field", "value", validate=True)
    assert result == "ok"
```

### Integration Testing

```python
@pytest.mark.asyncio
async def test_resource_agent_integration():
    from good_agent import Agent
    from good_agent.resources import EditableYAML

    editor = EditableYAML("count: 0", name="counter")

    async with Agent("You count things") as agent:
        async with editor(agent):
            response = await agent.call("Increment the count to 5")

    # Verify the change was applied
    assert editor.state.count == 5
```

## Best Practices

### 1. Resource Naming

Use descriptive names that indicate the resource's purpose and scope:

```python
# Good
config_editor = EditableYAML(content, name="app-config")
docs_editor = EditableMDXL(mdxl, name="project-docs")

# Avoid
editor1 = EditableYAML(content, name="yaml")  # Too generic
```

### 2. Validation Strategy

Implement validation that provides actionable feedback:

```python
def comprehensive_validator(doc: dict) -> tuple[bool, list[str]]:
    errors = []
    warnings = []

    # Check required structure
    if "metadata" not in doc:
        errors.append("Missing metadata section")

    # Check optional but recommended fields
    if doc.get("version") is None:
        warnings.append("Consider adding version field")

    # Return errors (warnings don't fail validation)
    return len(errors) == 0, errors
```

### 3. Error Recovery

Plan for validation failures and provide recovery paths:

```python
# Attempt update with validation
result = await editor.set("config.timeout", new_value, validate=True)

if result.startswith("ERROR:"):
    # Try with relaxed validation
    print(f"Validation failed: {result}")
    result = await editor.set("config.timeout", fallback_value, validate=False)
    print("Used fallback value")
```

### 4. Context Management

Use resource contexts judiciously to avoid tool pollution:

```python
# Good - Focused resource usage
async with config_editor(agent):
    # Only configuration tools available
    await agent.call("Update database settings")

# Resume normal agent capabilities outside context
response = await agent.call("What's the weather like?")
```

### 5. Performance Considerations

- Use batch operations (`patch`) for multiple changes
- Implement selective reading for large documents
- Cache resource instances when used repeatedly
- Consider lazy initialization for expensive resources

```python
# Efficient batch updates
operations = [
    {"op": "merge", "path": "database", "value": updated_db_config},
    {"op": "add", "path": "cache", "value": cache_settings},
    {"op": "remove", "path": "deprecated_settings"}
]

result = await editor.patch(operations, validate=True)
```

This comprehensive resource system enables powerful document editing workflows while maintaining data consistency and providing rich integration with the Good Agent framework.
