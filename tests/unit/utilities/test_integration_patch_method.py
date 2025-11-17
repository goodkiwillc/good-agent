from good_agent.utilities.integration import patch_method


class _Sample:
    def greet(self) -> str:
        return "hi"


def test_patch_method_temporarily_overrides_behavior():
    obj = _Sample()

    def new_greet(self):
        return "patched"

    assert obj.greet() == "hi"
    with patch_method(_Sample, "greet", new_greet):
        assert obj.greet() == "patched"

    assert obj.greet() == "hi"
