"""A minimal, dependency-free validator for the small subset of JSON Schema
(draft-07) that `schemas/*.schema.json` actually uses.

Not a general JSON Schema engine -- deliberately so. Adding a `jsonschema`
dependency (even dev-only) for a handful of flat objects with `type`,
`required`, `properties`, `enum`, `items`, `minimum`/`maximum`, and one
level of local `$ref`/`$defs` would be more machinery than the schema it
checks; see docs/LANGUAGE_STRATEGY.md's "zero required dependency" reasoning
-- the same principle applies to test-only tooling, not just runtime code.
Extend this if a future schema needs a feature it doesn't support yet;
don't silently ignore an unsupported keyword.
"""
from typing import Any, Dict, List

_TYPE_MAP = {
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
}


class SchemaValidationError(AssertionError):
    pass


def _resolve(schema: Dict[str, Any], root: Dict[str, Any]) -> Dict[str, Any]:
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/$defs/"):
            raise SchemaValidationError(f"Unsupported $ref (only local #/$defs/ is supported): {ref}")
        return root["$defs"][ref.split("/")[-1]]
    return schema


def _check_type(value: Any, type_spec, path: str) -> None:
    types = type_spec if isinstance(type_spec, list) else [type_spec]
    py_types = tuple(_TYPE_MAP[t] for t in types)
    # bool is a subclass of int in Python; JSON Schema treats them as
    # distinct, so reject a bool where only "number"/"integer" is allowed.
    if isinstance(value, bool) and bool not in py_types:
        raise SchemaValidationError(f"{path}: expected {types}, got bool")
    if not isinstance(value, py_types):
        raise SchemaValidationError(f"{path}: expected {types}, got {type(value).__name__}")


def validate(instance: Any, schema: Dict[str, Any], root: Dict[str, Any] = None, path: str = "$") -> None:
    """Raises SchemaValidationError on the first violation found."""
    root = root if root is not None else schema
    schema = _resolve(schema, root)

    if "type" in schema:
        _check_type(instance, schema["type"], path)

    if "enum" in schema and instance not in schema["enum"]:
        raise SchemaValidationError(f"{path}: {instance!r} not in enum {schema['enum']}")

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                raise SchemaValidationError(f"{path}: missing required property '{key}'")
        for key, subschema in schema.get("properties", {}).items():
            if key in instance:
                validate(instance[key], subschema, root, f"{path}.{key}")

    if isinstance(instance, list) and "items" in schema:
        for i, item in enumerate(instance):
            validate(item, schema["items"], root, f"{path}[{i}]")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            raise SchemaValidationError(f"{path}: {instance} < minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            raise SchemaValidationError(f"{path}: {instance} > maximum {schema['maximum']}")


def required_fields(schema: Dict[str, Any], *path: str) -> List[str]:
    """Walk `path` through $defs (e.g. required_fields(schema, "$defs", "taskProfile"))
    and return its `required` list -- used to cross-check against each
    language implementation's own required-field list, so schema drift
    fails a test instead of going unnoticed."""
    node = schema
    for segment in path:
        node = node[segment]
    return list(node.get("required", []))
