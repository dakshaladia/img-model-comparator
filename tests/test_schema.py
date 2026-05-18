"""Unit tests for services/schema.py — schema parser."""

from services.schema import parse_schema


def test_basic_types(sample_schema):
    inputs = parse_schema(sample_schema)
    by_name = {i.name: i for i in inputs}

    assert by_name["prompt"].type == "string"
    assert by_name["seed"].type == "integer"
    assert by_name["cfg"].type == "number"
    assert by_name["go_fast"].type == "boolean"


def test_ref_enum_resolution(sample_schema):
    inputs = parse_schema(sample_schema)
    by_name = {i.name: i for i in inputs}

    ar = by_name["aspect_ratio"]
    assert ar.type == "string"
    assert ar.enum == ["1:1", "16:9", "9:16", "4:3", "3:4"]
    assert ar.default == "1:1"


def test_min_max_preserved(sample_schema):
    inputs = parse_schema(sample_schema)
    by_name = {i.name: i for i in inputs}

    assert by_name["num_outputs"].minimum == 1
    assert by_name["num_outputs"].maximum == 4
    assert by_name["cfg"].minimum == 1.0
    assert by_name["cfg"].maximum == 10.0


def test_format_uri_not_sweepable(sample_schema):
    inputs = parse_schema(sample_schema)
    by_name = {i.name: i for i in inputs}

    assert by_name["image"].sweepable is False


def test_never_sweep_names(sample_schema):
    """'image' is in NEVER_SWEEP_INPUT_NAMES — should not be sweepable."""
    inputs = parse_schema(sample_schema)
    by_name = {i.name: i for i in inputs}

    assert by_name["image"].sweepable is False


def test_array_type_not_sweepable(sample_schema):
    inputs = parse_schema(sample_schema)
    by_name = {i.name: i for i in inputs}

    assert by_name["image_input"].sweepable is False
    assert by_name["image_input"].type == "array"


def test_sweepable_inputs(sample_schema):
    inputs = parse_schema(sample_schema)
    by_name = {i.name: i for i in inputs}

    assert by_name["prompt"].sweepable is True
    assert by_name["seed"].sweepable is True
    assert by_name["aspect_ratio"].sweepable is True
    assert by_name["cfg"].sweepable is True
    assert by_name["go_fast"].sweepable is True


def test_x_order_sorting(sample_schema):
    inputs = parse_schema(sample_schema)
    names = [i.name for i in inputs]

    # x-order: prompt=0, aspect_ratio=1, num_outputs=2, cfg=3, seed=4, go_fast=8, image=9, image_input=10
    assert names.index("prompt") < names.index("aspect_ratio")
    assert names.index("aspect_ratio") < names.index("num_outputs")
    assert names.index("num_outputs") < names.index("cfg")
    assert names.index("cfg") < names.index("seed")
    assert names.index("seed") < names.index("go_fast")


def test_missing_type_defaults_to_string():
    schema = {
        "components": {
            "schemas": {
                "Input": {
                    "type": "object",
                    "properties": {
                        "mystery": {"description": "No type field"},
                    },
                }
            }
        }
    }
    inputs = parse_schema(schema)
    assert len(inputs) == 1
    assert inputs[0].type == "string"


def test_empty_schema():
    assert parse_schema({}) == []
    assert parse_schema({"components": {"schemas": {}}}) == []
    assert parse_schema({"components": {"schemas": {"Input": {}}}}) == []
