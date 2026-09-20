import unittest

from mcp4immich.constants import build_server_instructions


class InstructionsTests(unittest.TestCase):
    def test_build_server_instructions_with_domain(self) -> None:
        instructions = build_server_instructions("https://immich.example")
        self.assertIn("External domain for link building: https://immich.example.", instructions)

    def test_build_server_instructions_without_domain(self) -> None:
        instructions = build_server_instructions(None)
        self.assertIn("External domain for link building:", instructions)
        self.assertIn("call the server config endpoint", instructions)

    def test_instructions_contain_workflow_hints(self) -> None:
        instructions = build_server_instructions(None)
        self.assertIn("path_<name>", instructions)
        self.assertIn("query_<name>", instructions)
        self.assertIn("POST /api/search/smart", instructions)
        self.assertIn("tool_access_report", instructions)
        self.assertIn("IMMICH_PROFILE", instructions)
        self.assertIn("/photos/<asset-id>", instructions)
