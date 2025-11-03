"""
CONTEXT: Core model infrastructure and domain entities for goodintel_core.
ROLE: Provide foundational model classes, domain entities, and utilities for data modeling,
      validation, serialization, and template rendering across the GoodIntel platform.
DEPENDENCIES:
  - pydantic: Core validation, serialization, and model infrastructure
  - good_common.utilities: Shared utilities for hashing, datetime conversion
  - lxml: XML processing for structured data extraction
  - jinja2: Template rendering engine for model output generation
ARCHITECTURE: Layered architecture with base classes → domain entities → specialized models.
              Includes rendering capabilities, type safety, and serialization patterns.
KEY EXPORTS:
  Base Classes:
  - GoodBase: Repository-wide base with consistent config and stable hashing
  - Identifiable: Base with auto-generated UUID primary keys
  - PrivateAttrBase: Base with validated private attributes support
  - Renderable: Template-based rendering with Jinja2 integration

  Domain Entities:
  - Person/Organization: Core entity models with profiles and validation
  - Content/Profile: Content and social media profile models
  - Position/ReferenceSource: Employment positions and source attribution
  - UserPosts: Profile and collected posts aggregation

  Application Models:
  - Document/Report: Structured document and report generation
  - Query/QueryResults: Query processing and result handling
  - IterableCollection: Collection management utilities

  Utilities:
  - ModelAllFields/Convertible: Model introspection and conversion utilities
  - Field validators/serializers: Data validation and transformation
USAGE PATTERNS:
  1) Extend base classes for consistent behavior across models
  2) Use domain entities for core business objects
  3) Apply Renderable for template-based output generation
  4) Leverage validation/serialization for data consistency
RELATED MODULES:
  - goodintel_core.types: Core type definitions used across models
  - goodintel_core.templating: Template system integration
  - goodintel_store.v3: Storage layer model usage patterns
"""

from pydantic import (
    ConfigDict,
    Field,
    PrivateAttr,
    computed_field,
    field_serializer,
    field_validator,
    model_serializer,
    model_validator,
    validate_call,
)

# template_loader
from .application import Document, IterableCollection, Query, QueryResults, Report
from .base import (
    GoodBase,
    Identifiable,
    PrivateAttrBase,
    PydanticBaseModel,
)
from .mixins import Convertible, ModelAllFields
from .renderable import Renderable

__all__ = [
    "GoodBase",
    # "template_loader",
    "computed_field",
    "ConfigDict",
    "Convertible",
    "Document",
    "field_serializer",
    "field_validator",
    "Field",
    "Identifiable",
    "IterableCollection",
    "model_serializer",
    "model_validator",
    "ModelAllFields",
    "PrivateAttr",
    "PrivateAttrBase",
    "PydanticBaseModel",
    "Query",
    "QueryResults",
    "Renderable",
    "Report",
    "validate_call",
]
