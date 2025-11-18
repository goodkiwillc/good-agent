import sys
import types

from good_agent.model.manager import ModelManager, ModelOverride


def test_register_model_updates_litellm_costs(monkeypatch):
    fake_litellm = types.SimpleNamespace(model_cost={})
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

    manager = ModelManager()
    manager.register_model(
        "custom-model",
        "openai",
        input_cost_per_token=0.01,
        output_cost_per_token=0.02,
    )

    info = manager.get_model_info("custom-model")
    assert info["input_cost_per_token"] == 0.01
    assert fake_litellm.model_cost["custom-model"]["output_cost_per_token"] == 0.02


def test_create_router_uses_registered_models_and_fallbacks(monkeypatch):
    manager = ModelManager()
    manager.register_model("primary", "provider", api_base="https://api.local")

    captured: dict[str, object] = {}

    class DummyRouter:
        pass

    def fake_create_managed_router(*, model_list, managed_callbacks=None, **kwargs):
        captured["model_list"] = model_list
        captured["kwargs"] = kwargs
        captured["callbacks"] = managed_callbacks
        router_instance = DummyRouter()
        captured["router"] = router_instance
        return router_instance

    monkeypatch.setattr(
        "good_agent.model.manager.create_managed_router",
        fake_create_managed_router,
    )

    router = manager.create_router(
        "primary", fallback_models=["secondary"], managed_callbacks=["cb"], timeout=5
    )

    assert router is captured["router"]
    model_list = captured["model_list"]
    assert model_list[0]["litellm_params"]["model"] == "primary"
    assert model_list[1]["litellm_params"]["model"] == "secondary"
    assert captured["kwargs"]["timeout"] == 5
    assert captured["callbacks"] == ["cb"]


def test_list_models_includes_override_patterns():
    manager = ModelManager()
    manager.register_model("registered", "provider")
    manager.register_override(ModelOverride(model_pattern="bespoke-model"))

    models = manager.list_models()
    assert "registered" in models
    assert "bespoke-model" in models
