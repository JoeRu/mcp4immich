"""Tests for mcp4immich/prompts.py"""


def test_prompts_module_available():
    """Test that prompts module can be imported."""
    from mcp4immich import prompts

    assert prompts is not None


def test_register_prompts_and_resources():
    """Test that register_prompts_and_resources is callable."""
    from mcp4immich.prompts import register_prompts_and_resources

    # Test that the function exists and is callable
    assert callable(register_prompts_and_resources)


def test_load_usage_guide():
    """Test that _load_usage_guide can be imported."""
    from mcp4immich.prompts import _load_usage_guide

    # Test that the function exists
    assert callable(_load_usage_guide)


def test_all_prompts_have_descriptions():
    """Test that every prompt registered via register_prompts_and_resources has a non-empty description."""
    from mcp4immich.prompts import register_prompts_and_resources

    registered_prompts = []

    class FakeMCP:
        def resource(self, *args, **kwargs):
            def decorator(fn):
                return fn
            return decorator

        def prompt(self, *args, **kwargs):
            def decorator(fn):
                registered_prompts.append(kwargs)
                return fn
            return decorator

    fake = FakeMCP()
    register_prompts_and_resources(fake)

    assert len(registered_prompts) == 10, f"Expected 10 prompts, got {len(registered_prompts)}"
    for prompt_kwargs in registered_prompts:
        title = prompt_kwargs.get("title", "<no title>")
        desc = prompt_kwargs.get("description", "")
        assert desc, f"Prompt '{title}' has an empty description"


def test_prompt_messages_use_explicit_tool_names():
    """Ensure key prompts provide concrete tool names and argument examples."""
    from mcp4immich.prompts import register_prompts_and_resources

    registered_prompts = {}

    class FakeMCP:
        def resource(self, *args, **kwargs):
            def decorator(fn):
                return fn
            return decorator

        def prompt(self, *args, **kwargs):
            def decorator(fn):
                title = kwargs.get("title")
                registered_prompts[title] = fn
                return fn
            return decorator

    fake = FakeMCP()
    register_prompts_and_resources(fake)

    search_assets_msg = registered_prompts["Immich: Search assets"]("mountain")
    assert "immich_searchassets" in search_assets_msg
    assert "Example args" in search_assets_msg

    smart_msg = registered_prompts["Immich: Smart search"]("dog")
    assert "immich_searchsmart" in smart_msg
    assert "body_query" in smart_msg

    get_image_msg = registered_prompts["Immich: Get image"]("asset-1")
    assert "immich_getassetinfo" in get_image_msg
    assert "path_id" in get_image_msg
