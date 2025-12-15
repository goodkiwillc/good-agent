from __future__ import annotations

import copy
import logging
import re
from collections.abc import Callable
from typing import Any

import yaml
from box import Box
from pydantic import Field

from good_agent import tool
from good_agent.resources.base import StatefulResource

logger = logging.getLogger(__name__)


def _ensure_mapping_top_level(data: Any) -> dict[str, Any]:
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("YAML top-level must be a mapping")
    return data


def _parse_yaml_to_box(text: str) -> Box:
    data = yaml.safe_load(text) if text is not None else {}
    data = _ensure_mapping_top_level(data)
    return Box(data, default_box=False, frozen_box=False)


def _dump_box_to_yaml(box_obj: Box) -> str:
    return yaml.safe_dump(box_obj.to_dict(), sort_keys=False)


def _is_mapping(v: Any) -> bool:
    return isinstance(v, (dict, Box))


def _deep_to_box(v: Any) -> Any:
    if isinstance(v, Box):
        return v
    if isinstance(v, dict):
        return Box(
            {k: _deep_to_box(val) for k, val in v.items()},
            default_box=False,
            frozen_box=False,
        )
    if isinstance(v, list):
        return [_deep_to_box(x) for x in v]
    return v


def _deep_to_plain(v: Any) -> Any:
    if isinstance(v, Box):
        return {k: _deep_to_plain(val) for k, val in v.items()}
    if isinstance(v, dict):
        return {k: _deep_to_plain(val) for k, val in v.items()}
    if isinstance(v, list):
        return [_deep_to_plain(x) for x in v]
    return v


def _is_scalar(v: Any) -> bool:
    return isinstance(v, (bool, int, float, str))


def _coerce_like(existing: Any, value: Any) -> Any:
    try:
        if isinstance(existing, bool):
            if isinstance(value, str):
                low = value.strip().lower()
                if low in {"true", "yes", "1"}:
                    return True
                if low in {"false", "no", "0"}:
                    return False
            return bool(value)

        if isinstance(existing, int) and not isinstance(existing, bool):
            if isinstance(value, (int, bool)):
                return int(value)
            if isinstance(value, float):
                return int(value) if float(value).is_integer() else value
            if isinstance(value, str):
                try:
                    return int(value)
                except Exception:
                    try:
                        f = float(value)
                        return int(f) if f.is_integer() else value
                    except Exception:
                        return value

        if isinstance(existing, float):
            if isinstance(value, (int, float, bool)):
                return float(value)
            if isinstance(value, str):
                try:
                    return float(value)
                except Exception:
                    return value

        if isinstance(existing, str):
            return str(value)
    except Exception:
        return value
    return value


def _get_node(doc: Box | dict[str, Any], path: str) -> tuple[bool, Any]:
    cur: Any = doc
    for part in path.split(".") if path else []:
        if not _is_mapping(cur) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


def _ensure_parents(doc: Box | dict[str, Any], parts: list[str]) -> None:
    cur: Any = doc
    for p in parts:
        if not _is_mapping(cur):
            raise ValueError(f"Parent at '{p}' is not a mapping")
        if p not in cur or not _is_mapping(cur[p]):
            cur[p] = Box({}, default_box=False, frozen_box=False)
        cur = cur[p]


def _set_node(doc: Box | dict[str, Any], path: str, value: Any, create_missing: bool) -> None:
    parts = path.split(".") if path else []
    if not parts:
        if not _is_mapping(value):
            raise ValueError("Top-level must be a mapping")
        if isinstance(doc, Box):
            keys = list(doc.keys())
            for k in keys:
                del doc[k]
            for k, v in _deep_to_box(value).items():
                doc[k] = v
            return
        else:
            raise ValueError("Internal error: top-level document must be Box")

    parent_parts, leaf = parts[:-1], parts[-1]
    cur: Any = doc
    for p in parent_parts:
        if p not in cur or not _is_mapping(cur[p]):
            if not create_missing:
                raise KeyError(f"Missing parent path: {p}")
            cur[p] = Box({}, default_box=False, frozen_box=False)
        cur = cur[p]
    cur[leaf] = _deep_to_box(value)


def _del_node(doc: Box | dict[str, Any], path: str) -> None:
    parts = path.split(".") if path else []
    if not parts:
        return
    cur: Any = doc
    for p in parts[:-1]:
        if p not in cur or not _is_mapping(cur[p]):
            return
        cur = cur[p]
    if parts[-1] in cur:
        del cur[parts[-1]]


def _merge_shallow(a: Any, b: Any) -> Any:
    if _is_mapping(a) and _is_mapping(b):
        out = {**_deep_to_plain(a), **_deep_to_plain(b)}
        return out
    return copy.deepcopy(b)


def _merge_deep(a: Any, b: Any) -> Any:
    if _is_mapping(a) and _is_mapping(b):
        out = dict(_deep_to_plain(a))
        for k, v in _deep_to_plain(b).items():
            if k in out:
                out[k] = _merge_deep(out[k], v)
            else:
                out[k] = copy.deepcopy(v)
        return out
    return copy.deepcopy(_deep_to_plain(b))


def _merge_array(existing: Any, patch: Any, key: str | None = None) -> Any:
    if not isinstance(existing, list) or not isinstance(patch, list):
        return copy.deepcopy(_deep_to_plain(patch))

    if not key:
        seen = set()
        out: list[Any] = []
        for item in existing + patch:
            h = yaml.safe_dump(_deep_to_plain(item), sort_keys=True)
            if h not in seen:
                seen.add(h)
                out.append(_deep_to_box(item))
        return out

    by_key: dict[Any, Any] = {}
    for item in existing:
        if _is_mapping(item) and key in item:
            by_key[item[key]] = _deep_to_box(item)
        else:
            by_key[id(item)] = _deep_to_box(item)
    for item in patch:
        if _is_mapping(item) and key in item:
            if item[key] in by_key and _is_mapping(by_key[item[key]]):
                by_key[item[key]] = _deep_to_box(_merge_deep(by_key[item[key]], item))
            else:
                by_key[item[key]] = _deep_to_box(item)
        else:
            by_key[id(item)] = _deep_to_box(item)
    result_out: list[Any] = []
    existing_keys = [it.get(key) if _is_mapping(it) else id(it) for it in existing]
    for k in existing_keys:
        if k in by_key:
            result_out.append(by_key.pop(k))
    result_out.extend(by_key.values())
    return result_out


def _apply_strategy(current: Any, value: Any, strategy: str, array_key: str | None = None) -> Any:
    s = (strategy or "assign").lower()
    if s == "assign":
        return copy.deepcopy(_deep_to_box(value))
    if s == "merge":
        return _deep_to_box(_merge_shallow(current, value))
    if s == "deep_merge":
        return _deep_to_box(_merge_deep(current, value))
    if s == "merge_array":
        return _merge_array(current, value, key=array_key)
    if s == "replace_array":
        return _deep_to_box(value)
    return _deep_to_box(value)


ValidatorReturn = dict[str, Any] | tuple[bool, list[str]]
ValidatorType = Callable[[dict[str, Any]], ValidatorReturn] | Callable[[str], ValidatorReturn]


class EditableYAML(StatefulResource[Box]):
    """YAML editor resource with object-native state and JSON-friendly tools."""

    def __init__(
        self,
        yaml_text: str,
        name: str = "yaml_document",
        validator: ValidatorType | None = None,
    ):
        super().__init__(name=name)
        self._initial_content = yaml_text
        self._validator = validator
        self._modified = False

    async def initialize(self) -> None:
        self.state = _parse_yaml_to_box(self._initial_content)

    async def persist(self) -> None:
        self._modified = False

    def _validate_data(self, data_box: Box) -> tuple[bool, list[str], dict | None]:
        try:
            _ = yaml.safe_dump(_deep_to_plain(data_box), sort_keys=False)
        except Exception as e:
            return False, ["YAML serialization error: " + str(e)], None

        if self._validator is None:
            return True, [], None

        try:
            try:
                res = self._validator(_deep_to_plain(data_box))  # type: ignore[misc]
            except TypeError:
                res = self._validator(_dump_box_to_yaml(data_box))  # type: ignore[arg-type,misc]
        except Exception as e:
            return False, ["Validator error: " + str(e)], None

        if isinstance(res, tuple) and len(res) >= 2:
            ok, errors = bool(res[0]), list(res[1])
            return ok, errors, None
        if isinstance(res, dict):
            ok = bool(res.get("ok", False))
            errors = list(res.get("errors", []))
            return ok, errors, res
        return False, ["Validator returned unsupported result"], None

    @tool
    async def read(
        self,
        start_line: int | None = Field(default=None, description="1-based line to start from"),
        num_lines: int | None = Field(default=None, description="Number of lines to return"),
    ) -> str:
        text = _dump_box_to_yaml(self.state)
        lines = text.split("\n")
        if start_line is not None:
            s = max(0, start_line - 1)
            e = len(lines) if num_lines is None else min(len(lines), s + num_lines)
            lines = lines[s:e]
            base = start_line
        else:
            base = 1
        return "\n".join(f"{base + i:4}: {ln}" for i, ln in enumerate(lines))

    @tool
    async def get(self, path: str = Field(..., description="Dot-path to value")) -> str:
        try:
            ok, node = _get_node(self.state, path)
            return yaml.safe_dump(_deep_to_plain(node), sort_keys=False) if ok else ""
        except Exception as e:
            return f"ERROR: {e}"

    @tool(name="set")  # type: ignore[arg-type,misc]
    async def _tool_set(
        self,
        path: str = Field(..., description="Dot-path to set"),
        value: Any = Field(..., description="JSON value to set (dict/list/str/number/bool/null)"),
        create_missing: bool = Field(True, description="Create containers if missing"),
        strategy: str = Field(
            "assign",
            description="assign|merge|deep_merge|merge_array|replace_array",
        ),
        array_key: str | None = Field(
            None,
            description="Key used to merge array of objects when strategy=merge_array",
        ),
        run_validation: bool = Field(
            True,
            description="Run validator and rollback on failure",
            alias="validate",
            validation_alias="validate",
            serialization_alias="validate",
        ),
        coerce_to_existing_type: bool = Field(
            True,
            description=(
                "When target path exists and is a scalar (bool/int/float/str), coerce the incoming value to match the existing type"
            ),
        ),
        reasoning: str | None = None,
    ) -> str:
        logger.debug(f"SET path={path} value={value} strategy={strategy}")
        before = copy.deepcopy(self.state)
        try:
            exists, current = _get_node(self.state, path)
            new_val = _apply_strategy(current if exists else None, value, strategy, array_key)
            if coerce_to_existing_type and exists and _is_scalar(current) and _is_scalar(new_val):
                new_val = _coerce_like(current, new_val)
            _set_node(self.state, path, new_val, create_missing=create_missing)
            if run_validation:
                ok, errors, extra = self._validate_data(self.state)
                if not ok:
                    self.state = before
                    return "ERROR: " + "; ".join(errors)
            self._modified = True
            return "ok"
        except Exception as e:
            self.state = before
            return f"ERROR: {e}"

    async def set(
        self,
        path: str,
        value: Any,
        create_missing: bool = True,
        strategy: str = "assign",
        array_key: str | None = None,
        validate: bool = True,
        coerce_to_existing_type: bool = True,
        reasoning: str | None = None,
    ) -> str:
        # mypy can't infer BoundTool call signature properly
        return await self._tool_set(  # type: ignore[return-value,call-overload,misc]
            path=path,  # type: ignore[arg-type]
            value=value,  # type: ignore[arg-type]
            create_missing=create_missing,  # type: ignore[arg-type]
            strategy=strategy,  # type: ignore[arg-type]
            array_key=array_key,  # type: ignore[arg-type]
            run_validation=validate,  # type: ignore[arg-type]
            coerce_to_existing_type=coerce_to_existing_type,  # type: ignore[arg-type]
            reasoning=reasoning,  # type: ignore[arg-type]
        )

    @tool(name="delete")  # type: ignore[arg-type,misc]
    async def _tool_delete(
        self,
        path: str = Field(..., description="Dot-path to delete"),
        run_validation: bool = Field(
            True,
            description="Run validator and rollback on failure",
            alias="validate",
            validation_alias="validate",
            serialization_alias="validate",
        ),
        reasoning: str | None = None,
    ) -> str:
        before = copy.deepcopy(self.state)
        try:
            _del_node(self.state, path)
            if run_validation:
                ok, errors, extra = self._validate_data(self.state)
                if not ok:
                    self.state = before
                    return "ERROR: " + "; ".join(errors)
            self._modified = True
            return "ok"
        except Exception as e:
            self.state = before
            return f"ERROR: {e}"

    async def delete(
        self,
        path: str,
        validate: bool = True,
        reasoning: str | None = None,
    ) -> str:
        # mypy can't infer BoundTool call signature properly
        return await self._tool_delete(  # type: ignore[return-value,call-overload,misc]
            path=path,  # type: ignore[arg-type]
            run_validation=validate,  # type: ignore[arg-type]
            reasoning=reasoning,  # type: ignore[arg-type]
        )

    @tool(name="replace")  # type: ignore[arg-type,misc]
    async def _tool_replace(
        self,
        pattern: str = Field(..., description="Regex pattern"),
        replacement: str = Field(..., description="Replacement text"),
        flags: str = Field("", description="Regex flags: i,m"),
        run_validation: bool = Field(
            True,
            description="Run validator and rollback on failure",
            alias="validate",
            validation_alias="validate",
            serialization_alias="validate",
        ),
        reasoning: str | None = None,
    ) -> str:
        before = copy.deepcopy(self.state)
        try:
            text = _dump_box_to_yaml(self.state)
            fl = 0
            if "i" in flags:
                fl |= re.IGNORECASE
            if "m" in flags:
                fl |= re.MULTILINE
            candidate_text = re.sub(pattern, replacement, text, flags=fl)
            candidate_box = _parse_yaml_to_box(candidate_text)
            if run_validation:
                ok, errors, extra = self._validate_data(candidate_box)
                if not ok:
                    return "ERROR: " + "; ".join(errors)
            self.state = candidate_box
            self._modified = True
            return "ok"
        except Exception as e:
            self.state = before
            return f"ERROR: {e}"

    async def replace(
        self,
        pattern: str,
        replacement: str,
        flags: str = "",
        validate: bool = True,
        reasoning: str | None = None,
    ) -> str:
        # mypy can't infer BoundTool call signature properly
        return await self._tool_replace(  # type: ignore[return-value,call-overload,misc]
            pattern=pattern,  # type: ignore[arg-type]
            replacement=replacement,  # type: ignore[arg-type]
            flags=flags,  # type: ignore[arg-type]
            run_validation=validate,  # type: ignore[arg-type]
            reasoning=reasoning,  # type: ignore[arg-type]
        )

    @tool(name="patch")  # type: ignore[arg-type,misc]
    async def _tool_patch(
        self,
        ops: list[dict[str, Any]] = Field(
            ...,
            description=(
                "List of operations. Supported ops: add, replace, remove, merge, deep_merge, "
                "merge_array, replace_array, move, copy, test. Fields: op, path, value?, strategy?, array_key?, from?"
            ),
        ),
        run_validation: bool = Field(
            True,
            description="Run validator and rollback on failure",
            alias="validate",
            validation_alias="validate",
            serialization_alias="validate",
        ),
        coerce_to_existing_type: bool = Field(
            True,
            description=(
                "When target path exists and is a scalar (bool/int/float/str), coerce the incoming value to match the existing type"
            ),
        ),
    ) -> dict:
        before = copy.deepcopy(self.state)
        try:
            working = copy.deepcopy(self.state)
            applied: list[dict[str, Any]] = []

            for i, op in enumerate(ops):
                if not isinstance(op, dict) or "op" not in op:
                    return {
                        "ok": False,
                        "errors": [f"Invalid op at index {i}"],
                        "yaml": _dump_box_to_yaml(before),
                    }
                typ = str(op["op"]).lower()
                path = op.get("path", "")
                value = op.get("value")
                strategy = str(op.get("strategy", "assign"))
                array_key = op.get("array_key")

                if typ in {"add", "replace"}:
                    exists, current = _get_node(working, path)
                    new_val = _apply_strategy(
                        current if exists else None, value, strategy, array_key
                    )
                    if (
                        coerce_to_existing_type
                        and exists
                        and _is_scalar(current)
                        and _is_scalar(new_val)
                    ):
                        new_val = _coerce_like(current, new_val)
                    _set_node(working, path, new_val, create_missing=True)
                elif typ == "remove":
                    _del_node(working, path)
                elif typ in {"merge", "deep_merge", "merge_array", "replace_array"}:
                    exists, current = _get_node(working, path)
                    if not exists:
                        parent_parts = path.split(".")[:-1]
                        _ensure_parents(working, parent_parts)
                        current = None
                    new_val = _apply_strategy(current, value, typ, array_key)
                    if (
                        coerce_to_existing_type
                        and current is not None
                        and _is_scalar(current)
                        and _is_scalar(new_val)
                    ):
                        new_val = _coerce_like(current, new_val)
                    _set_node(working, path, new_val, create_missing=True)
                elif typ in {"move", "copy"}:
                    src = op.get("from")
                    if not src:
                        return {
                            "ok": False,
                            "errors": [f"op {typ} requires 'from'"],
                            "yaml": _dump_box_to_yaml(before),
                        }
                    ok_src, node = _get_node(working, src)
                    if not ok_src:
                        return {
                            "ok": False,
                            "errors": [f"source not found: {src}"],
                            "yaml": _dump_box_to_yaml(before),
                        }
                    if typ == "move":
                        _del_node(working, src)
                    _set_node(working, path, copy.deepcopy(node), create_missing=True)
                elif typ == "test":
                    ok_node, node = _get_node(working, path)
                    if not ok_node:
                        return {
                            "ok": False,
                            "errors": [f"test failed: missing {path}"],
                            "yaml": _dump_box_to_yaml(before),
                        }
                    if yaml.safe_dump(_deep_to_plain(node), sort_keys=True) != yaml.safe_dump(
                        _deep_to_plain(value), sort_keys=True
                    ):
                        return {
                            "ok": False,
                            "errors": [f"test failed at {path}"],
                            "yaml": _dump_box_to_yaml(before),
                        }
                else:
                    return {
                        "ok": False,
                        "errors": [f"Unsupported op: {typ}"],
                        "yaml": _dump_box_to_yaml(before),
                    }
                applied.append({"index": i, "op": typ, "path": path})

            if run_validation:
                ok, errors, extra = self._validate_data(working)
                if not ok:
                    return {
                        "ok": False,
                        "errors": errors,
                        "yaml": _dump_box_to_yaml(before),
                        **({"validate": extra} if extra else {}),
                    }

            self.state = working
            self._modified = True
            return {
                "ok": True,
                "yaml": _dump_box_to_yaml(self.state),
                "applied": applied,
            }
        except Exception as e:
            self.state = before
            return {"ok": False, "errors": [str(e)], "yaml": _dump_box_to_yaml(before)}

    async def patch(
        self,
        ops: list[dict[str, Any]],
        validate: bool = True,
        coerce_to_existing_type: bool = True,
    ) -> dict:
        # mypy can't infer BoundTool call signature properly
        return await self._tool_patch(  # type: ignore[return-value,call-overload,misc]
            ops=ops,  # type: ignore[arg-type]
            run_validation=validate,  # type: ignore[arg-type]
            coerce_to_existing_type=coerce_to_existing_type,  # type: ignore[arg-type]
        )

    @tool  # type: ignore[arg-type,misc]
    async def validate(self) -> str:
        ok, errors, extra = self._validate_data(self.state)
        return "ok" if ok else ("ERROR: " + "; ".join(errors))

    @tool  # type: ignore[arg-type,misc]
    async def text(self) -> str:
        return _dump_box_to_yaml(self.state)

    @tool(name="save")  # type: ignore[arg-type,misc]
    async def save(self) -> str:
        await self.persist()
        return f"Saved {self.name}"
