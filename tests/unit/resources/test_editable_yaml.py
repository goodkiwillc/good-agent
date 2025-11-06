import pytest
import yaml
from good_agent.resources import EditableYAML


@pytest.mark.asyncio
async def test_basic_get_set_delete_validate_v2():
    doc = """
fields:
  id: { path: o.id }
"""
    ed = EditableYAML(doc)
    await ed.initialize()

    r_get = await ed.get("fields.id.path")
    assert r_get.success is True
    assert r_get.response.strip().startswith("o.id")

    r_set = await ed.set("fields.created_at", {"path": "o.created_at"})
    assert r_set.success is True and r_set.response == "ok"
    full = await ed.text()
    y = yaml.safe_load(full.response) or {}
    assert y["fields"]["created_at"]["path"] == "o.created_at"

    r_del = await ed.delete("fields.id")
    assert r_del.success is True and r_del.response == "ok"
    full2 = await ed.text()
    y2 = yaml.safe_load(full2.response) or {}
    assert "id" not in y2["fields"]

    r_val = await ed.validate()
    assert r_val.success is True and r_val.response == "ok"


@pytest.mark.asyncio
async def test_merge_strategies_v2():
    doc = """
fields:
  a: { x: 1 }
  b: [1, 2]
  objs:
    - { name: a, v: 1 }
    - { name: b, v: 2 }
"""
    ed = EditableYAML(doc)
    await ed.initialize()

    await ed.set("fields.a", {"y": 2}, strategy="merge")
    y1 = yaml.safe_load((await ed.text()).response) or {}
    assert y1["fields"]["a"] == {"x": 1, "y": 2}

    await ed.set("fields.a", {"x": 10, "z": 5}, strategy="deep_merge")
    y2 = yaml.safe_load((await ed.text()).response) or {}
    assert y2["fields"]["a"] == {"x": 10, "y": 2, "z": 5}

    await ed.set("fields.b", [2, 3], strategy="merge_array")
    y3 = yaml.safe_load((await ed.text()).response) or {}
    assert y3["fields"]["b"] == [1, 2, 3]

    patch_list = [{"name": "b", "v": 3}, {"name": "c", "v": 9}]
    await ed.set("fields.objs", patch_list, strategy="merge_array", array_key="name")
    y4 = yaml.safe_load((await ed.text()).response) or {}
    objs = {o["name"]: o for o in y4["fields"]["objs"]}
    assert objs["a"]["v"] == 1
    assert objs["b"]["v"] == 3
    assert objs["c"]["v"] == 9


@pytest.mark.asyncio
async def test_patch_ops_v2():
    doc = """
source: data.objects as o
fields: {}
arr: [1, 2]
"""
    ed = EditableYAML(doc)
    await ed.initialize()

    ops = [
        {"op": "add", "path": "fields.created_at", "value": {"path": "o.created_at"}},
        {"op": "merge", "path": "metadata", "value": {"source": "x"}},
        {"op": "merge_array", "path": "arr", "value": [2, 3]},
        {"op": "move", "from": "fields.created_at", "path": "fields.captured_at"},
        {"op": "test", "path": "fields.captured_at", "value": {"path": "o.created_at"}},
        {"op": "remove", "path": "metadata.source"},
    ]

    r = await ed.patch(ops)
    assert r.success is True and r.response["ok"] is True
    y = yaml.safe_load(r.response["yaml"]) or {}
    assert "created_at" not in (y.get("fields") or {})
    assert y["fields"]["captured_at"]["path"] == "o.created_at"
    assert y["arr"] == [1, 2, 3]
    assert (y.get("metadata") or {}).get("source") is None


@pytest.mark.asyncio
async def test_replace_and_read_v2():
    doc = """
fields:
  created_at: { path: o.created_at }
"""
    ed = EditableYAML(doc)
    await ed.initialize()

    r = await ed.replace(r"created_at", "captured_at")
    assert r.success is True and r.response == "ok"
    y = yaml.safe_load((await ed.text()).response) or {}
    assert "created_at" not in y["fields"] and "captured_at" in y["fields"]

    r2 = await ed.read(start_line=1, num_lines=1)
    assert r2.success is True
    assert r2.response.split("\n")[0].startswith("   1:")


@pytest.mark.asyncio
async def test_validation_and_rollback_v2():
    def validator(doc: dict):
        fields = (
            set((doc.get("fields") or {}).keys()) if isinstance(doc, dict) else set()
        )
        if "invalid_col" in fields:
            return False, ["invalid_col not allowed"]
        return True, []

    doc = """
fields:
  ok: { path: o.id }
"""
    ed = EditableYAML(doc, validator=validator)
    await ed.initialize()

    r_fail = await ed.set("fields.invalid_col", {"path": "o.x"}, validate=True)
    assert r_fail.success is True and r_fail.response.startswith("ERROR:")
    g = await ed.get("fields.invalid_col")
    assert g.response.strip() == ""

    r_bad = await ed.replace(r"fields:\n", "fields\n", validate=True)
    assert r_bad.success is True and r_bad.response.startswith("ERROR:")
    t = await ed.read()
    assert "ok:" in t.response
