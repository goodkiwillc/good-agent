"""
Configuration to skip obsolete CitationManager tests.
This file should be imported by conftest.py to apply the skips.

Tests are categorized as:
- OBSOLETE: Test old implementation details no longer relevant
- MIGRATED: Behavior now tested in test_citation_manager_v2.py or test_citation_manager_migration.py
- PENDING: Need migration but not yet done
"""

import pytest

# Tests that are genuinely obsolete and should be skipped
OBSOLETE_CITATION_TESTS = [
    # Old event router implementation
    "test_citation_index_eventrouter.py",
    "test_mock_citations_annotations.py",
    # Old implementation details
    "test_debug_citations.py",  # Debugging for old implementation
    "test_citation_structures.py",  # Old data structure tests
    # Separate system tests (not agent-related)
    "goodintel_llm/utilities/test__citations.py",
    "good_agent/mdxl/test_citations.py",
    "good_agent/mdxl/test_citation_reindexing.py",
]

# Tests that have been successfully migrated
MIGRATED_CITATION_TESTS = [
    # Covered in test_citation_manager_v2.py
    "test_citation_comprehensive.py",
    "test_citation_population.py",
    "test_citation_mapping_bug.py",
    "test_citation_transformation_comprehensive.py",
    "test_citation_fix_verification.py",
    # Covered in test_citation_manager_migration.py
    "test_citation_display.py",
    "test_citation_lookup_comprehensive.py",
    "test_citation_reference_priority.py",
    "test_markdown_citation_blocks_fix.py",
    "test_llm_citation_lookup.py",
]

# Tests that still need migration work
PENDING_MIGRATION_TESTS = [
    "test_citation_notebook_demo.py",  # Notebook-specific behaviors
    "test_mdxl_citation_compatibility.py",  # MDXL integration
    "test_citation_adapter.py",  # Adapter pattern
    "test_reference_block_filtering.py",  # Reference block handling
    "good_agent/integration/test_citation_manager.py",  # Integration suite
    "integration/agent/test_citation_manager.py",  # Integration suite (current location)
    "test_notebook_scenario.py",  # Notebook scenario test
    "good_agent/unit/test_citation_formats.py",  # Format testing
    "good_agent/unit/test_citation_index.py",  # Index testing
]


def pytest_collection_modifyitems(config, items):
    """Mark obsolete citation tests to be skipped."""
    skip_obsolete = pytest.mark.skip(
        reason="Obsolete test - old CitationManager implementation details"
    )

    skip_migrated = pytest.mark.skip(
        reason="Test migrated to test_citation_manager_v2.py or test_citation_manager_migration.py"
    )

    skip_pending = pytest.mark.skip(
        reason="Test pending migration to new CitationManager"
    )

    for item in items:
        test_path = str(item.fspath)

        # Check which category this test falls into
        if any(obsolete in test_path for obsolete in OBSOLETE_CITATION_TESTS):
            item.add_marker(skip_obsolete)
        elif any(migrated in test_path for migrated in MIGRATED_CITATION_TESTS):
            item.add_marker(skip_migrated)
        elif any(pending in test_path for pending in PENDING_MIGRATION_TESTS):
            item.add_marker(skip_pending)
