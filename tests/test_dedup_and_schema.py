"""Tests for duplicate tool name deduplication and openapi schema resolution."""
import unittest


class TestDeduplicateName(unittest.TestCase):
    """Test the _deduplicate_name function."""
    
    def test_deduplicate_name_no_conflict(self):
        """Test _deduplicate_name when name doesn't exist in seen set."""
        from mcp4immich.tooling import _deduplicate_name
        
        seen = {"tool_a", "tool_b"}
        result = _deduplicate_name("tool_c", seen)
        assert result == "tool_c"
    
    def test_deduplicate_name_with_conflict(self):
        """Test _deduplicate_name when name already exists."""
        from mcp4immich.tooling import _deduplicate_name
        
        seen = {"search_assets"}
        result = _deduplicate_name("search_assets", seen)
        assert result == "search_assets_2"
    
    def test_deduplicate_name_multiple_conflicts(self):
        """Test _deduplicate_name with multiple existing suffixes."""
        from mcp4immich.tooling import _deduplicate_name
        
        seen = {"search_assets", "search_assets_2", "search_assets_3"}
        result = _deduplicate_name("search_assets", seen)
        assert result == "search_assets_4"
    
    def test_deduplicate_name_empty_seen(self):
        """Test _deduplicate_name with empty seen set."""
        from mcp4immich.tooling import _deduplicate_name
        
        seen: set[str] = set()
        result = _deduplicate_name("tool_a", seen)
        assert result == "tool_a"


class TestResolveSchema(unittest.TestCase):
    """Test the _resolve_schema function."""
    
    def test_resolve_schema_no_ref(self):
        """Test _resolve_schema with schema that has no $ref."""
        from mcp4immich.openapi import _resolve_schema
        
        schema = {"type": "string", "description": "A string field"}
        spec = {}
        result = _resolve_schema(schema, spec)
        assert result == schema
    
    def test_resolve_schema_single_ref(self):
        """Test _resolve_schema resolves a single $ref."""
        from mcp4immich.openapi import _resolve_schema
        
        schema = {"$ref": "#/components/schemas/SearchDto"}
        spec = {
            "components": {
                "schemas": {
                    "SearchDto": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"}
                        }
                    }
                }
            }
        }
        result = _resolve_schema(schema, spec)
        assert result["type"] == "object"
        assert "query" in result["properties"]
    
    def test_resolve_schema_nested_ref(self):
        """Test _resolve_schema resolves nested $ref (schema referencing another schema)."""
        from mcp4immich.openapi import _resolve_schema
        
        # SearchDto has a $ref to another schema
        schema = {"$ref": "#/components/schemas/SearchDto"}
        spec = {
            "components": {
                "schemas": {
                    "SearchDto": {
                        "$ref": "#/components/schemas/BaseSearchDto"
                    },
                    "BaseSearchDto": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "page": {"type": "integer"}
                        }
                    }
                }
            }
        }
        result = _resolve_schema(schema, spec)
        assert result["type"] == "object"
        assert "query" in result["properties"]
        assert "page" in result["properties"]
    
    def test_resolve_schema_cycle_detection(self):
        """Test _resolve_schema handles circular references gracefully."""
        from mcp4immich.openapi import _resolve_schema
        
        # Schema A references B, B references A (cycle)
        schema = {"$ref": "#/components/schemas/SchemaA"}
        spec = {
            "components": {
                "schemas": {
                    "SchemaA": {
                        "$ref": "#/components/schemas/SchemaB"
                    },
                    "SchemaB": {
                        "$ref": "#/components/schemas/SchemaA"
                    }
                }
            }
        }
        # Should not hang or crash; returns the schema when cycle detected
        result = _resolve_schema(schema, spec)
        assert result is not None
    
    def test_resolve_schema_depth_limit(self):
        """Test _resolve_schema respects depth limit."""
        from mcp4immich.openapi import _resolve_schema
        
        # Create a deep chain of references
        spec = {"components": {"schemas": {}}}
        for i in range(15):
            spec["components"]["schemas"][f"Schema{i}"] = {
                "$ref": f"#/components/schemas/Schema{i+1}"
            }
        # Terminal schema
        spec["components"]["schemas"]["Schema15"] = {"type": "string"}
        
        schema = {"$ref": "#/components/schemas/Schema0"}
        # Should stop at depth limit and return something, not recurse infinitely
        result = _resolve_schema(schema, spec)
        assert result is not None
    
    def test_resolve_schema_missing_ref(self):
        """Test _resolve_schema with missing referenced schema."""
        from mcp4immich.openapi import _resolve_schema
        
        schema = {"$ref": "#/components/schemas/NonExistent"}
        spec = {"components": {"schemas": {}}}
        result = _resolve_schema(schema, spec)
        # Should return None when ref doesn't exist
        assert result is None
    
    def test_resolve_schema_none_input(self):
        """Test _resolve_schema with None input."""
        from mcp4immich.openapi import _resolve_schema
        
        result = _resolve_schema(None, {})
        assert result is None
    
    def test_resolve_schema_non_dict_input(self):
        """Test _resolve_schema with non-dict input."""
        from mcp4immich.openapi import _resolve_schema
        
        result = _resolve_schema("not a dict", {})
        assert result is None


def test_parameter_without_type_or_enum_is_described_as_free_text():
    from mcp4immich.tooling import _describe_parameter

    described = _describe_parameter({"name": "q", "in": "query", "schema": {}})

    assert "unknown" not in described
    assert "string" in described


def test_parameter_with_enum_lists_allowed_values():
    from mcp4immich.tooling import _describe_parameter

    described = _describe_parameter(
        {"name": "type", "in": "query", "schema": {"type": "string", "enum": ["country", "city"]}}
    )

    assert "allowed: country, city" in described


def test_no_spec_parameter_renders_as_unknown():
    import json
    from pathlib import Path

    from mcp4immich.tooling import _describe_parameter

    spec = json.loads(Path("mcp4immich/data/immich-openapi-3.json").read_text())
    rendered = [
        _describe_parameter(p)
        for ops in spec["paths"].values()
        for op in ops.values()
        if isinstance(op, dict)
        for p in op.get("parameters", [])
        if isinstance(p, dict)
    ]

    assert rendered, "spec should expose parameters"
    assert [r for r in rendered if "unknown" in r] == []


def _load_vendored_spec():
    import json
    from pathlib import Path

    return json.loads(Path("mcp4immich/data/immich-openapi-3.json").read_text())


def _find_operation_params(spec, operation_id):
    for ops in spec["paths"].values():
        for op in ops.values():
            if isinstance(op, dict) and op.get("operationId") == operation_id:
                return op.get("parameters", [])
    raise AssertionError(f"operationId {operation_id!r} not found in vendored spec")


def test_ref_parameter_resolves_to_its_component_enum_getpartners():
    from mcp4immich.tooling import _describe_parameter

    spec = _load_vendored_spec()
    params = _find_operation_params(spec, "getPartners")
    direction = next(p for p in params if p.get("name") == "direction")

    described = _describe_parameter(direction, spec)

    assert "allowed: shared-by, shared-with" in described


def test_ref_parameter_resolves_to_its_component_enum_getsearchsuggestions():
    from mcp4immich.tooling import _describe_parameter

    spec = _load_vendored_spec()
    params = _find_operation_params(spec, "getSearchSuggestions")
    type_param = next(p for p in params if p.get("name") == "type")

    described = _describe_parameter(type_param, spec)

    for value in (
        "country",
        "state",
        "city",
        "camera-make",
        "camera-model",
        "camera-lens-model",
    ):
        assert value in described
    assert "allowed:" in described


def test_ref_parameter_with_no_enum_falls_back_to_type():
    from mcp4immich.tooling import _describe_parameter

    spec = {
        "components": {
            "schemas": {
                "PlainThing": {"type": "integer"},
            }
        }
    }
    described = _describe_parameter(
        {"name": "count", "in": "query", "schema": {"$ref": "#/components/schemas/PlainThing"}},
        spec,
    )

    assert "unknown" not in described
    assert "integer" in described


def test_ref_parameter_with_missing_target_degrades_to_free_text():
    from mcp4immich.tooling import _describe_parameter

    spec = {"components": {"schemas": {}}}
    described = _describe_parameter(
        {"name": "ghost", "in": "query", "schema": {"$ref": "#/components/schemas/NoSuchThing"}},
        spec,
    )

    assert "unknown" not in described
    assert "string (free text)" in described


def test_ref_parameter_to_a_ref_is_left_unresolved_not_looped():
    from mcp4immich.tooling import _describe_parameter

    spec = {
        "components": {
            "schemas": {
                "Alias": {"$ref": "#/components/schemas/Real"},
                "Real": {"type": "string", "enum": ["a", "b"]},
            }
        }
    }
    described = _describe_parameter(
        {"name": "x", "in": "query", "schema": {"$ref": "#/components/schemas/Alias"}},
        spec,
    )

    # One level only: Alias resolves to another $ref, which is treated as
    # unresolved rather than chased further, so this must NOT see "Real"'s enum.
    assert "unknown" not in described
    assert "allowed:" not in described
    assert "string (free text)" in described


def test_all_single_level_ref_enums_in_spec_render_as_allowed():
    from mcp4immich.tooling import _describe_parameter

    spec = _load_vendored_spec()
    schemas = spec["components"]["schemas"]
    checked = 0
    for ops in spec["paths"].values():
        for op in ops.values():
            if not isinstance(op, dict):
                continue
            for p in op.get("parameters", []):
                if not isinstance(p, dict):
                    continue
                schema = p.get("schema")
                if not isinstance(schema, dict):
                    continue
                ref = schema.get("$ref", "")
                if not isinstance(ref, str) or not ref.startswith(
                    "#/components/schemas/"
                ):
                    continue
                target = schemas.get(ref.rsplit("/", 1)[-1])
                if not isinstance(target, dict) or "$ref" in target:
                    continue
                if not target.get("enum"):
                    continue
                checked += 1
                described = _describe_parameter(p, spec)
                assert "allowed:" in described, (p.get("name"), described)

    assert checked > 0, "expected at least one single-level $ref enum in the vendored spec"


if __name__ == "__main__":
    unittest.main()
