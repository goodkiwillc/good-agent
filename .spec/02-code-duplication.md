# Code Duplication Issues

## Overview

The codebase exhibits severe code duplication, primarily between `utilities/` and `core/` directories. This creates maintenance burden and confusion about canonical implementations.

---

## 1. Complete Module Duplication

### A. event_router.py

**Location 1:** `core/event_router.py` (2,000+ lines)  
**Location 2:** `utilities/event_router.py` (3 lines wrapper)

```python
# utilities/event_router.py - ENTIRE FILE
from good_agent.core.event_router import *  # noqa: F401,F403
from good_agent.core.event_router import __all__ as __all__  # re-export
```

**Used in:**
- `agent.py`: `from good_agent.utilities.event_router import ...`
- `components/component.py`: `from good_agent.core.event_router import ...`
- `extensions/citations/manager.py`: `from good_agent.utilities.event_router import ...`
- `extensions/logfire_tracking.py`: `from good_agent.utilities.event_router import ...`

**Issue:** Inconsistent imports create confusion about source of truth.

**Fix:** Delete `utilities/event_router.py`, use `core.event_router` everywhere.

---

### B. ulid_monotonic.py

**Location 1:** `core/ulid_monotonic.py` (250 lines)  
**Location 2:** `utilities/ulid_monotonic.py` (2 lines wrapper)

```python
# utilities/ulid_monotonic.py - ENTIRE FILE
from good_agent.core.ulid_monotonic import *  # noqa: F401,F403
from good_agent.core.ulid_monotonic import __all__ as __all__  # re-export
```

**Used in:**
- `agent.py`: `from good_agent.utilities.ulid_monotonic import create_monotonic_ulid`
- `messages.py`: `from good_agent.core.ulid_monotonic import create_monotonic_ulid`

**Issue:** Split usage between wrapper and direct import.

**Fix:** Delete wrapper, standardize on `core.ulid_monotonic`.

---

### C. signal_handler.py

**Location 1:** `core/signal_handler.py` (250 lines)  
**Location 2:** `utilities/signal_handler.py` (5 lines wrapper)

```python
# utilities/signal_handler.py
from good_agent.core.signal_handler import *  # noqa: F401,F403
from good_agent.core.signal_handler import (
    __all__ as __all__,
)  # re-export
```

**Fix:** Delete wrapper, use `core.signal_handler`.

---

### D. text.py

**Location 1:** `core/text.py` (700 lines)  
**Location 2:** `utilities/text.py` (700 lines)

**Status:** IDENTICAL FILES!

```python
# Both files start with identical content:
import os
import quopri
import re
import sys
import textwrap
import unicodedata
from typing import Final

import numpy as np

DEFAULT_WRAP_WIDTH = 70  # same as textwrap's default

UNICODE_BULLETS: Final[list[str]] = [
    "\u0095",
    "\u2022",
    # ... etc
]

class StringFormatter:
    # ... identical implementation
```

**Issue:** Complete duplication of 700 lines of text manipulation code.

**Fix:** Delete one, keep canonical version.

---

## 2. Partial Duplication

### A. Templating System

The template system is duplicated across multiple locations:

**Location 1:** `core/templating/` (primary implementation)
```
core/templating/
├── __init__.py
├── _core.py (600+ lines)
├── _environment.py (400+ lines)
├── _extensions.py (300+ lines)
├── _filters.py (100+ lines)
└── type_safety_patterns.py (200+ lines)
```

**Location 2:** `templating/` (wrapper + additions)
```
templating/
├── __init__.py (re-exports from core)
├── core.py (600+ lines, TemplateManager component)
├── environment.py
├── storage.py
├── index.py
└── injection.py
```

**Location 3:** `core/templates.py` (50 lines of template utilities)

**Location 4:** Template functionality in `core/models/renderable.py`

**Analysis:**

```python
# templating/__init__.py
from good_agent.core.templating import (  # re-export for compatibility
    Template,
    AbstractTemplate,
    TemplateRegistry,
    # ... etc
)

# But templating/core.py ALSO has TemplateManager class (600 lines)
# which is an AgentComponent wrapping core functionality
```

**Issues:**
1. Unclear which is canonical
2. `TemplateManager` (component) vs template core logic split awkwardly
3. Re-exports create confusion
4. Template-related code in 4 different locations

**Fix:**
```
Consolidate to:
src/good_agent/
└── templating/
    ├── __init__.py (public API)
    ├── core.py (Template, AbstractTemplate)
    ├── environment.py (Jinja2 setup)
    ├── manager.py (TemplateManager component)
    ├── filters.py
    └── extensions.py

Remove: core/templating/, core/templates.py
Integrate: renderable.py template logic
```

---

### B. Models Module

**Location 1:** `models/` (wrapper)
```python
# models/__init__.py - ENTIRE FILE
from good_agent.core.models import *  # noqa: F401,F403
from good_agent.core.models import __all__ as __all__  # re-export public API
```

**Location 2:** `core/models/` (actual implementation)
```
core/models/
├── __init__.py
├── base.py
├── protocols.py
├── renderable.py
├── serializers.py
├── mixins.py
├── application.py
└── reference.py
```

**Issue:** Another thin wrapper creating indirection.

**Fix:** Delete `models/__init__.py` wrapper, import from `core.models` directly.

---

### C. Types Module

**Location 1:** `types/` (wrapper)
```python
# types/__init__.py - ENTIRE FILE
from good_agent.core.types import *  # noqa: F401,F403
from good_agent.core.types import __all__ as __all__  # re-export public API
```

**Location 2:** `core/types/` (actual implementation)
```
core/types/
├── __init__.py
├── _base.py
├── _dates.py
├── _functional.py
├── _json.py
├── _uuid.py
└── _web.py
```

**Issue:** Yet another thin wrapper.

**Fix:** Delete `types/` wrapper, use `core.types` directly.

---

## 3. Functional Duplication

### A. XML/MDXL Processing

**Location 1:** `core/mdxl.py` (full MDXL implementation)
**Location 2:** `utilities/lxml.py` (XML utilities)
**Location 3:** `core/models/application.py` (XML extraction functions)
**Location 4:** `core/models/renderable.py` (more XML utilities)

```python
# utilities/lxml.py
def extract_first_level_xml(xml_string: str) -> str:
    """Extract first level XML elements."""
    # ... implementation

# core/models/application.py
def extract_first_level_xml(xml_string):  # Same name, similar function!
    """Extract first level tags from XML."""
    # ... slightly different implementation

# core/models/renderable.py
def _extract_inner_tags(content: str) -> str:
    """Extract content from section tags."""
    # ... similar functionality
```

**Issue:** Multiple functions doing similar XML extraction in different modules.

**Fix:** Consolidate XML utilities in one module, share implementations.

---

### B. String Formatting

String formatting utilities scattered across:
- `core/text.py`: `StringFormatter` class (700 lines)
- `utilities/text.py`: Identical copy
- `core/templating/_filters.py`: Formatting filters
- Various modules: inline string manipulation

**Fix:** Single canonical string utilities module.

---

## 4. Duplication Statistics

| Pattern | Occurrences | Total Duplicate Lines | Impact |
|---------|-------------|----------------------|--------|
| Thin wrapper re-exports | 4 modules | ~15 lines | High confusion |
| Complete file duplication | 1 (text.py) | ~700 lines | Critical |
| Template system split | 4 locations | ~2000 lines | High complexity |
| XML utilities | 4 locations | ~200 lines | Medium |
| Type definitions | Various | ~100 lines | Low |

**Total estimated duplicate/wrapper code: ~3000 lines**

---

## 5. Import Inconsistency Matrix

Analysis of where different modules import common utilities:

| Module | event_router | ulid_monotonic | signal_handler | models | types |
|--------|-------------|---------------|---------------|---------|-------|
| agent.py | utilities | utilities | - | - | yes |
| components/component.py | core | - | - | - | - |
| messages.py | - | core | - | core | core |
| extensions/citations/manager.py | utilities | - | - | - | - |
| extensions/logfire_tracking.py | utilities | - | - | - | - |

**Observation:** No consistency in import paths even for identical functionality.

---

## 6. Recommended Consolidation Plan

### Phase 1: Remove Thin Wrappers (Low Risk, High Value)
1. Delete `utilities/event_router.py` → use `core.event_router`
2. Delete `utilities/ulid_monotonic.py` → use `core.ulid_monotonic`
3. Delete `utilities/signal_handler.py` → use `core.signal_handler`
4. Delete `models/__init__.py` wrapper → use `core.models`
5. Delete `types/__init__.py` wrapper → use `core.types`

**Effort:** 1 day  
**Complexity:** Low (mostly find-replace in imports)

### Phase 2: Resolve text.py Duplication (Low Risk)
1. Keep `core/text.py` as canonical
2. Delete `utilities/text.py`
3. Update imports

**Effort:** 2 hours  
**Complexity:** Low

### Phase 3: Consolidate Template System (Medium Risk)
1. Move template logic to unified location
2. Separate core templates from TemplateManager component
3. Remove redundant code
4. Update imports

**Effort:** 3-4 days  
**Complexity:** Medium (affects multiple modules)

### Phase 4: Consolidate XML Utilities (Low Risk)
1. Create canonical `utilities/xml.py` or `core/xml.py`
2. Consolidate all XML extraction functions
3. Update imports

**Effort:** 1 day  
**Complexity:** Low

---

## 7. Verification Strategy

After consolidation:

```bash
# Check for remaining wrappers
rg "from good_agent\.(utilities|core)\..* import \*"

# Check for import inconsistencies
rg "from good_agent\.(utilities|core)\.event_router"
rg "from good_agent\.(utilities|core)\.ulid_monotonic"

# Verify no duplicate implementations
fd -e py | xargs -I {} sh -c 'echo "=== {} ===" && wc -l {}'
```

---

## Impact Assessment

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Total Lines | ~35,000 | ~32,000 | -9% |
| Module Wrappers | 5 | 0 | -100% |
| Import Paths | Inconsistent | Consistent | ✅ |
| Canonical Sources | Unclear | Clear | ✅ |
| Developer Confusion | High | Low | ✅ |
