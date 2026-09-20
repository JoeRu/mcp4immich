"""Tests for URL decoration functions in mcp4immich/tooling.py"""
import pytest


def test_should_decorate_response_asset():
    """Test _should_decorate_response detects asset endpoints."""
    from mcp4immich.tooling import _should_decorate_response
    
    result, url_type = _should_decorate_response("GET", "/assets/{id}")
    assert result is True
    assert url_type == "asset"


def test_should_decorate_response_album():
    """Test _should_decorate_response detects album endpoints."""
    from mcp4immich.tooling import _should_decorate_response
    
    result, url_type = _should_decorate_response("GET", "/albums/{id}")
    assert result is True
    assert url_type == "album"


def test_should_decorate_response_person():
    """Test _should_decorate_response detects person endpoints."""
    from mcp4immich.tooling import _should_decorate_response
    
    result, url_type = _should_decorate_response("GET", "/people/{id}")
    assert result is True
    assert url_type == "person"


def test_should_decorate_response_place():
    """Test _should_decorate_response detects place endpoints."""
    from mcp4immich.tooling import _should_decorate_response
    
    result, url_type = _should_decorate_response("GET", "/places/{id}")
    assert result is True
    assert url_type == "place"


def test_should_decorate_response_no_match():
    """Test _should_decorate_response ignores non-matching endpoints."""
    from mcp4immich.tooling import _should_decorate_response
    
    result, url_type = _should_decorate_response("GET", "/server/version")
    assert result is False
    assert url_type is None


def test_should_decorate_response_post_non_search_not_decorated():
    """Test _should_decorate_response does not decorate non-search POST methods."""
    from mcp4immich.tooling import _should_decorate_response
    
    result, url_type = _should_decorate_response("POST", "/assets/{id}")
    assert result is False
    assert url_type is None


def test_should_decorate_response_post_search_decorated():
    """Test _should_decorate_response decorates POST search endpoints."""
    from mcp4immich.tooling import _should_decorate_response

    result, url_type = _should_decorate_response("POST", "/search/assets")
    assert result is True
    assert url_type == "array"


def test_extract_single_id_with_id_field():
    """Test _extract_single_id extracts id field."""
    from mcp4immich.tooling import _extract_single_id
    
    data = {"id": "abc-123", "name": "Test Asset"}
    result = _extract_single_id(data)
    assert result == "abc-123"


def test_extract_single_id_with_albumid_field():
    """Test _extract_single_id extracts albumId field."""
    from mcp4immich.tooling import _extract_single_id
    
    data = {"albumId": "album-456", "albumName": "My Album"}
    result = _extract_single_id(data)
    assert result == "album-456"


def test_extract_single_id_with_personid_field():
    """Test _extract_single_id extracts personId field."""
    from mcp4immich.tooling import _extract_single_id
    
    data = {"personId": "person-789", "name": "John"}
    result = _extract_single_id(data)
    assert result == "person-789"


def test_extract_single_id_with_placeid_field():
    """Test _extract_single_id extracts placeId field."""
    from mcp4immich.tooling import _extract_single_id
    
    data = {"placeId": "place-999", "name": "New York"}
    result = _extract_single_id(data)
    assert result == "place-999"


def test_extract_single_id_no_id():
    """Test _extract_single_id returns None when no ID found."""
    from mcp4immich.tooling import _extract_single_id
    
    data = {"name": "Test", "description": "No ID here"}
    result = _extract_single_id(data)
    assert result is None


def test_extract_single_id_not_dict():
    """Test _extract_single_id returns None for non-dict input."""
    from mcp4immich.tooling import _extract_single_id
    
    result = _extract_single_id("not a dict")
    assert result is None


def test_extract_single_id_empty_dict():
    """Test _extract_single_id returns None for empty dict."""
    from mcp4immich.tooling import _extract_single_id
    
    result = _extract_single_id({})
    assert result is None


def test_decorate_response_asset():
    """Test _decorate_response adds web_url for asset."""
    from mcp4immich.tooling import _decorate_response
    
    response = {"id": "asset-123", "name": "My Photo"}
    decorated = _decorate_response(response, "https://immich.example.com", "asset")
    
    assert "web_url" in decorated
    assert decorated["web_url"] == "https://immich.example.com/photos/asset-123"


def test_decorate_response_album():
    """Test _decorate_response adds web_url for album."""
    from mcp4immich.tooling import _decorate_response
    
    response = {"albumId": "album-456", "albumName": "My Album"}
    decorated = _decorate_response(response, "https://immich.example.com", "album")
    
    assert "web_url" in decorated
    assert decorated["web_url"] == "https://immich.example.com/albums/album-456"


def test_decorate_response_person():
    """Test _decorate_response adds web_url for person."""
    from mcp4immich.tooling import _decorate_response
    
    response = {"personId": "person-789", "name": "John"}
    decorated = _decorate_response(response, "https://immich.example.com", "person")
    
    assert "web_url" in decorated
    assert decorated["web_url"] == "https://immich.example.com/people/person-789"


def test_decorate_response_place():
    """Test _decorate_response adds web_url for place."""
    from mcp4immich.tooling import _decorate_response
    
    response = {"placeId": "place-999", "name": "New York"}
    decorated = _decorate_response(response, "https://immich.example.com", "place")
    
    assert "web_url" in decorated
    assert decorated["web_url"] == "https://immich.example.com/explore?places=place-999"


def test_decorate_response_no_domain():
    """Test _decorate_response returns unchanged response when no domain."""
    from mcp4immich.tooling import _decorate_response
    
    response = {"id": "asset-123", "name": "My Photo"}
    decorated = _decorate_response(response, None, "asset")
    
    assert "web_url" not in decorated
    assert decorated == response


def test_decorate_response_not_dict():
    """Test _decorate_response returns unchanged response for non-dict."""
    from mcp4immich.tooling import _decorate_response
    
    response = "string response"
    decorated = _decorate_response(response, "https://immich.example.com", "asset")
    
    assert decorated == response


def test_decorate_response_no_id():
    """Test _decorate_response returns unchanged response when no ID."""
    from mcp4immich.tooling import _decorate_response
    
    response = {"name": "No ID here", "description": "Test"}
    decorated = _decorate_response(response, "https://immich.example.com", "asset")
    
    assert "web_url" not in decorated
    assert decorated == response


def test_decorate_response_existing_web_url():
    """Test _decorate_response does not overwrite existing web_url."""
    from mcp4immich.tooling import _decorate_response
    
    response = {"id": "asset-123", "web_url": "https://custom.url"}
    decorated = _decorate_response(response, "https://immich.example.com", "asset")
    
    # Should not overwrite existing web_url
    assert decorated["web_url"] == "https://custom.url"


def test_decorate_response_http_domain():
    """Test _decorate_response works with HTTP domain."""
    from mcp4immich.tooling import _decorate_response
    
    response = {"id": "asset-123"}
    decorated = _decorate_response(response, "http://localhost:2283", "asset")
    
    assert "web_url" in decorated
    assert decorated["web_url"] == "http://localhost:2283/photos/asset-123"


def test_should_decorate_response_search_endpoint():
    """Test _should_decorate_response detects search endpoints."""
    from mcp4immich.tooling import _should_decorate_response
    
    result, url_type = _should_decorate_response("GET", "/search/array")
    assert result is True
    assert url_type == "array"


def test_should_decorate_response_assets_list():
    """Test _should_decorate_response detects bulk assets endpoint."""
    from mcp4immich.tooling import _should_decorate_response
    
    result, url_type = _should_decorate_response("GET", "/assets")
    assert result is True
    assert url_type == "array"


def test_should_decorate_response_albums_list():
    """Test _should_decorate_response detects bulk albums endpoint."""
    from mcp4immich.tooling import _should_decorate_response
    
    result, url_type = _should_decorate_response("GET", "/albums")
    assert result is True
    assert url_type == "array"


def test_detect_response_type_image():
    """Test _detect_response_type identifies IMAGE type as asset."""
    from mcp4immich.tooling import _detect_response_type
    
    item = {"id": "asset-123", "type": "IMAGE", "name": "Photo"}
    url_type = _detect_response_type(item)
    assert url_type == "asset"


def test_detect_response_type_video():
    """Test _detect_response_type identifies VIDEO type as asset."""
    from mcp4immich.tooling import _detect_response_type
    
    item = {"id": "video-456", "type": "VIDEO", "name": "Movie"}
    url_type = _detect_response_type(item)
    assert url_type == "asset"


def test_detect_response_type_memory():
    """Test _detect_response_type identifies MEMORY type as asset."""
    from mcp4immich.tooling import _detect_response_type
    
    item = {"id": "mem-789", "type": "MEMORY", "name": "Memory"}
    url_type = _detect_response_type(item)
    assert url_type == "asset"


def test_detect_response_type_album():
    """Test _detect_response_type identifies ALBUM type."""
    from mcp4immich.tooling import _detect_response_type
    
    item = {"albumId": "album-123", "type": "ALBUM", "albumName": "Collection"}
    url_type = _detect_response_type(item)
    assert url_type == "album"


def test_detect_response_type_person():
    """Test _detect_response_type identifies PERSON type."""
    from mcp4immich.tooling import _detect_response_type
    
    item = {"personId": "person-456", "type": "PERSON", "name": "John"}
    url_type = _detect_response_type(item)
    assert url_type == "person"


def test_detect_response_type_place():
    """Test _detect_response_type identifies PLACE type."""
    from mcp4immich.tooling import _detect_response_type
    
    item = {"placeId": "place-789", "type": "PLACE", "name": "New York"}
    url_type = _detect_response_type(item)
    assert url_type == "place"


def test_detect_response_type_infer_from_field():
    """Test _detect_response_type infers type from ID field names."""
    from mcp4immich.tooling import _detect_response_type
    
    # Can't determine without type field
    item = {"albumId": "album-123"}
    url_type = _detect_response_type(item)
    assert url_type == "album"


def test_detect_response_type_no_type():
    """Test _detect_response_type returns None when unable to determine."""
    from mcp4immich.tooling import _detect_response_type
    
    item = {"name": "Unknown", "description": "No type field"}
    url_type = _detect_response_type(item)
    assert url_type is None


def test_detect_response_type_not_dict():
    """Test _detect_response_type returns None for non-dict."""
    from mcp4immich.tooling import _detect_response_type
    
    url_type = _detect_response_type("string")
    assert url_type is None


def test_decorate_response_array_with_images():
    """Test _decorate_response handles array of IMAGE items."""
    from mcp4immich.tooling import _decorate_response
    
    response = [
        {"id": "img-1", "type": "IMAGE", "name": "Photo 1"},
        {"id": "img-2", "type": "IMAGE", "name": "Photo 2"},
    ]
    
    decorated = _decorate_response(response, "https://immich.example.com", "array")
    
    assert len(decorated) == 2
    assert decorated[0]["web_url"] == "https://immich.example.com/photos/img-1"
    assert decorated[1]["web_url"] == "https://immich.example.com/photos/img-2"


def test_decorate_response_array_mixed_types():
    """Test _decorate_response handles array with mixed types."""
    from mcp4immich.tooling import _decorate_response
    
    response = [
        {"id": "img-1", "type": "IMAGE", "name": "Photo"},
        {"albums": [{"albumId": "album-1", "type": "ALBUM", "albumName": "Collection"}]},
    ]
    
    decorated = _decorate_response(response, "https://immich.example.com", "array")
    
    assert len(decorated) == 2
    assert "web_url" in decorated[0]
    assert decorated[0]["web_url"] == "https://immich.example.com/photos/img-1"
    # Second item doesn't have top-level type field, so it won't be decorated
    assert "web_url" not in decorated[1]


def test_decorate_response_array_preserves_structure():
    """Test _decorate_response preserves array structure."""
    from mcp4immich.tooling import _decorate_response
    
    response = [
        {"id": "img-1", "type": "IMAGE"},
        {"id": "img-2", "type": "IMAGE"},
        {"id": "img-3", "type": "IMAGE"},
    ]
    
    decorated = _decorate_response(response, "https://immich.example.com", "array")
    
    assert isinstance(decorated, list)
    assert len(decorated) == 3


def test_decorate_response_array_empty():
    """Test _decorate_response handles empty arrays."""
    from mcp4immich.tooling import _decorate_response
    
    response = []
    decorated = _decorate_response(response, "https://immich.example.com", "array")
    
    assert decorated == []


def test_decorate_response_array_no_domain():
    """Test _decorate_response returns array unchanged when no domain."""
    from mcp4immich.tooling import _decorate_response
    
    response = [
        {"id": "img-1", "type": "IMAGE"},
        {"id": "img-2", "type": "IMAGE"},
    ]
    
    decorated = _decorate_response(response, None, "array")
    
    # Should return original response when no domain
    assert decorated == response
    assert "web_url" not in decorated[0]


def test_decorate_response_array_skip_items_without_id():
    """Test _decorate_response skips array items without ID."""
    from mcp4immich.tooling import _decorate_response
    
    response = [
        {"id": "img-1", "type": "IMAGE"},
        {"type": "IMAGE", "name": "No ID"},  # Missing id field
        {"id": "img-3", "type": "IMAGE"},
    ]
    
    decorated = _decorate_response(response, "https://immich.example.com", "array")
    
    assert len(decorated) == 3
    assert "web_url" in decorated[0]
    assert "web_url" not in decorated[1]  # Skipped due to no ID
    assert "web_url" in decorated[2]


def test_decorate_response_asset_uses_assetid_over_personid():
    """Asset decoration should use asset UUID, not person UUID fields."""
    from mcp4immich.tooling import _decorate_response

    response = {
        "assetId": "asset-123",
        "personId": "person-999",
        "type": "IMAGE",
        "name": "Tagged photo",
    }

    decorated = _decorate_response(response, "https://immich.example.com", "array")
    assert decorated["web_url"] == "https://immich.example.com/photos/asset-123"


def test_decorate_response_asset_ignores_personid_when_id_present():
    """Asset decoration should use id and never fall back to personId for /photos URLs."""
    from mcp4immich.tooling import _decorate_response

    response = {
        "id": "asset-456",
        "personId": "person-123",
        "type": "IMAGE",
    }

    decorated = _decorate_response(response, "https://immich.example.com", "array")
    assert decorated["web_url"] == "https://immich.example.com/photos/asset-456"


def test_decorate_response_asset_without_asset_id_skips_personid():
    """Asset decoration should not build /photos URL from personId when asset ID is missing."""
    from mcp4immich.tooling import _decorate_response

    response = {
        "personId": "person-123",
        "type": "IMAGE",
    }

    decorated = _decorate_response(response, "https://immich.example.com", "array")
    assert "web_url" not in decorated


def test_decorate_response_array_non_dict_items():
    """Test _decorate_response skips non-dict items in arrays."""
    from mcp4immich.tooling import _decorate_response
    
    response = [
        {"id": "img-1", "type": "IMAGE"},
        "string item",
        {"id": "img-2", "type": "IMAGE"},
    ]
    
    decorated = _decorate_response(response, "https://immich.example.com", "array")
    
    assert len(decorated) == 3
    assert "web_url" in decorated[0]
    assert decorated[1] == "string item"
    assert "web_url" in decorated[2]


def test_decorate_response_backward_compat_single_object():
    """Test _decorate_response maintains backward compatibility for single objects."""
    from mcp4immich.tooling import _decorate_response
    
    # Single object with specific url_type (not 'array')
    response = {"id": "asset-123"}
    decorated = _decorate_response(response, "https://immich.example.com", "asset")
    
    assert isinstance(decorated, dict)
    assert "web_url" in decorated
    assert decorated["web_url"] == "https://immich.example.com/photos/asset-123"


def test_decorate_response_backward_compat_album():
    """Test _decorate_response maintains backward compatibility for albums."""
    from mcp4immich.tooling import _decorate_response
    
    response = {"albumId": "album-456"}
    decorated = _decorate_response(response, "https://immich.example.com", "album")
    
    assert isinstance(decorated, dict)
    assert "web_url" in decorated
    assert decorated["web_url"] == "https://immich.example.com/albums/album-456"


def test_decorate_response_array_videos():
    """Test _decorate_response handles VIDEO items in arrays."""
    from mcp4immich.tooling import _decorate_response
    
    response = [
        {"id": "vid-1", "type": "VIDEO", "name": "Movie 1"},
        {"id": "vid-2", "type": "VIDEO", "name": "Movie 2"},
    ]
    
    decorated = _decorate_response(response, "https://immich.example.com", "array")
    
    assert len(decorated) == 2
    # Videos should also map to /photos/{id}
    assert decorated[0]["web_url"] == "https://immich.example.com/photos/vid-1"
    assert decorated[1]["web_url"] == "https://immich.example.com/photos/vid-2"


def test_decorate_response_array_existing_web_urls():
    """Test _decorate_response doesn't overwrite existing web_urls in arrays."""
    from mcp4immich.tooling import _decorate_response
    
    response = [
        {"id": "img-1", "type": "IMAGE", "web_url": "https://custom.com/1"},
        {"id": "img-2", "type": "IMAGE"},
    ]
    
    decorated = _decorate_response(response, "https://immich.example.com", "array")
    
    # Should preserve custom URL
    assert decorated[0]["web_url"] == "https://custom.com/1"
    # Should add URL to second item
    assert decorated[1]["web_url"] == "https://immich.example.com/photos/img-2"


def test_extract_decoratable_array_direct_list():
    """Test _extract_decoratable_array returns direct list as-is."""
    from mcp4immich.tooling import _extract_decoratable_array
    
    response = [
        {"id": "img-1", "type": "IMAGE"},
        {"id": "img-2", "type": "IMAGE"},
    ]
    
    array, wrapper_type = _extract_decoratable_array(response)
    assert array == response
    assert wrapper_type == "direct"


def test_extract_decoratable_array_results_wrapper():
    """Test _extract_decoratable_array extracts from 'results' field."""
    from mcp4immich.tooling import _extract_decoratable_array
    
    response = {
        "results": [
            {"id": "img-1", "type": "IMAGE"},
            {"id": "img-2", "type": "IMAGE"},
        ],
        "total": 2,
    }
    
    array, wrapper_type = _extract_decoratable_array(response)
    assert len(array) == 2
    assert wrapper_type == "wrapped"
    assert array[0]["id"] == "img-1"


def test_extract_decoratable_array_data_wrapper():
    """Test _extract_decoratable_array extracts from 'data' field."""
    from mcp4immich.tooling import _extract_decoratable_array
    
    response = {
        "data": [
            {"id": "img-1", "type": "IMAGE"},
            {"id": "img-2", "type": "IMAGE"},
        ],
        "pagination": {"page": 1},
    }
    
    array, wrapper_type = _extract_decoratable_array(response)
    assert len(array) == 2
    assert wrapper_type == "wrapped"


def test_extract_decoratable_array_assets_wrapper():
    """Test _extract_decoratable_array extracts from 'assets' field."""
    from mcp4immich.tooling import _extract_decoratable_array
    
    response = {
        "assets": [
            {"id": "img-1", "type": "IMAGE"},
            {"id": "img-2", "type": "IMAGE"},
        ],
    }
    
    array, wrapper_type = _extract_decoratable_array(response)
    assert len(array) == 2
    assert wrapper_type == "wrapped"


def test_extract_decoratable_array_items_wrapper():
    """Test _extract_decoratable_array extracts from 'items' field."""
    from mcp4immich.tooling import _extract_decoratable_array
    
    response = {
        "items": [
            {"id": "img-1", "type": "IMAGE"},
        ],
    }
    
    array, wrapper_type = _extract_decoratable_array(response)
    assert len(array) == 1
    assert wrapper_type == "wrapped"


def test_extract_decoratable_array_no_wrapper():
    """Test _extract_decoratable_array returns None when no array found."""
    from mcp4immich.tooling import _extract_decoratable_array
    
    response = {"name": "Search Result", "count": 5}
    
    array, wrapper_type = _extract_decoratable_array(response)
    assert array is None
    assert wrapper_type == "none"


def test_extract_decoratable_array_non_dict():
    """Test _extract_decoratable_array returns None for non-dict, non-list."""
    from mcp4immich.tooling import _extract_decoratable_array
    
    array, wrapper_type = _extract_decoratable_array("string")
    assert array is None
    assert wrapper_type == "none"


def test_decorate_response_wrapped_results():
    """Test _decorate_response handles wrapped 'results' array."""
    from mcp4immich.tooling import _decorate_response
    
    response = {
        "results": [
            {"id": "img-1", "type": "IMAGE", "name": "Photo 1"},
            {"id": "img-2", "type": "IMAGE", "name": "Photo 2"},
        ],
        "total": 2,
    }
    
    decorated = _decorate_response(response, "https://immich.example.com", "array")
    
    # Should preserve wrapper structure
    assert "results" in decorated
    assert "total" in decorated
    # Items should be decorated
    assert decorated["results"][0]["web_url"] == "https://immich.example.com/photos/img-1"
    assert decorated["results"][1]["web_url"] == "https://immich.example.com/photos/img-2"


def test_decorate_response_wrapped_data():
    """Test _decorate_response handles wrapped 'data' array with pagination."""
    from mcp4immich.tooling import _decorate_response
    
    response = {
        "data": [
            {"id": "img-1", "type": "IMAGE"},
            {"id": "img-2", "type": "IMAGE"},
        ],
        "pagination": {"next": "cursor123"},
    }
    
    decorated = _decorate_response(response, "https://immich.example.com", "array")
    
    assert "data" in decorated
    assert "pagination" in decorated
    assert decorated["data"][0]["web_url"] == "https://immich.example.com/photos/img-1"
    assert decorated["pagination"]["next"] == "cursor123"


def test_decorate_response_wrapped_assets():
    """Test _decorate_response handles 'assets' wrapper field."""
    from mcp4immich.tooling import _decorate_response
    
    response = {
        "assets": [
            {"id": "img-1", "type": "IMAGE"},
            {"id": "img-2", "type": "VIDEO"},
        ],
    }
    
    decorated = _decorate_response(response, "https://immich.example.com", "array")
    
    assert len(decorated["assets"]) == 2
    assert decorated["assets"][0]["web_url"] == "https://immich.example.com/photos/img-1"
    assert decorated["assets"][1]["web_url"] == "https://immich.example.com/photos/img-2"


def test_decorate_response_wrapped_preserves_metadata():
    """Test _decorate_response preserves metadata fields in wrapped responses."""
    from mcp4immich.tooling import _decorate_response
    
    response = {
        "results": [
            {"id": "img-1", "type": "IMAGE"},
        ],
        "count": 1,
        "hasNextPage": False,
        "hasPreviousPage": False,
    }
    
    decorated = _decorate_response(response, "https://immich.example.com", "array")
    
    # All metadata should be preserved
    assert decorated["count"] == 1
    assert decorated["hasNextPage"] is False
    assert decorated["hasPreviousPage"] is False
    assert decorated["results"][0]["web_url"] == "https://immich.example.com/photos/img-1"


def test_should_decorate_response_explore_endpoint():
    """Test _should_decorate_response detects explore endpoints."""
    from mcp4immich.tooling import _should_decorate_response
    
    result, url_type = _should_decorate_response("GET", "/explore")
    assert result is True
    assert url_type == "array"


def test_should_decorate_response_memories_endpoint():
    """Test _should_decorate_response detects memories endpoints."""
    from mcp4immich.tooling import _should_decorate_response
    
    result, url_type = _should_decorate_response("GET", "/memories")
    assert result is True
    assert url_type == "array"


def test_should_decorate_response_cine_endpoint():
    """Test _should_decorate_response detects cine endpoints."""
    from mcp4immich.tooling import _should_decorate_response
    
    result, url_type = _should_decorate_response("GET", "/cine")
    assert result is True
    assert url_type == "array"


def test_should_decorate_response_timelines_endpoint():
    """Test _should_decorate_response detects timeline endpoints."""
    from mcp4immich.tooling import _should_decorate_response
    
    result, url_type = _should_decorate_response("GET", "/timelines")
    assert result is True
    assert url_type == "array"


def test_should_decorate_response_statistics_endpoint():
    """Test _should_decorate_response detects statistics endpoints."""
    from mcp4immich.tooling import _should_decorate_response
    
    result, url_type = _should_decorate_response("GET", "/statistics")
    assert result is True
    assert url_type == "array"


def test_should_decorate_response_map_endpoint():
    """Test _should_decorate_response detects map endpoints."""
    from mcp4immich.tooling import _should_decorate_response
    
    result, url_type = _should_decorate_response("GET", "/map")
    assert result is True
    assert url_type == "array"


def test_should_decorate_response_bulk_albums():
    """Test _should_decorate_response detects bulk albums endpoint."""
    from mcp4immich.tooling import _should_decorate_response
    
    result, url_type = _should_decorate_response("GET", "/albums")
    assert result is True
    assert url_type == "array"


def test_should_decorate_response_bulk_people():
    """Test _should_decorate_response detects bulk people endpoint."""
    from mcp4immich.tooling import _should_decorate_response
    
    result, url_type = _should_decorate_response("GET", "/people")
    assert result is True
    assert url_type == "array"


def test_should_decorate_response_bulk_places():
    """Test _should_decorate_response detects bulk places endpoint."""
    from mcp4immich.tooling import _should_decorate_response
    
    result, url_type = _should_decorate_response("GET", "/places")
    assert result is True
    assert url_type == "array"


def test_decorate_response_complex_nested_search_result():
    """Test _decorate_response with realistic search result structure."""
    from mcp4immich.tooling import _decorate_response
    
    # Realistic search response structure
    response = {
        "results": [
            {
                "data": {
                    "id": "asset-1",
                    "type": "IMAGE",
                    "name": "Beach Photo",
                },
                "score": 0.95,
            },
            {
                "data": {
                    "id": "asset-2",
                    "type": "VIDEO",
                    "name": "Sunset Video",
                },
                "score": 0.87,
            },
        ],
        "query": "beach",
        "duration": 125,
    }
    
    # Decorate the results array
    decorated = _decorate_response(response, "https://immich.example.com", "array")
    
    assert "query" in decorated
    assert decorated["query"] == "beach"
    assert len(decorated["results"]) == 2
    # Note: nested "data" field won't be decorated by default since we only search top-level
    # But the outer results array would preserve the structure


def test_decorate_response_empty_wrapped_array():
    """Test _decorate_response handles empty wrapped arrays."""
    from mcp4immich.tooling import _decorate_response
    
    response = {
        "results": [],
        "total": 0,
    }
    
    decorated = _decorate_response(response, "https://immich.example.com", "array")
    
    assert decorated["results"] == []
    assert decorated["total"] == 0


def test_detect_response_type_person_with_birthdate():
    """Test _detect_response_type identifies person by birthDate field (no explicit type)."""
    from mcp4immich.tooling import _detect_response_type
    
    # Person object with just "id" and "birthDate" (common in search results)
    item = {"id": "person-123", "name": "John", "birthDate": "1990-01-01"}
    url_type = _detect_response_type(item)
    assert url_type == "person"


def test_detect_response_type_person_with_thumbnailpath():
    """Test _detect_response_type identifies person by thumbnailPath field (no explicit type)."""
    from mcp4immich.tooling import _detect_response_type
    
    # Person object with just "id" and "thumbnailPath" (common in people endpoint)
    item = {"id": "person-456", "name": "Jane", "thumbnailPath": "/path/to/thumb.jpg"}
    url_type = _detect_response_type(item)
    assert url_type == "person"


def test_decorate_response_person_with_id_and_birthdate():
    """Test _decorate_response correctly decorates person with id + birthDate (no personId)."""
    from mcp4immich.tooling import _decorate_response
    
    # Person object from search results with just "id" field
    response = {"id": "person-123", "name": "John", "birthDate": "1990-01-01"}
    decorated = _decorate_response(response, "https://immich.example.com", "array")
    
    # Should have correct /people/{id} URL, not /photos/{id}
    assert "web_url" in decorated
    assert decorated["web_url"] == "https://immich.example.com/people/person-123"


def test_decorate_response_person_with_id_and_thumbnailpath():
    """Test _decorate_response correctly decorates person with id + thumbnailPath (no personId)."""
    from mcp4immich.tooling import _decorate_response
    
    # Person object from /people endpoint with just "id" field
    response = {"id": "person-456", "name": "Jane", "thumbnailPath": "/path/to/thumb.jpg"}
    decorated = _decorate_response(response, "https://immich.example.com", "array")
    
    # Should have correct /people/{id} URL, not /photos/{id}
    assert "web_url" in decorated
    assert decorated["web_url"] == "https://immich.example.com/people/person-456"


def test_decorate_response_person_array_with_birthdate():
    """Test _decorate_response correctly decorates array of people with birthDate field."""
    from mcp4immich.tooling import _decorate_response
    
    # Array of people (e.g., from search results)
    response = [
        {"id": "person-1", "name": "Alice", "birthDate": "1990-01-01"},
        {"id": "person-2", "name": "Bob", "birthDate": "1985-06-15"},
    ]
    decorated = _decorate_response(response, "https://immich.example.com", "array")
    
    # Each person should have correct /people/{id} URL
    assert len(decorated) == 2
    assert decorated[0]["web_url"] == "https://immich.example.com/people/person-1"
    assert decorated[1]["web_url"] == "https://immich.example.com/people/person-2"


def test_decorate_response_asset_still_works_after_fix():
    """Test that image/asset decoration still works correctly (regression test)."""
    from mcp4immich.tooling import _decorate_response
    
    # Image asset with just "id" (no birthDate, thumbnailPath, etc.)
    response = {"id": "asset-123", "type": "IMAGE", "filename": "photo.jpg"}
    decorated = _decorate_response(response, "https://immich.example.com", "asset")
    
    # Should have /photos/{id} URL
    assert decorated["web_url"] == "https://immich.example.com/photos/asset-123"


def test_decorate_response_person_birthdate_has_priority_over_generic_id():
    """Test that person-specific fields take priority in type detection."""
    from mcp4immich.tooling import _decorate_response
    
    # Ambiguous: has "id" which could be interpreted as asset, but has "birthDate" which indicates person
    response = {"id": "entity-789", "birthDate": "1995-03-20", "name": "Chris"}
    decorated = _decorate_response(response, "https://immich.example.com", "array")
    
    # Should be treated as person due to birthDate field
    assert decorated["web_url"] == "https://immich.example.com/people/entity-789"

def test_detect_response_type_person_with_ishidden():
    """Test _detect_response_type identifies person by isHidden field (always present on persons)."""
    from mcp4immich.tooling import _detect_response_type

    # Person object that has no birthDate / thumbnailPath but has isHidden
    item = {"id": "person-789", "name": "Dana", "isHidden": False}
    url_type = _detect_response_type(item)
    assert url_type == "person"


def test_detect_response_type_person_with_faces():
    """Test _detect_response_type identifies person by faces field."""
    from mcp4immich.tooling import _detect_response_type

    # Person object returned with a faces list (common in detailed person responses)
    item = {"id": "person-999", "name": "Eve", "faces": []}
    url_type = _detect_response_type(item)
    assert url_type == "person"


def test_decorate_response_person_with_ishidden_field():
    """Test _decorate_response gives /people/{id} URL when only isHidden distinguishes person."""
    from mcp4immich.tooling import _decorate_response

    # Edge case: person has no birthDate or thumbnailPath — only isHidden marks it as a person
    response = {"id": "person-789", "name": "Dana", "isHidden": True}
    decorated = _decorate_response(response, "https://immich.example.com", "array")

    assert "web_url" in decorated
    assert decorated["web_url"] == "https://immich.example.com/people/person-789"


def test_detect_response_type_album_with_albumname_only():
    """Album objects with generic id + albumName should be treated as albums."""
    from mcp4immich.tooling import _detect_response_type

    item = {"id": "album-123", "albumName": "Vacation"}
    assert _detect_response_type(item) == "album"


def test_decorate_response_album_with_albumname_field():
    """Array decoration should produce /albums/{id} for albumName-based album objects."""
    from mcp4immich.tooling import _decorate_response

    response = [{"id": "album-123", "albumName": "Vacation"}]
    decorated = _decorate_response(response, "https://immich.example.com", "array")

    assert isinstance(decorated, list)
    assert decorated[0]["web_url"] == "https://immich.example.com/albums/album-123"


# ---------------------------------------------------------------------------
# Multi-section search response tests (Items 52 & 56)
# ---------------------------------------------------------------------------

_SEARCH_RESPONSE_FIXTURE = {
    "albums": {
        "total": 1,
        "count": 1,
        "items": [
            {"id": "album-abc", "albumName": "Holiday", "ownerId": "user-1"}
        ],
        "facets": [],
    },
    "assets": {
        "total": 2,
        "count": 2,
        "items": [
            {
                "id": "asset-001",
                "type": "IMAGE",
                "originalFileName": "sunset.jpg",
                "people": [],
            },
            {
                "id": "asset-002",
                "type": "VIDEO",
                "originalFileName": "clip.mp4",
                "people": [
                    {"id": "person-999", "name": "Amy"}
                ],
            },
        ],
        "facets": [],
        "nextPage": None,
    },
}


def test_extract_decoratable_array_nested_sections():
    """Nested search response with dict sections should be detected as 'sections'."""
    from mcp4immich.tooling import _extract_decoratable_array

    arr, wtype = _extract_decoratable_array(_SEARCH_RESPONSE_FIXTURE)
    assert wtype == "sections"
    assert arr is None  # individual arrays live inside the sections


def test_extract_decoratable_array_flat_assets_still_works():
    """A response with 'assets' as a flat list should still be detected as 'wrapped'."""
    from mcp4immich.tooling import _extract_decoratable_array

    flat = {"assets": [{"id": "a1"}, {"id": "a2"}], "total": 2}
    arr, wtype = _extract_decoratable_array(flat)
    assert wtype == "wrapped"
    assert len(arr) == 2


def test_decorate_response_search_sections():
    """_decorate_response adds web_url inside every nested section."""
    from mcp4immich.tooling import _decorate_response
    import copy

    response = copy.deepcopy(_SEARCH_RESPONSE_FIXTURE)
    decorated = _decorate_response(response, "https://photos.example.com", "array")

    # Assets section
    assets = decorated["assets"]["items"]
    assert len(assets) == 2
    assert assets[0]["web_url"] == "https://photos.example.com/photos/asset-001"
    assert assets[1]["web_url"] == "https://photos.example.com/photos/asset-002"

    # Albums section
    albums = decorated["albums"]["items"]
    assert len(albums) == 1
    assert albums[0]["web_url"] == "https://photos.example.com/albums/album-abc"


def test_decorate_response_search_preserves_metadata():
    """Decoration must not destroy totals, facets, or nextPage in sections."""
    from mcp4immich.tooling import _decorate_response
    import copy

    response = copy.deepcopy(_SEARCH_RESPONSE_FIXTURE)
    decorated = _decorate_response(response, "https://photos.example.com", "array")

    assert decorated["assets"]["total"] == 2
    assert decorated["assets"]["count"] == 2
    assert decorated["assets"]["facets"] == []
    assert decorated["assets"]["nextPage"] is None
    assert decorated["albums"]["total"] == 1


def test_decorate_response_search_empty_sections():
    """Empty items lists are harmless."""
    from mcp4immich.tooling import _decorate_response

    response = {
        "assets": {"total": 0, "count": 0, "items": [], "facets": []},
        "albums": {"total": 0, "count": 0, "items": [], "facets": []},
    }
    decorated = _decorate_response(response, "https://photos.example.com", "array")
    assert decorated["assets"]["items"] == []
    assert decorated["albums"]["items"] == []


def test_decorate_response_search_person_uuid_not_leaked():
    """Item 56: asset with nested people must NOT use person UUID in web_url."""
    from mcp4immich.tooling import _decorate_response

    response = {
        "assets": {
            "total": 1,
            "count": 1,
            "items": [
                {
                    "id": "asset-abc",
                    "type": "IMAGE",
                    "people": [
                        {"id": "person-BAD", "name": "Amy"}
                    ],
                }
            ],
            "facets": [],
        },
        "albums": {"total": 0, "count": 0, "items": [], "facets": []},
    }
    decorated = _decorate_response(response, "https://photos.example.com", "array")
    url = decorated["assets"]["items"][0]["web_url"]
    assert "person-BAD" not in url
    assert url == "https://photos.example.com/photos/asset-abc"


def test_decorate_response_search_asset_with_personid_field():
    """Item 56 edge-case: asset containing a stray personId field should still
    receive an asset URL, not a person URL, when type='IMAGE'."""
    from mcp4immich.tooling import _decorate_response

    response = {
        "assets": {
            "total": 1,
            "count": 1,
            "items": [
                {
                    "id": "asset-xyz",
                    "type": "IMAGE",
                    "personId": "person-STRAY",
                }
            ],
            "facets": [],
        },
    }
    decorated = _decorate_response(response, "https://photos.example.com", "array")
    url = decorated["assets"]["items"][0]["web_url"]
    assert "person-STRAY" not in url
    assert url == "https://photos.example.com/photos/asset-xyz"


def test_decorate_single_asset_response_with_people_keeps_top_level_asset_url():
    """Item 58: asset detail response should decorate top-level asset, not nested relation arrays."""
    from mcp4immich.tooling import _decorate_response

    response = {
        "id": "asset-main",
        "type": "IMAGE",
        "people": [{"id": "person-1", "name": "Ada"}],
    }
    decorated = _decorate_response(response, "https://photos.example.com", "asset")

    assert decorated["web_url"] == "https://photos.example.com/photos/asset-main"
    assert "web_url" not in decorated["people"][0]


def test_decorate_single_asset_response_does_not_create_people_photo_links():
    """Item 59: nested person objects must never get /photos/{person-id} via asset context."""
    from mcp4immich.tooling import _decorate_response

    response = {
        "id": "asset-main-2",
        "type": "IMAGE",
        "people": [{"id": "person-2", "name": "Grace"}],
    }
    decorated = _decorate_response(response, "https://photos.example.com", "asset")

    assert decorated["web_url"] == "https://photos.example.com/photos/asset-main-2"
    nested = decorated["people"][0]
    assert "web_url" not in nested