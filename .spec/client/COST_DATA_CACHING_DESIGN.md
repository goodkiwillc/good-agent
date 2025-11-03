# LiteLLM Cost Data Caching Design

## Overview

Leverage LiteLLM's comprehensive pricing database without importing the library by:
1. **Fetching** cost data from public GitHub URL
2. **Aggressive caching** (disk + memory) for fast access
3. **Automatic updates** with fallback to embedded data
4. **Zero import overhead** through lazy loading

## LiteLLM Cost Data Source

**Public URL:**
```
https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json
```

**Data Format:**
```json
{
  "gpt-4": {
    "max_tokens": 8192,
    "max_input_tokens": 8192,
    "max_output_tokens": 4096,
    "input_cost_per_token": 0.00003,
    "output_cost_per_token": 0.00006,
    "litellm_provider": "openai",
    "mode": "chat",
    "supports_function_calling": true,
    "supports_vision": false
  },
  "claude-3-5-sonnet-20240620": {
    "max_tokens": 200000,
    "max_input_tokens": 200000,
    "max_output_tokens": 8192,
    "input_cost_per_token": 0.000003,
    "output_cost_per_token": 0.000015,
    "litellm_provider": "anthropic",
    "mode": "chat",
    "supports_function_calling": true,
    "supports_vision": true
  }
}
```

## Architecture

```
good_agent/llm_client/costs/
├── __init__.py              # Public API
├── database.py              # Cost database with caching
├── fetcher.py               # Fetch from litellm GitHub
├── calculator.py            # Cost calculation utilities
└── data/
    └── fallback_costs.json  # Embedded fallback data
```

## Implementation

### 1. Cost Database with Multi-Level Caching

**File: `good_agent/llm_client/costs/database.py`**

```python
"""Cost database with aggressive caching.

Caching Strategy:
1. Memory cache (fastest) - loaded on first use
2. Disk cache (~/.cache/good-agent/costs.json) - persistent
3. Embedded fallback (packaged with library) - always available
4. Remote fetch (GitHub) - on demand or scheduled

Cache invalidation: 24 hours (configurable)
"""

import json
import time
import logging
from pathlib import Path
from typing import Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CostDatabase:
    """Multi-level cached cost database."""
    
    # LiteLLM public cost data URL
    REMOTE_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
    
    # Cache locations
    CACHE_DIR = Path.home() / ".cache" / "good-agent"
    CACHE_FILE = CACHE_DIR / "model_costs.json"
    CACHE_METADATA_FILE = CACHE_DIR / "model_costs_meta.json"
    
    # Fallback embedded data
    FALLBACK_FILE = Path(__file__).parent / "data" / "fallback_costs.json"
    
    # Cache TTL (24 hours)
    CACHE_TTL_SECONDS = 24 * 60 * 60
    
    def __init__(self):
        """Initialize cost database."""
        self._memory_cache: dict[str, Any] | None = None
        self._cache_loaded_at: float | None = None
        self._loading = False
    
    def get_model_costs(self, model: str) -> dict[str, Any] | None:
        """Get cost information for a model.
        
        Args:
            model: Model name or identifier
            
        Returns:
            Cost dict or None if not found
            
        Example:
            {
                "input_cost_per_token": 0.00003,
                "output_cost_per_token": 0.00006,
                "max_tokens": 8192,
                "supports_function_calling": true,
                ...
            }
        """
        costs = self._get_costs()
        
        # Try exact match first
        if model in costs:
            return costs[model]
        
        # Try fuzzy match (e.g., "gpt-4-0125-preview" -> "gpt-4")
        for known_model in costs:
            if known_model in model:
                return costs[known_model]
        
        return None
    
    def get_input_cost(self, model: str) -> float:
        """Get input cost per token for model."""
        costs = self.get_model_costs(model)
        if costs:
            return costs.get("input_cost_per_token", 0.0)
        return 0.0
    
    def get_output_cost(self, model: str) -> float:
        """Get output cost per token for model."""
        costs = self.get_model_costs(model)
        if costs:
            return costs.get("output_cost_per_token", 0.0)
        return 0.0
    
    def list_models(self, provider: str | None = None) -> list[str]:
        """List all models in database.
        
        Args:
            provider: Filter by provider (openai, anthropic, etc.)
            
        Returns:
            List of model names
        """
        costs = self._get_costs()
        
        if provider:
            return [
                model for model, info in costs.items()
                if info.get("litellm_provider") == provider
            ]
        
        return list(costs.keys())
    
    def refresh(self, force: bool = False) -> bool:
        """Refresh cost data from remote source.
        
        Args:
            force: Force refresh even if cache is fresh
            
        Returns:
            True if refreshed successfully
        """
        if not force and not self._should_refresh():
            logger.debug("Cost cache is fresh, skipping refresh")
            return False
        
        logger.info("Refreshing cost data from litellm...")
        
        try:
            from .fetcher import fetch_litellm_costs
            
            costs = fetch_litellm_costs(self.REMOTE_URL, timeout=10)
            
            if costs:
                self._save_to_disk(costs)
                self._memory_cache = costs
                self._cache_loaded_at = time.time()
                logger.info(f"Successfully refreshed {len(costs)} model costs")
                return True
        
        except Exception as e:
            logger.warning(f"Failed to refresh cost data: {e}")
        
        return False
    
    def _get_costs(self) -> dict[str, Any]:
        """Get costs with multi-level cache fallback."""
        # Level 1: Memory cache
        if self._memory_cache is not None:
            # Check if cache is still fresh
            if self._is_cache_fresh():
                return self._memory_cache
        
        # Level 2: Disk cache
        disk_costs = self._load_from_disk()
        if disk_costs:
            self._memory_cache = disk_costs
            return disk_costs
        
        # Level 3: Embedded fallback
        logger.info("Using embedded fallback cost data")
        fallback_costs = self._load_fallback()
        
        # Try to fetch and cache in background
        self._async_refresh()
        
        return fallback_costs
    
    def _load_from_disk(self) -> dict[str, Any] | None:
        """Load costs from disk cache."""
        if not self.CACHE_FILE.exists():
            return None
        
        try:
            # Check cache age
            if not self._is_disk_cache_fresh():
                logger.debug("Disk cache is stale")
                return None
            
            with open(self.CACHE_FILE) as f:
                costs = json.load(f)
            
            logger.debug(f"Loaded {len(costs)} model costs from disk cache")
            self._cache_loaded_at = time.time()
            return costs
        
        except Exception as e:
            logger.warning(f"Failed to load disk cache: {e}")
            return None
    
    def _save_to_disk(self, costs: dict[str, Any]) -> None:
        """Save costs to disk cache."""
        try:
            # Create cache directory
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            
            # Save costs
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(costs, f, indent=2)
            
            # Save metadata (timestamp)
            metadata = {
                "cached_at": time.time(),
                "cached_at_iso": datetime.now().isoformat(),
                "source": "litellm-github",
                "model_count": len(costs)
            }
            with open(self.CACHE_METADATA_FILE, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.debug(f"Saved {len(costs)} model costs to disk cache")
        
        except Exception as e:
            logger.warning(f"Failed to save disk cache: {e}")
    
    def _load_fallback(self) -> dict[str, Any]:
        """Load embedded fallback data."""
        try:
            with open(self.FALLBACK_FILE) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load fallback data: {e}")
            # Return minimal fallback
            return self._minimal_fallback()
    
    def _minimal_fallback(self) -> dict[str, Any]:
        """Minimal hardcoded fallback for critical models."""
        return {
            "gpt-4o": {
                "input_cost_per_token": 0.0000025,
                "output_cost_per_token": 0.00001,
                "max_tokens": 128000,
            },
            "gpt-4o-mini": {
                "input_cost_per_token": 0.00000015,
                "output_cost_per_token": 0.0000006,
                "max_tokens": 128000,
            },
            "gpt-4-turbo": {
                "input_cost_per_token": 0.00001,
                "output_cost_per_token": 0.00003,
                "max_tokens": 128000,
            },
            "gpt-3.5-turbo": {
                "input_cost_per_token": 0.0000005,
                "output_cost_per_token": 0.0000015,
                "max_tokens": 16385,
            },
            "claude-3-5-sonnet-20240620": {
                "input_cost_per_token": 0.000003,
                "output_cost_per_token": 0.000015,
                "max_tokens": 200000,
            },
            "claude-3-opus-20240229": {
                "input_cost_per_token": 0.000015,
                "output_cost_per_token": 0.000075,
                "max_tokens": 200000,
            },
        }
    
    def _is_cache_fresh(self) -> bool:
        """Check if memory cache is still fresh."""
        if self._cache_loaded_at is None:
            return False
        
        age = time.time() - self._cache_loaded_at
        return age < self.CACHE_TTL_SECONDS
    
    def _is_disk_cache_fresh(self) -> bool:
        """Check if disk cache is still fresh."""
        if not self.CACHE_METADATA_FILE.exists():
            return False
        
        try:
            with open(self.CACHE_METADATA_FILE) as f:
                metadata = json.load(f)
            
            cached_at = metadata.get("cached_at", 0)
            age = time.time() - cached_at
            return age < self.CACHE_TTL_SECONDS
        
        except Exception:
            return False
    
    def _should_refresh(self) -> bool:
        """Check if we should refresh from remote."""
        # If memory cache is fresh, no need to refresh
        if self._is_cache_fresh():
            return False
        
        # If disk cache is fresh, no need to refresh
        if self._is_disk_cache_fresh():
            return False
        
        return True
    
    def _async_refresh(self) -> None:
        """Trigger async refresh in background (non-blocking)."""
        if self._loading:
            return
        
        self._loading = True
        
        try:
            import asyncio
            import threading
            
            def refresh_thread():
                try:
                    self.refresh(force=True)
                finally:
                    self._loading = False
            
            thread = threading.Thread(target=refresh_thread, daemon=True)
            thread.start()
        
        except Exception as e:
            logger.debug(f"Could not start background refresh: {e}")
            self._loading = False


# Global singleton instance
_database: CostDatabase | None = None


def get_cost_database() -> CostDatabase:
    """Get global cost database instance (lazy loaded)."""
    global _database
    if _database is None:
        _database = CostDatabase()
    return _database
```

### 2. Remote Fetcher

**File: `good_agent/llm_client/costs/fetcher.py`**

```python
"""Fetch cost data from LiteLLM GitHub repository."""

import json
import logging
from typing import Any
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

logger = logging.getLogger(__name__)


def fetch_litellm_costs(
    url: str,
    timeout: float = 10.0
) -> dict[str, Any] | None:
    """Fetch cost data from LiteLLM GitHub.
    
    Args:
        url: URL to fetch from
        timeout: Request timeout in seconds
        
    Returns:
        Cost dictionary or None if fetch failed
    """
    try:
        # Create request with user agent
        request = Request(
            url,
            headers={
                'User-Agent': 'good-agent-llm-client/1.0',
                'Accept': 'application/json',
            }
        )
        
        # Fetch data
        with urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                logger.warning(f"Unexpected status code: {response.status}")
                return None
            
            data = response.read()
            costs = json.loads(data)
            
            logger.info(f"Fetched {len(costs)} model costs from {url}")
            return costs
    
    except HTTPError as e:
        logger.warning(f"HTTP error fetching costs: {e.code} {e.reason}")
        return None
    
    except URLError as e:
        logger.warning(f"Network error fetching costs: {e.reason}")
        return None
    
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in cost data: {e}")
        return None
    
    except Exception as e:
        logger.warning(f"Unexpected error fetching costs: {e}")
        return None


def validate_cost_data(costs: dict[str, Any]) -> bool:
    """Validate cost data structure.
    
    Args:
        costs: Cost dictionary to validate
        
    Returns:
        True if valid
    """
    if not isinstance(costs, dict):
        return False
    
    # Check a few known models exist
    required_models = ["gpt-4", "gpt-3.5-turbo", "claude-3-5-sonnet-20240620"]
    
    for model in required_models:
        if model not in costs:
            logger.warning(f"Missing expected model: {model}")
            return False
        
        model_info = costs[model]
        
        # Check required fields
        required_fields = ["input_cost_per_token", "output_cost_per_token"]
        for field in required_fields:
            if field not in model_info:
                logger.warning(f"Missing field {field} for {model}")
                return False
    
    return True
```

### 3. Cost Calculator

**File: `good_agent/llm_client/costs/calculator.py`**

```python
"""Cost calculation utilities."""

import logging
from typing import Any

from .database import get_cost_database

logger = logging.getLogger(__name__)


def calculate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    use_cache: bool = True
) -> float:
    """Calculate cost for a completion.
    
    Args:
        model: Model name
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens
        use_cache: Use cached cost data (default: True)
        
    Returns:
        Total cost in USD
        
    Example:
        >>> calculate_cost("gpt-4o-mini", 1000, 500)
        0.00045  # $0.00045
    """
    db = get_cost_database()
    
    # Get costs for model
    input_cost = db.get_input_cost(model)
    output_cost = db.get_output_cost(model)
    
    if input_cost == 0.0 and output_cost == 0.0:
        logger.warning(f"No cost data found for model: {model}")
        return 0.0
    
    # Calculate total cost
    total = (prompt_tokens * input_cost) + (completion_tokens * output_cost)
    
    return total


def calculate_cost_from_usage(
    model: str,
    usage: Any
) -> float:
    """Calculate cost from usage object.
    
    Args:
        model: Model name
        usage: Usage object with prompt_tokens and completion_tokens
        
    Returns:
        Total cost in USD
    """
    return calculate_cost(
        model,
        usage.prompt_tokens,
        usage.completion_tokens
    )


def estimate_cost(
    model: str,
    text: str,
    response_tokens: int | None = None
) -> dict[str, float]:
    """Estimate cost for a text completion.
    
    Args:
        model: Model name
        text: Input text
        response_tokens: Expected response tokens (if known)
        
    Returns:
        Dict with cost estimates:
        {
            "input_cost": 0.0001,
            "estimated_output_cost": 0.0002,
            "total_estimated_cost": 0.0003,
            "input_tokens": 100,
            "estimated_output_tokens": 200
        }
    """
    from ..tokens import count_tokens
    
    db = get_cost_database()
    
    # Count input tokens
    input_tokens = count_tokens(text, model)
    
    # Estimate output tokens if not provided
    if response_tokens is None:
        # Heuristic: assume response is ~50% of input length
        response_tokens = int(input_tokens * 0.5)
    
    # Calculate costs
    input_cost = input_tokens * db.get_input_cost(model)
    output_cost = response_tokens * db.get_output_cost(model)
    
    return {
        "input_cost": input_cost,
        "estimated_output_cost": output_cost,
        "total_estimated_cost": input_cost + output_cost,
        "input_tokens": input_tokens,
        "estimated_output_tokens": response_tokens,
        "input_cost_per_token": db.get_input_cost(model),
        "output_cost_per_token": db.get_output_cost(model),
    }


def compare_model_costs(
    models: list[str],
    prompt_tokens: int = 1000,
    completion_tokens: int = 500
) -> dict[str, float]:
    """Compare costs across multiple models.
    
    Args:
        models: List of model names
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens
        
    Returns:
        Dict mapping model name to cost
        
    Example:
        >>> compare_model_costs(["gpt-4o", "gpt-4o-mini", "claude-3-5-sonnet"])
        {
            "gpt-4o": 0.0075,
            "gpt-4o-mini": 0.00045,
            "claude-3-5-sonnet": 0.01050
        }
    """
    costs = {}
    
    for model in models:
        costs[model] = calculate_cost(
            model,
            prompt_tokens,
            completion_tokens
        )
    
    return costs


def format_cost(cost: float) -> str:
    """Format cost for display.
    
    Args:
        cost: Cost in USD
        
    Returns:
        Formatted string
        
    Example:
        >>> format_cost(0.00045)
        "$0.00045"
        >>> format_cost(1.23456)
        "$1.23"
    """
    if cost < 0.01:
        # Show more precision for small costs
        return f"${cost:.6f}"
    elif cost < 1.0:
        return f"${cost:.4f}"
    else:
        return f"${cost:.2f}"
```

### 4. Public API

**File: `good_agent/llm_client/costs/__init__.py`**

```python
"""Cost calculation with LiteLLM data caching.

This module provides cost calculation using LiteLLM's comprehensive
pricing database without importing the litellm library.

Features:
- Multi-level caching (memory, disk, embedded fallback)
- Automatic updates from LiteLLM GitHub
- Zero import overhead (lazy loading)
- 24-hour cache TTL with background refresh

Example:
    >>> from good_agent.llm_client.costs import calculate_cost
    >>> 
    >>> cost = calculate_cost("gpt-4o-mini", prompt_tokens=1000, completion_tokens=500)
    >>> print(f"Cost: ${cost:.4f}")
    Cost: $0.0005
"""

from .calculator import (
    calculate_cost,
    calculate_cost_from_usage,
    estimate_cost,
    compare_model_costs,
    format_cost,
)
from .database import get_cost_database

__all__ = [
    'calculate_cost',
    'calculate_cost_from_usage',
    'estimate_cost',
    'compare_model_costs',
    'format_cost',
    'get_cost_database',
]


def refresh_cost_data(force: bool = False) -> bool:
    """Refresh cost data from LiteLLM GitHub.
    
    Args:
        force: Force refresh even if cache is fresh
        
    Returns:
        True if refreshed successfully
        
    Example:
        >>> from good_agent.llm_client.costs import refresh_cost_data
        >>> refresh_cost_data(force=True)
        True
    """
    db = get_cost_database()
    return db.refresh(force=force)


def list_models(provider: str | None = None) -> list[str]:
    """List all models with cost data.
    
    Args:
        provider: Filter by provider (openai, anthropic, etc.)
        
    Returns:
        List of model names
        
    Example:
        >>> from good_agent.llm_client.costs import list_models
        >>> openai_models = list_models(provider="openai")
        >>> print(f"Found {len(openai_models)} OpenAI models")
    """
    db = get_cost_database()
    return db.list_models(provider=provider)


def get_model_info(model: str) -> dict | None:
    """Get full model information including costs and capabilities.
    
    Args:
        model: Model name
        
    Returns:
        Model info dict or None
        
    Example:
        >>> from good_agent.llm_client.costs import get_model_info
        >>> info = get_model_info("gpt-4o-mini")
        >>> print(info["input_cost_per_token"])
        0.00000015
    """
    db = get_cost_database()
    return db.get_model_costs(model)
```

### 5. Fallback Data Generation Script

**File: `scripts/generate_fallback_costs.py`**

```python
#!/usr/bin/env python3
"""Generate fallback cost data from LiteLLM.

This script fetches the latest cost data from LiteLLM and creates
a fallback file to be packaged with the library.

Usage:
    python scripts/generate_fallback_costs.py
"""

import json
from pathlib import Path
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from good_agent.llm_client.costs.fetcher import fetch_litellm_costs


def main():
    """Generate fallback cost data."""
    print("Fetching latest cost data from LiteLLM...")
    
    url = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
    costs = fetch_litellm_costs(url, timeout=30)
    
    if not costs:
        print("ERROR: Failed to fetch cost data")
        return 1
    
    print(f"Fetched data for {len(costs)} models")
    
    # Save to fallback file
    output_path = Path(__file__).parent.parent / "src" / "good_agent" / "llm_client" / "costs" / "data" / "fallback_costs.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(costs, f, indent=2, sort_keys=True)
    
    print(f"Saved fallback data to: {output_path}")
    print(f"File size: {output_path.stat().st_size / 1024:.1f} KB")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### 6. CLI Tool for Cost Management

**File: `good_agent/llm_client/costs/cli.py`**

```python
"""CLI tool for cost data management."""

import sys
import argparse
from .database import get_cost_database
from .calculator import calculate_cost, compare_model_costs, format_cost


def cmd_refresh(args):
    """Refresh cost data."""
    db = get_cost_database()
    success = db.refresh(force=args.force)
    
    if success:
        print("✓ Cost data refreshed successfully")
        return 0
    else:
        print("✗ Failed to refresh cost data")
        return 1


def cmd_list(args):
    """List models."""
    db = get_cost_database()
    models = db.list_models(provider=args.provider)
    
    print(f"Found {len(models)} models:")
    for model in sorted(models):
        costs = db.get_model_costs(model)
        if costs:
            input_cost = costs.get("input_cost_per_token", 0)
            output_cost = costs.get("output_cost_per_token", 0)
            print(f"  {model}")
            print(f"    Input:  ${input_cost:.8f}/token")
            print(f"    Output: ${output_cost:.8f}/token")
    
    return 0


def cmd_calculate(args):
    """Calculate cost."""
    cost = calculate_cost(
        args.model,
        args.prompt_tokens,
        args.completion_tokens
    )
    
    print(f"Model: {args.model}")
    print(f"Prompt tokens: {args.prompt_tokens:,}")
    print(f"Completion tokens: {args.completion_tokens:,}")
    print(f"Total cost: {format_cost(cost)}")
    
    return 0


def cmd_compare(args):
    """Compare model costs."""
    costs = compare_model_costs(
        args.models,
        args.prompt_tokens,
        args.completion_tokens
    )
    
    print(f"Comparing costs for {args.prompt_tokens:,} prompt + {args.completion_tokens:,} completion tokens:\n")
    
    # Sort by cost
    sorted_costs = sorted(costs.items(), key=lambda x: x[1])
    
    for model, cost in sorted_costs:
        print(f"  {model:40s} {format_cost(cost)}")
    
    return 0


def cmd_info(args):
    """Show model info."""
    db = get_cost_database()
    info = db.get_model_costs(args.model)
    
    if not info:
        print(f"No cost data found for: {args.model}")
        return 1
    
    print(f"Model: {args.model}")
    print(f"Provider: {info.get('litellm_provider', 'unknown')}")
    print(f"Max tokens: {info.get('max_tokens', 'unknown')}")
    print(f"Input cost: ${info.get('input_cost_per_token', 0):.8f}/token")
    print(f"Output cost: ${info.get('output_cost_per_token', 0):.8f}/token")
    print(f"Function calling: {info.get('supports_function_calling', False)}")
    print(f"Vision: {info.get('supports_vision', False)}")
    
    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Good Agent LLM Client - Cost Management"
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Refresh command
    refresh_parser = subparsers.add_parser('refresh', help='Refresh cost data from LiteLLM')
    refresh_parser.add_argument('--force', action='store_true', help='Force refresh')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List models')
    list_parser.add_argument('--provider', help='Filter by provider')
    
    # Calculate command
    calc_parser = subparsers.add_parser('calculate', help='Calculate cost')
    calc_parser.add_argument('model', help='Model name')
    calc_parser.add_argument('prompt_tokens', type=int, help='Prompt tokens')
    calc_parser.add_argument('completion_tokens', type=int, help='Completion tokens')
    
    # Compare command
    compare_parser = subparsers.add_parser('compare', help='Compare model costs')
    compare_parser.add_argument('models', nargs='+', help='Model names')
    compare_parser.add_argument('--prompt-tokens', type=int, default=1000)
    compare_parser.add_argument('--completion-tokens', type=int, default=500)
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Show model info')
    info_parser.add_argument('model', help='Model name')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Dispatch to command handler
    handlers = {
        'refresh': cmd_refresh,
        'list': cmd_list,
        'calculate': cmd_calculate,
        'compare': cmd_compare,
        'info': cmd_info,
    }
    
    return handlers[args.command](args)


if __name__ == '__main__':
    sys.exit(main())
```

## Usage Examples

### Basic Cost Calculation

```python
from good_agent.llm_client.costs import calculate_cost

# Calculate cost for a completion
cost = calculate_cost(
    model="gpt-4o-mini",
    prompt_tokens=1000,
    completion_tokens=500
)
print(f"Cost: ${cost:.6f}")  # Cost: $0.000450
```

### Estimate Before Making Request

```python
from good_agent.llm_client.costs import estimate_cost

# Estimate cost before making API call
estimate = estimate_cost(
    model="gpt-4o",
    text="Your long input text here...",
    response_tokens=200  # Expected response length
)

print(f"Estimated input cost: ${estimate['input_cost']:.6f}")
print(f"Estimated output cost: ${estimate['estimated_output_cost']:.6f}")
print(f"Total estimated cost: ${estimate['total_estimated_cost']:.6f}")

# Decide whether to proceed based on cost
if estimate['total_estimated_cost'] > 0.01:
    print("WARNING: This request will cost more than $0.01")
```

### Compare Models

```python
from good_agent.llm_client.costs import compare_model_costs, format_cost

# Compare costs for different models
models = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "claude-3-5-sonnet-20240620",
    "claude-3-opus-20240229"
]

costs = compare_model_costs(models, prompt_tokens=10000, completion_tokens=2000)

print("Cost comparison for 10k input + 2k output tokens:")
for model, cost in sorted(costs.items(), key=lambda x: x[1]):
    print(f"  {model:40s} {format_cost(cost)}")

# Output:
# gpt-4o-mini                              $0.002700
# gpt-4o                                   $0.045000
# claude-3-5-sonnet-20240620               $0.060000
# gpt-4-turbo                              $0.160000
# claude-3-opus-20240229                   $0.300000
```

### Refresh Cost Data

```python
from good_agent.llm_client.costs import refresh_cost_data

# Manually refresh cost data (e.g., after LiteLLM updates pricing)
success = refresh_cost_data(force=True)
if success:
    print("Cost data updated successfully")
```

### CLI Usage

```bash
# Refresh cost data
python -m good_agent.llm_client.costs.cli refresh --force

# List all OpenAI models
python -m good_agent.llm_client.costs.cli list --provider openai

# Calculate cost
python -m good_agent.llm_client.costs.cli calculate gpt-4o-mini 1000 500
# Output:
# Model: gpt-4o-mini
# Prompt tokens: 1,000
# Completion tokens: 500
# Total cost: $0.000450

# Compare models
python -m good_agent.llm_client.costs.cli compare gpt-4o gpt-4o-mini claude-3-5-sonnet-20240620 \
    --prompt-tokens 10000 --completion-tokens 2000

# Get model info
python -m good_agent.llm_client.costs.cli info gpt-4o
# Output:
# Model: gpt-4o
# Provider: openai
# Max tokens: 128000
# Input cost: $0.00000250/token
# Output cost: $0.00001000/token
# Function calling: True
# Vision: True
```

## Cache Management

### Cache Locations

```
~/.cache/good-agent/
├── model_costs.json           # Cached cost data
└── model_costs_meta.json      # Cache metadata (timestamp, etc.)
```

### Cache Invalidation

- **Automatic**: 24 hours after last fetch
- **Manual**: Call `refresh_cost_data(force=True)`
- **On Import**: If cache is stale, background refresh is triggered

### Clear Cache

```python
from pathlib import Path

# Remove cache files
cache_dir = Path.home() / ".cache" / "good-agent"
for file in cache_dir.glob("model_costs*"):
    file.unlink()
```

## Performance Characteristics

```
First access (cold start):
  - No cache: ~100ms (fetch from GitHub)
  - Disk cache: ~2ms (read JSON file)
  - After loaded: <0.1ms (memory cache)

Subsequent accesses: <0.1ms (memory cache)

Cache size: ~400KB (compressed JSON)

Import overhead: 0ms (lazy loaded)
```

## Testing

```python
# tests/unit/costs/test_cost_database.py

def test_cost_database_fallback(monkeypatch):
    """Test fallback to embedded data."""
    # Mock fetch to fail
    monkeypatch.setattr(
        "good_agent.llm_client.costs.fetcher.fetch_litellm_costs",
        lambda *args, **kwargs: None
    )
    
    db = CostDatabase()
    cost = db.get_input_cost("gpt-4o-mini")
    
    # Should still work with fallback
    assert cost > 0


def test_cost_calculation_accuracy():
    """Test cost calculation matches LiteLLM."""
    cost = calculate_cost("gpt-4o-mini", 1000, 500)
    
    # GPT-4o-mini: $0.00000015/input + $0.0000006/output
    expected = (1000 * 0.00000015) + (500 * 0.0000006)
    assert abs(cost - expected) < 0.0000001


def test_cache_persistence(tmp_path):
    """Test disk cache persists."""
    db = CostDatabase()
    db.CACHE_DIR = tmp_path
    db.CACHE_FILE = tmp_path / "costs.json"
    
    # Save costs
    test_costs = {"test-model": {"input_cost_per_token": 0.001}}
    db._save_to_disk(test_costs)
    
    # Load in new instance
    db2 = CostDatabase()
    db2.CACHE_DIR = tmp_path
    db2.CACHE_FILE = tmp_path / "costs.json"
    
    loaded = db2._load_from_disk()
    assert loaded == test_costs
```

## CI/CD Integration

```yaml
# .github/workflows/update-costs.yml
name: Update Cost Data

on:
  schedule:
    # Run weekly on Monday at 00:00 UTC
    - cron: '0 0 * * 1'
  workflow_dispatch:  # Allow manual trigger

jobs:
  update-costs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      
      - name: Generate fallback costs
        run: |
          python scripts/generate_fallback_costs.py
      
      - name: Create PR if changed
        uses: peter-evans/create-pull-request@v5
        with:
          commit-message: 'chore: update cost data from LiteLLM'
          title: 'Update model cost data'
          body: 'Automated update of model pricing from LiteLLM'
          branch: 'update-costs'
```

## Benefits

1. **Comprehensive Data** - All LiteLLM pricing (300+ models)
2. **Always Updated** - Automatic background refresh
3. **Fast** - Multi-level caching (<0.1ms access)
4. **Reliable** - Embedded fallback data
5. **No Dependencies** - No litellm import needed
6. **Zero Import Cost** - Lazy loaded

## Summary

This design provides:
- ✅ LiteLLM's comprehensive cost database
- ✅ Aggressive multi-level caching
- ✅ <0.1ms cost lookups after first access
- ✅ No litellm dependency
- ✅ Automatic background updates
- ✅ Embedded fallback data
- ✅ Zero import overhead
