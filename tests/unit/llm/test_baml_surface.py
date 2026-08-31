"""Structural tests for the generated BAML client surface.

These tests verify that BAML functions remain present on the generated
client after regeneration.  They do not call the LLM; they only inspect
the client's attribute surface.
"""

import inspect

from agrag.llm.baml_client import b
from agrag.llm.baml_client import parser as baml_parser


class TestGenerateCypherQuerySurface:
    """GenerateCypherQuery must exist on the generated client."""

    def test_function_exists_on_async_client(self) -> None:
        """b.GenerateCypherQuery is callable."""
        assert hasattr(b, "GenerateCypherQuery")
        assert callable(b.GenerateCypherQuery)

    def test_function_has_expected_parameters(self) -> None:
        """GenerateCypherQuery accepts question and schema_description."""
        sig = inspect.signature(b.GenerateCypherQuery)
        param_names = list(sig.parameters.keys())
        assert "question" in param_names
        assert "schema_description" in param_names

    def test_parser_handles_generate_cypher_query(self) -> None:
        """The parser can parse a GenerateCypherQuery response."""
        assert hasattr(baml_parser, "LlmResponseParser")
        assert hasattr(baml_parser.LlmResponseParser, "GenerateCypherQuery")
