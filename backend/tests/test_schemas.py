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
    ProcessingStageItem,
    ProcessingHistoryItem,
    EnableDisableDocumentRequest,
    BaseResponse,
    BatchResult,
    BatchResponse,
    ProcessingTriggerRequest,
)


VALID_HASH = "a1b2c3d4e5f678901234567890123456"


class TestDocumentStatus:
    """测试 DocumentStatus 枚举"""

    def test_values(self):
        assert DocumentStatus.ENABLED == "enabled"
        assert DocumentStatus.DISABLED == "disabled"

    def test_string_comparison(self):
        assert DocumentStatus.ENABLED.value == "enabled"
        assert DocumentStatus.DISABLED.value == "disabled"


class TestProcessingStatus:
    """测试 ProcessingStatus 枚举"""

    def test_values(self):
        assert ProcessingStatus.PENDING == "pending"
        assert ProcessingStatus.PROCESSING == "processing"
        assert ProcessingStatus.SUCCEEDED == "succeeded"
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

    def test_status_filter(self):
        q = DocumentListQuery(status=DocumentStatus.ENABLED)
        assert q.status == DocumentStatus.ENABLED


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


class TestBaseResponse:
    """测试 BaseResponse 统一响应"""

    def test_default_success(self):
        resp = BaseResponse()
        assert resp.code == "000000"
        assert resp.description == "成功"
        assert resp.content is None

    def test_error_response(self):
        resp = BaseResponse(code="404001", description="文档不存在", content=None)
        assert resp.code == "404001"

    def test_with_content(self):
        resp = BaseResponse(content={"key": "value"})
        assert resp.content == {"key": "value"}


class TestBatchResult:
    """测试 BatchResult"""

    def test_success_result(self):
        r = BatchResult(id="doc_1", status="success")
        assert r.status == "success"
        assert r.reason is None

    def test_failed_result(self):
        r = BatchResult(id="doc_2", status="failed", reason="文档不存在")
        assert r.status == "failed"
        assert r.reason == "文档不存在"


class TestBatchResponse:
    """测试 BatchResponse"""

    def test_empty_results(self):
        resp = BatchResponse()
        assert resp.results == []

    def test_with_results(self):
        resp = BatchResponse(results=[
            BatchResult(id="1", status="success"),
            BatchResult(id="2", status="failed", reason="error"),
        ])
        assert len(resp.results) == 2


class TestProcessingTriggerRequest:
    """测试 ProcessingTriggerRequest"""

    def test_valid(self):
        req = ProcessingTriggerRequest(document_ids=[1, 2, 3])
        assert req.document_ids == [1, 2, 3]

    def test_empty_list(self):
        req = ProcessingTriggerRequest(document_ids=[])
        assert req.document_ids == []


class TestProcessingStageItem:
    """测试 ProcessingStageItem"""

    def test_valid(self):
        item = ProcessingStageItem(stage_name="parsed", status="succeeded", duration_ms=150)
        assert item.stage_name == "parsed"
        assert item.status == "succeeded"
        assert item.duration_ms == 150
