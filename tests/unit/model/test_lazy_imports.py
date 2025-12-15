import importlib
import types

import pytest

import good_agent.model as model_module


def test_lazy_import_loads_and_caches_attribute(monkeypatch):
    dummy_module = types.SimpleNamespace(DummyAttr="loaded")

    monkeypatch.setitem(model_module._LAZY_IMPORTS, "DummyAttr", "dummy_module")

    def fake_import(name, package=None):
        assert name == ".dummy_module"
        assert package == model_module.__package__
        return dummy_module

    monkeypatch.setattr(importlib, "import_module", fake_import)

    try:
        assert model_module.DummyAttr == "loaded"
        # Attribute should now be cached on the module
        assert model_module.DummyAttr == "loaded"
    finally:
        if hasattr(model_module, "DummyAttr"):
            delattr(model_module, "DummyAttr")
        model_module._LAZY_IMPORTS.pop("DummyAttr", None)


def test_lazy_import_raises_for_unknown_attribute():
    with pytest.raises(AttributeError):
        _ = model_module.__getattr__("DoesNotExist")
