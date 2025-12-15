import hashlib
from typing import Any


class ParameterNameGenerator:
    """
    Generates unique parameter names for SQL queries to prevent naming collisions.

    This class provides deterministic parameter naming that avoids hash collisions
    by using a combination of field, operator, value, and counter information.
    """

    def __init__(self):
        """Initialize the parameter name generator."""
        self._counters: dict[str, int] = {}

    def generate(self, field: str, operator: str, value: Any, counter: int | None = None) -> str:
        """
        Generate a unique parameter name.

        Args:
            field: The field name (e.g., 'content', 'platform')
            operator: The operator (e.g., 'equals', 'contains', 'in')
            value: The parameter value
            counter: Optional counter for additional uniqueness

        Returns:
            A unique parameter name safe for use in SQL queries
        """
        # Create a base identifier from field and operator
        base_id = f"{field}_{operator}"

        # Add counter if provided, otherwise use internal counter
        if counter is not None:
            counter_str = f"_{counter}"
        else:
            # Use internal counter for this base_id to ensure uniqueness
            current_count = self._counters.get(base_id, 0)
            self._counters[base_id] = current_count + 1
            counter_str = f"_{current_count}" if current_count > 0 else ""

        # Create a hash of the value for additional uniqueness
        value_str = str(value)
        value_hash = hashlib.md5(value_str.encode("utf-8")).hexdigest()[:8]

        # Combine all parts: field_operator_counter_hash
        param_name = f"{base_id}{counter_str}_{value_hash}"

        # Ensure the parameter name is valid for ClickHouse (alphanumeric + underscore)
        # Replace any invalid characters
        param_name = "".join(c if c.isalnum() or c == "_" else "_" for c in param_name)

        return param_name

    def generate_for_condition(
        self, field: str, operator: str, value: Any, condition_id: str | None = None
    ) -> str:
        """
        Generate a parameter name specifically for filter conditions.

        Args:
            field: The field name
            operator: The operator
            value: The parameter value
            condition_id: Optional condition identifier for additional uniqueness

        Returns:
            A unique parameter name
        """
        if condition_id:
            # Include condition_id for maximum uniqueness
            return self.generate(f"{field}_{condition_id}", operator, value)
        else:
            return self.generate(field, operator, value)

    def reset_counters(self):
        """Reset all internal counters. Useful for testing or when starting a new query."""
        self._counters.clear()


# Global instance for convenience
_default_generator = ParameterNameGenerator()


def generate_param_name(field: str, operator: str, value: Any, counter: int | None = None) -> str:
    """
    Convenience function to generate parameter names using the default generator.

    Args:
        field: The field name
        operator: The operator
        value: The parameter value
        counter: Optional counter for additional uniqueness

    Returns:
        A unique parameter name
    """
    return _default_generator.generate(field, operator, value, counter)


def generate_condition_param_name(
    field: str, operator: str, value: Any, condition_id: str | None = None
) -> str:
    """
    Convenience function to generate parameter names for filter conditions.

    Args:
        field: The field name
        operator: The operator
        value: The parameter value
        condition_id: Optional condition identifier

    Returns:
        A unique parameter name
    """
    return _default_generator.generate_for_condition(field, operator, value, condition_id)


def reset_param_counters():
    """Reset the default generator's counters."""
    _default_generator.reset_counters()
