# Migration Guide

This guide helps you migrate your code to the refactored good-agent library.

## Table of Contents

- [Phase 1: Import Path Changes](#phase-1-import-path-changes)
- [Phase 2: Package Restructuring](#phase-2-package-restructuring)
- [Phase 3: Event Router Reliability & Migration Completion](#phase-3-event-router-reliability--migration-completion)
- [Automated Migration](#automated-migration)
- [Troubleshooting](#troubleshooting)

---

## Phase 1: Import Path Changes

**Status**: Completed (as of 2025-11-11, commit bd403b8)

**Breaking Changes**: Import paths for wrapper modules have changed.

### What Changed

The library eliminated duplicate wrapper modules in `utilities/` in favor of canonical implementations in `core/`. All wrapper modules have been deleted.

### Required Changes

Update your imports from `utilities.*` to `core.*`:

| Old Import (❌ Removed) | New Import (✅ Use This) |
|------------------------|-------------------------|
| `from good_agent.utilities.event_router import ...` | `from good_agent.core.event_router import ...` |
| `from good_agent.utilities.ulid_monotonic import ...` | `from good_agent.core.ulid_monotonic import ...` |
| `from good_agent.utilities.signal_handler import ...` | `from good_agent.core.signal_handler import ...` |
| `from good_agent.utilities.text import ...` | `from good_agent.core.text import ...` |
| `from good_agent.models import ...` | `from good_agent.core.models import ...` |
| `from good_agent.types import ...` | `from good_agent.core.types import ...` |

### Automated Migration Script

Run this script to automatically update all imports in your project:

```bash
#!/bin/bash
# Save as: migrate_phase1.sh

echo "Migrating imports from utilities.* to core.*..."

# Find all Python files in your project
find . -name "*.py" -type f | while read -r file; do
    # Skip virtual environments and build directories
    if [[ $file == *".venv"* ]] || [[ $file == *"build"* ]] || [[ $file == *"dist"* ]]; then
        continue
    fi

    # Update imports
    sed -i '' 's/from good_agent\.utilities\.event_router/from good_agent.core.event_router/g' "$file"
    sed -i '' 's/from good_agent\.utilities\.ulid_monotonic/from good_agent.core.ulid_monotonic/g' "$file"
    sed -i '' 's/from good_agent\.utilities\.signal_handler/from good_agent.core.signal_handler/g' "$file"
    sed -i '' 's/from good_agent\.utilities\.text/from good_agent.core.text/g' "$file"
    sed -i '' 's/from good_agent\.models/from good_agent.core.models/g' "$file"
    sed -i '' 's/from good_agent\.types/from good_agent.core.types/g' "$file"

    # Also update import statements with 'import' syntax
    sed -i '' 's/import good_agent\.utilities\.event_router/import good_agent.core.event_router/g' "$file"
    sed -i '' 's/import good_agent\.utilities\.ulid_monotonic/import good_agent.core.ulid_monotonic/g' "$file"
    sed -i '' 's/import good_agent\.utilities\.signal_handler/import good_agent.core.signal_handler/g' "$file"
    sed -i '' 's/import good_agent\.utilities\.text/import good_agent.core.text/g' "$file"
done

echo "Migration complete! Please verify changes with:"
echo "  git diff"
echo "  pytest"
```

### Manual Verification

After running the migration script:

1. **Search for old imports**:
   ```bash
   rg "from good_agent.utilities.(event_router|ulid_monotonic|signal_handler|text)"
   rg "from good_agent.models"
   rg "from good_agent.types"
   ```

   If any results appear, update them manually.

2. **Run your tests**:
   ```bash
   pytest
   ```

3. **Check for import errors**:
   ```bash
   python -c "import good_agent; print('✓ Import successful')"
   ```

---

## Phase 2: Package Restructuring

**Status**: Nearly Complete (as of 2025-11-14, commits 64e66db through ccddd0a)

**Breaking Changes**: ❌ None - Full backward compatibility maintained

### What Changed

Phase 2 split large files into focused modules:

1. **Agent Package** - `agent.py` → `agent/` package with manager classes
2. **Messages Package** - `messages.py` → `messages/` package
3. **Model Package** - `model/llm.py` split into focused modules

### Good News: No Code Changes Required! ✅

All Phase 2 changes are internal reorganization with **full backward compatibility**:

- ✅ Public APIs unchanged
- ✅ All imports work exactly as before
- ✅ `from good_agent import Agent` - still works
- ✅ `from good_agent.messages import Message, UserMessage` - still works
- ✅ `from good_agent.model.llm import LanguageModel` - still works

### How Backward Compatibility Works

Each refactored package maintains a `__init__.py` that re-exports all public APIs:

```python
# messages/__init__.py
from .base import Message, Annotation
from .roles import SystemMessage, UserMessage, AssistantMessage, ToolMessage
from .message_list import MessageList
from .filtering import FilteredMessageList
# ... etc

# Your code continues to work:
from good_agent.messages import Message, UserMessage  # ✅ Works!
```

### Optional: Using New Internal Structure

If you want to use the new internal structure (not required):

```python
# Old (still works):
from good_agent.messages import MessageList

# New (also works, more specific):
from good_agent.messages.message_list import MessageList

# Old (still works):
from good_agent.model.llm import LanguageModel

# New (also works, more specific):
from good_agent.model.llm import LanguageModel
from good_agent.model.capabilities import ModelCapabilities
from good_agent.model.formatting import MessageFormatter
```

### What If You Were Using Internal APIs?

If you were directly importing from internal modules (unlikely), you may need to update:

#### Agent Internal Managers

```python
# If you were using (unlikely):
from good_agent.agent import Agent
agent._resolve_pending_tool_calls()  # ❌ Method moved

# Update to:
await agent._tool_executor.resolve_pending_tool_calls()  # ✅
```

**Note**: Internal methods starting with `_` are not part of the public API and may change.

#### Message Internals

```python
# If you were using:
from good_agent.messages import MessageFactory  # ✅ Still works (re-exported)

# Or use specific module:
from good_agent.messages.utilities import MessageFactory  # ✅ Also works
```

#### Model Internals

```python
# If you were using:
from good_agent.model.llm import MessageFormatter  # ❌ Moved

# Update to:
from good_agent.model.formatting import MessageFormatter  # ✅
```

---

## Phase 3: Event Router Reliability & Migration Completion

**Status**: Completed (2025-11-16, commits 4773a22 → latest)

**Breaking Changes**: ❌ None – public API remains identical

### What Changed

- The legacy monolithic module `src/good_agent/core/event_router.py` has been removed. The `good_agent.core.event_router` **package** (and its `__init__.py` re-exports) is now the canonical import path.
- `EventRouter` internally uses a dedicated `_handler_registry` (thread-safe `HandlerRegistry`) and `SyncBridge` for async/sync coordination. Private fields like `_events`, `_tasks`, `_thread_pool`, etc. are retained only for backward-compatible access.
- Docstrings were trimmed and now point to executable samples in `examples/event_router/`.
- New reliability-focused test suites cover registration, predicates, race conditions, concurrency, and sync bridge behavior.

### Required Changes

- **Most users do nothing.** Existing imports such as `from good_agent.core.event_router import EventRouter` continue to work.
- **If you referenced `event_router.py` directly** (e.g., `import good_agent.core.event_router as er_module`): keep the import, but be aware it now resolves to the package, not a single file. No code changes are needed.
- **If you were poking private internals**:
  - `_events` is still available but read-only; treat it as diagnostic-only.
  - The old `_registry` attribute no longer exists. Update any private tooling to use `_handler_registry` (new name) if absolutely necessary.
  - Avoid reaching into `_sync_bridge` unless you are extending the router itself.
- **Custom subclasses overriding `_registry`**: rename your attribute (e.g., `_template_registry`) to avoid clobbering the base class handler registry.

### Verification Steps

1. Ensure your code does not assign to `router._registry`. If it does, rename your attribute.
2. Run your test suite; concurrency behavior should be more deterministic thanks to the new locking strategy.
3. Optional sanity checks:
   ```python
   from good_agent.core.event_router import EventRouter

   router = EventRouter()
   assert router._events == router._handler_registry._events
   ```

---

## Automated Migration

### Complete Migration Script (Phase 1 + Phase 2)

```bash
#!/bin/bash
# Complete migration script for good-agent refactoring
# Covers Phase 1 import changes (Phase 2 is backward compatible)

set -e

echo "=== Good-Agent Migration Script ==="
echo ""

# Check if ripgrep is installed
if ! command -v rg &> /dev/null; then
    echo "⚠️  ripgrep (rg) not found. Install with: brew install ripgrep"
    echo "   Falling back to grep (slower)..."
    USE_RG=false
else
    USE_RG=true
fi

echo "Step 1: Backing up your code..."
timestamp=$(date +%Y%m%d_%H%M%S)
backup_dir="good_agent_migration_backup_${timestamp}"
mkdir -p "$backup_dir"
cp -r . "$backup_dir/" 2>/dev/null || true
echo "✓ Backup created: $backup_dir"
echo ""

echo "Step 2: Migrating Phase 1 import paths..."
find . -name "*.py" -type f | while read -r file; do
    # Skip virtual environments, build directories, and backup
    if [[ $file == *".venv"* ]] || [[ $file == *"build"* ]] || \
       [[ $file == *"dist"* ]] || [[ $file == *"$backup_dir"* ]]; then
        continue
    fi

    # Update imports (macOS version with -i '')
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' 's/from good_agent\.utilities\.event_router/from good_agent.core.event_router/g' "$file"
        sed -i '' 's/from good_agent\.utilities\.ulid_monotonic/from good_agent.core.ulid_monotonic/g' "$file"
        sed -i '' 's/from good_agent\.utilities\.signal_handler/from good_agent.core.signal_handler/g' "$file"
        sed -i '' 's/from good_agent\.utilities\.text/from good_agent.core.text/g' "$file"
        sed -i '' 's/from good_agent\.models/from good_agent.core.models/g' "$file"
        sed -i '' 's/from good_agent\.types/from good_agent.core.types/g' "$file"
    else
        # Linux
        sed -i 's/from good_agent\.utilities\.event_router/from good_agent.core.event_router/g' "$file"
        sed -i 's/from good_agent\.utilities\.ulid_monotonic/from good_agent.core.ulid_monotonic/g' "$file"
        sed -i 's/from good_agent\.utilities\.signal_handler/from good_agent.core.signal_handler/g' "$file"
        sed -i 's/from good_agent\.utilities\.text/from good_agent.core.text/g' "$file"
        sed -i 's/from good_agent\.models/from good_agent.core.models/g' "$file"
        sed -i 's/from good_agent\.types/from good_agent.core.types/g' "$file"
    fi
done
echo "✓ Import paths updated"
echo ""

echo "Step 3: Verifying migration..."
if [ "$USE_RG" = true ]; then
    old_imports=$(rg "from good_agent\.utilities\.(event_router|ulid_monotonic|signal_handler|text)" --count-matches 2>/dev/null | wc -l)
else
    old_imports=$(grep -r "from good_agent\.utilities\." --include="*.py" . 2>/dev/null | wc -l)
fi

if [ "$old_imports" -gt 0 ]; then
    echo "⚠️  Warning: Found $old_imports files with old import paths"
    echo "   Run this to see them:"
    if [ "$USE_RG" = true ]; then
        echo "     rg 'from good_agent.utilities.(event_router|ulid_monotonic|signal_handler|text)'"
    else
        echo "     grep -r 'from good_agent.utilities.' --include='*.py' ."
    fi
else
    echo "✓ No old import paths found"
fi
echo ""

echo "Step 4: Phase 2 check..."
echo "ℹ️  Phase 2 is backward compatible - no code changes needed"
echo "   Your existing imports will continue to work"
echo ""

echo "=== Migration Complete ==="
echo ""
echo "Next steps:"
echo "  1. Review changes: git diff"
echo "  2. Run tests: pytest"
echo "  3. Commit changes: git commit -am 'Migrate to good-agent refactored imports'"
echo ""
echo "If anything went wrong, restore from: $backup_dir"
```

Save the script as `migrate_good_agent.sh`, make it executable, and run:

```bash
chmod +x migrate_good_agent.sh
./migrate_good_agent.sh
```

---

## Troubleshooting

### Import Errors After Migration

**Error**: `ImportError: cannot import name 'X' from 'good_agent.utilities'`

**Solution**: The wrapper modules were removed. Update your import:
```python
# Change from:
from good_agent.utilities.event_router import EventRouter

# To:
from good_agent.core.event_router import EventRouter
```

### Tests Failing After Migration

1. **Check for old imports**:
   ```bash
   rg "from good_agent.utilities"
   ```

2. **Verify good-agent is installed**:
   ```bash
   pip show good-agent
   # or
   uv pip list | grep good-agent
   ```

3. **Clear Python cache**:
   ```bash
   find . -type d -name __pycache__ -exec rm -r {} +
   find . -type f -name "*.pyc" -delete
   ```

### Type Checking Errors

If you're using mypy and seeing type errors after migration:

```bash
# Clear mypy cache
rm -rf .mypy_cache/

# Run mypy again
mypy src/
```

### Still Having Issues?

1. **Check the CHANGELOG**: Review [CHANGELOG.md](CHANGELOG.md) for detailed changes
2. **Check the spec**: See [.spec/refactoring-plan.md](.spec/refactoring-plan.md) for technical details
3. **Restore from backup**: Use the backup created by the migration script

---

## Summary

### Phase 1 ✅
- **Action Required**: Update import paths from `utilities.*` to `core.*`
- **Breaking**: Yes (import paths changed)
- **Automated**: Yes (use migration script above)

### Phase 2 ✅
- **Action Required**: None (fully backward compatible)
- **Breaking**: No
- **Automated**: N/A (no changes needed)

### Future Phases
- Phase 3-6 migration guides will be added as those phases complete
- Watch the CHANGELOG for updates
