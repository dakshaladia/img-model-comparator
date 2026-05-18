"""Parse a Replicate OpenAPI schema dict into a list of ModelInput objects."""

from __future__ import annotations

from config import NEVER_SWEEP_INPUT_NAMES
from models import ModelInput


def _resolve_ref(ref_path: str, all_schemas: dict) -> dict:
    """Resolve a $ref like '#/components/schemas/aspect_ratio' to its schema dict."""
    name = ref_path.split("/")[-1]
    return all_schemas.get(name, {})


def parse_schema(raw_schema: dict) -> list[ModelInput]:
    """Convert a raw Replicate OpenAPI schema into a sorted list of ModelInput."""
    all_schemas = raw_schema.get("components", {}).get("schemas", {})
    input_schema = all_schemas.get("Input", {})
    properties = input_schema.get("properties", {})

    inputs: list[ModelInput] = []

    for idx, (name, prop) in enumerate(properties.items()):
        prop_type = prop.get("type")
        enum_values = prop.get("enum")

        # Resolve $ref enums via allOf
        if not prop_type and "allOf" in prop:
            for ref_obj in prop["allOf"]:
                if "$ref" in ref_obj:
                    resolved = _resolve_ref(ref_obj["$ref"], all_schemas)
                    prop_type = resolved.get("type", "string")
                    enum_values = resolved.get("enum")
                    break

        # Default to string if type is still unknown
        if not prop_type:
            prop_type = "string"

        # Determine sweepability
        sweepable = True
        if name in NEVER_SWEEP_INPUT_NAMES:
            sweepable = False
        elif prop.get("format") == "uri":
            sweepable = False
        elif prop_type == "array":
            sweepable = False

        inputs.append(ModelInput(
            name=name,
            type=prop_type,
            default=prop.get("default"),
            description=prop.get("description", ""),
            minimum=prop.get("minimum"),
            maximum=prop.get("maximum"),
            enum=enum_values,
            format=prop.get("format", ""),
            sweepable=sweepable,
            order=prop.get("x-order", idx),
        ))

    inputs.sort(key=lambda i: i.order)
    return inputs
