from good_agent.core.param_naming import (
    ParameterNameGenerator,
    generate_param_name,
    reset_param_counters,
)


def test_generator_produces_stable_unique_names():
    generator = ParameterNameGenerator()
    first = generator.generate("field", "eq", "value")
    second = generator.generate("field", "eq", "value")
    assert first != second
    assert second.startswith("field_eq_1_")


def test_generate_for_condition_incorporates_condition_id():
    generator = ParameterNameGenerator()
    name = generator.generate_for_condition("status", "in", ["open"], "cond1")
    assert name.startswith("status_cond1_in")


def test_module_level_helpers_reset_counters():
    first = generate_param_name("priority", "gt", 5)
    reset_param_counters()
    second = generate_param_name("priority", "gt", 5)
    assert first == second
