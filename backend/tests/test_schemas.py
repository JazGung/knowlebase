"""
单元测试 - Pydantic Schemas 验证
"""

import pytest
from pydantic import ValidationError

from knowlebase.schemas.document import (
    DocumentStatus,
    ProcessingStatus,
    FileCheckItem,
    FileCheckRequest,
    DuplicateFileInfo,
    FileCheckResponse,
    DocumentUploadRequestMetadata,
    DocumentUploadResponse,
    IntegrityValidationError,
    DocumentListQuery,
    ProcessingStage,
    ProcessingHistoryItem,
    EnableDisableDocumentRequest,
    ReprocessDocumentRequest,
    ReprocessDocumentResponse,
    BaseResponse,
    SuccessResponse,
    ErrorResponse,
)


VALID_HASH = "a1b2c3d4e5f678901234567890123456"


class TestDocumentStatus:
    """测试 DocumentStatus 枚举"""

    def test_values(self):
        assert DocumentStatus.PENDING == "pending"
        assert DocumentStatus.PROCESSING == "processing"
        assert DocumentStatus.SUCCESS == "success"
        assert DocumentStatus.FAILED == "failed"
        assert DocumentStatus.DELETED == "deleted"

    def test_string_comparison(self):
        assert DocumentStatus.PENDING == "pending"
        assert DocumentStatus.SUCCESS.value == "success"


class TestProcessingStatus:
    """测试 ProcessingStatus 枚举"""

    def test_values(self):
        assert ProcessingStatus.PENDING == "pending"
        assert ProcessingStatus.PROCESSING == "processing"
        assert ProcessingStatus.SUCCESS == "success"
        assert ProcessingStatus.FAILED == "failed"


class TestFileCheckItem:
    """测试 FileCheckItem"""

    def test_valid(self):
        item = FileCheckItem(filename="test.pdf", hash=VALID_HASH)
        assert item.filename == "test.pdf"
        assert item.hash == VALID_HASH.lower()

    def test_hash_lowercased(self):
        item = FileCheckItem(filename="test.pdf", hash=VALID_HASH.upper())
        assert item.hash == VALID_HASH.lower()

    def test_hash_too_short(self):
        with pytest.raises(ValidationError):
            FileCheckItem(filename="test.pdf", hash="abc123")

    def test_hash_invalid_chars(self):
        with pytest.raises(ValidationError):
            FileCheckItem(filename="test.pdf", hash="z" * 32)

    def test_empty_filename_accepted(self):
        # Pydantic 允许空字符串，实际业务逻辑会在 service 层验证
        item = FileCheckItem(filename="", hash=VALID_HASH)
        assert item.filename == ""


class TestFileCheckRequest:
    """测试 FileCheckRequest"""

    def test_valid_single(self):
        req = FileCheckRequest(files=[{"filename": "a.pdf", "hash": VALID_HASH}])
        assert len(req.files) == 1

    def test_valid_multiple(self):
        req = FileCheckRequest(files=[
            {"filename": "a.pdf", "hash": VALID_HASH},
            {"filename": "b.docx", "hash": "b" * 32},
        ])
        assert len(req.files) == 2

    def test_empty_files_raises_error(self):
        with pytest.raises(ValidationError):
            FileCheckRequest(files=[])

    def test_duplicate_filenames_raises_error(self):
        with pytest.raises(ValidationError):
            FileCheckRequest(files=[
                {"filename": "a.pdf", "hash": VALID_HASH},
                {"filename": "a.pdf", "hash": "b" * 32},
            ])


class TestDocumentUploadRequestMetadata:
    """测试 DocumentUploadRequestMetadata"""

    def test_all_fields_none(self):
        meta = DocumentUploadRequestMetadata()
        assert meta.title is None
        assert meta.tags is None

    def test_valid_tags(self):
        meta = DocumentUploadRequestMetadata(tags="python, fastapi, test")
        assert meta.tags == "python, fastapi, test"

    def test_tag_too_long_raises_error(self):
        with pytest.raises(ValidationError):
            DocumentUploadRequestMetadata(tags="a" * 51)

    def test_empty_tags_after_strip_raises_error(self):
        with pytest.raises(ValidationError):
            DocumentUploadRequestMetadata(tags=" , , ")


class TestDocumentListQuery:
    """测试 DocumentListQuery"""

    def test_defaults(self):
        q = DocumentListQuery()
        assert q.page == 1
        assert q.page_size == 20
        assert q.sort_by == "created_at"
        assert q.order == "desc"

    def test_valid_pagination(self):
        q = DocumentListQuery(page=3, page_size=50)
        assert q.page == 3
        assert q.page_size == 50

    def test_invalid_page_raises_error(self):
        with pytest.raises(ValidationError):
            DocumentListQuery(page=0)

    def test_page_size_too_large_raises_error(self):
        with pytest.raises(ValidationError):
            DocumentListQuery(page_size=101)

    def test_invalid_order_raises_error(self):
        with pytest.raises(ValidationError):
            DocumentListQuery(order="random")

    def test_invalid_sort_field_raises_error(self):
        with pytest.raises(ValidationError):
            DocumentListQuery(sort_by="unknown_field")

    def test_valid_order_asc(self):
        q = DocumentListQuery(order="asc")
        assert q.order == "asc"


class TestIntegrityValidationError:
    """测试 IntegrityValidationError"""

    def test_creation(self):
        err = IntegrityValidationError(
            field="hash",
            error="哈希不匹配",
            expected="aaa" * 11,
            actual="bbb" * 11,
        )
        assert err.field == "hash"
        assert err.error == "哈希不匹配"


class TestReprocessDocumentRequest:
    """测试 ReprocessDocumentRequest"""

    def test_default_force_false(self):
        req = ReprocessDocumentRequest(document_id="doc_123")
        assert req.force_reprocess is False

    def test_force_true(self):
        req = ReprocessDocumentRequest(document_id="doc_123", force_reprocess=True)
        assert req.force_reprocess is True
