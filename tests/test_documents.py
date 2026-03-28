"""Tests for document ingestion — rendering, CLI loading, and persistence."""

from __future__ import annotations

from pathlib import Path

import click
import pytest

from vguild.cli import _guess_content_type, _load_documents, _parse_doc_arg
from vguild.models import Document
from vguild.sdk_adapter import SDKAdapter


class TestRenderDocuments:
    def test_markdown_document_rendered_as_is(self) -> None:
        docs = [Document(label="PRD", source="inline", content="# Product Req\n\nDetails.")]
        result = SDKAdapter._render_documents(docs)
        assert "## Reference Document: PRD" in result
        assert "# Product Req" in result

    def test_json_document_wrapped_in_code_fence(self) -> None:
        docs = [
            Document(
                label="config",
                source="config.json",
                content='{"key": "value"}',
                content_type="application/json",
            )
        ]
        result = SDKAdapter._render_documents(docs)
        assert "```json" in result
        assert '{"key": "value"}' in result

    def test_yaml_document_wrapped_in_code_fence(self) -> None:
        docs = [
            Document(
                label="spec",
                source="spec.yaml",
                content="key: value",
                content_type="text/yaml",
            )
        ]
        result = SDKAdapter._render_documents(docs)
        assert "```yaml" in result

    def test_truncated_flag_shown_in_header(self) -> None:
        docs = [
            Document(
                label="big-doc",
                source="inline",
                content="data",
                truncated=True,
            )
        ]
        result = SDKAdapter._render_documents(docs)
        assert "(truncated)" in result

    def test_multiple_documents(self) -> None:
        docs = [
            Document(label="A", source="inline", content="Doc A"),
            Document(label="B", source="inline", content="Doc B"),
        ]
        result = SDKAdapter._render_documents(docs)
        assert "## Reference Document: A" in result
        assert "## Reference Document: B" in result

    def test_documents_appear_in_user_message(self) -> None:
        adapter = SDKAdapter(dry_run=True)
        docs = [Document(label="PRD", source="inline", content="Requirements")]
        msg = adapter._build_user_message("Fix bug", None, documents=docs)
        assert "## Task" in msg
        assert "## Reference Document: PRD" in msg
        assert "Requirements" in msg

    def test_documents_before_context(self) -> None:
        adapter = SDKAdapter(dry_run=True)
        docs = [Document(label="PRD", source="inline", content="Requirements")]
        context = {
            "notes_for_next_agent": ["Check auth module"],
            "findings": ["Found issue"],
            "artifacts_changed": ["auth.py"],
        }
        msg = adapter._build_user_message("Fix bug", context, documents=docs)
        doc_pos = msg.index("Reference Document")
        ctx_pos = msg.index("Context from Previous Agent")
        assert doc_pos < ctx_pos


class TestParseDocArg:
    def test_file_path(self, tmp_path: Path) -> None:
        doc_file = tmp_path / "prd.md"
        doc_file.write_text("hello world")
        label, source, content, truncated = _parse_doc_arg(str(doc_file))
        assert label == "prd"
        assert source == str(doc_file.resolve())
        assert content == "hello world"
        assert truncated is False

    def test_file_with_label_override(self, tmp_path: Path) -> None:
        doc_file = tmp_path / "doc.md"
        doc_file.write_text("content")
        label, source, content, truncated = _parse_doc_arg(f'{doc_file}:label="My PRD"')
        assert label == "My PRD"

    def test_missing_file_raises(self) -> None:
        with pytest.raises(click.BadParameter):
            _parse_doc_arg("/nonexistent/file.md")

    def test_truncation_on_large_content(self, tmp_path: Path) -> None:
        doc_file = tmp_path / "big.md"
        doc_file.write_text("x" * 200_000)
        label, source, content, truncated = _parse_doc_arg(str(doc_file))
        assert truncated is True
        assert len(content) < 200_000
        assert "[... truncated ...]" in content


class TestLoadDocuments:
    def test_none_returns_empty(self) -> None:
        assert _load_documents(None) == []

    def test_empty_list_returns_empty(self) -> None:
        assert _load_documents([]) == []

    def test_loads_file(self, tmp_path: Path) -> None:
        doc_file = tmp_path / "req.md"
        doc_file.write_text("# Requirements\n\nBuild feature X.")
        docs = _load_documents([str(doc_file)])
        assert len(docs) == 1
        assert docs[0].label == "req"
        assert docs[0].content_type == "text/markdown"

    def test_loads_json_file(self, tmp_path: Path) -> None:
        doc_file = tmp_path / "issue.json"
        doc_file.write_text('{"title": "Bug"}')
        docs = _load_documents([str(doc_file)])
        assert docs[0].content_type == "application/json"

    def test_multiple_docs(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.md"
        f2 = tmp_path / "b.txt"
        f1.write_text("doc a")
        f2.write_text("doc b")
        docs = _load_documents([str(f1), str(f2)])
        assert len(docs) == 2

    def test_total_budget_truncation(self, tmp_path: Path) -> None:
        """When total budget is exceeded, later documents are truncated."""
        from vguild.cli import _MAX_TOTAL_DOC_SIZE

        # Create two files that together exceed total budget
        f1 = tmp_path / "a.md"
        f2 = tmp_path / "b.md"
        # Each just under per-doc limit but together over total
        size = (_MAX_TOTAL_DOC_SIZE // 2) + 1000
        f1.write_text("a" * min(size, 100_000))
        f2.write_text("b" * min(size, 100_000))
        docs = _load_documents([str(f1), str(f2)])
        total_len = sum(len(d.content) for d in docs)
        assert total_len <= _MAX_TOTAL_DOC_SIZE + 100  # small margin for truncation suffix


class TestGuessContentType:
    def test_markdown(self) -> None:
        assert _guess_content_type("/foo/bar.md") == "text/markdown"

    def test_json(self) -> None:
        assert _guess_content_type("/foo/bar.json") == "application/json"

    def test_yaml(self) -> None:
        assert _guess_content_type("/foo/bar.yaml") == "text/yaml"

    def test_yml(self) -> None:
        assert _guess_content_type("/foo/bar.yml") == "text/yaml"

    def test_python(self) -> None:
        assert _guess_content_type("/foo/bar.py") == "text/x-python"

    def test_unknown_defaults_to_plain(self) -> None:
        assert _guess_content_type("/foo/bar.xyz") == "text/plain"

    def test_inline_returns_plain(self) -> None:
        assert _guess_content_type("inline") == "text/plain"
