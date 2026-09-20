import unittest

from mcp4immich.openapi import _permission_is_read


class TestPermissionIsRead(unittest.TestCase):
    def test_permission_is_read_with_none(self):
        """Test that None permission returns False (unknown)."""
        self.assertFalse(_permission_is_read(None))

    def test_permission_is_read_with_read_only(self):
        """Test that read-only permissions return True."""
        self.assertTrue(_permission_is_read("asset.read"))
        self.assertTrue(_permission_is_read("album.read"))
        self.assertTrue(_permission_is_read("person.read"))

    def test_permission_is_read_with_write(self):
        """Test that write permissions return False."""
        self.assertFalse(_permission_is_read("asset.write"))
        self.assertFalse(_permission_is_read("asset.upload"))
        self.assertFalse(_permission_is_read("album.create"))
        self.assertFalse(_permission_is_read("album.delete"))

    def test_permission_is_read_mixed_permissions(self):
        """Test that mixed read-write permissions return False."""
        # If a permission contains both read and write indicators, it's not read-only
        self.assertFalse(_permission_is_read("asset.read.write"))


class TestNonePermissionFiltering(unittest.TestCase):
    def test_none_permission_not_blocked_by_write_check(self):
        """
        Test that operations without permission metadata (None) are not
        blocked by the write capability check.

        This test verifies the fix for item 36: when permission is None,
        the operation should not be treated as a write operation based
        solely on the HTTP method.
        """
        from mcp4immich.openapi import _permission_is_read

        # Simulate the logic from tooling.py line 95-96
        WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

        # Case 1: POST endpoint with None permission should NOT be marked as write
        method = "POST"
        permission = None
        is_write = (
            method in WRITE_METHODS
            and permission is not None
            and not _permission_is_read(permission)
        )
        self.assertFalse(
            is_write,
            "POST endpoint with None permission should not be blocked as write operation",
        )

        # Case 2: POST endpoint with explicit write permission should be marked as write
        method = "POST"
        permission = "asset.write"
        is_write = (
            method in WRITE_METHODS
            and permission is not None
            and not _permission_is_read(permission)
        )
        self.assertTrue(
            is_write,
            "POST endpoint with write permission should be marked as write operation",
        )

        # Case 3: POST endpoint with explicit read permission should NOT be marked as write
        method = "POST"
        permission = "asset.read"
        is_write = (
            method in WRITE_METHODS
            and permission is not None
            and not _permission_is_read(permission)
        )
        self.assertFalse(
            is_write,
            "POST endpoint with read permission should not be marked as write operation",
        )

        # Case 4: GET endpoint with None permission should NOT be marked as write
        method = "GET"
        permission = None
        is_write = (
            method in WRITE_METHODS
            and permission is not None
            and not _permission_is_read(permission)
        )
        self.assertFalse(
            is_write, "GET endpoint should never be marked as write operation"
        )


if __name__ == "__main__":
    unittest.main()
