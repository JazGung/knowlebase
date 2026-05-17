"""
单元测试 — 模型域 Schema + Service
"""

import base64

import pytest
from pydantic import ValidationError

from knowlebase.schemas.model import (
    ParseRequest,
    ParseResponse,
    EmbeddingRequest,
    EmbeddingResponse,
)


class TestParseRequestSchema:

    def test_valid_pdf(self):
        body = ParseRequest(
            file_content=base64.b64encode(b"hello").decode(),
            file_format="pdf",
            file_name="test.pdf",
        )
        assert body.file_format == "pdf"
        assert body.file_name == "test.pdf"

    def test_valid_docx(self):
        body = ParseRequest(
            file_content=base64.b64encode(b"world").decode(),
            file_format="docx",
            file_name="report.docx",
        )
        assert body.file_format == "docx"

    def test_valid_doc(self):
        body = ParseRequest(
            file_content=base64.b64encode(b"old").decode(),
            file_format="doc",
            file_name="legacy.doc",
        )
        assert body.file_format == "doc"

    def test_invalid_format_rejected(self):
        with pytest.raises(ValidationError):
            ParseRequest(
                file_content=base64.b64encode(b"x").decode(),
                file_format="png",
                file_name="image.png",
            )

    def test_empty_file_name_rejected(self):
        with pytest.raises(ValidationError):
            ParseRequest(
                file_content=base64.b64encode(b"x").decode(),
                file_format="pdf",
                file_name="",
            )

    def test_missing_file_content_rejected(self):
        with pytest.raises(ValidationError):
            ParseRequest(file_format="pdf", file_name="test.pdf")


class TestEmbeddingRequestSchema:

    def test_valid_request(self):
        body = EmbeddingRequest(text="hello world")
        assert body.text == "hello world"

    def test_empty_text_rejected(self):
        with pytest.raises(ValidationError):
            EmbeddingRequest(text="")


class TestParseResponseSchema:

    def test_default_sections(self):
        resp = ParseResponse()
        assert resp.sections == []

    def test_with_sections(self):
        resp = ParseResponse(sections=[
            {"title": "Introduction", "content": [{"type": "text", "text": "Hello"}]}
        ])
        assert len(resp.sections) == 1
        assert resp.sections[0]["title"] == "Introduction"


class TestEmbeddingResponseSchema:

    def test_valid_response(self):
        resp = EmbeddingResponse(vector=[0.1, 0.2, 0.3], dimension=3)
        assert len(resp.vector) == 3
        assert resp.dimension == 3

    def test_dimension_matches_vector(self):
        resp = EmbeddingResponse(vector=[0.5, -0.3, 0.8, 0.1], dimension=4)
        assert resp.dimension == 4
        assert len(resp.vector) == 4
